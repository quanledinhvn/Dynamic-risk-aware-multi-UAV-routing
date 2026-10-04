"""Optional short-route compression before contextual search."""

from uav_routing.destroy import remove_customers
from uav_routing.evaluator import Evaluator
from uav_routing.models import Instance, Solution
from uav_routing.repair import (
    GreedyRepair,
    Regret2Repair,
    RepairContext,
    RiskPriorityRepair,
)

MAX_ROUTE_SIZE = 5
MAX_ROUTES_PER_ROUND = 8
MAX_ROUNDS = 3


def compress_short_routes(
    instance: Instance,
    solution: Solution,
    d_ref: float,
    alpha: float,
    beta: float,
) -> Solution:
    """Try to absorb short routes without changing the reference distance."""
    evaluator = Evaluator(instance, d_ref, alpha, beta)
    context = RepairContext(instance, evaluator, d_ref, alpha, beta)
    repair_operators = (GreedyRepair(), Regret2Repair(), RiskPriorityRepair())

    for _ in range(MAX_ROUNDS):
        indices = sorted(
            range(len(solution.routes)), key=lambda index: len(solution.routes[index])
        )
        short_indices = [
            index for index in indices if len(solution.routes[index]) <= MAX_ROUTE_SIZE
        ]
        improved = False

        for route_index in short_indices[:MAX_ROUTES_PER_ROUND]:
            destroyed = remove_customers(solution, solution.routes[route_index])
            candidates = []

            for repair in repair_operators:
                result = repair.apply(destroyed.partial, destroyed.removed, context)

                if result.success and len(result.solution.routes) < len(
                    solution.routes
                ):
                    candidates.append(result.solution)

            if candidates:
                solution = min(
                    candidates, key=lambda item: evaluator.solution(item).score
                )
                improved = True
                break

        if not improved:
            break

    return solution
