"""Central route scheduling, feasibility, and objective evaluation."""

import math

from .models import (
    Instance,
    Route,
    RouteEvaluation,
    SearchConstraints,
    Solution,
    SolutionEvaluation,
    StopSchedule,
)


class Evaluator:
    def __init__(self, instance: Instance, d_ref: float, alpha: float, beta: float):
        if d_ref <= 0:
            raise ValueError("d_ref must be positive")

        if alpha < 0 or beta < 0:
            raise ValueError("alpha and beta must be non-negative")

        if not math.isclose(alpha + beta, 1.0, abs_tol=1e-9):
            raise ValueError("alpha and beta must sum to 1")

        self.instance = instance
        self.d_ref = float(d_ref)
        self.alpha = float(alpha)
        self.beta = float(beta)
        self._customers = {customer.id: customer for customer in instance.customers}
        self._matrix_index = {
            customer.id: index
            for index, customer in enumerate(instance.customers, start=1)
        }

    def route(self, route: Route, *, departure: float = 0.0) -> RouteEvaluation:
        if not route:
            return RouteEvaluation(False, 0.0, 0.0, 0.0, (), ("empty_route",))

        unknown = [
            customer_id for customer_id in route if customer_id not in self._customers
        ]

        if unknown:
            return RouteEvaluation(False, 0.0, 0.0, 0.0, (), ("unknown_customer",))

        schedule, violations, load, distance, departure, previous_index = (
            self._build_route_schedule(route, departure)
        )

        return_leg = float(self.instance.distance_matrix[previous_index, 0])
        distance += return_leg
        depot_return = departure + return_leg

        self._append_route_limit_violations(violations, load, depot_return)

        return RouteEvaluation(
            feasible=not violations,
            distance=distance,
            load=load,
            depot_return=depot_return,
            schedule=tuple(schedule),
            violations=tuple(violations),
        )

    def _build_route_schedule(
        self, route: Route, departure: float
    ) -> tuple[list[StopSchedule], list[str], float, float, float, int]:
        schedule: list[StopSchedule] = []
        violations: list[str] = []

        load = 0.0
        distance = 0.0
        previous_index = 0

        for customer_id in route:
            customer = self._customers[customer_id]
            customer_index = self._matrix_index[customer_id]

            leg = float(self.instance.distance_matrix[previous_index, customer_index])

            distance += leg
            arrival = departure + leg
            service_start = max(arrival, customer.ready_time)
            departure = service_start + customer.service_time

            schedule.append(
                StopSchedule(customer_id, arrival, service_start, departure)
            )
            load += customer.demand

            if service_start > customer.due_date:
                _append_once(violations, "customer_due_date")

            previous_index = customer_index

        return schedule, violations, load, distance, departure, previous_index

    def _append_route_limit_violations(
        self, violations: list[str], load: float, depot_return: float
    ) -> None:
        if load > self.instance.capacity:
            _append_once(violations, "capacity")

        if depot_return > self.instance.depot.due_date:
            _append_once(violations, "depot_due_date")

    def solution(
        self, solution: Solution, constraints: SearchConstraints | None = None
    ) -> SolutionEvaluation:
        route_results = tuple(
            self.route(route, departure=_route_departure(index, constraints))
            for index, route in enumerate(solution.routes)
        )
        violations = self._solution_violations(solution, route_results)

        if not _prefixes_respected(solution, constraints):
            _append_once(violations, "locked_prefix")
        distance = sum(result.distance for result in route_results)
        risk_delay = self._risk_delay(route_results)
        objective = self.alpha * distance / self.d_ref + self.beta * risk_delay
        vehicle_count = len(solution.routes)

        return SolutionEvaluation(
            feasible=not violations,
            vehicle_count=vehicle_count,
            distance=distance,
            risk_delay=risk_delay,
            objective=objective,
            score=(vehicle_count, objective),
            routes=route_results,
            violations=tuple(violations),
        )

    def _solution_violations(
        self,
        solution: Solution,
        route_results: tuple[RouteEvaluation, ...],
    ) -> list[str]:
        violations: list[str] = []

        if len(solution.routes) > self.instance.max_vehicles:
            _append_once(violations, "vehicle_limit")

        served = [customer_id for route in solution.routes for customer_id in route]
        expected = set(self._customers)
        served_known = [
            customer_id for customer_id in served if customer_id in expected
        ]

        if len(served_known) != len(set(served_known)):
            _append_once(violations, "duplicate_customers")

        if set(served_known) != expected:
            _append_once(violations, "missing_customers")

        if any(customer_id not in expected for customer_id in served):
            _append_once(violations, "unknown_customer")

        for route_result in route_results:
            for violation in route_result.violations:
                _append_once(violations, violation)

        return violations

    def _risk_delay(self, route_results: tuple[RouteEvaluation, ...]) -> float:
        weighted_delay = 0.0

        for result in route_results:
            for stop in result.schedule:
                customer = self._customers[stop.customer_id]
                index = self._matrix_index[stop.customer_id]
                relative_delay = (stop.service_start - customer.ready_time) / max(
                    1.0, customer.due_date - customer.ready_time
                )
                weighted_delay += (
                    float(self.instance.risk_priority[index]) * relative_delay
                )

        total_priority = float(sum(self.instance.risk_priority[1:]))

        return weighted_delay / total_priority if total_priority > 0 else 0.0


def lexicographically_better(left: tuple[int, float], right: tuple[int, float]) -> bool:
    return left < right


def evaluate_route(instance: Instance, route: Route) -> RouteEvaluation:
    """Evaluate a route when only feasibility and schedule are needed."""
    return Evaluator(instance, d_ref=1.0, alpha=1.0, beta=0.0).route(route)


def evaluate_solution(
    instance: Instance,
    solution: Solution,
    d_ref: float,
    alpha: float,
    beta: float,
) -> SolutionEvaluation:
    return Evaluator(instance, d_ref, alpha, beta).solution(solution)


def _route_departure(route_index: int, constraints: SearchConstraints | None) -> float:
    if constraints is None or route_index < constraints.locked_route_count:
        return 0.0

    return constraints.free_departure


def _prefixes_respected(
    solution: Solution, constraints: SearchConstraints | None
) -> bool:
    if constraints is None:
        return True

    if len(solution.routes) < constraints.locked_route_count:
        return False

    return all(
        route[: len(prefix)] == prefix
        for route, prefix in zip(solution.routes, constraints.locked_prefixes)
    )


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
