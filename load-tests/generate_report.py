"""
Generate a p50/p95/p99 latency and throughput report from Locust CSV output.

Usage:
    python generate_report.py --csv-prefix results/locust [--output report.md]
"""
import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path


def parse_stats(csv_prefix: str) -> list[dict]:
    stats_file = f"{csv_prefix}_stats.csv"
    if not os.path.exists(stats_file):
        sys.exit(f"ERROR: {stats_file} not found. Run locust with --csv={csv_prefix}")

    rows = []
    with open(stats_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def parse_history(csv_prefix: str) -> list[dict]:
    history_file = f"{csv_prefix}_stats_history.csv"
    if not os.path.exists(history_file):
        return []
    rows = []
    with open(history_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def float_or_zero(val: str) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def build_report(csv_prefix: str) -> str:
    stats = parse_stats(csv_prefix)
    history = parse_history(csv_prefix)

    lines = [
        "# LLM Inference Platform — Load Test Report",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
        "## Summary by Endpoint",
        "",
        "| Endpoint | Requests | Failures | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg (ms) | Min (ms) | Max (ms) |",
        "|----------|----------|----------|-----|----------|----------|----------|----------|----------|----------|",
    ]

    total_requests = 0
    total_failures = 0
    total_rps = 0.0

    for row in stats:
        name = row.get("Name", "")
        if name == "Aggregated":
            continue
        req = int(float_or_zero(row.get("Request Count", 0)))
        fail = int(float_or_zero(row.get("Failure Count", 0)))
        rps = float_or_zero(row.get("Requests/s", 0))
        p50 = float_or_zero(row.get("50%", 0))
        p95 = float_or_zero(row.get("95%", 0))
        p99 = float_or_zero(row.get("99%", 0))
        avg = float_or_zero(row.get("Average Response Time", 0))
        mn = float_or_zero(row.get("Min Response Time", 0))
        mx = float_or_zero(row.get("Max Response Time", 0))
        total_requests += req
        total_failures += fail
        total_rps += rps
        lines.append(
            f"| {name} | {req} | {fail} | {rps:.2f} | "
            f"{p50:.0f} | {p95:.0f} | {p99:.0f} | "
            f"{avg:.0f} | {mn:.0f} | {mx:.0f} |"
        )

    # Aggregated row
    for row in stats:
        if row.get("Name") == "Aggregated":
            p50 = float_or_zero(row.get("50%", 0))
            p95 = float_or_zero(row.get("95%", 0))
            p99 = float_or_zero(row.get("99%", 0))
            avg = float_or_zero(row.get("Average Response Time", 0))
            mn = float_or_zero(row.get("Min Response Time", 0))
            mx = float_or_zero(row.get("Max Response Time", 0))
            rps = float_or_zero(row.get("Requests/s", 0))
            lines.append(
                f"| **TOTAL** | **{total_requests}** | **{total_failures}** | **{rps:.2f}** | "
                f"**{p50:.0f}** | **{p95:.0f}** | **{p99:.0f}** | "
                f"**{avg:.0f}** | **{mn:.0f}** | **{mx:.0f}** |"
            )

    error_rate = (total_failures / total_requests * 100) if total_requests else 0
    lines += [
        "",
        "---",
        "",
        "## Key Metrics",
        "",
        f"- **Total Requests:** {total_requests:,}",
        f"- **Total Failures:** {total_failures:,}",
        f"- **Error Rate:** {error_rate:.2f}%",
        f"- **Peak RPS:** {total_rps:.2f}",
        "",
    ]

    # Throughput over time (from history)
    if history:
        peak_users = max(int(float_or_zero(r.get("User count", 0))) for r in history)
        peak_rps_hist = max(float_or_zero(r.get("Requests/s", 0)) for r in history)
        lines += [
            "## Throughput Over Time",
            "",
            f"- **Peak Concurrent Users:** {peak_users}",
            f"- **Peak Requests/s:** {peak_rps_hist:.2f}",
            "",
        ]

    lines += [
        "---",
        "",
        "## Pass / Fail Criteria",
        "",
        f"| Criterion | Target | Actual | Status |",
        f"|-----------|--------|--------|--------|",
    ]

    # Retrieve aggregated p50/p95 again for criteria check
    agg_p50 = agg_p95 = 0.0
    for row in stats:
        if row.get("Name") == "Aggregated":
            agg_p50 = float_or_zero(row.get("50%", 0))
            agg_p95 = float_or_zero(row.get("95%", 0))

    def status(passed: bool) -> str:
        return "PASS" if passed else "FAIL"

    lines += [
        f"| p50 latency | < 2000 ms | {agg_p50:.0f} ms | {status(agg_p50 < 2000)} |",
        f"| p95 latency | < 5000 ms | {agg_p95:.0f} ms | {status(agg_p95 < 5000)} |",
        f"| Error rate  | < 5%      | {error_rate:.2f}%  | {status(error_rate < 5)} |",
        "",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate load test report from Locust CSV")
    parser.add_argument("--csv-prefix", required=True, help="Prefix used with --csv in locust")
    parser.add_argument("--output", default="report.md", help="Output markdown file")
    args = parser.parse_args()

    Path(os.path.dirname(args.output) or ".").mkdir(parents=True, exist_ok=True)
    report = build_report(args.csv_prefix)
    with open(args.output, "w") as f:
        f.write(report)

    print(report)
    print(f"\nReport written to: {args.output}")


if __name__ == "__main__":
    main()
