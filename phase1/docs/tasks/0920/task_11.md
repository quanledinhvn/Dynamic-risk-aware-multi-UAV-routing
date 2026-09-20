# Task 11: Add single-instance CLI and complete JSON output

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M4 — Reproducible experiments

**Depends on:** Task 10

**Unlocks:** Bàn giao CLI

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/src/uav_routing/cli.py`
- Create: `phase1/configs/default.json`
- Create: `phase1/tests/test_cli.py`

**Interfaces:**
- Consumes: parser, config and `run_alns`.
- Produces: command `uv run python -m uav_routing.cli solve`; `result_to_dict(result: SearchResult, instance: Instance, config: ALNSConfig) -> dict[str, object]`.

- [ ] **Step 1: Write CLI success, schema and invalid-argument tests**

```python
def test_solve_writes_required_json_fields(tmp_path, c101_path):
    output = tmp_path / "result.json"
    completed = run_cli("solve", "--instance", str(c101_path), "--customers", "25", "--iterations", "5", "--seed", "42", "--output", str(output))
    assert completed.returncode == 0
    data = json.loads(output.read_text())
    assert {"instance", "customers", "seed", "iterations", "vehicles", "distance", "risk_delay", "objective", "runtime_seconds", "feasible", "operators", "routes"} <= data.keys()
    assert all({"customer_id", "arrival", "service_start", "departure"} <= stop.keys() for route in data["routes"] for stop in route["schedule"])

def test_cli_rejects_weights_that_do_not_sum_to_one(c101_path):
    completed = run_cli("solve", "--instance", str(c101_path), "--alpha", ".7", "--beta", ".7")
    assert completed.returncode == 2
    assert "sum to 1" in completed.stderr
```

- [ ] **Step 2: Add an executable CLI scaffold, then verify behavioral RED**

```python
def result_to_dict(result: SearchResult, instance: Instance, config: ALNSConfig) -> dict[str, object]:
    raise NotImplementedError("result serialization is not implemented")

def main(argv: Sequence[str] | None = None) -> int:
    raise NotImplementedError("CLI behavior is not implemented")

if __name__ == "__main__":
    raise SystemExit(main())
```

Run: `cd phase1 && uv run pytest tests/test_cli.py -v`

Expected: module imports and subprocess reaches `main`; schema and exit-code assertions fail because CLI behavior is not implemented.

- [ ] **Step 3: Implement argument mapping, console summary and atomic JSON write**

```python
parser = argparse.ArgumentParser(prog="uav-routing")
solve = parser.add_subparsers(dest="command", required=True).add_parser("solve")
solve.add_argument("--instance", type=Path, required=True)
solve.add_argument("--customers", type=int, default=25)
solve.add_argument("--iterations", type=int, default=10_000)
solve.add_argument("--seed", type=int, default=42)
solve.add_argument("--alpha", type=float, default=.5)
solve.add_argument("--beta", type=float, default=.5)
solve.add_argument("--output", type=Path)
```

Serialize plain Python scalars, not NumPy scalar objects. Write JSON to `output.with_suffix(output.suffix + ".tmp")`, then replace the target after success. Convert domain/config/parser errors with `parser.error(str(exc))` so invalid user input exits 2 with a concise message; unexpected exceptions retain a traceback.

- [ ] **Step 4: Run CLI tests and the requested smoke command**

Run: `cd phase1 && uv run pytest tests/test_cli.py -v && uv run python -m uav_routing.cli solve --instance ../dataset/solomon_risk/c101.txt --customers 25 --iterations 10 --seed 42 --alpha 0.5 --beta 0.5 --output results/c101-seed42-smoke.json`

Expected: tests pass; command exits 0; JSON says `feasible: true` and includes 25 scheduled customer stops.

- [ ] **Step 5: Commit CLI and defaults**

```bash
git add phase1/src/uav_routing/cli.py phase1/configs/default.json phase1/tests/test_cli.py
git commit -m "feat(phase1): add single-instance solver CLI"
```
