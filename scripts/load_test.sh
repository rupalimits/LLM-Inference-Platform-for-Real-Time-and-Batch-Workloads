#!/usr/bin/env bash
# Run Locust load test and generate the latency report.
set -euo pipefail

HOST="${HOST:-http://localhost:8000}"
USERS="${USERS:-20}"
SPAWN_RATE="${SPAWN_RATE:-2}"
RUN_TIME="${RUN_TIME:-2m}"
CSV_PREFIX="results/locust"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/load-tests"
mkdir -p results

pip install -q -r requirements.txt

echo "==> Running Locust: $USERS users, spawn-rate $SPAWN_RATE, duration $RUN_TIME"
locust -f locustfile.py \
  --host "$HOST" \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "$RUN_TIME" \
  --csv "$CSV_PREFIX" \
  --headless \
  --only-summary

echo ""
echo "==> Generating latency report..."
python generate_report.py --csv-prefix "$CSV_PREFIX" --output results/report.md
echo "==> Report saved to load-tests/results/report.md"
