# Benchmark Results

This folder stores generated NSGA-III CSV artifacts and is intentionally kept
separate from source code.

Each benchmark writes two files in the selected output directory:

- `nsga3_pareto_raw.csv`: one row per Pareto solution.
- `aggregate.csv`: per-instance and risk-level statistics across seeds. Each
  seed contributes its best value for each objective before the cross-seed
  mean, standard deviation, best, and worst values are calculated.

While a benchmark is running, each completed instance/seed/risk case is
atomically checkpointed as `.tmp/run-<id>/<index>.json` below the output
directory. Checkpoints remain available if the benchmark fails and are removed
only after both final CSV files are written successfully.

Run the configured benchmark from `phase1_NSGA`:

```bash
uv run uav-routing-nsga-benchmark \
  --config configs/benchmark.json \
  --workers 8
```

Override the generation count and seeds without changing the JSON file:

```bash
uv run uav-routing-nsga-benchmark \
  --config configs/benchmark.json \
  --generations 500 \
  --seeds 0 1 2 3 4 \
  --workers 8 \
  --output-dir results/benchmark-c100
```

`--iterations` is accepted as an alias for `--generations`. In the JSON file,
`iterations` is also accepted when `generations` is absent. For NSGA-III,
`generations` is the preferred term.

Run the full risk dataset on AWS through SkyPilot from the repository root:

```bash
scripts/sky_benchmark.sh run \
  --config phase1_NSGA/configs/benchmark_c100_r5_s20_g100.json \
  --workers 8 \
  --region ap-southeast-1 \
  --instance-type c7i.2xlarge \
  --cluster uav-nsga-c100
```

The wrapper selects `infra/skypilot/nsga_benchmark.yaml` automatically and
downloads artifacts into `phase1_NSGA/results/sky/<run-id>/`.
