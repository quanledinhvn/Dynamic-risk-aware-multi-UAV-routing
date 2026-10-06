"""Rolling-horizon controller: reveal events, lock, project, solve, record."""

import time as clock
from dataclasses import replace
from functools import partial

import numpy as np

from uav_routing.alns import SearchResult, run_alns
from uav_routing.config import ALNSConfig
from uav_routing.contextual.config import ContextualBanditConfig
from uav_routing.evaluator import Evaluator
from uav_routing.initial import build_initial_solution
from uav_routing.models import Instance, SearchConstraints, Solution
from uav_routing.repair import RepairContext

from .config import RollingHorizonConfig
from .events import apply_events, drop_customers
from .locking import lock_solution
from .models import DeadlineUpdate, EpochRecord, Event, Scenario, SimulationResult
from .policies import (
    POLICIES,
    EpochSolver,
    contextual_warm_alns,
    evaluate_only,
)
from .projection import lost_customers, project, triage
from .scenario import base_instance


def next_decision_time(
    time: float,
    config: RollingHorizonConfig,
    pending: tuple[Event, ...],
    horizon: float,
) -> float:
    upcoming = [event.time for event in pending if event.time > time]
    next_event = min(upcoming) if upcoming else horizon
    periodic = min(time + effective_epoch_length(config, horizon), horizon)

    if config.trigger == "periodic":
        return float(periodic)

    if config.trigger == "event":
        return float(min(next_event, horizon))

    return float(min(periodic, next_event))


def effective_epoch_length(config: RollingHorizonConfig, horizon: float) -> float:
    """Epoch length in time units: a fraction of the horizon when configured."""
    if config.epoch_fraction is not None:
        return float(config.epoch_fraction * horizon)

    return float(config.epoch_length)


def decision_times(
    scenario: Scenario, config: RollingHorizonConfig
) -> tuple[float, ...]:
    """Epoch times after epoch 0, without running any solver."""
    times: list[float] = []
    pending = tuple(scenario.events)
    time = 0.0

    while time < scenario.horizon:
        time = next_decision_time(time, config, pending, scenario.horizon)
        pending = tuple(event for event in pending if event.time > time)
        times.append(time)

    return tuple(times)


def epoch_seed(base_seed: int, epoch_index: int) -> int:
    sequence = np.random.SeedSequence([int(base_seed) & 0xFFFFFFFF, int(epoch_index)])

    return int(sequence.generate_state(1, dtype=np.uint32)[0])


class _Simulation:
    def __init__(
        self,
        scenario: Scenario,
        alns: ALNSConfig,
        config: RollingHorizonConfig,
        solver: EpochSolver,
    ) -> None:
        self.scenario = scenario
        self.alns = alns
        self.config = config
        self.solver = solver

        self.instance: Instance = base_instance(scenario)
        self.constraints = SearchConstraints()
        self.frozen: dict[int, float] = {}

        self.rejected: tuple[int, ...] = ()
        self.lost: list[int] = []
        self.lost_priority = 0.0

        self.epochs: list[EpochRecord] = []
        self.pending = list(scenario.events)
        self.time = 0.0

    def run(self) -> SimulationResult:
        started = clock.perf_counter()

        result = self._solve_epoch_zero()
        self.d_ref = result.d_ref
        self.solution = result.best_solution

        self._record(result, (), started)

        while self.time < self.scenario.horizon:
            self._advance()

        return self._finish(started)

    def _solve_epoch_zero(self) -> SearchResult:
        seed = epoch_seed(self.config.seed, 0)
        alns = replace(self.alns, seed=seed)

        if self.config.policy == "contextual_warm_alns":
            initial, d_ref = build_initial_solution(
                self.instance,
                alns.alpha,
                alns.beta,
            )

            return self.solver(
                self.instance,
                initial,
                self.constraints,
                d_ref,
                alns,
                self.config.iterations_epoch0,
                seed,
            )

        if self.config.iterations_epoch0 > 0:
            return run_alns(
                self.instance, replace(alns, iterations=self.config.iterations_epoch0)
            )

        initial, d_ref = build_initial_solution(self.instance, alns.alpha, alns.beta)

        return evaluate_only(
            self.instance, initial, self.constraints, d_ref, alns, seed
        )

    def _advance(self) -> None:
        epoch_started = clock.perf_counter()
        next_time = next_decision_time(
            self.time, self.config, tuple(self.pending), self.scenario.horizon
        )
        revealed = tuple(event for event in self.pending if event.time <= next_time)

        self.pending = [event for event in self.pending if event.time > next_time]
        self.time = next_time

        self._lock()
        self._apply(revealed)
        self._drop_lost()

        initial, epoch_instance = self._prepare_initial()
        result = self.solver(
            epoch_instance,
            initial,
            self.constraints,
            self.d_ref,
            self.alns,
            self.config.iterations_per_epoch,
            epoch_seed(self.config.seed, len(self.epochs)),
        )
        self.solution = result.best_solution

        self._record(result, revealed, epoch_started)

    def _lock(self) -> None:
        evaluator = self._evaluator()
        self.solution, self.constraints = lock_solution(
            self.solution, evaluator, self.time, self.constraints
        )
        priorities = self._priorities()

        for customer_id in self.constraints.locked_customers():
            self.frozen.setdefault(customer_id, priorities[customer_id])

    def _apply(self, revealed: tuple[Event, ...]) -> None:
        applicable = tuple(event for event in revealed if self._applicable(event))

        self.instance = apply_events(self.instance, applicable, self.frozen)

    def _applicable(self, event: Event) -> bool:
        if not isinstance(event, DeadlineUpdate):
            return True

        return event.customer_id not in self.frozen and event.customer_id not in (
            self.lost
        )

    def _drop_lost(self) -> None:
        newly_lost = lost_customers(self.instance, self.rejected, self.time)

        if not newly_lost:
            return

        priorities = self._priorities()

        self.lost.extend(newly_lost)
        self.lost_priority += sum(priorities[customer_id] for customer_id in newly_lost)
        self.instance = drop_customers(self.instance, newly_lost, self.frozen)

    def _prepare_initial(self) -> tuple[Solution, Instance]:
        evaluator = self._evaluator()
        projected, pool = project(
            self.solution, self.instance, evaluator, self.constraints
        )
        context = RepairContext(
            self.instance,
            evaluator,
            self.d_ref,
            self.alns.alpha,
            self.alns.beta,
            self.constraints,
        )
        initial, self.rejected = triage(projected, pool, context)

        if not self.rejected:
            return initial, self.instance

        return initial, drop_customers(self.instance, self.rejected, self.frozen)

    def _record(
        self, result: SearchResult, revealed: tuple[Event, ...], started: float
    ) -> None:
        self.epochs.append(
            EpochRecord(
                index=len(self.epochs),
                time=self.time,
                revealed=revealed,
                locked_customers=len(self.constraints.locked_customers()),
                rejected=self.rejected,
                solution=self.solution,
                evaluation=result.evaluation,
                iterations=result.iterations,
                runtime_seconds=clock.perf_counter() - started,
            )
        )

    def _finish(self, started: float) -> SimulationResult:
        priorities = self._priorities()
        final_instance = (
            drop_customers(self.instance, self.rejected, self.frozen)
            if self.rejected
            else self.instance
        )
        evaluation = Evaluator(
            final_instance, self.d_ref, self.alns.alpha, self.alns.beta
        ).solution(self.solution, self.constraints)
        unserved = tuple(sorted(set(self.rejected) | set(self.lost)))
        unserved_priority = self.lost_priority + sum(
            priorities[customer_id] for customer_id in self.rejected
        )

        return SimulationResult(
            scenario=self.scenario.name,
            policy=self.config.policy,
            seed=self.config.seed,
            d_ref=self.d_ref,
            final_instance=final_instance,
            realized=self.solution,
            evaluation=evaluation,
            unserved=unserved,
            unserved_priority=float(unserved_priority),
            epochs=tuple(self.epochs),
            total_iterations=sum(record.iterations for record in self.epochs),
            runtime_seconds=clock.perf_counter() - started,
        )

    def _evaluator(self) -> Evaluator:
        return Evaluator(self.instance, self.d_ref, self.alns.alpha, self.alns.beta)

    def _priorities(self) -> dict[int, float]:
        return {
            customer.id: float(self.instance.risk_priority[index])
            for index, customer in enumerate(self.instance.customers, start=1)
        }


def run_rolling_horizon(
    scenario: Scenario,
    alns: ALNSConfig,
    config: RollingHorizonConfig,
    solver: EpochSolver | None = None,
    bandit: ContextualBanditConfig | None = None,
) -> SimulationResult:
    config.validate()
    alns.validate()

    if solver is None:
        if config.policy not in POLICIES:
            raise ValueError(f"unknown policy {config.policy!r}")

        if config.policy == "contextual_warm_alns":
            if bandit is not None:
                bandit.validate()

            solver = partial(
                contextual_warm_alns,
                bandit=bandit or ContextualBanditConfig(),
            )
        else:
            solver = POLICIES[config.policy]

    return _Simulation(scenario, alns, config, solver).run()
