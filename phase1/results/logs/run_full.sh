#!/bin/bash
# Full benchmark agreed on 06/10: 10,000 iterations, 20 run seeds, 25 and 100 customers,
# policies warm_alns and contextual_warm_alns (+ clairvoyant reference).
P=/home/hainh/code/projects/Dynamic-risk-aware-multi-UAV-routing/phase1
UV=$HOME/.local/bin/uv
cd $P
for name in n25_d5 n25_d12 n25_d25 n100_d5 n100_d12 n100_d25; do
  echo "=== $(date '+%F %T') start $name ==="
  $UV run --directory $P python -m uav_routing.dynamic.experiment \
    --config $P/configs/dynamic/full/$name.json \
    --workers 16 \
    --output-dir $P/results/full/$name
  echo "=== $(date '+%F %T') done $name (exit $?) ==="
done
echo "=== ALL DONE $(date '+%F %T') ==="
