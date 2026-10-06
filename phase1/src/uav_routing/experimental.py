"""Experimental risk-aware neighborhoods for controlled ablations."""

from .destroy import DestroyResult, remove_customers
from .models import Solution
from .repair import (
    RepairContext,
    RepairResult,
    _complete_result,
    _valid_removed,
    feasible_insertions,
)


class AbsorbableRouteRemoval:
    name = "absorbable_route"

    def apply(self, solution, instance, evaluator, rng, q) -> DestroyResult:
        if not solution.routes:
            return DestroyResult(solution, ())

        ranked = []

        for route_index, route in enumerate(solution.routes):
            other_routes = tuple(
                candidate for index, candidate in enumerate(solution.routes)
                if index != route_index
            )
            possible = 0

            for customer_id in route:
                if _has_existing_insertion(other_routes, customer_id, evaluator):
                    possible += 1

            ranked.append((-possible / len(route), len(route), route_index))

        best_score = min(item[:2] for item in ranked)
        choices = [item[2] for item in ranked if item[:2] == best_score]
        selected_index = int(rng.choice(choices))

        return remove_customers(solution, solution.routes[selected_index])


def _has_existing_insertion(routes, customer_id, evaluator) -> bool:
    for route in routes:
        for position in range(len(route) + 1):
            candidate = route[:position] + (customer_id,) + route[position:]

            if evaluator.route(candidate).feasible:
                return True

    return False


class RiskRegretRepair:
    name = "risk_regret"

    def apply(
        self, partial: Solution, removed: tuple[int, ...], context: RepairContext
    ) -> RepairResult:
        return _risk_regret(partial, removed, context, allow_new_route=True)


class RouteEliminationRepair:
    name = "route_elimination"

    def apply(
        self, partial: Solution, removed: tuple[int, ...], context: RepairContext
    ) -> RepairResult:
        return _risk_regret(partial, removed, context, allow_new_route=False)


class NoRemoval:
    name = "none"

    def apply(self, solution, instance, evaluator, rng, q) -> DestroyResult:
        return DestroyResult(solution, ())


class RiskRelocateRepair:
    name = "risk_relocate"

    def apply(
        self, partial: Solution, removed: tuple[int, ...], context: RepairContext
    ) -> RepairResult:
        if removed or not _valid_removed(partial, removed, context):
            return RepairResult(False, None)

        base = context.evaluator.solution(partial)

        if not base.feasible:
            return RepairResult(False, None)

        customers = {customer.id: customer for customer in context.instance.customers}
        priorities = {
            customer.id: float(context.instance.risk_priority[index])
            for index, customer in enumerate(context.instance.customers, start=1)
        }
        critical = []

        for route_index, route_result in enumerate(base.routes):
            if len(partial.routes[route_index]) < 2:
                continue

            for stop in route_result.schedule:
                customer = customers[stop.customer_id]
                priority = priorities[stop.customer_id]
                delay = (stop.service_start - customer.ready_time) / max(
                    1.0, customer.due_date - customer.ready_time
                )
                critical.append((priority * delay, priority, stop.customer_id))

        ranked = sorted(critical, reverse=True)
        best = partial
        best_score = base.score

        for _, priority, customer_id in ranked[:2]:
            if priority <= 0:
                continue

            source_index = next(
                index for index, route in enumerate(partial.routes)
                if customer_id in route
            )
            source = partial.routes[source_index]
            reduced = tuple(cid for cid in source if cid != customer_id)

            for target_index, target in enumerate(partial.routes):
                target_base = reduced if target_index == source_index else target

                for position in range(len(target_base) + 1):
                    inserted = (
                        target_base[:position]
                        + (customer_id,)
                        + target_base[position:]
                    )
                    candidate_routes = list(partial.routes)
                    candidate_routes[source_index] = reduced
                    candidate_routes[target_index] = inserted
                    candidate = Solution(tuple(candidate_routes))

                    if candidate == partial:
                        continue

                    candidate_eval = context.evaluator.solution(candidate)

                    if candidate_eval.feasible and candidate_eval.score < best_score:
                        best = candidate
                        best_score = candidate_eval.score

        return RepairResult(True, best)


def _risk_regret(
    partial: Solution,
    removed: tuple[int, ...],
    context: RepairContext,
    *,
    allow_new_route: bool,
) -> RepairResult:
    if not _valid_removed(partial, removed, context):
        return RepairResult(False, None)

    current = partial
    remaining = list(removed)
    customers = {customer.id: customer for customer in context.instance.customers}
    priorities = {
        customer.id: float(context.instance.risk_priority[index])
        for index, customer in enumerate(context.instance.customers, start=1)
    }

    while remaining:
        options = []

        for customer_id in remaining:
            insertions = feasible_insertions(current, customer_id, context)

            if not allow_new_route:
                insertions = tuple(
                    insertion for insertion in insertions
                    if insertion.delta_k == 0
                )

            if not insertions:
                return RepairResult(False, None)

            best = insertions[0]
            alternatives = [
                insertion for insertion in insertions
                if insertion.route_index != best.route_index
            ]
            fallback = alternatives[0] if alternatives else None
            regret = fallback.delta_f - best.delta_f if fallback else 0.0
            customer = customers[customer_id]
            urgency = priorities[customer_id] / max(
                1.0, customer.due_date - customer.ready_time
            )
            rank = (bool(alternatives), -regret, -urgency, best.delta_f, customer_id)
            options.append((rank, best))

        choice = min(options, key=lambda option: option[0])[1]
        current = choice.solution
        remaining.remove(choice.customer_id)

    return _complete_result(current, context)
