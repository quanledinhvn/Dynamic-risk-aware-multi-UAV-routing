# Phase 1 — Static Risk-Aware Multi-UAV Routing

This package implements a reproducible Adaptive Large Neighborhood Search (ALNS) baseline for the static phase of the Dynamic Risk-Aware Multi-UAV Routing project. It uses Solomon VRPTW instances extended with circular risk zones and does not depend on an external optimization solver.

## Scope

- Homogeneous UAVs start at and return to one depot.
- Capacity, customer time windows, the depot return deadline, the fleet limit, and exactly-once service are hard constraints.
- Euclidean distance is also travel time because speed is fixed to 1.
- The default study uses the first 25 customers of `C101`, `C102`, `C103`, `R101`, `R102`, `R103`, `RC101`, `RC102`, and `RC103`.
- Battery, wind, no-fly zones, uncertainty, and online changes are reserved for later phases.

## Installation

Python 3.11 or newer and [uv](https://docs.astral.sh/uv/) are required.

```bash
cd phase1
uv sync
```

Runtime code depends only on NumPy. Tests use pytest.

## Input format

An input file contains the exact section headings `VEHICLE`, `CUSTOMER`, and `RISK`, in that order. The vehicle data row has `NUMBER CAPACITY`; every depot/customer row has seven numeric fields (`id`, coordinates, demand, ready time, due date, service time); every risk row has four numeric fields (`id`, center coordinates, radius). Depot id must be `0`, ids must be unique, capacities and radii must be positive, and the file must contain at least the requested number of non-depot customers.

## Model and objective

For customer $i$ and risk zone $z$, priority is derived from radial influence:

$$
p_i=\max_{z}\max\left(0,1-\frac{d_{iz}}{r_z}\right).
$$

If service starts at $s_i$ in time window $[e_i,l_i]$, normalized delay is:

$$
q_i=\frac{s_i-e_i}{\max(1,l_i-e_i)}.
$$

The priority-weighted risk delay is:

$$
R(S)=\frac{\sum_i p_iq_i}{\sum_i p_i},
$$

with $R(S)=0$ when all priorities are zero. The deterministic greedy initial solution $S_0$ defines the fixed reference distance:

$$
D_{\mathrm{ref}}=D(S_0).
$$

The secondary objective is:

$$
F(S)=\alpha\frac{D(S)}{D_{\mathrm{ref}}}+\beta R(S),
\qquad \alpha+\beta=1.
$$

Solutions are compared lexicographically by:

$$
\operatorname{Score}(S)=(K(S),F(S)),
$$

so reducing the number of UAVs always takes priority over improving distance-risk cost.

## Solve one instance

```bash
uv run python -m uav_routing.cli solve \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --iterations 10000 \
  --seed 42 \
  --alpha 0.5 \
  --beta 0.5 \
  --output results/c101-seed42.json
```

The command prints the result as JSON and optionally writes it atomically. The JSON contains instance metadata, seed, iterations, vehicle count, distance, risk delay, objective, runtime, feasibility, final operator weights/use counts, routes, and each stop's arrival, service-start, and departure times.

## Run the benchmark

The committed development configuration uses ten seeds (`0` through `9`), 25 customers, and 10,000 iterations for all nine target instances:

```bash
uv run python -m uav_routing.experiment \
  --config configs/benchmark.json \
  --output-dir results/benchmark
```

For a fast smoke run without changing the committed defaults:

```bash
uv run python -m uav_routing.experiment \
  --config configs/benchmark.json \
  --iterations 2 \
  --seeds 0 \
  --output-dir results/smoke
```

`raw.csv` has one row per instance/seed with columns `instance`, `customers`, `seed`, `iterations`, `vehicles`, `distance`, `risk_delay`, `objective`, `runtime_seconds`, and `feasible`. `aggregate.csv` groups by instance, customer count, iterations, alpha, and beta; it reports run count plus mean, sample standard deviation, numeric best, and numeric worst for solution metrics, and mean/sample standard deviation for runtime. With one run, standard deviation is `0`.

Results are checkpointed atomically after every completed run. Any infeasible run aborts the benchmark instead of silently entering the aggregate.

## Reproducibility

Every search decision uses one `numpy.random.Generator` created from the run seed. With the same input file, customer limit, configuration, and seed, routes, objective components, and operator statistics are identical. Runtime is measured but is not expected to be identical.

## Tests

```bash
uv run pytest tests -q
```

The suite covers parsing, geometry, hard constraints, objective calculation, deterministic initialization, destroy/repair invariants, adaptive weights, acceptance, reproducibility, CLI output, and benchmark aggregation.
