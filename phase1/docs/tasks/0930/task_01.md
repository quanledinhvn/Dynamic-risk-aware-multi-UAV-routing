# Task 01: Dynamic package skeleton, event models and RollingHorizonConfig

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md)

**Milestone:** M1 — Constraint-aware core

**Depends on:** Không có

**Unlocks:** Tasks 02 và 06

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Modify: `phase1/src/uav_routing/models.py` (thêm `SearchConstraints`)
- Create: `phase1/src/uav_routing/dynamic/__init__.py`
- Create: `phase1/src/uav_routing/dynamic/models.py`
- Create: `phase1/src/uav_routing/dynamic/config.py`
- Create: `phase1/tests/dynamic/__init__.py`
- Create: `phase1/tests/dynamic/test_models.py`
- Create: `phase1/tests/dynamic/test_config.py`

**Interfaces:**
- Consumes: `Customer`, `RiskZone`, `Route`, `Solution` từ `uav_routing.models`.
- Produces: `SearchConstraints`; `CustomerArrival`, `RiskUpdate`, `DeadlineUpdate`, `Event`, `Scenario`, `LockState`, `EpochRecord`, `SimulationResult`; `RollingHorizonConfig.validate()`, `RollingHorizonConfig.from_dict()`.

- [x] **Step 1: Write behavioral tests for constraints helpers and config validation**

```python
def test_constraints_default_is_unconstrained():
    constraints = SearchConstraints()

    assert constraints.locked_route_count == 0
    assert constraints.locked_customers() == frozenset()
    assert constraints.first_free_position(3) == 0

def test_constraints_expose_locked_customers_and_positions():
    constraints = SearchConstraints(locked_prefixes=((1, 2), (5,)), free_departure=30.0)

    assert constraints.locked_route_count == 2
    assert constraints.locked_customers() == frozenset({1, 2, 5})
    assert constraints.is_locked(2) and not constraints.is_locked(9)
    assert constraints.first_free_position(0) == 2
    assert constraints.first_free_position(1) == 1
    assert constraints.first_free_position(2) == 0

def test_constraints_reject_duplicate_locked_customers_and_negative_departure():
    with pytest.raises(ValueError):
        SearchConstraints(locked_prefixes=((1,), (1,)))
    with pytest.raises(ValueError):
        SearchConstraints(free_departure=-1.0)

def test_default_rolling_config_is_valid():
    RollingHorizonConfig().validate()

@pytest.mark.parametrize("changes", [
    {"policy": "unknown"}, {"trigger": "never"}, {"epoch_length": 0.0},
    {"iterations_epoch0": -1}, {"iterations_per_epoch": -1},
])
def test_invalid_rolling_config_is_rejected(changes):
    with pytest.raises(ValueError):
        replace(RollingHorizonConfig(), **changes).validate()

def test_iterations_per_epoch_zero_is_allowed():
    replace(RollingHorizonConfig(), iterations_per_epoch=0).validate()
```

`iterations_per_epoch = 0` phải hợp lệ vì `greedy_insert` và bất biến kịch bản rỗng (Task 10) dựa vào nó.

- [x] **Step 2: Create importable scaffolds, then verify behavioral RED**

Khai báo `SearchConstraints` trong `uav_routing/models.py` với hai field, các phương thức trả placeholder (`0`, `frozenset()`, `False`). Khai báo mọi dataclass sự kiện và kết quả trong `dynamic/models.py` đúng theo “Stable interface contracts”. Khai báo `RollingHorizonConfig` với các field mặc định trong mục 9 của design spec, `validate()` trả `None`, `from_dict()` gọi `cls(**values)`.

Run: `cd phase1 && uv run pytest tests/dynamic -v`

Expected: collection thành công; test giá trị mặc định pass; test hành vi khác thất bại tại assertion hoặc `DID NOT RAISE`.

- [x] **Step 3: Implement validation and helpers**

- `SearchConstraints.__post_init__` từ chối khách hàng khóa trùng giữa các tiền tố và `free_departure < 0`.
- `locked_customers()` trả `frozenset` gộp mọi tiền tố; `first_free_position(k)` trả `len(locked_prefixes[k])` khi `k < locked_route_count`, ngược lại `0`.
- `RollingHorizonConfig.validate()` theo bảng rule giống `ALNSConfig`: `policy ∈ {greedy_insert, cold_restart, warm_alns}`, `trigger ∈ {periodic, event, hybrid}`, `epoch_length > 0`, hai số vòng lặp không âm, `seed` là số nguyên.

- [x] **Step 4: Run focused tests and the full suite**

Run: `cd phase1 && uv run pytest tests/dynamic -v && uv run pytest tests -q`

Expected: mọi test pass; 211 test Pha 1 không đổi.

- [x] **Step 5: Commit**

```bash
git add phase1/src/uav_routing/models.py phase1/src/uav_routing/dynamic phase1/tests/dynamic
git commit -m "feat(dynamic): add search constraints, event models and rolling horizon config"
```
