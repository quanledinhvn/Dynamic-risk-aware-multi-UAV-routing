# Task 02: Parse Solomon-RISK instances and derive geometry

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M1 — Deterministic problem core

**Depends on:** Task 01

**Unlocks:** Task 03

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/src/uav_routing/parser.py`
- Create: `phase1/src/uav_routing/geometry.py`
- Create: `phase1/tests/test_parser.py`
- Create: `phase1/tests/test_geometry.py`
- Create: `phase1/tests/fixtures/tiny_valid.txt`

**Interfaces:**
- Consumes: `Customer`, `RiskZone`, `Instance` from Task 1.
- Produces: `parse_instance(path: Path, customer_limit: int) -> Instance`, `euclidean_distance_matrix(nodes: tuple[Customer, ...]) -> np.ndarray`, `compute_risk_priorities(customers: tuple[Customer, ...], zones: tuple[RiskZone, ...]) -> np.ndarray`.

- [ ] **Step 1: Write parser and geometry tests from explicit fixtures**

```python
def test_parse_limits_customers_and_builds_derived_arrays(tmp_path):
    path = write_tiny_solomon_file(tmp_path, customer_rows=3, zones=[(1, 3, 4, 5)])
    instance = parse_instance(path, customer_limit=2)
    assert instance.name == "TINY"
    assert instance.max_vehicles == 2
    assert instance.capacity == 10
    assert [c.id for c in instance.customers] == [1, 2]
    assert instance.distance_matrix.shape == (3, 3)
    assert instance.risk_priority.shape == (3,)

def test_risk_priority_at_center_inside_boundary_and_outside():
    customers = make_customers([(0, 0), (3, 0), (5, 0), (6, 0)])
    zones = (RiskZone(1, 0, 0, 5),)
    assert compute_risk_priorities(customers, zones) == pytest.approx([1.0, 0.4, 0.0, 0.0])

def test_overlapping_zones_use_maximum_influence():
    customer = make_customers([(2, 0)])
    zones = (RiskZone(1, 0, 0, 4), RiskZone(2, 3, 0, 2))
    assert compute_risk_priorities(customer, zones)[0] == pytest.approx(0.5)

@pytest.mark.parametrize("content, message", [
    ("BROKEN", "VEHICLE"),
    (valid_text_without_depot(), "depot"),
    (valid_text_with_zone_radius(0), "radius"),
])
def test_malformed_input_reports_path_and_reason(tmp_path, content, message):
    path = tmp_path / "bad.txt"
    path.write_text(content)
    with pytest.raises(InstanceFormatError, match=message):
        parse_instance(path, customer_limit=2)
```

- [ ] **Step 2: Add importable parser/geometry stubs, then verify behavioral RED**

```python
class InstanceFormatError(ValueError):
    pass

def parse_instance(path: Path, customer_limit: int) -> Instance:
    raise NotImplementedError("Solomon-RISK parsing is not implemented")

def euclidean_distance_matrix(nodes: tuple[Customer, ...]) -> np.ndarray:
    raise NotImplementedError("distance matrix is not implemented")

def compute_risk_priorities(customers, zones) -> np.ndarray:
    raise NotImplementedError("risk priority is not implemented")
```

Run: `cd phase1 && python -m pytest tests/test_parser.py tests/test_geometry.py -v`

Expected: both modules import and tests collect; calls fail at the stubs with `NotImplementedError`, not during import or collection.

- [ ] **Step 3: Implement strict section parsing and vectorized formulas**

```python
def euclidean_distance_matrix(nodes: tuple[Customer, ...]) -> np.ndarray:
    xy = np.asarray([(node.x, node.y) for node in nodes], dtype=float)
    delta = xy[:, None, :] - xy[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))

def compute_risk_priorities(customers, zones):
    priorities = np.zeros(len(customers) + 1, dtype=float)
    for index, customer in enumerate(customers, start=1):
        influences = [max(0.0, 1.0 - math.hypot(customer.x - zone.x, customer.y - zone.y) / zone.radius) for zone in zones]
        priorities[index] = max(influences, default=0.0)
    return priorities
```

Parser requirements: locate `VEHICLE`, `CUSTOMER`, and `RISK` sections by exact stripped heading; parse vehicle row as two numbers; parse customer rows as seven numbers until `RISK`; require depot id 0; retain the first `customer_limit` non-depot rows in file order; reject non-positive limit, insufficient customers, non-positive vehicle/capacity/radius, duplicate customer ids, and malformed row widths. Build matrix in index order `(depot, *customers)` and priority array aligned to that same index order.

- [ ] **Step 4: Verify fixtures and all nine target files**

Run: `cd phase1 && python -m pytest tests/test_parser.py tests/test_geometry.py -v && python -c 'from pathlib import Path; from uav_routing.parser import parse_instance; [parse_instance(p, 25) for p in sorted(Path("../dataset/solomon_risk").glob("[crCR]*10[1-3].txt")) if p.stem.lower() in {"c101","c102","c103","r101","r102","r103","rc101","rc102","rc103"}]'`

Expected: tests pass; exactly nine target files parse without exception.

- [ ] **Step 5: Commit input and geometry**

```bash
git add phase1/src/uav_routing/parser.py phase1/src/uav_routing/geometry.py phase1/tests/test_parser.py phase1/tests/test_geometry.py phase1/tests/fixtures/tiny_valid.txt
git commit -m "feat(phase1): parse Solomon risk instances"
```
