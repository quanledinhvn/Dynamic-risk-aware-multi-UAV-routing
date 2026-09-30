# Task 06: Define the scenario format, loader and deterministic generator

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 3.1, 3.2 và 11

**Milestone:** M2 — Dynamic model

**Depends on:** Task 01

**Unlocks:** Task 07

---

**Files:**
- Create: `phase1/src/uav_routing/dynamic/scenario.py`
- Create: `dataset/scripts/generate_solomon_dynamic.py`
- Create: `phase1/tests/dynamic/fixtures/tiny_scenario.json`
- Create: `phase1/tests/dynamic/test_scenario.py`

**Interfaces:**
- Consumes: `parse_instance`, `Scenario`, các `Event`.
- Produces: `load_scenario`, `save_scenario`, `generate_scenario`, `base_instance`, `ScenarioFormatError`.

- [x] **Step 1: Write behavioural tests**

```python
def test_load_tiny_scenario_parses_all_event_types(): ...
def test_events_must_be_sorted_and_within_horizon(): ...
def test_arrival_ready_time_not_before_release(): ...
def test_arrival_id_must_not_collide_with_static_customers(): ...
def test_deadline_update_must_tighten(): ...
def test_risk_update_requires_positive_radius(): ...
def test_save_then_load_round_trips(tmp_path): ...

def test_generate_is_deterministic_for_same_seed():
    left = generate_scenario(C101, static_customers=25, dynamic_customers=5, risk_limit=5,
                             risk_events=2, deadline_events=2, release_fraction=0.6, seed=7)
    right = generate_scenario(...same...)

    assert left == right

def test_generate_uses_next_solomon_rows_as_dynamic_customers():
    scenario = generate_scenario(C101, static_customers=25, dynamic_customers=5, ...)
    arrivals = [event for event in scenario.events if isinstance(event, CustomerArrival)]

    assert [event.customer.id for event in arrivals] == [26, 27, 28, 29, 30]
    assert all(event.customer.ready_time >= event.time for event in arrivals)

def test_generate_rejects_when_solomon_has_too_few_rows(): ...
def test_base_instance_matches_phase1_parser():
    assert base_instance(scenario) == parse_instance(C101, 25, 5)  # so sánh field-by-field
```

- [x] **Step 2: Scaffold `scenario.py` with signatures, verify RED**

Run: `cd phase1 && uv run pytest tests/dynamic/test_scenario.py -v`

- [x] **Step 3: Implement**

- JSON schema đúng mục 11; `instance_path` giải theo thư mục chứa file kịch bản.
- `load_scenario` kiểm tra mọi điều kiện trong mục 11 và báo `ScenarioFormatError` kèm chỉ số sự kiện.
- `generate_scenario`: đọc toàn bộ file Solomon qua `parse_instance(path, static + dynamic, risk_limit)`, tách $n_0$ dòng đầu làm tĩnh, $n_{\mathrm{dyn}}$ dòng kế làm động; $\tau_i = U(0, \rho\, l_i)$, $e_i \leftarrow \max(e_i, \tau_i)$; sự kiện risk và deadline theo mục 3.2; sắp theo `time` rồi loại sự kiện; `horizon = l_0`.
- Mọi ngẫu nhiên qua `np.random.default_rng(seed)`; làm tròn tọa độ và thời gian tới 1 chữ số thập phân để JSON ổn định.
- `dataset/scripts/generate_solomon_dynamic.py` là CLI mỏng gọi `generate_scenario` cho danh sách instance × $n_{\mathrm{dyn}}$ × seed và ghi vào `dataset/solomon_dynamic/`, tên file `<instance>-n<n0>-d<n_dyn>-s<seed>.json`.

- [x] **Step 4: Verify and generate the development set**

Run: `cd phase1 && uv run pytest tests/dynamic/test_scenario.py -v && uv run python ../dataset/scripts/generate_solomon_dynamic.py --instances c101 r101 rc101 --dynamic 5 --seeds 0 --output ../dataset/solomon_dynamic`

- [x] **Step 5: Commit**

```bash
git add phase1/src/uav_routing/dynamic/scenario.py dataset/scripts/generate_solomon_dynamic.py phase1/tests/dynamic
git commit -m "feat(dynamic): add scenario format, loader and deterministic generator"
```
