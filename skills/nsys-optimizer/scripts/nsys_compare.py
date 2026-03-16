#!/usr/bin/env python3
"""Extract metrics from repeated nsys profiles and compare two conditions statistically.

Metric specifications (--metric):
  Each metric is a string of the form "type:pattern" where type is one of:

  nvtx:<name>         Total time of NVTX range matching <name> (exact match on text field).
                      Example: "nvtx:step" extracts the "step" range.

  nvtx_avg:<name>     Average per-instance time of NVTX range matching <name>.
                      Example: "nvtx_avg:detect_contacts"

  kernel:<substring>  Total GPU time for kernels whose demangled name contains <substring>.
                      Example: "kernel:sim_vbd_solve_kernel"

  kernel_avg:<sub>    Average per-instance GPU time for matching kernels.
                      Example: "kernel_avg:detect_ee_contacts_kernel"

  cuda_api:<name>     Total time for a CUDA API call (substring match, handles version suffixes).
                      Example: "cuda_api:cudaMalloc"

  sql:<query>         Custom SQL query that returns a single numeric value (in ns).
                      The query runs against the .sqlite file.
                      Example: "sql:SELECT SUM(end-start) FROM NVTX_EVENTS WHERE text LIKE '%vbd_color%'"

  wall                Wall-clock time (total duration from first to last NVTX event).

Usage:
    # Compare two conditions with multiple metrics:
    python nsys_compare.py \
        --baseline /tmp/nsys_ab/baseline \
        --optimized /tmp/nsys_ab/optimized \
        --metric "nvtx:step" \
        --metric "kernel:sim_vbd_solve_kernel" \
        --metric "kernel:detect_ee_contacts_kernel"

    # Use custom SQL:
    python nsys_compare.py \
        --baseline /tmp/nsys_ab/baseline \
        --optimized /tmp/nsys_ab/optimized \
        --metric "sql:SELECT SUM(end-start) FROM CUPTI_ACTIVITY_KIND_KERNEL"
"""

import argparse
import glob
import os
import sqlite3
import sys
from dataclasses import dataclass, field

from scipy import stats as sp_stats


@dataclass
class MetricResult:
    name: str
    values_a: list = field(default_factory=list)
    values_b: list = field(default_factory=list)


def extract_metric(sqlite_path: str, metric_spec: str) -> float | None:
    """Extract a single metric value (in ms) from a .sqlite file."""
    if not os.path.exists(sqlite_path):
        return None

    conn = sqlite3.connect(sqlite_path)
    try:
        kind, _, pattern = metric_spec.partition(":")
        if kind == "nvtx":
            query = (
                "SELECT SUM(end - start) FROM NVTX_EVENTS "
                "WHERE text = ? AND end IS NOT NULL"
            )
            row = conn.execute(query, (pattern,)).fetchone()
        elif kind == "nvtx_avg":
            query = (
                "SELECT AVG(end - start) FROM NVTX_EVENTS "
                "WHERE text = ? AND end IS NOT NULL"
            )
            row = conn.execute(query, (pattern,)).fetchone()
        elif kind == "kernel":
            query = (
                "SELECT SUM(k.end - k.start) "
                "FROM CUPTI_ACTIVITY_KIND_KERNEL k "
                "JOIN StringIds s ON k.demangledName = s.id "
                "WHERE s.value LIKE ?"
            )
            row = conn.execute(query, (f"%{pattern}%",)).fetchone()
        elif kind == "kernel_avg":
            query = (
                "SELECT AVG(k.end - k.start) "
                "FROM CUPTI_ACTIVITY_KIND_KERNEL k "
                "JOIN StringIds s ON k.demangledName = s.id "
                "WHERE s.value LIKE ?"
            )
            row = conn.execute(query, (f"%{pattern}%",)).fetchone()
        elif kind == "cuda_api":
            query = (
                "SELECT SUM(end - start) FROM CUPTI_ACTIVITY_KIND_RUNTIME "
                "WHERE nameId IN (SELECT id FROM StringIds WHERE value LIKE ?)"
            )
            row = conn.execute(query, (f"{pattern}%",)).fetchone()
        elif kind == "sql":
            row = conn.execute(pattern).fetchone()
        elif kind == "wall":
            query = (
                "SELECT MAX(end) - MIN(start) FROM NVTX_EVENTS "
                "WHERE end IS NOT NULL"
            )
            row = conn.execute(query).fetchone()
        else:
            print(f"Unknown metric type: {kind}", file=sys.stderr)
            return None

        if row and row[0] is not None:
            return row[0] / 1e6  # ns -> ms
        return None
    finally:
        conn.close()


def find_sqlite_files(directory: str) -> list[str]:
    """Find all .sqlite files in a directory, sorted by name."""
    files = sorted(glob.glob(os.path.join(directory, "*.sqlite")))
    if not files:
        print(f"No .sqlite files found in {directory}", file=sys.stderr)
        print(
            "Run nsys_repeat_profile.py first, or export with: "
            "nsys export --type=sqlite <report>.nsys-rep",
            file=sys.stderr,
        )
        sys.exit(1)
    return files


def compute_stats(values: list[float]) -> dict:
    """Compute basic statistics."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": 0, "std": 0, "median": 0, "min": 0, "max": 0}

    mean = sum(values) / n
    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = variance**0.5
    else:
        std = 0.0

    sorted_v = sorted(values)
    if n % 2 == 1:
        median = sorted_v[n // 2]
    else:
        median = (sorted_v[n // 2 - 1] + sorted_v[n // 2]) / 2

    return {
        "n": n,
        "mean": mean,
        "std": std,
        "median": median,
        "min": min(values),
        "max": max(values),
    }


def welch_t_test(
    values_a: list[float], values_b: list[float]
) -> tuple[float, float, float]:
    """Welch's t-test. Returns (t_statistic, degrees_of_freedom, p_value)."""
    na, nb = len(values_a), len(values_b)
    if na < 2 or nb < 2:
        return (0.0, 0.0, 1.0)

    t_stat, p_value = sp_stats.ttest_ind(values_a, values_b, equal_var=False)
    # Welch-Satterthwaite degrees of freedom
    sa = compute_stats(values_a)
    sb = compute_stats(values_b)
    var_a, var_b = sa["std"] ** 2, sb["std"] ** 2
    num = (var_a / na + var_b / nb) ** 2
    denom = (var_a / na) ** 2 / (na - 1) + (var_b / nb) ** 2 / (nb - 1)
    df = num / denom if denom > 1e-30 else na + nb - 2

    return (t_stat, df, p_value)


def format_table(
    metric_name: str,
    stats_a: dict,
    stats_b: dict,
    t_stat: float,
    df: float,
    p_value: float,
    label_a: str,
    label_b: str,
) -> str:
    """Format comparison results as a readable table."""
    speedup = stats_a["mean"] / stats_b["mean"] if stats_b["mean"] > 0 else float("inf")
    change_pct = (stats_b["mean"] - stats_a["mean"]) / stats_a["mean"] * 100

    lines = []
    lines.append(f"\n{'=' * 70}")
    lines.append(f"  Metric: {metric_name}")
    lines.append(f"{'=' * 70}")
    lines.append(f"  {'':20s} {'Mean (ms)':>12s} {'Std (ms)':>12s} {'Median (ms)':>12s} {'Min (ms)':>12s} {'Max (ms)':>12s} {'N':>5s}")
    lines.append(f"  {'-' * 20} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 5}")

    for label, s in [(label_a, stats_a), (label_b, stats_b)]:
        lines.append(
            f"  {label:20s} {s['mean']:12.3f} {s['std']:12.3f} {s['median']:12.3f} "
            f"{s['min']:12.3f} {s['max']:12.3f} {s['n']:5d}"
        )

    lines.append(f"  {'-' * 20} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 5}")
    lines.append(f"  Change:   {change_pct:+.2f}%   (speedup: {speedup:.3f}x)")
    lines.append(f"  Welch's t-test:  t = {t_stat:.3f},  df = {df:.1f},  p = {p_value:.4f}")
    if p_value < 0.01:
        lines.append(f"  ** Statistically significant (p < 0.01)")
    elif p_value < 0.05:
        lines.append(f"  *  Statistically significant (p < 0.05)")
    else:
        lines.append(f"     Not statistically significant (p >= 0.05)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Compare nsys profiling results between two conditions."
    )
    parser.add_argument(
        "--baseline",
        required=True,
        help="Directory containing baseline .sqlite files.",
    )
    parser.add_argument(
        "--optimized",
        required=True,
        help="Directory containing optimized .sqlite files.",
    )
    parser.add_argument(
        "--metric",
        action="append",
        required=True,
        help="Metric specification (repeatable). See --help for format.",
    )
    parser.add_argument(
        "--baseline-label",
        default="baseline",
        help="Label for baseline condition (default: 'baseline').",
    )
    parser.add_argument(
        "--optimized-label",
        default="optimized",
        help="Label for optimized condition (default: 'optimized').",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional: write results to CSV file.",
    )
    args = parser.parse_args()

    files_a = find_sqlite_files(args.baseline)
    files_b = find_sqlite_files(args.optimized)
    print(f"Found {len(files_a)} runs for '{args.baseline_label}', "
          f"{len(files_b)} runs for '{args.optimized_label}'")

    csv_rows = []

    for metric_spec in args.metric:
        values_a = []
        values_b = []

        for f in files_a:
            v = extract_metric(f, metric_spec)
            if v is not None:
                values_a.append(v)

        for f in files_b:
            v = extract_metric(f, metric_spec)
            if v is not None:
                values_b.append(v)

        if not values_a:
            print(f"\nWARNING: No data extracted for metric '{metric_spec}' "
                  f"from {args.baseline_label}")
            continue
        if not values_b:
            print(f"\nWARNING: No data extracted for metric '{metric_spec}' "
                  f"from {args.optimized_label}")
            continue

        stats_a = compute_stats(values_a)
        stats_b = compute_stats(values_b)
        t_stat, df, p_value = welch_t_test(values_a, values_b)

        print(format_table(
            metric_spec, stats_a, stats_b, t_stat, df, p_value,
            args.baseline_label, args.optimized_label,
        ))

        if args.csv:
            speedup = stats_a["mean"] / stats_b["mean"] if stats_b["mean"] > 0 else 0
            csv_rows.append({
                "metric": metric_spec,
                "baseline_mean_ms": stats_a["mean"],
                "baseline_std_ms": stats_a["std"],
                "optimized_mean_ms": stats_b["mean"],
                "optimized_std_ms": stats_b["std"],
                "speedup": speedup,
                "change_pct": (stats_b["mean"] - stats_a["mean"]) / stats_a["mean"] * 100,
                "t_stat": t_stat,
                "df": df,
                "p_value": p_value,
            })

    if args.csv and csv_rows:
        import csv

        with open(args.csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"\nCSV results written to {args.csv}")


if __name__ == "__main__":
    main()
