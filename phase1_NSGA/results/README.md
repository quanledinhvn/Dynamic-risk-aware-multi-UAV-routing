# Benchmark Results

This folder stores generated NSGA-III CSV artifacts and is intentionally kept
separate from source code.

Run a quick nine-instance smoke benchmark from `phase1_NSGA`:

```powershell
$env:PYTHONPATH = "src"
python -c "import json; from pathlib import Path; from uav_routing_nsga.experiment import run_benchmark; c=json.loads(Path('configs/benchmark.json').read_text()); run_benchmark(Path('../dataset/solomon_risk'), tuple(c['instances']), (42,), Path('results/nsga3_smoke_raw.csv'), c['customer_limit'], c['risk_limit'], 4, 1, 2)"
```

Run the configured benchmark with three seeds and risk scenarios `0`, `1`, and `5`:

```powershell
$env:PYTHONPATH = "src"
python -c "import json; from pathlib import Path; from uav_routing_nsga.experiment import run_benchmark; c=json.loads(Path('configs/benchmark.json').read_text()); run_benchmark(Path('../dataset/solomon_risk'), tuple(c['instances']), tuple(c['seeds']), Path('results/nsga3_pareto_raw.csv'), c['customer_limit'], 5, c['population_size'], c['generations'], c['divisions'], tuple(c['risk_limits']))"
```