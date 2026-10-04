#!/bin/bash
P=/home/hainh/code/projects/Dynamic-risk-aware-multi-UAV-routing/phase1
UV=$HOME/.local/bin/uv
cd $P
for name in base trigger_event trigger_hybrid epoch_0.025 epoch_0.1 epoch_0.2 budget_100 budget_250 budget_1000; do
  echo "=== $(date '+%F %T') start $name ==="
  $UV run --directory $P python -m uav_routing.dynamic.experiment \
    --config $P/configs/dynamic/ablation/$name.json \
    --workers 16 \
    --output-dir $P/results/ablation/$name
  echo "=== $(date '+%F %T') done $name (exit $?) ==="
done
echo "=== ALL DONE $(date '+%F %T') ==="
