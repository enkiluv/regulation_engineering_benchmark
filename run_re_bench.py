# -*- coding: utf-8 -*-
"""
run_re_bench.py -- Regulation Engineering ablation bench runner

Usage:
  # Step 1: start the server with the desired ablation condition:
  #   bench/run_ablation_full.cmd
  #   bench/run_ablation_no_regulation.cmd
  #   bench/run_ablation_no_control.cmd
  #   bench/run_ablation_no_memory.cmd
  #   bench/run_ablation_bare_llm.cmd
  #
  # Step 2: run this script in a second window:
  #   python bench/run_re_bench.py --condition full --model gpt-4o
  #   python bench/run_re_bench.py --condition no_regulation --model gpt-4o --reps 5
"""

import argparse, asyncio, json, os, re, sys, time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from bench.bench_config import (
    SCL_SERVER_HOST, LANGUAGE, MAX_CYCLES, METRIC_WEIGHTS, RESULTS_DIR,
)
from bench.re_evaluator import evaluate_case
from bench.cases.regulation_engineering import CASES

ABLATION_CONDITIONS = [
    "full",
    "no_regulation",
    "no_control",
    "no_regulation_control",
    "no_memory",
    "bare_llm",
    "bare_llm_no_pgr",
]


async def run_single(case: Dict[str, Any], verbose: bool) -> Dict[str, Any]:
    """Run a single test case via WebSocket and return raw results."""
    import websockets, requests as _req

    ws_url = SCL_SERVER_HOST.replace("http://", "ws://").rstrip("/") + "/chat-stream"
    session_url = SCL_SERVER_HOST.rstrip("/") + "/session-id"

    chunks: List[str] = []
    response_text = trace_summary = ""
    tool_calls: List[Dict] = []
    error = None

    try:
        sid = _req.get(session_url, timeout=10).json()["session_id"]

        async with websockets.connect(
            ws_url, ping_interval=None,
            close_timeout=10, max_size=16 * 1024 * 1024,
        ) as ws:
            await ws.send(json.dumps({
                "type": "chat",
                "session_id": sid,
                "user_input": case["query"],
                "language": LANGUAGE,
                "max_cycles": MAX_CYCLES,
                "auto_approval": True,
            }, ensure_ascii=False))

            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=120)
                if raw == "__END__":
                    break
                msg = json.loads(raw)
                etype = msg.get("type") or msg.get("status")

                if etype == "chunk":
                    delta = msg.get("delta", "")
                    chunks.append(delta)
                    if verbose:
                        print(delta, end="", flush=True)

                elif etype == "pending_approval":
                    await ws.send(json.dumps({
                        "type": "approve",
                        "session_id": sid,
                        "decision": "skipped_continue",
                        "comments": "",
                    }, ensure_ascii=False))

                elif etype in {"complete", "rejected", "error"}:
                    if etype == "error":
                        error = msg.get("error", "unknown")
                    else:
                        response_text = msg.get("response", "")
                        trace_summary = str(msg.get("trace_summary", "") or "")
                        for f in (msg.get("funcalls") or []):
                            called = str(f.get("called", ""))
                            tool_name = called.split("(")[0] if "(" in called else called
                            tool_calls.append({"tool": tool_name, "called": called})
                    break

    except asyncio.TimeoutError:
        error = "Timeout"
    except Exception as e:
        error = str(e)

    if verbose:
        print()

    return {
        "case_id":       case["id"],
        "chunks":        chunks,
        "response_text": response_text,
        "trace_summary": trace_summary,
        "tool_calls":    tool_calls,
        "error":         error,
    }


async def run_bench(condition: str, model_label: str,
                    reps: int = 1, verbose: bool = True):
    """Run all cases under one ablation condition, repeated reps times."""
    import requests as _req

    # verify server
    try:
        r = _req.get(f"{SCL_SERVER_HOST}/session-id", timeout=5)
        r.raise_for_status()
        print(f"  [server OK] {SCL_SERVER_HOST}")
    except Exception as e:
        print(f"\n[ERROR] Cannot reach server: {e}")
        print(f"  Start the server first: bench/run_ablation_{condition}.cmd")
        return

    label = f"{condition}__{model_label}"
    print(f"\n{'='*65}")
    print(f"  Regulation Engineering Ablation Bench")
    print(f"  condition: {condition}  |  model: {model_label}  |  reps: {reps}  |  cases: {len(CASES)}")
    print(f"{'='*65}\n")

    all_evals: List[Dict] = []

    for rep in range(1, reps + 1):
        print(f"\n-- rep {rep}/{reps} ----------------------------------------------------------")
        for i, case in enumerate(CASES, 1):
            print(f"\n  [{i}/{len(CASES)}] {case['id']} -- {case['name']}")
            if verbose:
                print(f"  query: {case['query'][:70]}...")
            print("  " + "-" * 48)

            t0 = time.perf_counter()
            run_result = await run_single(case, verbose=verbose)
            elapsed = time.perf_counter() - t0

            if run_result["error"]:
                ev = {
                    "case_id": case["id"],
                    "name":    case["name"],
                    "metric":  case.get("eval", {}).get("metric", ""),
                    "pass":    False,
                    "score":   0.0,
                    "reason":  f"run error: {run_result['error']}",
                    "rep":     rep,
                    "elapsed": round(elapsed, 2),
                    "error":   run_result["error"],
                }
            else:
                ev = evaluate_case(case, run_result)
                ev["rep"]          = rep
                ev["elapsed"]      = round(elapsed, 2)
                ev["error"]        = None
                ev["trace_summary"] = run_result["trace_summary"]

            status = "PASS" if ev["pass"] else ("ERR " if run_result.get("error") else "FAIL")
            over_note = f"  |  {ev.get('over_call_note','')}" if ev.get("over_call_note") else ""
            print(f"  [{status}]  {ev['reason']}  ({elapsed:.1f}s){over_note}")
            all_evals.append(ev)

    # --- aggregate ---
    print(f"\n{'='*65}")
    print(f"  Summary  |  condition: {condition}  |  model: {model_label}")
    print(f"{'='*65}")

    case_rates: Dict[str, List[float]] = {}
    for ev in all_evals:
        case_rates.setdefault(ev["case_id"], []).append(ev["score"])

    print(f"\n  pass-rate per case ({reps} reps):")
    for case in CASES:
        scores = case_rates.get(case["id"], [])
        rate = sum(scores) / len(scores) if scores else 0.0
        bar  = "#" * int(rate * 20) + "." * (20 - int(rate * 20))
        print(f"  {case['id']:<10} [{bar}] {rate*100:.0f}%")

    metric_scores: Dict[str, List[float]] = {}
    for ev in all_evals:
        metric_scores.setdefault(ev["metric"], []).append(ev["score"])

    print(f"\n  pass-rate per metric:")
    total_w = 0.0; w_sum = 0.0
    for metric, scores in sorted(metric_scores.items()):
        avg    = sum(scores) / len(scores)
        weight = METRIC_WEIGHTS.get(metric, 0.1)
        total_w += avg * weight
        w_sum   += weight
        bar = "#" * int(avg * 20) + "." * (20 - int(avg * 20))
        print(f"  {metric:<24} [{bar}] {avg*100:.0f}%")

    overall = total_w / w_sum if w_sum else 0.0
    print(f"\n  overall score: {overall*100:.1f} / 100")

    # --- over_call summary ---
    case_excess: Dict[str, List[int]] = {}
    for ev in all_evals:
        if ev.get("excess_calls") is not None:
            case_excess.setdefault(ev["case_id"], []).append(ev["excess_calls"])
    if case_excess:
        print(f"\n  over-call (excess tool calls beyond expected):")
        for case in CASES:
            vals = case_excess.get(case["id"], [])
            if vals:
                max_exp = case.get("eval", {}).get("max_total_calls", "?")
                avg_excess = sum(vals) / len(vals)
                max_excess = max(vals)
                over_rate  = sum(1 for v in vals if v > 0) / len(vals)
                print(f"  {case['id']:<10} avg_excess={avg_excess:.1f}  "
                      f"max={max_excess}  over_rate={over_rate*100:.0f}%  "
                      f"(threshold={max_exp})")

    # --- save ---
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS_DIR, f"re_ablation__{label}__{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "condition":       condition,
            "model":           model_label,
            "reps":            reps,
            "timestamp":       ts,
            "results":         all_evals,
            "case_pass_rates": {cid: sum(s)/len(s) for cid, s in case_rates.items()},
            "metric_averages": {m: sum(s)/len(s) for m, s in metric_scores.items()},
            "overall_score":   overall,
            "over_call_stats": {
                cid: {
                    "avg_excess":  sum(vals)/len(vals),
                    "max_excess":  max(vals),
                    "over_rate":   sum(1 for v in vals if v > 0)/len(vals),
                }
                for cid, vals in case_excess.items() if vals
            },
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  saved: {out}")


def main():
    parser = argparse.ArgumentParser(
        description="Regulation Engineering Ablation Bench",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
server start scripts (run from bench\\ folder):
  run_ablation_full.cmd            Full SCL (baseline)
  run_ablation_no_regulation.cmd   SCL minus Regulation
  run_ablation_no_control.cmd      SCL minus Control
  run_ablation_no_memory.cmd       SCL minus Memory
  run_ablation_bare_llm.cmd        Bare LLM (all removed)
        """
    )
    parser.add_argument("--condition", required=True, choices=ABLATION_CONDITIONS,
                        help="ablation condition to label results")
    parser.add_argument("--model",     required=True,
                        help="model name running on the server (label only)")
    parser.add_argument("--reps",      type=int, default=5,
                        help="repetitions per case (default: 5)")
    parser.add_argument("--quiet",     action="store_true",
                        help="suppress streaming output")
    args = parser.parse_args()

    asyncio.run(run_bench(
        condition=args.condition,
        model_label=args.model,
        reps=args.reps,
        verbose=not args.quiet,
    ))


if __name__ == "__main__":
    main()
