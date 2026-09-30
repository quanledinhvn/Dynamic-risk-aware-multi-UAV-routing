# Rolling Horizon Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mở rộng baseline ALNS tĩnh thành bộ giải rolling horizon xác định, tái lập được cho dynamic risk-aware multi-UAV routing: mô phỏng sự kiện, khóa tiền tố tuyến, warm start, ba chính sách đối chứng, CLI mô phỏng, benchmark và tài liệu.

**Architecture:** Phần lõi Pha 1 nhận thêm một `SearchConstraints` tùy chọn đi qua `Evaluator`, destroy, repair và `run_alns`; giá trị mặc định tái tạo đúng Pha 1. Subpackage `uav_routing.dynamic` chứa kịch bản, sự kiện, khóa, chiếu nghiệm, vòng lặp epoch, chính sách, CLI và benchmark. `Evaluator` vẫn là nguồn duy nhất tính lịch, feasibility và mục tiêu.

**Tech Stack:** Python 3.11+, uv, NumPy, pytest, thư viện chuẩn `dataclasses`, `argparse`, `json`, `csv`, `statistics`, `time`.

**Spec:** `phase1/docs/2026-09-30-rolling-horizon-design.md`

**Task files:** [`phase1/docs/tasks/0930/`](tasks/0930/README.md)

**Branch:** `f/hai`, tách từ `f/quan`.

## Global Constraints

- Mọi test Pha 1 hiện có (211 test) phải tiếp tục vượt qua mà không sửa test.
- `run_alns(instance, config)` với tham số mặc định phải cho đúng route, metric và operator statistics như trước; Task 02 và Task 05 khóa điều này bằng snapshot test.
- Không dùng OR-Tools, Gurobi hoặc solver bên ngoài; không thêm dependency ngoài NumPy.
- `Evaluator` là nơi duy nhất kiểm tra tiền tố khóa, departure tuyến tự do, time window, capacity, depot deadline và tính $D$, $R$, $F$, score.
- Destroy không bao giờ tháo khách hàng đã khóa; repair không bao giờ chèn vào bên trong tiền tố khóa.
- Tuyến có tiền tố khóa chiếm các chỉ số đầu tiên theo thứ tự cố định trong suốt một epoch.
- Priority của khách hàng đã khóa được đóng băng; sự kiện risk chỉ đổi priority khách hàng tự do.
- $D_{\mathrm{ref}}$ được tính một lần tại epoch 0 và dùng cho toàn kịch bản.
- Mọi ngẫu nhiên (sinh kịch bản, ALNS, tie-break) đi qua một `numpy.random.Generator` tạo từ seed.
- Cùng kịch bản, cấu hình và seed phải sinh cùng `SimulationResult`; runtime không cần giống.
- Khách hàng không chèn được không làm ALNS thất bại; họ được ghi vào `rejected` và thử lại ở epoch sau.
- TDD theo quy ước [`tasks/0930/README.md`](tasks/0930/README.md): scaffold importable trước RED, RED thất bại tại assertion hoặc `NotImplementedError`.

## Review Focus

- Khách hàng mà UAV đang bay tới phải bị khóa; Task 08 có test riêng cho trường hợp $\operatorname{departure}_{\mathrm{prev}} \leq t < \operatorname{arrival}_i$.
- Tuyến tự do phải khởi hành không sớm hơn $t$ hiện tại; Task 02 có test `free_departure` làm một tuyến trở thành infeasible do depot deadline.
- Deadline bị siết trên khách hàng tự do phải được `project` xử lý bằng cách tháo khách hàng, không bao giờ tạo nghiệm infeasible cho ALNS; Task 09 kiểm tra.
- Kịch bản rỗng với `iterations_per_epoch = 0` phải cho đúng nghiệm tĩnh epoch 0; Task 10 khóa bất biến này.
- Chỉ số tuyến khóa không được dịch chuyển khi tuyến tự do bị xóa; Task 03 và Task 09 kiểm tra bất biến thứ tự.

---

## 1. Phân rã từ abstract đến concrete

### Outcome Pha 2

Một lệnh mô phỏng một kịch bản động theo một chính sách và xuất JSON có nghiệm thực hiện, lịch sử epoch và metric; một lệnh chạy benchmark kịch bản × seed × chính sách ra CSV; kết quả tái lập từ file kịch bản, cấu hình và seed.

### Milestones

| Milestone | Câu hỏi nghiệm thu | Tasks | Deliverable |
|---|---|---:|---|
| M1 — Constraint-aware core | Lõi Pha 1 có tôn trọng tiền tố khóa và departure tự do mà không đổi kết quả tĩnh không? | 01–05 | `SearchConstraints` đi qua evaluator, destroy, repair, `run_alns`; snapshot tĩnh giữ nguyên |
| M2 — Dynamic model | Kịch bản, sự kiện, khóa và chiếu nghiệm có xác định, thuần túy và kiểm thử độc lập không? | 06–09 | Bộ sinh kịch bản, `apply_events`, `locked_prefixes`, `project`, `triage` |
| M3 — Controller | Vòng lặp epoch có tái lập, tôn trọng ngân sách và đúng ba chính sách không? | 10 | `run_rolling_horizon`, bốn chính sách, `SimulationResult` |
| M4 — Experiments | Người khác có mô phỏng, benchmark và đọc kết quả được không? | 11–12 | CLI `simulate`, benchmark CSV, configs, README |

### Dependency graph

```text
Task 01: dynamic package + models + config
  ├── Task 02: SearchConstraints in Evaluator
  │     ├── Task 03: constraint-aware destroy
  │     ├── Task 04: constraint-aware insertion + repair
  │     └── Task 08: locking from schedule
  ├── Task 06: scenario format + generator
  │     └── Task 07: event application
  └── Tasks 03 + 04
        └── Task 05: run_alns warm start + constraints

Tasks 04 + 07 + 08
  └── Task 09: projection + triage
        └── Task 10 (with Task 05): controller + policies
              ├── Task 11: CLI simulate
              └── Task 12: benchmark + configs + README
```

## 2. File map and ownership

| File | Trách nhiệm duy nhất |
|---|---|
| `phase1/src/uav_routing/models.py` | Thêm `SearchConstraints` bất biến |
| `phase1/src/uav_routing/evaluator.py` | Kiểm tra tiền tố, departure tuyến tự do |
| `phase1/src/uav_routing/destroy.py` | Lọc khách hàng tự do theo ràng buộc |
| `phase1/src/uav_routing/repair.py` | Vị trí chèn hợp lệ, departure tuyến mới |
| `phase1/src/uav_routing/alns.py` | `initial_solution`, `constraints`, `d_ref` |
| `phase1/src/uav_routing/dynamic/models.py` | `Event`, `Scenario`, `LockState`, `EpochRecord`, `SimulationResult` |
| `phase1/src/uav_routing/dynamic/config.py` | `RollingHorizonConfig` và validation |
| `phase1/src/uav_routing/dynamic/scenario.py` | Đọc/ghi JSON kịch bản, sinh kịch bản từ Solomon-RISK |
| `phase1/src/uav_routing/dynamic/events.py` | `apply_events` thuần túy, đóng băng priority |
| `phase1/src/uav_routing/dynamic/locking.py` | `locked_prefixes` từ lịch tuyến |
| `phase1/src/uav_routing/dynamic/projection.py` | `project`, `triage` |
| `phase1/src/uav_routing/dynamic/policies.py` | `greedy_insert`, `cold_restart`, `warm_alns`, `clairvoyant` |
| `phase1/src/uav_routing/dynamic/horizon.py` | Vòng lặp epoch, `run_rolling_horizon` |
| `phase1/src/uav_routing/dynamic/cli.py` | `simulate`, JSON output |
| `phase1/src/uav_routing/dynamic/experiment.py` | Kịch bản × seed × chính sách, raw/aggregate CSV |
| `dataset/scripts/generate_solomon_dynamic.py` | Script sinh bộ kịch bản dùng chung |
| `dataset/solomon_dynamic/` | Kịch bản JSON đã sinh |
| `phase1/configs/dynamic/` | Cấu hình benchmark động |
| `phase1/tests/dynamic/` | Unit, integration và CLI tests của Pha 2 |
| `phase1/tests/test_static_snapshot.py` | Snapshot hồi quy kết quả tĩnh |

## 3. Stable interface contracts

Các task phải giữ nguyên tên và kiểu sau:

```python
# uav_routing/models.py
@dataclass(frozen=True)
class SearchConstraints:
    locked_prefixes: tuple[Route, ...] = ()
    free_departure: float = 0.0

    @property
    def locked_route_count(self) -> int: ...
    def locked_customers(self) -> frozenset[int]: ...
    def is_locked(self, customer_id: int) -> bool: ...
    def first_free_position(self, route_index: int) -> int: ...

# uav_routing/evaluator.py
class Evaluator:
    def route(self, route: Route, *, departure: float = 0.0) -> RouteEvaluation: ...
    def solution(
        self, solution: Solution, constraints: SearchConstraints | None = None
    ) -> SolutionEvaluation: ...
# vi phạm mới: "locked_prefix"

# uav_routing/repair.py
@dataclass(frozen=True)
class RepairContext:
    instance: Instance
    evaluator: Evaluator
    d_ref: float
    alpha: float
    beta: float
    constraints: SearchConstraints = SearchConstraints()

# uav_routing/destroy.py
class DestroyOperator(Protocol):
    def apply(self, solution, instance, evaluator, rng, q,
              constraints: SearchConstraints | None = None) -> DestroyResult: ...

# uav_routing/alns.py
def run_alns(
    instance: Instance,
    config: ALNSConfig,
    *,
    initial_solution: Solution | None = None,
    constraints: SearchConstraints | None = None,
    d_ref: float | None = None,
) -> SearchResult: ...
```

```python
# uav_routing/dynamic/models.py
@dataclass(frozen=True)
class CustomerArrival:
    time: float
    customer: Customer

@dataclass(frozen=True)
class RiskUpdate:
    time: float
    zone: RiskZone

@dataclass(frozen=True)
class DeadlineUpdate:
    time: float
    customer_id: int
    due_date: float

Event = CustomerArrival | RiskUpdate | DeadlineUpdate

@dataclass(frozen=True)
class Scenario:
    name: str
    instance_path: Path
    static_customers: int
    risk_limit: int
    seed: int
    horizon: float
    events: tuple[Event, ...]

@dataclass(frozen=True)
class LockState:
    time: float
    constraints: SearchConstraints
    frozen_priority: dict[int, float]

@dataclass(frozen=True)
class EpochRecord:
    index: int
    time: float
    revealed: tuple[Event, ...]
    locked_customers: int
    rejected: tuple[int, ...]
    solution: Solution
    evaluation: SolutionEvaluation
    iterations: int
    runtime_seconds: float

@dataclass(frozen=True)
class SimulationResult:
    scenario: str
    policy: str
    seed: int
    d_ref: float
    final_instance: Instance
    realized: Solution
    evaluation: SolutionEvaluation
    unserved: tuple[int, ...]
    unserved_priority: float
    epochs: tuple[EpochRecord, ...]
    total_iterations: int
    runtime_seconds: float
```

Public call contracts:

```python
load_scenario(path: Path) -> Scenario
save_scenario(scenario: Scenario, path: Path) -> None
generate_scenario(instance_path: Path, *, static_customers: int, dynamic_customers: int,
                  risk_limit: int, risk_events: int, deadline_events: int,
                  release_fraction: float, seed: int) -> Scenario
base_instance(scenario: Scenario) -> Instance
apply_events(instance: Instance, events: tuple[Event, ...],
             frozen_priority: dict[int, float]) -> Instance
locked_prefixes(solution: Solution, instance: Instance, evaluator: Evaluator,
                time: float) -> SearchConstraints
project(solution: Solution, instance: Instance, evaluator: Evaluator,
        constraints: SearchConstraints) -> tuple[Solution, tuple[int, ...]]
triage(partial: Solution, pool: tuple[int, ...], context: RepairContext
       ) -> tuple[Solution, tuple[int, ...]]
run_rolling_horizon(scenario: Scenario, alns: ALNSConfig,
                    config: RollingHorizonConfig) -> SimulationResult
```

Chính sách là callable có chữ ký chung để `horizon.py` không phân nhánh theo tên:

```python
class EpochSolver(Protocol):
    def __call__(self, instance: Instance, initial: Solution,
                 constraints: SearchConstraints, d_ref: float,
                 alns: ALNSConfig, iterations: int, rng_seed: int) -> SearchResult: ...
```

---

## Detailed task files

| Task | File thực thi |
|---:|---|
| 01 | [Dynamic package skeleton, event models and RollingHorizonConfig](tasks/0930/task_01.md) |
| 02 | [Add SearchConstraints to the Evaluator without changing static results](tasks/0930/task_02.md) |
| 03 | [Make destroy operators respect locked customers](tasks/0930/task_03.md) |
| 04 | [Make insertion and repair respect locked prefixes and free departure](tasks/0930/task_04.md) |
| 05 | [Add warm start, constraints and fixed d_ref to run_alns](tasks/0930/task_05.md) |
| 06 | [Define the scenario format, loader and deterministic generator](tasks/0930/task_06.md) |
| 07 | [Apply events to an Instance with frozen priorities](tasks/0930/task_07.md) |
| 08 | [Derive locked prefixes from the executed schedule](tasks/0930/task_08.md) |
| 09 | [Project the previous plan and triage the unassigned pool](tasks/0930/task_09.md) |
| 10 | [Implement the rolling-horizon controller and the four policies](tasks/0930/task_10.md) |
| 11 | [Add the simulate CLI and JSON output](tasks/0930/task_11.md) |
| 12 | [Add the dynamic benchmark runner, configs, scenarios and README](tasks/0930/task_12.md) |

## 4. Final Definition of Done

- [x] `cd phase1 && uv run pytest tests -q` passes from a clean checkout, including all Phase 1 tests unchanged.
- [x] Static snapshot test proves `run_alns` defaults reproduce Phase 1 routes and metrics.
- [x] `generate_solomon_dynamic.py` produces the nine-instance scenario set for $n_{\mathrm{dyn}} \in \{5, 12, 25\}$ deterministically.
- [ ] `simulate` runs each policy on each generated scenario with a fixed seed and returns a feasible realized solution.
- [x] Every locked prefix of epoch $j$ is a prefix of the same route in epoch $j+1$ for every recorded run.
- [x] Empty scenario with zero epoch iterations reproduces the epoch-0 static solution exactly.
- [x] Same scenario + config + seed reproduces `SimulationResult`.
- [x] Benchmark CSV contains realized metrics, unserved metrics, gap to clairvoyant and per-epoch runtime.
- [x] README documents the dynamic model, scenario format, policies, commands and reproduction steps.

## 5. Suggested review gates

- **Gate A after Task 05:** review that constraints are enforced only in `Evaluator`, destroy and repair, and that the static snapshot is unchanged.
- **Gate B after Task 09:** review locking, event application and projection invariants on hand-computed small cases.
- **Gate C after Task 10:** review reproducibility, budget accounting and policy semantics.
- **Gate D after Task 12:** run the nine-scenario smoke suite, inspect CSV schemas, then merge `origin/perf/route-local-repair-delta` before long experiments.
