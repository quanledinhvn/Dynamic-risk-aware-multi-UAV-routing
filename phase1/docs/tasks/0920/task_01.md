# Task 01: Package skeleton, domain models and validated configuration

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M1 — Deterministic problem core

**Depends on:** Không có

**Unlocks:** Tasks 02 và 08

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/pyproject.toml`
- Create: `phase1/src/uav_routing/__init__.py`
- Create: `phase1/src/uav_routing/models.py`
- Create: `phase1/src/uav_routing/config.py`
- Create: `phase1/tests/test_config.py`

**Interfaces:**
- Consumes: không có.
- Produces: toàn bộ dataclass trong “Stable interface contracts”; `ALNSConfig.validate() -> None`; `ALNSConfig.from_dict(dict[str, object]) -> ALNSConfig`.

- [ ] **Step 1: Write behavioral configuration and immutability tests**

```python
def test_default_config_is_valid():
    ALNSConfig().validate()

@pytest.mark.parametrize("changes", [
    {"iterations": 0}, {"q_min": 0}, {"q_min": 6, "q_max": 5},
    {"alpha": -0.1, "beta": 1.1}, {"alpha": 0.4, "beta": 0.5},
    {"initial_temperature": 0.0}, {"cooling_rate": 1.01},
    {"minimum_weight": 0.0}, {"reaction_factor": 1.1},
    {"removal_determinism": 0.0},
    {"related_distance_weight": 0.0, "related_time_weight": 0.0,
     "related_demand_weight": 0.0, "related_risk_weight": 0.0},
])
def test_invalid_config_is_rejected(changes):
    config = replace(ALNSConfig(), **changes)
    with pytest.raises(ValueError):
        config.validate()

def test_solution_routes_are_immutable():
    solution = Solution(routes=((1, 2),))
    with pytest.raises(TypeError):
        solution.routes[0][0] = 9

def test_from_dict_constructs_and_validates():
    assert ALNSConfig.from_dict({"iterations": 50}).iterations == 50
    with pytest.raises(ValueError, match="iterations"):
        ALNSConfig.from_dict({"iterations": 0})
```

- [ ] **Step 2: Add an importable scaffold, then verify behavioral RED**

Create package metadata and the dataclasses from “Stable interface contracts”. In `config.py`, declare all public fields but deliberately leave validation behavior neutral:

```python
@dataclass(frozen=True)
class ALNSConfig:
    iterations: int = 10_000
    seed: int = 42
    alpha: float = 0.5
    beta: float = 0.5
    q_min: int = 2
    q_max: int = 5
    segment_length: int = 100
    reaction_factor: float = 0.2
    initial_temperature: float = 0.05
    cooling_rate: float = 0.9995
    minimum_temperature: float = 1e-6
    minimum_weight: float = 0.1
    removal_determinism: float = 6.0
    related_distance_weight: float = 1.0
    related_time_weight: float = 1.0
    related_demand_weight: float = 1.0
    related_risk_weight: float = 1.0
    reward_best: float = 20.0
    reward_improve: float = 10.0
    reward_accepted: float = 2.0

    def validate(self) -> None:
        return None

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> "ALNSConfig":
        return cls(**values)
```

Run: `cd phase1 && python -m pytest tests/test_config.py -v`

Expected: test collection succeeds; default config and immutable solution tests pass; invalid-config cases fail with `DID NOT RAISE ValueError` because validation behavior is not implemented yet.

- [ ] **Step 3: Implement declarative validation with one error branch**

Replace the two scaffold methods inside `ALNSConfig` with:

```python
    def validate(self) -> None:
        related = (
            self.related_distance_weight,
            self.related_time_weight,
            self.related_demand_weight,
            self.related_risk_weight,
        )
        rules = (
            (self.iterations > 0, "iterations must be positive"),
            (self.segment_length > 0, "segment_length must be positive"),
            (0 < self.q_min <= self.q_max, "require 0 < q_min <= q_max"),
            (self.alpha >= 0 and self.beta >= 0, "alpha and beta must be non-negative"),
            (math.isclose(self.alpha + self.beta, 1.0, abs_tol=1e-9), "alpha and beta must sum to 1"),
            (self.initial_temperature > 0 and self.minimum_temperature > 0, "temperatures must be positive"),
            (0 < self.cooling_rate <= 1, "cooling_rate must be in (0, 1]"),
            (0 <= self.reaction_factor <= 1, "reaction_factor must be in [0, 1]"),
            (self.minimum_weight > 0, "minimum_weight must be positive"),
            (self.removal_determinism > 0, "removal_determinism must be positive"),
            (all(weight >= 0 for weight in related) and sum(related) > 0,
             "relatedness weights must be non-negative and not all zero"),
            (min(self.reward_best, self.reward_improve, self.reward_accepted) >= 0,
             "operator rewards must be non-negative"),
        )
        errors = [message for valid, message in rules if not valid]
        if errors:
            raise ValueError("; ".join(errors))

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> "ALNSConfig":
        try:
            config = cls(**values)
        except TypeError as exc:
            raise ValueError(f"invalid configuration keys: {exc}") from exc
        config.validate()
        return config
```

Cách table-driven này được chọn vì không thêm dependency và gom các rule đơn trường lẫn rule liên trường vào cùng một cấu trúc. `pydantic` cũng giảm boilerplate, nhưng chưa cần thiết cho baseline chỉ có một config object; field metadata của `dataclasses` không phù hợp với các rule liên trường như `q_min <= q_max` và `alpha + beta = 1`.

Set `requires-python = ">=3.11"`, runtime dependency `numpy>=2.0`, optional test dependency `pytest>=8.0`, package directory `src`, and pytest `pythonpath = ["src"]` in `pyproject.toml`.

- [ ] **Step 4: Run the focused test and package import check**

Run: `cd phase1 && python -m pytest tests/test_config.py -v && python -c 'from uav_routing.config import ALNSConfig; ALNSConfig().validate()'`

Expected: all tests pass and the import command exits 0.

- [ ] **Step 5: Commit the foundation**

```bash
git add phase1/pyproject.toml phase1/src/uav_routing phase1/tests/test_config.py
git commit -m "feat(phase1): add domain models and ALNS configuration"
```
