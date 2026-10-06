"""Bounded route-elimination repair, isolated from the default solver."""

import time

from .models import Solution
from .repair import RepairContext, RepairResult, _complete_result, _valid_removed


class EjectionRepair:
    name = "ejection"

    def __init__(
        self,
        *,
        max_ejections: int = 2,
        beam_width: int = 4,
        max_evaluations: int = 2000,
        risk_aware: bool = True,
    ):
        self.max_ejections = max_ejections
        self.beam_width = beam_width
        self.max_evaluations = max_evaluations

        self.risk_aware = risk_aware
        self.evaluations = 0
        self.used_ejections = 0

        self.deadline = float("inf")

    def apply(
        self,
        partial: Solution,
        removed: tuple[int, ...],
        context: RepairContext,
    ) -> RepairResult:
        self.evaluations = 0
        self.used_ejections = 0

        if not _valid_removed(partial, removed, context.instance):
            return RepairResult(False, None)

        if self.beam_width < 1 or self.max_ejections < 0 or self.max_evaluations < 0:
            raise ValueError("invalid ejection search limits")

        customers = {customer.id: customer for customer in context.instance.customers}
        priorities = dict(
            zip(customers, map(float, context.instance.risk_priority[1:]), strict=True)
        )
        total_priority = sum(priorities.values()) or 1.0

        cache = {}
        visited = set()

        def route_info(route):
            if route in cache:
                return cache[route]

            if (
                self.evaluations >= self.max_evaluations
                or time.perf_counter() >= self.deadline
            ):
                raise _BudgetExhausted

            self.evaluations += 1
            evaluation = context.evaluator.route(route)
            risk = (
                sum(
                    priorities[stop.customer_id]
                    * (stop.service_start - customers[stop.customer_id].ready_time)
                    / max(
                        1.0,
                        customers[stop.customer_id].due_date
                        - customers[stop.customer_id].ready_time,
                    )
                    for stop in evaluation.schedule
                )
                / total_priority
            )

            slack = min(
                (
                    (customers[stop.customer_id].due_date - stop.service_start)
                    / max(
                        1.0,
                        customers[stop.customer_id].due_date
                        - customers[stop.customer_id].ready_time,
                    )
                    for stop in evaluation.schedule
                ),
                default=0.0,
            )
            cost = context.alpha * evaluation.distance / context.d_ref

            if self.risk_aware:
                cost += context.beta * risk

            cache[route] = (evaluation.feasible, cost, slack)

            return cache[route]

        def options(routes, customer_id, eject, protected):
            candidates = []

            for index, route in enumerate(routes):
                base_cost = route_info(route)[1]
                victims = (
                    [cid for cid in route if cid not in protected] if eject else [None]
                )

                for victim in victims:
                    reduced = tuple(cid for cid in route if cid != victim)
                    load = sum(customers[cid].demand for cid in reduced)

                    if load + customers[customer_id].demand > context.instance.capacity:
                        continue

                    for position in range(len(reduced) + 1):
                        inserted = (
                            reduced[:position] + (customer_id,) + reduced[position:]
                        )
                        feasible, cost, slack = route_info(inserted)

                        if not feasible:
                            continue

                        changed = routes[:index] + (inserted,) + routes[index + 1 :]
                        rank = (cost - base_cost, -slack if self.risk_aware else 0.0)
                        candidates.append((rank, changed, victim))

            candidates.sort(key=lambda candidate: candidate[0])

            return candidates[: self.beam_width]

        def search(routes, pending, used, protected):
            if time.perf_counter() >= self.deadline:
                raise _BudgetExhausted

            if not pending:
                result = _complete_result(Solution(routes), context)

                if result.success:
                    self.used_ejections = used

                return result

            key = (routes, pending, used, protected)

            if key in visited:
                return RepairResult(False, None)

            visited.add(key)
            customer_id, *rest = pending

            for eject in (False, True):
                if eject and used >= self.max_ejections:
                    continue

                for _, changed, victim in options(
                    routes, customer_id, eject, protected
                ):
                    next_pending = tuple(rest) if victim is None else (victim, *rest)
                    result = search(
                        changed,
                        next_pending,
                        used + int(eject),
                        protected | {customer_id},
                    )

                    if result.success:
                        return result

            return RepairResult(False, None)

        pending = tuple(
            sorted(
                removed,
                key=lambda cid: (
                    -customers[cid].demand,
                    customers[cid].due_date,
                    cid,
                ),
            )
        )

        try:
            if any(not route_info(route)[0] for route in partial.routes):
                return RepairResult(False, None)

            return search(partial.routes, pending, 0, frozenset())
        except _BudgetExhausted:
            return RepairResult(False, None)


class _BudgetExhausted(Exception):
    pass
