# NSGA-III Implementation Plan

## Milestone 1: Problem core

- [x] Package, models and strict parser.
- [x] Euclidean geometry and risk priority.
- [x] Central evaluator with hard feasibility.
- [ ] Add schedule JSON schema and richer risk exposure.

## Milestone 2: Evolution representation

- [x] Permutation encoding.
- [x] Feasible insertion decoder.
- [x] Deterministic fallback initialization.
- [x] Order crossover.
- [x] Swap mutation.

## Milestone 3: NSGA-III

- [x] Pareto dominance.
- [x] Fast non-dominated sorting.
- [x] Das-Dennis reference directions.
- [x] Objective normalization.
- [x] Reference association and niche selection.
- [x] Seeded population loop.

## Milestone 4: Reproducible experiments

- [x] Single-instance CLI and JSON output.
- [ ] Benchmark matrix over nine instances and multiple seeds.
- [ ] Hypervolume, spacing and IGD implementation.
- [ ] Statistical summary and plots.
- [ ] Dynamic rolling-horizon runner.

## Review gates

- Gate A: evaluator invariants and route feasibility.
- Gate B: chromosome-decoder preserves each customer exactly once.
- Gate C: reference direction association and environmental selection.
- Gate D: same seed reproduces Pareto objective values and routes.
