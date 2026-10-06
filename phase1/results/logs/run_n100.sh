#!/bin/bash
P=/home/hainh/code/projects/Dynamic-risk-aware-multi-UAV-routing/phase1
UV=$HOME/.local/bin/uv
cd $P
for d in 5 12 25; do
  echo "=== $(date '+%F %T') start n100 d$d ==="
  $UV run --directory $P python -m uav_routing.dynamic.experiment \
    --config $P/configs/dynamic/benchmark_n100_d$d.json \
    --workers 16 \
    --output-dir $P/results/dynamic_n100_d$d
  echo "=== $(date '+%F %T') done n100 d$d (exit $?) ==="
done
echo "=== ALL DONE $(date '+%F %T') ==="
