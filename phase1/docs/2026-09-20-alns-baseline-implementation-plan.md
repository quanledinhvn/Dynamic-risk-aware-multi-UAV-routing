# ALNS Baseline Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng baseline ALNS xác định, tái lập được cho static risk-aware multi-UAV routing trên chín instance Solomon có vùng risk, kèm kiểm thử, CLI, benchmark và tài liệu tái lập.

**Architecture:** Luồng dữ liệu một chiều đi từ parser và geometry vào một `Instance` bất biến; `Evaluator` là nguồn duy nhất tính lịch, tính khả thi và score. Các destroy/repair operator chỉ biến đổi `Solution`, còn `run_alns` điều phối selection, acceptance, reward và cooling qua một NumPy `Generator` duy nhất.

**Tech Stack:** Python 3.11+, NumPy, pytest, thư viện chuẩn `dataclasses`, `argparse`, `json`, `csv`, `statistics`, `time`.

**Spec:** `phase1/docs/2026-09-19-alns-baseline-design.md`

**Task files:** [`phase1/docs/tasks/0920/`](tasks/0920/README.md)

## Global Constraints

- Toàn bộ mã nguồn, kiểm thử, cấu hình, tài liệu và kết quả của baseline nằm trong `phase1/`.
- Không dùng OR-Tools, Gurobi hoặc solver tối ưu bên ngoài.
- Phạm vi mặc định là depot và 25 khách hàng đầu; số khách hàng phải cấu hình được.
- Capacity, time window, depot due date, giới hạn UAV và phục vụ đúng một lần là ràng buộc cứng.
- Chỉ candidate hoàn chỉnh và khả thi mới được đưa vào acceptance.
- Mọi lựa chọn ngẫu nhiên phải đi qua đúng một `numpy.random.Generator` được tạo từ seed của lần chạy.
- `Evaluator` là nguồn duy nhất tính lịch, feasibility, distance, risk delay, objective và lexicographic score.
- Mặc định dùng $\alpha=0.5$, $\beta=0.5$, $q\in[2,5]$, và dừng theo số vòng lặp cố định.
- Mỗi lần chạy phải báo cáo riêng số UAV, distance, risk delay, objective, runtime, feasibility, operator statistics, routes và service schedule.
- TDD phải dùng importable API scaffold trước lần chạy RED; RED hợp lệ thất bại tại hành vi hoặc API stub, không thất bại ở import, collection hay cú pháp. Quy trình chi tiết nằm trong [`tasks/0920/README.md`](tasks/0920/README.md).

## Review Focus

- File Solomon có header hoặc số cột sai phải tạo lỗi parser có tên file và dòng gây lỗi; Task 2 khóa hành vi này bằng test malformed input.
- Một route hợp lệ tại mọi khách hàng nhưng về depot trễ vẫn phải infeasible; Task 3 có test riêng cho depot deadline.
- Khi mọi priority bằng 0, risk delay phải bằng đúng 0 và objective vẫn hữu hạn; Task 3 có test zero-priority.
- Repair không chèn hết khách hàng phải trả thất bại, không làm thay đổi nghiệm hiện tại; Task 7 và Task 10 kiểm tra tính nguyên tử này.
- Cùng instance, cấu hình và seed phải sinh cùng route và metric, không yêu cầu runtime giống nhau; Task 10 có integration test tái lập.

---

## 1. Phân rã từ abstract đến concrete

### Outcome Pha 1

Một lệnh có thể giải một instance và một lệnh có thể chạy benchmark chín instance; mọi nghiệm cuối được kiểm tra độc lập và mọi bảng kết quả có thể tái tạo từ config cùng seed.

### Milestones

| Milestone | Câu hỏi nghiệm thu | Tasks | Deliverable |
|---|---|---:|---|
| M1 — Deterministic problem core | Dữ liệu, risk và objective có đúng, xác định và kiểm thử độc lập không? | 1–4 | Package cài được, parser/geometry/evaluator/initial solution vượt unit test |
| M2 — Search neighborhoods | Destroy và repair có bảo toàn tập khách hàng, feasibility và lexicographic insertion không? | 5–7 | 5 destroy + 3 repair operator có contract thống nhất |
| M3 — Adaptive search | Solver có chọn operator, chấp nhận candidate, thưởng và cooling đúng đặc tả không? | 8–10 | ALNS tái lập, trả nghiệm best hoàn chỉnh và khả thi |
| M4 — Reproducible experiments | Người khác có chạy, kiểm tra và tổng hợp đủ chín instance không? | 11–12 | CLI, JSON, CSV thô/tổng hợp, README và smoke suite |

### Dependency graph

```text
Task 1: package + models + config
  ├── Task 2: parser + geometry
  │     └── Task 3: evaluator
  │           ├── Task 4: initial solution
  │           ├── Task 5: destroy operators
  │           └── Task 6: insertion engine
  │                 └── Task 7: repair operators
  └── Task 8: adaptive weights

Tasks 4 + 5 + 7 + 8
  └── Task 9: acceptance + ALNS loop
        └── Task 10: reproducibility integration
              ├── Task 11: CLI + JSON output
              └── Task 12: benchmark + documentation
```

## 2. File map and ownership

| File | Trách nhiệm duy nhất |
|---|---|
| `phase1/pyproject.toml` | Packaging, dependency và pytest configuration |
| `phase1/src/uav_routing/models.py` | Domain dataclasses và immutable result records |
| `phase1/src/uav_routing/config.py` | Solver configuration và validation |
| `phase1/src/uav_routing/parser.py` | Solomon + `RISK` text thành dữ liệu thô có kiểm tra |
| `phase1/src/uav_routing/geometry.py` | Distance matrix và risk priority |
| `phase1/src/uav_routing/evaluator.py` | Schedule, feasibility, $D$, $R$, $F$, score |
| `phase1/src/uav_routing/initial.py` | Deterministic greedy construction và $D_{ref}$ |
| `phase1/src/uav_routing/destroy.py` | Năm destroy operators |
| `phase1/src/uav_routing/repair.py` | Insertion engine và ba repair operators |
| `phase1/src/uav_routing/adaptive.py` | Roulette selection và segmented weight updates |
| `phase1/src/uav_routing/alns.py` | Acceptance, cooling và orchestration loop |
| `phase1/src/uav_routing/cli.py` | Một lần solve, validation CLI, JSON/console rendering |
| `phase1/src/uav_routing/experiment.py` | Matrix instance × seed, raw CSV và aggregate CSV |
| `phase1/configs/default.json` | Cấu hình baseline mặc định |
| `phase1/configs/benchmark.json` | Chín instance và danh sách seed phát triển |
| `phase1/tests/` | Unit, integration và CLI smoke tests |
| `phase1/README.md` | Mô hình, cách chạy và tái lập |

## 3. Stable interface contracts

Các task phải giữ nguyên tên và kiểu sau để có thể triển khai độc lập:

```python
CustomerId = int
Route = tuple[CustomerId, ...]

@dataclass(frozen=True)
class Customer:
    id: int
    x: float
    y: float
    demand: float
    ready_time: float
    due_date: float
    service_time: float

@dataclass(frozen=True)
class RiskZone:
    id: int
    x: float
    y: float
    radius: float

@dataclass(frozen=True)
class Instance:
    name: str
    depot: Customer
    customers: tuple[Customer, ...]
    risk_zones: tuple[RiskZone, ...]
    max_vehicles: int
    capacity: float
    distance_matrix: np.ndarray
    risk_priority: np.ndarray

@dataclass(frozen=True)
class Solution:
    routes: tuple[Route, ...]

@dataclass(frozen=True)
class StopSchedule:
    customer_id: int
    arrival: float
    service_start: float
    departure: float

@dataclass(frozen=True)
class RouteEvaluation:
    feasible: bool
    distance: float
    load: float
    depot_return: float
    schedule: tuple[StopSchedule, ...]
    violations: tuple[str, ...]

@dataclass(frozen=True)
class SolutionEvaluation:
    feasible: bool
    vehicle_count: int
    distance: float
    risk_delay: float
    objective: float
    score: tuple[int, float]
    routes: tuple[RouteEvaluation, ...]
    violations: tuple[str, ...]
```

Public call contracts:

```python
parse_instance(path: Path, customer_limit: int) -> Instance
evaluate_route(instance: Instance, route: Route) -> RouteEvaluation
evaluate_solution(instance: Instance, solution: Solution, d_ref: float, alpha: float, beta: float) -> SolutionEvaluation
build_initial_solution(instance: Instance, alpha: float, beta: float) -> tuple[Solution, float]
destroy(solution: Solution, instance: Instance, evaluator: Evaluator, rng: np.random.Generator, q: int) -> DestroyResult
repair(partial: Solution, removed: tuple[int, ...], context: RepairContext) -> RepairResult
run_alns(instance: Instance, config: ALNSConfig) -> SearchResult
```

Operator protocols dùng xuyên suốt Tasks 5–9:

```python
class DestroyOperator(Protocol):
    name: str
    def apply(
        self,
        solution: Solution,
        instance: Instance,
        evaluator: Evaluator,
        rng: np.random.Generator,
        q: int,
    ) -> DestroyResult:
        raise NotImplementedError

class RepairOperator(Protocol):
    name: str
    def apply(
        self,
        partial: Solution,
        removed: tuple[int, ...],
        context: RepairContext,
    ) -> RepairResult:
        raise NotImplementedError
```

---

## Detailed task files

Checklist triển khai được tách để mỗi task có thể thực hiện và review độc lập. Xem [mục lục task ngày 20/09](tasks/0920/README.md) để theo dõi dependency và review gates.

| Task | File thực thi |
|---:|---|
| 01 | [Package skeleton, domain models and validated configuration](tasks/0920/task_01.md) |
| 02 | [Parse Solomon-RISK instances and derive geometry](tasks/0920/task_02.md) |
| 03 | [Make Evaluator the single feasibility and objective oracle](tasks/0920/task_03.md) |
| 04 | [Build the deterministic greedy initial solution](tasks/0920/task_04.md) |
| 05 | [Implement five destroy operators with a common contract](tasks/0920/task_05.md) |
| 06 | [Build the lexicographic insertion engine](tasks/0920/task_06.md) |
| 07 | [Implement Greedy, Regret-2 and Risk-Priority repair](tasks/0920/task_07.md) |
| 08 | [Implement roulette selection and segmented adaptive weights](tasks/0920/task_08.md) |
| 09 | [Implement acceptance, cooling and the ALNS loop](tasks/0920/task_09.md) |
| 10 | [Lock reproducibility and end-to-end search invariants](tasks/0920/task_10.md) |
| 11 | [Add single-instance CLI and complete JSON output](tasks/0920/task_11.md) |
| 12 | [Add benchmark runner, aggregation, README and final verification](tasks/0920/task_12.md) |

## 4. Final Definition of Done

- [ ] `cd phase1 && python -m pytest tests -q` passes from a clean checkout.
- [ ] All nine target files parse with `customer_limit=25`.
- [ ] A fixed-seed run on each target instance returns a complete feasible solution.
- [ ] Same instance + config + seed reproduces routes, metrics and operator statistics.
- [ ] JSON contains routes and full service schedules; CSV contains all raw metrics and aggregate statistics.
- [ ] No production module except `evaluator.py` computes route schedule or reinterprets time-window feasibility.
- [ ] No randomness source other than the injected NumPy `Generator` participates in search decisions.
- [ ] README commands work exactly as written from `phase1/`.

## 5. Suggested review gates

- **Gate A after Task 3:** review mathematical correctness before any heuristic code depends on it.
- **Gate B after Task 7:** review neighborhood invariants and atomic repair failure.
- **Gate C after Task 10:** review stochastic reproducibility and reward/acceptance semantics.
- **Gate D after Task 12:** run the nine-instance smoke suite and inspect output schemas before launching long experiments.
