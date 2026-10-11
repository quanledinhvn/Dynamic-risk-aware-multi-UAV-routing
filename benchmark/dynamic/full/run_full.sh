#!/bin/bash
# Full benchmark agreed on 06/10: 10,000 iterations, 20 run seeds, 25 and 100 customers,
# policies warm_alns and contextual_warm_alns (+ clairvoyant reference).
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
PHASE1_DIR="$REPOSITORY_ROOT/phase1"

for name in n25_d5 n25_d12 n25_d25 n100_d5 n100_d12 n100_d25; do
  echo "=== $(date '+%F %T') start $name ==="

  uv run --directory "$PHASE1_DIR" python -m uav_routing.dynamic.experiment \
    --config "$SCRIPT_DIR/$name/benchmark_$name.json" \
    --workers 16 \
    --output-dir "$SCRIPT_DIR/$name"

  echo "=== $(date '+%F %T') done $name (exit $?) ==="
done

echo "=== ALL DONE $(date '+%F %T') ==="
