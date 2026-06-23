# -*- coding: utf-8 -*-
"""
run_re_meta.py -- Aggregate and compare all ablation condition results.

Usage (after all conditions have been run):
  python bench/run_re_meta.py

Reads re_ablation__*.json files from bench/results/ and prints a
comparison table, then saves meta_re_*.json.
"""

from __future__ import annotations
import json, os, glob, sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from bench.bench_config import METRIC_WEIGHTS, RESULTS_DIR


CONDITION_ORDER = [
    "full",
    "no_regulation",
    "no_control",
    "no_memory",
    "bare_llm",
]

CONDITION_LABEL = {
    "full":          "Full SCL",
    "no_regulation": "SCL - Regulation",
    "no_control":    "SCL - Control",
    "no_memory":     "SCL - Memory",
    "bare_llm":      "Bare LLM",
}

METRIC_SHORT = {
    "premature_termination": "PTR(pass)",
    "branch_isolation":      "BI",
    "kgrr_compliance":       "KGRR",
    "tool_order":            "Order",
}


def load_results(results_dir: str) -> Dict[str, List[Dict]]:
    """Load result files grouped by condition."""
    pattern = os.path.join(results_dir, "re_ablation__*.json")
    files   = sorted(glob.glob(pattern))

    grouped: Dict[str, List[Dict]] = {}
    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        cond = data.get("condition", "unknown")
        grouped.setdefault(cond, []).append(data)

    return grouped


def aggregate(runs: List[Dict]) -> Dict[str, Any]:
    """Average metrics across multiple runs of the same condition."""
    metric_scores: Dict[str, List[float]] = {}
    case_scores:   Dict[str, List[float]] = {}

    for run in runs:
        for m, avg in run.get("metric_averages", {}).items():
            metric_scores.setdefault(m, []).append(avg)
        for cid, rate in run.get("case_pass_rates", {}).items():
            case_scores.setdefault(cid, []).append(rate)

    metric_avg = {m: sum(s)/len(s) for m, s in metric_scores.items()}
    case_avg   = {c: sum(s)/len(s) for c, s in case_scores.items()}

    total_w = sum(METRIC_WEIGHTS.get(m, 0.1) * v for m, v in metric_avg.items())
    w_sum   = sum(METRIC_WEIGHTS.get(m, 0.1) for m in metric_avg)
    overall = total_w / w_sum if w_sum else 0.0

    return {
        "metric_averages": metric_avg,
        "case_pass_rates": case_avg,
        "overall_score":   overall,
        "run_count":       len(runs),
    }


def print_comparison(comparison: Dict[str, Any]) -> None:
    metrics = list(METRIC_WEIGHTS.keys())
    col_w   = 10
    header  = f"  {'condition':<20}" + "".join(f"{METRIC_SHORT.get(m, m)[:col_w]:>{col_w}}" for m in metrics) + f"  {'overall':>8}"
    print(f"\n{'='*70}")
    print(f"  Regulation Engineering Ablation -- Condition Comparison")
    print(f"{'='*70}")
    print(header)
    print("  " + "-" * (len(header) - 2))

    for cond in CONDITION_ORDER:
        if cond not in comparison:
            continue
        agg   = comparison[cond]
        avgs  = agg["metric_averages"]
        label = CONDITION_LABEL.get(cond, cond)
        row   = f"  {label:<20}"
        for m in metrics:
            v = avgs.get(m)
            row += f"  {'N/A':>{col_w-2}}" if v is None else f"  {v*100:>{col_w-2}.0f}%"
        row += f"  {agg['overall_score']*100:>6.1f}pts"
        print(row)

    print()
    print("  * PTR(pass) = pass-rate for premature_termination (higher = fewer early stops)")
    print()


def main():
    grouped = load_results(RESULTS_DIR)
    if not grouped:
        print(f"[ERROR] No re_ablation__*.json files found in {RESULTS_DIR}/")
        print("  Run run_re_bench.py for each condition first.")
        return

    comparison: Dict[str, Any] = {}
    for cond, runs in grouped.items():
        comparison[cond] = aggregate(runs)

    print_comparison(comparison)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS_DIR, f"meta_re_ablation__{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp":  ts,
            "comparison": {
                cond: {
                    "label":           CONDITION_LABEL.get(cond, cond),
                    "metric_averages": agg["metric_averages"],
                    "case_pass_rates": agg["case_pass_rates"],
                    "overall_score":   agg["overall_score"],
                    "run_count":       agg["run_count"],
                }
                for cond, agg in comparison.items()
            }
        }, f, ensure_ascii=False, indent=2)
    print(f"  saved: {out}")


if __name__ == "__main__":
    main()
