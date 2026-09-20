# Task 12: Add benchmark runner, aggregation, README and final verification

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M4 — Reproducible experiments

**Depends on:** Task 10

**Unlocks:** Definition of Done

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/src/uav_routing/experiment.py`
- Create: `phase1/configs/benchmark.json`
- Create: `phase1/tests/test_experiment.py`
- Create: `phase1/README.md`
- Create: `phase1/results/.gitkeep`

**Interfaces:**
- Consumes: CLI-equivalent solve configuration and nine dataset paths.
- Produces: `uv run python -m uav_routing.experiment --config configs/benchmark.json`; raw CSV and aggregate CSV with stable schemas.

- [ ] **Step 1: Write benchmark matrix and CSV aggregation tests**

```python
def test_benchmark_runs_cartesian_product(tmp_path, fake_solver):
    config = benchmark_config(instances=["c101", "r101"], seeds=[1, 2, 3])
    rows = run_benchmark(config, solver=fake_solver)
    assert len(rows) == 6
    assert {(r["instance"], r["seed"]) for r in rows} == {
        ("c101", 1), ("c101", 2), ("c101", 3),
        ("r101", 1), ("r101", 2), ("r101", 3),
    }

def test_raw_and_aggregate_csv_have_stable_schema(tmp_path, sample_rows):
    raw, aggregate = write_results(sample_rows, tmp_path)
    assert read_header(raw) == ["instance", "customers", "seed", "iterations", "vehicles", "distance", "risk_delay", "objective", "runtime_seconds", "feasible"]
    assert read_header(aggregate) == ["instance", "customers", "iterations", "alpha", "beta", "runs", "vehicles_mean", "vehicles_std", "vehicles_best", "vehicles_worst", "distance_mean", "distance_std", "distance_best", "distance_worst", "risk_delay_mean", "risk_delay_std", "risk_delay_best", "risk_delay_worst", "objective_mean", "objective_std", "objective_best", "objective_worst", "runtime_mean", "runtime_std"]
```

- [ ] **Step 2: Add importable experiment stubs, then verify behavioral RED**

```python
@dataclass(frozen=True)
class BenchmarkConfig:
    instance_paths: tuple[Path, ...]
    seeds: tuple[int, ...]
    alns: ALNSConfig

def run_benchmark(config: BenchmarkConfig, solver: Callable | None = None) -> list[dict[str, object]]:
    raise NotImplementedError("benchmark execution is not implemented")

def write_results(rows: list[dict[str, object]], output_dir: Path) -> tuple[Path, Path]:
    raise NotImplementedError("CSV output is not implemented")
```

Run: `cd phase1 && uv run pytest tests/test_experiment.py -v`

Expected: module imports and tests collect; benchmark and CSV calls fail at their respective stubs.

- [ ] **Step 3: Implement sequential benchmark and statistically explicit aggregation**

```python
for instance_path in config.instance_paths:
    for seed in config.seeds:
        result = solve_one(instance_path, replace(config.alns, seed=seed))
        rows.append(flatten_run(result))

mean = statistics.fmean(values)
std = statistics.stdev(values) if len(values) >= 2 else 0.0
```

Use instance order `c101,c102,c103,r101,r102,r103,rc101,rc102,rc103` and seed order from config. Development config contains seeds `0..9`, 25 customers and 10,000 iterations. Fail the benchmark if any run is infeasible; retain already completed raw rows by rewriting CSV atomically after each run. Define “best/worst” numerically per metric; vehicle count remains a separate metric and no row is selected as a combined best solution in the aggregate file.

README must include: Phase 1 scope; installation; input format; feasibility rules; formulas for $p_i$, $q_i$, $R(S)$, $D_{ref}$, $F(S)$ and lexicographic score; single-run command; benchmark command; output schemas; seed/reproducibility statement; test command; and the nine-instance scope.

- [ ] **Step 4: Run all acceptance checks**

Run:

```bash
cd phase1
uv run pytest tests -q
uv run python -m uav_routing.cli solve --instance ../dataset/solomon_risk/c101.txt --customers 25 --iterations 50 --seed 42 --output results/c101-acceptance.json
uv run python -m uav_routing.experiment --config configs/benchmark.json --iterations 2 --seeds 0 --output-dir results/smoke
```

Expected: complete test suite passes; single result is feasible with 25 unique customers; smoke benchmark produces 9 raw rows and 9 aggregate rows, one per target instance. The reduced CLI overrides are for smoke verification only; committed benchmark defaults remain 10 seeds and 10,000 iterations.

- [ ] **Step 5: Commit reproducible experiment delivery**

```bash
git add phase1/src/uav_routing/experiment.py phase1/configs/benchmark.json phase1/tests/test_experiment.py phase1/README.md phase1/results/.gitkeep
git commit -m "feat(phase1): add reproducible benchmark workflow"
```
