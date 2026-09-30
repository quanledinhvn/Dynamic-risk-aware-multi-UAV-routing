# Task 07: Apply events to an Instance with frozen priorities

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 3.3

**Milestone:** M2 — Dynamic model

**Depends on:** Task 06

**Unlocks:** Task 09

---

**Files:**
- Create: `phase1/src/uav_routing/dynamic/events.py`
- Create: `phase1/tests/dynamic/test_events.py`

**Interfaces:**
- Consumes: `Instance`, `Event`, `euclidean_distance_matrix`, `compute_risk_priorities`.
- Produces: `apply_events(instance, events, frozen_priority) -> Instance`, `EventApplicationError`.

- [ ] **Step 1: Write behavioural tests**

```python
def test_arrival_appends_customer_and_grows_matrix():
    updated = apply_events(instance, (CustomerArrival(10.0, new_customer),), {})

    assert updated.customers[-1] == new_customer
    assert updated.distance_matrix.shape == (len(instance.customers) + 2,) * 2
    assert updated.risk_priority.shape == (len(instance.customers) + 2,)

def test_arrival_with_existing_id_is_rejected(): ...

def test_risk_update_changes_only_free_customer_priorities():
    frozen = {1: instance.risk_priority[1]}
    updated = apply_events(instance, (RiskUpdate(5.0, RiskZone(9, x1, y1, 10)),), frozen)

    assert updated.risk_priority[1] == pytest.approx(frozen[1])
    assert updated.risk_priority[2] > instance.risk_priority[2]

def test_risk_update_with_existing_id_replaces_zone(): ...

def test_deadline_update_tightens_free_customer():
    updated = apply_events(instance, (DeadlineUpdate(5.0, 2, 40.0),), {})

    assert updated.customers[1].due_date == 40.0

def test_deadline_update_on_frozen_customer_is_rejected(): ...
def test_deadline_update_that_loosens_is_rejected(): ...
def test_unknown_customer_is_rejected(): ...
def test_no_events_returns_equal_instance(): ...
def test_input_instance_is_not_mutated(): ...
```

- [ ] **Step 2: Scaffold, verify RED**

Run: `cd phase1 && uv run pytest tests/dynamic/test_events.py -v`

- [ ] **Step 3: Implement**

- Duyệt sự kiện theo thứ tự; xây `customers`, `risk_zones` mới; gọi `euclidean_distance_matrix((depot, *customers))` và `compute_risk_priorities(customers, zones)`.
- Ghi đè priority của khách hàng có trong `frozen_priority` bằng giá trị đóng băng, theo chỉ số `enumerate(customers, start=1)`.
- Trả `dataclasses.replace(instance, ...)`; không thay `name`, `depot`, `max_vehicles`, `capacity`.
- `EventApplicationError` là `ValueError` con, thông báo kèm loại sự kiện và `id`.

- [ ] **Step 4: Verify**

Run: `cd phase1 && uv run pytest tests/dynamic -v && uv run pytest tests -q`

- [ ] **Step 5: Commit**

```bash
git add phase1/src/uav_routing/dynamic/events.py phase1/tests/dynamic/test_events.py
git commit -m "feat(dynamic): apply arrival, risk and deadline events with frozen priorities"
```
