"""Central route scheduling, feasibility, and objective evaluation."""

import math

from .models import (
    Instance,
    Route,
    RouteEvaluation,
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

    def route(self, route: Route) -> RouteEvaluation:
        if not route:
            return RouteEvaluation(False, 0.0, 0.0, 0.0, (), ("empty_route",))
        unknown = [customer_id for customer_id in route if customer_id not in self._customers]
        if unknown:
            return RouteEvaluation(
                False, 0.0, 0.0, 0.0, (), ("unknown_customer",)
            )

        schedule: list[StopSchedule] = []
        violations: list[str] = []
        load = 0.0
        distance = 0.0
        departure = 0.0
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

        return_leg = float(self.instance.distance_matrix[previous_index, 0])
        distance += return_leg
        depot_return = departure + return_leg
        if load > self.instance.capacity:
            _append_once(violations, "capacity")
        if depot_return > self.instance.depot.due_date:
            _append_once(violations, "depot_due_date")
        return RouteEvaluation(
            feasible=not violations,
            distance=distance,
            load=load,
            depot_return=depot_return,
            schedule=tuple(schedule),
            violations=tuple(violations),
        )

    def solution(self, solution: Solution) -> SolutionEvaluation:
        route_results = tuple(self.route(route) for route in solution.routes)
        violations: list[str] = []
        if len(solution.routes) > self.instance.max_vehicles:
            _append_once(violations, "vehicle_limit")

        served = [customer_id for route in solution.routes for customer_id in route]
        expected = set(self._customers)
        served_known = [customer_id for customer_id in served if customer_id in expected]
        if len(served_known) != len(set(served_known)):
            _append_once(violations, "duplicate_customers")
        if set(served_known) != expected:
            _append_once(violations, "missing_customers")
        if any(customer_id not in expected for customer_id in served):
            _append_once(violations, "unknown_customer")
        for route_result in route_results:
            for violation in route_result.violations:
                _append_once(violations, violation)

        distance = sum(result.distance for result in route_results)
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
        risk_delay = weighted_delay / total_priority if total_priority > 0 else 0.0
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


def lexicographically_better(
    left: tuple[int, float], right: tuple[int, float]
) -> bool:
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


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
