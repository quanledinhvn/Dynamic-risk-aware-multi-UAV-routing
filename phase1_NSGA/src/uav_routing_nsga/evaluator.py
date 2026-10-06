"""Single oracle for schedules, feasibility, and multi-objective values."""

from .models import Evaluation, Instance, Route, RouteEvaluation, Solution, StopSchedule


class Evaluator:
    def __init__(self, instance: Instance):
        self.instance = instance
        self.customers = {customer.id: customer for customer in instance.customers}
        self.indices = {customer.id: index for index, customer in enumerate(instance.customers, 1)}

    def route(self, route: Route) -> RouteEvaluation:
        if not route:
            return RouteEvaluation(False, 0.0, 0.0, 0.0, (), ("empty_route",))
        violations = []
        schedule = []
        load = 0.0
        distance = 0.0
        departure = 0.0
        previous = 0
        for customer_id in route:
            if customer_id not in self.customers:
                return RouteEvaluation(False, 0.0, 0.0, 0.0, (), ("unknown_customer",))
            customer = self.customers[customer_id]
            index = self.indices[customer_id]
            leg = float(self.instance.distance_matrix[previous, index])
            arrival = departure + leg
            service_start = max(arrival, customer.ready_time)
            departure = service_start + customer.service_time
            distance += leg
            load += customer.demand
            schedule.append(StopSchedule(customer_id, arrival, service_start, departure))
            if service_start > customer.due_date and "customer_due_date" not in violations:
                violations.append("customer_due_date")
            previous = index
        return_leg = float(self.instance.distance_matrix[previous, 0])
        distance += return_leg
        depot_return = departure + return_leg
        if load > self.instance.capacity:
            violations.append("capacity")
        if depot_return > self.instance.depot.due_date:
            violations.append("depot_due_date")
        return RouteEvaluation(not violations, distance, load, depot_return, tuple(schedule), tuple(violations))

    def solution(self, solution: Solution) -> Evaluation:
        routes = tuple(self.route(route) for route in solution.routes)
        violations = []
        if len(solution.routes) > self.instance.max_vehicles:
            violations.append("vehicle_limit")
        served = [customer_id for route in solution.routes for customer_id in route]
        expected = set(self.customers)
        if len(served) != len(set(served)):
            violations.append("duplicate_customers")
        if set(served) != expected:
            violations.append("missing_customers")
        if any(customer_id not in expected for customer_id in served):
            violations.append("unknown_customer")
        for result in routes:
            for violation in result.violations:
                if violation not in violations:
                    violations.append(violation)
        distance = sum(result.distance for result in routes)
        risk_numerator = 0.0
        total_priority = float(self.instance.risk_priority[1:].sum())
        lateness = 0.0
        for result in routes:
            for stop in result.schedule:
                customer = self.customers[stop.customer_id]
                priority = float(self.instance.risk_priority[self.indices[stop.customer_id]])
                relative = (stop.service_start - customer.ready_time) / max(1.0, customer.due_date - customer.ready_time)
                risk_numerator += priority * relative
                lateness += max(0.0, stop.service_start - customer.due_date)
        risk_delay = risk_numerator / total_priority if total_priority else 0.0
        max_load = max((result.load for result in routes), default=0.0)
        objectives = (float(len(solution.routes)), distance, risk_delay, max_load, lateness)
        return Evaluation(not violations, objectives, len(solution.routes), distance, risk_delay, max_load, lateness, routes, tuple(violations))


def evaluate_solution(instance: Instance, solution: Solution) -> Evaluation:
    return Evaluator(instance).solution(solution)
