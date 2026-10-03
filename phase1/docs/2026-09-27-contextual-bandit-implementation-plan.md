# Contextual Bandit ALNS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible Disjoint LinUCB ALNS variant that selects destroy--repair pairs from nine-dimensional search context while preserving the roulette ALNS as the default baseline.

**Architecture:** A new `uav_routing.contextual` package owns bandit configuration, context/history, LinUCB state, pair selection, and a separate contextual search loop. Existing operators, evaluator, initial construction, acceptance, reward classification, cooling, CLI rendering, and benchmark infrastructure are reused; `alns.py`, `adaptive.py`, `ALNSSolver`, `run_alns`, and `SearchResult` keep their public contracts.

**Tech Stack:** Python 3.11+, NumPy, pytest, dataclasses, argparse, JSON, CSV, multiprocessing through the existing benchmark runner.

**Spec:** `phase1/docs/2026-09-27-contextual-bandit-alns-design.md`

## Global Constraints

- Baseline remains the default and continues to run through `run_alns`; no LinUCB or context state is added to `uav_routing.alns` or `uav_routing.adaptive`.
- New contextual code lives under `phase1/src/uav_routing/contextual/`; contextual unit tests live under `phase1/tests/contextual/`.
- Every stochastic decision, including score ties, uses the solver's single injected `numpy.random.Generator`.
- Context is computed before arm selection and contains exactly nine finite features in the design-specified order.
- LinUCB uses `numpy.linalg.solve`, one independent matrix/vector pair per arm, and no new dependency.
- Contextual reward is the existing raw ALNS reward divided by the largest configured reward; baseline continues to receive raw reward.
- Existing evaluator, operators, `build_initial_solution`, `accept_score`, `classify_reward`, `cool_temperature`, and fixed-iteration stopping rule are reused.
- Same instance, configuration, and seed reproduce routes, evaluation, and pair statistics; runtime is excluded from equality.
- Follow the repository TDD convention: create an importable typed skeleton before its test, use a placeholder that makes the behavioral assertion fail, verify RED, then add the minimal implementation and verify GREEN.
- Markdown mathematics in repository files uses `$...$` inline and `$$...$$` for blocks.
- Keep logical code groups to at most three consecutive statements without a blank line.

## Review Focus

- `iterations=1` must produce finite progress and normalized temperature without division by zero; Task 2 adds this edge test.
- An empty history window must yield zero acceptance/improvement rates, while failed repair still appends `False`; Tasks 2 and 5 pin both behaviors.
- Duplicate or empty operator names must not silently collapse the Cartesian action space; Task 4 rejects them.
- Equal LinUCB scores must use only the injected RNG and remain reproducible; Task 3 tests two selectors initialized with the same seed.
- A benchmark CLI override from contextual config to baseline must blank all three bandit CSV columns and must not construct a contextual solver; Task 7 tests the dispatch boundary.

---

### Task 1: Contextual configuration and public package skeleton

**Files:**
- Create: `phase1/src/uav_routing/contextual/__init__.py`
- Create: `phase1/src/uav_routing/contextual/config.py`
- Create: `phase1/tests/contextual/__init__.py`
- Create: `phase1/tests/contextual/test_config.py`

**Interfaces:**
- Consumes: `uav_routing.config.ALNSConfig` only at contextual solver validation time, not in this task.
- Produces: `ContextualBanditConfig(context_window: int = 100, linucb_exploration: float = 0.5, linucb_regularization: float = 1.0)`, `validate() -> None`, and `from_dict(values: dict[str, object]) -> ContextualBanditConfig`.

- [x] **Step 1: Create importable skeletons**

Define the frozen dataclass and public exports with correct signatures. Let `validate()` return `None`; let `from_dict()` construct the dataclass but defer behavioral validation.

- [x] **Step 2: Write validation tests**

Add tests asserting defaults, valid dictionary construction, unknown-key rejection, `bool`/non-integer/nonpositive `context_window` rejection, nonfinite/negative exploration rejection, and nonfinite/nonpositive regularization rejection.

- [x] **Step 3: Run the tests to verify RED**

Run: `cd phase1 && uv run pytest tests/contextual/test_config.py -q`

Expected: FAIL at validation assertions, not during import or collection.

- [x] **Step 4: Implement minimal validation**

Use explicit type checks so `bool` is not accepted as an integer or real number. Convert constructor `TypeError` from unknown keys to `ValueError`, matching `ALNSConfig.from_dict` behavior.

- [x] **Step 5: Verify GREEN and baseline config regression**

Run: `cd phase1 && uv run pytest tests/contextual/test_config.py tests/test_config.py -q`

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add phase1/src/uav_routing/contextual phase1/tests/contextual
git commit -m "feat: add contextual bandit configuration"
```

---

### Task 2: Search history and nine-dimensional context

**Files:**
- Create: `phase1/src/uav_routing/contextual/context.py`
- Create: `phase1/tests/contextual/test_context.py`

**Interfaces:**
- Consumes: `SolutionEvaluation` fields `vehicle_count`, `objective`, and `risk_delay`.
- Produces:

```python
CONTEXT_DIMENSION = 9

class SearchHistory:
    def __init__(self, window: int) -> None: ...
    @property
    def stagnation(self) -> int: ...
    @property
    def total_iterations(self) -> int: ...
    @property
    def acceptance_rate(self) -> float: ...
    @property
    def improvement_rate(self) -> float: ...
    def record(self, *, accepted: bool, improved: bool, new_best: bool) -> None: ...

def build_context(
    *,
    iteration: int,
    total_iterations: int,
    temperature: float,
    initial_temperature: float,
    minimum_temperature: float,
    current: SolutionEvaluation,
    best: SolutionEvaluation,
    max_vehicles: int,
    history: SearchHistory,
) -> np.ndarray: ...
```

- [x] **Step 1: Create typed skeletons**

Return a zero vector of length nine from `build_context`; initialize all history counters and bounded boolean deques, but leave `record` as a no-op placeholder.

- [x] **Step 2: Write history tests**

Test empty rates, bounded window eviction, failed/rejected `(False, False)`, accepted-worse `(True, False)`, improvement `(True, True)`, stagnation increment, and reset to zero on `new_best=True`.

- [x] **Step 3: Run history tests to verify RED**

Run: `cd phase1 && uv run pytest tests/contextual/test_context.py -q`

Expected: FAIL on history mutation assertions.

- [x] **Step 4: Implement `SearchHistory` minimally**

Validate a positive non-boolean window, append accepted/improved outcomes, increment total iterations, and update stagnation after each completed iteration.

- [x] **Step 5: Write exact context tests**

Assert the order `[bias, progress, temperature, stagnation, acceptance_rate, improvement_rate, vehicle_gap, objective_gap, risk_delay]`; test `iterations=1`, `initial_temperature == minimum_temperature`, clipping at both ends, vehicle mismatch forcing objective gap to zero, zero best objective denominator, wrong/invalid scalar inputs, and rejection of nonfinite output.

- [x] **Step 6: Run context tests to verify RED**

Run: `cd phase1 && uv run pytest tests/contextual/test_context.py -q`

Expected: FAIL because the skeleton returns zeros.

- [x] **Step 7: Implement context extraction**

Use logarithmic temperature normalization, design-specified denominators and clipping, and a final shape/finite check that raises `ValueError` before returning corrupted input to a selector.

- [x] **Step 8: Verify GREEN**

Run: `cd phase1 && uv run pytest tests/contextual/test_context.py -q`

Expected: PASS.

- [x] **Step 9: Commit**

```bash
git add phase1/src/uav_routing/contextual/context.py phase1/tests/contextual/test_context.py
git commit -m "feat: extract contextual ALNS search state"
```

---

### Task 3: Disjoint LinUCB core

**Files:**
- Create: `phase1/src/uav_routing/contextual/linucb.py`
- Create: `phase1/tests/contextual/test_linucb.py`

**Interfaces:**
- Consumes: stable hashable arm identifiers, finite one-dimensional NumPy contexts, and an injected `numpy.random.Generator`.
- Produces:

```python
@dataclass(frozen=True)
class LinUCBArmState:
    matrix: np.ndarray
    reward_vector: np.ndarray

class DisjointLinUCB:
    def __init__(
        self,
        arms: tuple[Hashable, ...],
        dimension: int,
        exploration: float,
        regularization: float,
        rng: np.random.Generator,
    ) -> None: ...
    def select(self, context: np.ndarray) -> Hashable: ...
    def update(self, arm: Hashable, context: np.ndarray, reward: float) -> None: ...
    def state(self, arm: Hashable) -> LinUCBArmState: ...
```

- [x] **Step 1: Create the skeleton**

Validate constructor-independent imports and return the first arm from `select`; make `update` a no-op and `state` return copied placeholder arrays of the correct shape.

- [x] **Step 2: Write constructor and input tests**

Test nonempty unique arms, positive non-boolean dimension, nonnegative finite exploration, positive finite regularization, exact $\lambda I$/$0$ initialization, copied snapshots, unknown arms, wrong context shape, nonfinite contexts, and nonfinite rewards.

- [x] **Step 3: Run tests to verify RED**

Run: `cd phase1 && uv run pytest tests/contextual/test_linucb.py -q`

Expected: FAIL on initialization and validation behavior.

- [x] **Step 4: Implement validation and state initialization**

Store one independent matrix/vector per arm. Ensure returned state arrays cannot mutate internal bandit state.

- [x] **Step 5: Add selection/update tests**

Use hand-computable one- and two-dimensional cases to assert exploitation, uncertainty, `numpy.linalg.solve`-equivalent scores, selected-arm-only update $A \leftarrow A + xx^T$ and $b \leftarrow b + rx$, and reproducible random tie-breaking for equal scores.

- [x] **Step 6: Run tests to verify RED**

Run: `cd phase1 && uv run pytest tests/contextual/test_linucb.py -q`

Expected: FAIL because selection/update are placeholders.

- [x] **Step 7: Implement LinUCB selection and update**

Compute each mean and uncertainty with `numpy.linalg.solve`; identify ties with `numpy.isclose` and choose their index through the injected RNG only.

- [x] **Step 8: Verify GREEN**

Run: `cd phase1 && uv run pytest tests/contextual/test_linucb.py -q`

Expected: PASS.

- [x] **Step 9: Commit**

```bash
git add phase1/src/uav_routing/contextual/linucb.py phase1/tests/contextual/test_linucb.py
git commit -m "feat: implement disjoint LinUCB"
```

---

### Task 4: Destroy--repair pair selector and statistics

**Files:**
- Create: `phase1/src/uav_routing/contextual/selector.py`
- Create: `phase1/tests/contextual/test_selector.py`
- Modify: `phase1/src/uav_routing/contextual/__init__.py`

**Interfaces:**
- Consumes: `ContextualBanditConfig`, `DisjointLinUCB`, destroy names in stable order, repair names in stable order, raw reward scale, and solver RNG.
- Produces:

```python
OperatorPair = tuple[str, str]

@dataclass(frozen=True)
class PairSelectionStats:
    destroy_name: str
    repair_name: str
    total_uses: int
    total_raw_reward: float
    average_raw_reward: float

class OperatorPairSelector:
    def __init__(
        self,
        destroy_names: tuple[str, ...],
        repair_names: tuple[str, ...],
        config: ContextualBanditConfig,
        maximum_raw_reward: float,
        rng: np.random.Generator,
    ) -> None: ...
    @property
    def arms(self) -> tuple[OperatorPair, ...]: ...
    def select(self, context: np.ndarray) -> OperatorPair: ...
    def record(self, arm: OperatorPair, context: np.ndarray, raw_reward: float) -> None: ...
    def snapshot(self) -> tuple[PairSelectionStats, ...]: ...
```

- [x] **Step 1: Create the selector skeleton**

Build the Cartesian-product arm tuple, return its first item from `select`, leave `record` inert, and return zero-valued stats in arm order.

- [x] **Step 2: Write selector tests**

Test destroy-major Cartesian ordering and `destroy+repair` identity, rejection of empty/duplicate/blank names, rejection of nonpositive or nonfinite maximum reward, delegation of selection, normalization of raw rewards, one-arm-only updates, raw total/average statistics, zero-use averages, stable snapshots, and 15 default arms for five destroy by three repair names.

- [x] **Step 3: Run tests to verify RED**

Run: `cd phase1 && uv run pytest tests/contextual/test_selector.py -q`

Expected: FAIL on recording, validation, or bandit-update assertions.

- [x] **Step 4: Implement selector behavior**

Keep raw reward accounting separate from normalized LinUCB updates. Reject unknown arms, negative/nonfinite raw rewards, or invalid contexts through the bandit boundary.

- [x] **Step 5: Export selector APIs and verify GREEN**

Run: `cd phase1 && uv run pytest tests/contextual/test_selector.py tests/contextual/test_linucb.py -q`

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add phase1/src/uav_routing/contextual phase1/tests/contextual/test_selector.py
git commit -m "feat: select contextual operator pairs"
```

---

### Task 5: Contextual ALNS orchestration

**Files:**
- Create: `phase1/src/uav_routing/contextual/alns.py`
- Create: `phase1/tests/contextual/test_alns.py`
- Modify: `phase1/src/uav_routing/contextual/__init__.py`

**Interfaces:**
- Consumes: `ALNSConfig`; `ContextualBanditConfig`; baseline `_operators`, `_audit_best_solution`, `accept_score`, `classify_reward`, and `cool_temperature`; existing `Evaluator`, `RepairContext`, and `build_initial_solution`.
- Produces:

```python
@dataclass(frozen=True)
class ContextualSearchResult:
    initial_solution: Solution
    final_current: Solution
    best_solution: Solution
    d_ref: float
    evaluation: SolutionEvaluation
    iterations: int
    seed: int
    runtime_seconds: float
    pair_selection_stats: tuple[PairSelectionStats, ...]

@dataclass(frozen=True)
class CandidateOutcome:
    raw_reward: float
    accepted: bool
    improved: bool
    new_best: bool

class ContextualALNSSolver:
    def __init__(
        self,
        instance: Instance,
        alns_config: ALNSConfig,
        bandit_config: ContextualBanditConfig,
    ) -> None: ...
    def run(self) -> ContextualSearchResult: ...

def run_contextual_alns(
    instance: Instance,
    alns_config: ALNSConfig,
    bandit_config: ContextualBanditConfig | None = None,
) -> ContextualSearchResult: ...
```

- [x] **Step 1: Create solver skeletons**

Declare all records and signatures. The solver placeholder may raise `NotImplementedError` only when `run()` is invoked, so imports and test collection succeed.

- [x] **Step 2: Write validation and outcome tests**

Test both configs are validated, at least one ALNS reward must be positive, failures/infeasible/equal/rejected/accepted-worse/improved/new-best outcomes update state consistently, and failed repair produces `(raw_reward=0, accepted=False, improved=False, new_best=False)`.

- [x] **Step 3: Run focused tests to verify RED**

Run: `cd phase1 && uv run pytest tests/contextual/test_alns.py -q`

Expected: FAIL at `NotImplementedError` or behavioral assertions, not import/collection.

- [x] **Step 4: Implement resources and one iteration**

Create the same default five destroy and three repair operators through the baseline factory, build name maps and the selector, then perform exactly: context, random $q$, pair choice, destroy, repair, evaluation/acceptance/reward, state updates, selector record, history record, cooling.

- [x] **Step 5: Add end-to-end and reproducibility tests**

On the existing C101 fixture/config, assert a complete feasible best solution, no worse than initial, 15 stats entries, total uses equal iterations, and identical initial/current/best/evaluation/pair stats across same-seed runs. Add a one-iteration failed-repair test through a focused internal helper or injected resources so history still records the failure without changing current.

- [x] **Step 6: Run focused tests to verify RED**

Run: `cd phase1 && uv run pytest tests/contextual/test_alns.py -q`

Expected: FAIL until the complete loop returns the specified result.

- [x] **Step 7: Complete the contextual loop and exports**

Audit the best solution with the baseline audit helper. Do not introduce contextual fields, parameters, or imports into baseline `ALNSSolver`, `run_alns`, or `SearchResult`.

- [x] **Step 8: Verify contextual and baseline search**

Run: `cd phase1 && uv run pytest tests/contextual/test_alns.py tests/test_alns.py tests/test_integration.py -q`

Expected: PASS.

- [x] **Step 9: Commit**

```bash
git add phase1/src/uav_routing/contextual phase1/tests/contextual/test_alns.py
git commit -m "feat: add contextual ALNS search loop"
```

---

### Task 6: Single-instance CLI dispatch and shared JSON schema

**Files:**
- Modify: `phase1/src/uav_routing/cli.py`
- Modify: `phase1/tests/test_cli.py`

**Interfaces:**
- Consumes: baseline `SearchResult`, contextual `ContextualSearchResult`, and optional `ContextualBanditConfig`.
- Produces: `--algorithm {baseline,contextual}` defaulting to `baseline`; JSON keys `algorithm`, `contextual_bandit`, `operators`, and `pair_selection_stats` for every solve.

- [x] **Step 1: Add importable rendering/dispatch skeleton**

Add the parser option and extend `result_to_dict` with an optional bandit config while retaining the existing three-argument baseline call. Populate schema placeholders (`algorithm="baseline"`, `contextual_bandit=None`, `pair_selection_stats=[]`) before changing dispatch.

- [x] **Step 2: Write CLI schema and dispatch tests**

Test omitted algorithm and explicit baseline preserve baseline behavior; contextual invokes `run_contextual_alns`; argparse rejects unknown algorithms; baseline JSON has null bandit config/nonempty operators/empty pair stats; contextual JSON has exact bandit config/empty operators/15 pair stats; both stdout payloads are valid JSON and progress remains on stderr.

- [x] **Step 3: Run tests to verify RED**

Run: `cd phase1 && uv run pytest tests/test_cli.py -q`

Expected: FAIL for contextual dispatch/schema assertions while baseline smoke remains importable.

- [x] **Step 4: Implement algorithm-aware rendering and dispatch**

Use the default `ContextualBanditConfig` for a contextual single solve. Keep all preexisting route/schedule fields and atomic output writing unchanged.

- [x] **Step 5: Verify GREEN**

Run: `cd phase1 && uv run pytest tests/test_cli.py tests/test_alns.py -q`

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add phase1/src/uav_routing/cli.py phase1/tests/test_cli.py
git commit -m "feat: dispatch contextual solver from CLI"
```

---

### Task 7: Benchmark algorithm selection and stable CSV schemas

**Files:**
- Modify: `phase1/src/uav_routing/experiment.py`
- Modify: `phase1/tests/test_experiment.py`

**Interfaces:**
- Consumes: optional top-level benchmark `algorithm`, optional `contextual_bandit`, and CLI `--algorithm` override.
- Produces: `BenchmarkConfig.algorithm: str = "baseline"`, `BenchmarkConfig.bandit: ContextualBanditConfig | None = None`, design-specified raw/aggregate fields, algorithm-aware grouping, and completion text containing `algorithm=<value>`.

- [x] **Step 1: Add benchmark data skeleton**

Append defaulted algorithm/bandit fields to `BenchmarkConfig` so existing positional construction remains valid. Add the new raw and aggregate headers with blank baseline bandit columns, but leave `_solve_one` dispatching baseline as the placeholder.

- [x] **Step 2: Write config precedence and dispatch tests**

Test missing config key defaults baseline; contextual config loads all bandit values; CLI overrides either direction; invalid algorithm/config block is rejected; contextual jobs call contextual solve and baseline jobs do not. Preserve the custom four-argument solver contract used by existing sequential/parallel tests.

- [x] **Step 3: Run focused tests to verify RED**

Run: `cd phase1 && uv run pytest tests/test_experiment.py -q`

Expected: FAIL on algorithm dispatch or precedence assertions.

- [x] **Step 4: Implement picklable algorithm dispatch**

Select a top-level picklable solve callable for default benchmark jobs while leaving explicitly supplied custom solvers untouched. Ensure worker processes receive the chosen algorithm and contextual configuration without a closure.

- [x] **Step 5: Add schema/grouping tests**

Assert exact raw and aggregate header order from the design; baseline bandit columns are empty; contextual values are present; grouping separates baseline/contextual and distinct LinUCB hyperparameters; completion stdout includes algorithm; route JSON serialization and stable result ordering remain unchanged.

- [x] **Step 6: Run focused tests to verify RED**

Run: `cd phase1 && uv run pytest tests/test_experiment.py -q`

Expected: FAIL until row construction and grouping keys include all new fields.

- [x] **Step 7: Implement row rendering, aggregation, and output text**

Group by instance, size, algorithm, iteration budget, objective weights, and three contextual hyperparameters. Use `None` for baseline bandit values so `csv.DictWriter` emits blank cells.

- [x] **Step 8: Verify GREEN including parallel regressions**

Run: `cd phase1 && uv run pytest tests/test_experiment.py -q`

Expected: PASS, including picklability, stable order, checkpoint retention, and cleanup tests.

- [x] **Step 9: Commit**

```bash
git add phase1/src/uav_routing/experiment.py phase1/tests/test_experiment.py
git commit -m "feat: benchmark baseline and contextual ALNS"
```

---

### Task 8: Contextual benchmark config, documentation, and final regression

**Files:**
- Create: `phase1/configs/contextual/benchmark.json`
- Modify: `phase1/README.md`
- Modify: `phase1/tests/test_integration.py`
- Modify: `phase1/src/uav_routing/contextual/__init__.py`

**Interfaces:**
- Consumes: all public contextual APIs and final CLI/benchmark commands.
- Produces: documented action/context/reward model, static limitations, reproducible solve/benchmark examples, and final public exports `ContextualBanditConfig`, `ContextualALNSSolver`, `ContextualSearchResult`, and `run_contextual_alns`.

- [x] **Step 1: Add integration test skeleton cases**

Add test names and fixtures for baseline API preservation, contextual reproducibility, and selection-use totals. Keep assertions targeting the already importable APIs.

- [x] **Step 2: Run integration tests to establish RED if coverage finds a gap**

Run: `cd phase1 && uv run pytest tests/test_integration.py tests/contextual -q`

Expected: PASS if prior tasks cover the contracts; otherwise FAIL only on the missing end-to-end behavior, which must be fixed before continuing.

- [x] **Step 3: Add contextual benchmark configuration**

Copy the existing benchmark ALNS parameters and add `"algorithm": "contextual"` plus `context_window=100`, `linucb_exploration=0.5`, and `linucb_regularization=1.0` under `contextual_bandit`. Keep paths and workload consistent with the current benchmark config.

- [x] **Step 4: Update README**

Document baseline as default; describe 15 pair arms, nine context features, normalized discrete reward, LinUCB limits, JSON schema differences, exact solve commands, separate output directories, contextual config, algorithm precedence, and benchmark CSV columns/grouping.

- [x] **Step 5: Run formatting and the full test suite**

Run: `cd phase1 && uv run ruff check src tests`

Expected: PASS with no diagnostics.

Run: `cd phase1 && uv run pytest tests -q`

Expected: PASS with no failures or warnings.

- [x] **Step 6: Run two CLI smoke tests**

Run: `cd phase1 && uv run python -m uav_routing.cli solve --algorithm baseline --instance ../dataset/solomon_risk/c101.txt --customers 25 --risks 5 --iterations 2 --seed 42`

Expected: exit 0; stdout is one JSON object with `algorithm="baseline"`, `contextual_bandit=null`, and empty `pair_selection_stats`.

Run: `cd phase1 && uv run python -m uav_routing.cli solve --algorithm contextual --instance ../dataset/solomon_risk/c101.txt --customers 25 --risks 5 --iterations 2 --seed 42`

Expected: exit 0; stdout is one JSON object with `algorithm="contextual"`, non-null bandit configuration, empty `operators`, and 15 pair-stat entries whose uses sum to 2.

- [x] **Step 7: Run benchmark smoke tests in temporary output directories**

Run the existing baseline config and new contextual config with `--iterations 1 --seeds 0 --workers 1`; inspect stdout algorithm labels and exact CSV headers, then remove only those explicitly named smoke output directories.

- [x] **Step 8: Commit**

```bash
git add phase1/configs/contextual/benchmark.json phase1/README.md phase1/tests/test_integration.py phase1/src/uav_routing/contextual/__init__.py
git commit -m "docs: document contextual ALNS experiments"
```

## Final Definition of Done

- [x] `cd phase1 && uv run ruff check src tests` passes.
- [x] `cd phase1 && uv run pytest tests -q` passes.
- [x] Baseline deterministic regression remains unchanged for a fixed seed.
- [x] Contextual same-seed runs reproduce route, evaluation, and pair statistics.
- [x] Baseline is selected when no algorithm is provided.
- [x] Contextual solve reports all 15 pair stats and their uses sum to the configured iteration count.
- [x] Baseline and contextual JSON/CSV outputs match the shared schemas in the design.
- [x] No dependency is added and no contextual state enters baseline modules.
- [x] README commands work from `phase1/` and write baseline/contextual results to separate paths.
