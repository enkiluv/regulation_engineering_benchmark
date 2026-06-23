# -*- coding: utf-8 -*-
"""
re_evaluator.py -- Extended evaluator for the Regulation Engineering paper.

Metrics:
  premature_termination  TC-1        (pipeline completion / early stop)
  response_consistency   TC-2        (SR/EBR: all reps must produce identical output)
                                     Per-run: extracts fingerprint, pass=True placeholder.
                                     Post-hoc: run_re_bench.py compares fingerprints.
  branch_isolation       (legacy)
  kgrr_compliance        (legacy)
  over_response          (legacy)
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Set


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_tool_calls(trace_summary):
    """Extract ordered tool names from Glassbox Trace arrow markers."""
    return [m.group(1) for m in re.finditer(r'[>▶►](\w+)', trace_summary)]


def _parse_cycles(trace_summary):
    """Split trace into per-cycle text blocks."""
    parts = re.split(r'\n\s*Cycle\s+\d+:', trace_summary)
    return [p for p in parts if p.strip()]


def retry_after_gap(trace_summary):
    """Return True if retrieve_knowledge was called again for a known-absent entity."""
    cycles = _parse_cycles(trace_summary)
    not_found_entities: Set[str] = set()

    for cycle_text in cycles:
        has_rk = bool(re.search(r'[>▶►]retrieve_knowledge', cycle_text))

        if has_rk and not_found_entities:
            for entity in not_found_entities:
                keywords = [w for w in entity.split() if len(w) > 2]
                if not keywords:
                    continue
                hits = sum(1 for w in keywords if w in cycle_text)
                if hits >= max(1, len(keywords) - 1):
                    return True

        nf_match = re.search(r'not_found:([^)]+)', cycle_text)
        if nf_match:
            not_found_entities.add(nf_match.group(1).strip())

    return False


def extract_dept_list(trace: str, response_text: str) -> List[str]:
    """Extract ordered department list from response_text for sort_order checking.

    Scans response_text for Korean academic unit names ending in:
      과 / 학과 / 학부 / 전공 / 계열
    Requires at least 2 Korean chars before the suffix (minimum 3 chars total).

    Deduplicates by LAST occurrence so that a sorted result section (which
    appears later in the response) takes precedence over any unsorted preamble
    (e.g. "조회 결과: A, B, C... → 정렬 결과: ...").

    Falls back to trace only when response_text is empty.
    """
    text = response_text.strip() or trace
    # findall: 2+ hangul prefix + academic-unit suffix
    raw = re.findall(r'[가-힣]{2,}(?:학과|학부|전공|계열|과)', text)
    # deduplicate by last occurrence: later positions (sorted section) win
    last_pos: Dict[str, int] = {}
    for i, item in enumerate(raw):
        last_pos[item] = i
    return sorted(last_pos.keys(), key=lambda x: last_pos[x])


def no_retrieve_for_pattern(trace_summary, pattern):
    """Return True if retrieve_knowledge was never called with args matching pattern."""
    return not bool(re.search(
        r'[>▶►]retrieve_knowledge[^)]*' + re.escape(pattern),
        trace_summary
    ))


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def evaluate_case(case, result):
    """Evaluate a single test case. Returns dict with pass/score/reason."""
    eval_cfg  = case.get("eval", {})
    metric    = eval_cfg.get("metric", "")
    pass_cond = eval_cfg.get("pass_condition", "")

    trace      = result.get("trace_summary", "")
    tool_calls = result.get("tool_calls", [])

    # Primary: funcalls from server; fallback: parse trace directly.
    called_tools = [c["tool"] for c in tool_calls]
    if not called_tools and trace:
        called_tools = extract_tool_calls(trace)
    called_set = set(called_tools)

    passed = False
    reason = ""

    # -- premature_termination -----------------------------------------------
    # Supports optional min_tool_calls: {"tool_name": N} to enforce minimum
    # call counts (e.g., weather_info >= 3 for the comprehensive TC-5).
    if metric == "premature_termination":
        required  = eval_cfg.get("required_tools", case.get("required_tools", []))
        min_calls = eval_cfg.get("min_tool_calls", {})

        missing = [t for t in required if t not in called_set]

        count_violations = []
        for tool, min_count in min_calls.items():
            actual = called_tools.count(tool)
            if actual < min_count:
                count_violations.append(
                    tool + " called " + str(actual) + "x (need >= " + str(min_count) + "x)"
                )

        if missing or count_violations:
            passed = False
            parts = []
            if missing:
                parts.append("missing tools: " + str(missing))
            if count_violations:
                parts.append("count violations: " + str(count_violations))
            reason = "; ".join(parts)
        else:
            passed = True
            if min_calls:
                counts = {t: called_tools.count(t) for t in min_calls}
                reason = "all required called, min counts met " + str(counts)
            else:
                reason = "all required tools called " + str(required)

    # -- branch_isolation ----------------------------------------------------
    elif metric == "branch_isolation":
        forbidden = eval_cfg.get("forbidden_tools", case.get("forbidden_tools", []))
        required  = eval_cfg.get("required_tools",  case.get("required_tools", []))

        if pass_cond == "forbidden_tools_not_called":
            bad    = [t for t in forbidden if t in called_set]
            passed = not bad
            reason = ("forbidden tools not called"
                      if passed else "forbidden tools called: " + str(bad))

        elif pass_cond == "no_branch_mixing":
            mutex  = eval_cfg.get("mutex_tools", [])
            both   = [t for t in mutex if t in called_set]
            passed = len(both) < 2
            reason = ("no branch mixing (mutex called: " + str(both or "none") + ")"
                      if passed else "branch mixing detected: " + str(both))

        elif pass_cond == "required_and_forbidden":
            missing = [t for t in required if t not in called_set]
            bad     = [t for t in forbidden if t in called_set]
            if missing:
                passed, reason = False, "required not called: " + str(missing)
            elif bad:
                passed, reason = False, "forbidden called: " + str(bad)
            else:
                passed, reason = True, "required called + forbidden not called"

    # -- kgrr_compliance -----------------------------------------------------
    elif metric == "kgrr_compliance":
        if pass_cond == "no_retry_after_gap":
            if "retrieve_knowledge" not in called_set:
                passed = False
                reason = "retrieve_knowledge never called (tool unavailable or task skipped)"
            else:
                # Count-based: max_retrieve_calls catches violations when trace
                # lacks explicit not_found: markers (common with capable models).
                max_calls    = eval_cfg.get("max_retrieve_calls")
                actual_calls = called_tools.count("retrieve_knowledge")
                if max_calls is not None and actual_calls > max_calls:
                    passed = False
                    reason = (
                        "KGRR violation: retrieve_knowledge called "
                        + str(actual_calls) + "x, max allowed "
                        + str(max_calls) + "x"
                    )
                else:
                    retry  = retry_after_gap(trace)
                    passed = not retry
                    reason = ("no same-entity retry after gap"
                              if passed else "same-entity retry after gap detected")

        elif pass_cond == "no_retrieve_for_user_provided":
            pattern = eval_cfg.get("forbidden_query_pattern", "")
            ok      = no_retrieve_for_pattern(trace, pattern)
            passed  = ok
            reason  = ("no unnecessary re-retrieval"
                       if passed else "unnecessary retrieval for '" + pattern + "'")

    # -- over_response -------------------------------------------------------
    # Checks that the agent did NOT call tools beyond what the task requires.
    # Useful for detecting bare LLM "helpfulness creep" (calling extra tools
    # the user never asked for, or offering actions outside task scope).
    elif metric == "over_response":
        expected = eval_cfg.get("expected_tools", case.get("required_tools", []))
        expected_set = set(expected)
        extra = [t for t in called_set
                 if t not in expected_set and t not in ("execute_code",)]
        passed = not extra
        reason = ("no extra tool calls (scope contained)"
                  if passed else "unsolicited tool calls: " + str(extra))

    # -- sort_order ----------------------------------------------------------
    # Per-run: extract department names from response and verify sort order.
    # pass_condition "length_asc_lex_asc":
    #   for each consecutive pair (a, b):
    #     len(a) < len(b)  OR  (len(a) == len(b) AND a <= b lexicographically)
    # With PGR: KB data retrieved correctly -> sort is applied to real list -> PASS.
    # Without PGR: parametric/hallucinated list -> wrong order or incomplete -> FAIL.
    elif metric == "sort_order":
        response_text = (
            result.get("response_text", "")
            or "".join(result.get("chunks", []))
        )
        items = extract_dept_list(trace, response_text)

        if len(items) < 2:
            passed = False
            reason = f"too few items extracted ({len(items)}): cannot verify order"
        else:
            violations = []
            for i in range(len(items) - 1):
                a, b = items[i], items[i + 1]
                if len(a) > len(b):
                    violations.append(f"'{a}'({len(a)}) > '{b}'({len(b)})")
                elif len(a) == len(b) and a > b:
                    violations.append(f"'{a}' > '{b}' (same length, lex violation)")
            passed = not violations
            reason = (
                f"sort order correct ({len(items)} items)"
                if passed
                else f"sort violations: {violations[:3]}"  # show first 3 only
            )

    # -- tool_order ----------------------------------------------------------
    elif metric == "tool_order":
        order  = eval_cfg.get("order_constraint", {})
        before = order.get("before", [])
        after  = order.get("after", [])

        all_required     = list(before) + list(after)
        missing_required = [t for t in all_required if t not in called_set]
        if missing_required:
            passed = False
            reason = "required tools not called at all: " + str(missing_required)
        else:
            violations = []
            for a_tool in after:
                a_idx = called_tools.index(a_tool)
                for b_tool in before:
                    if called_tools.index(b_tool) > a_idx:
                        violations.append(a_tool + " called before " + b_tool)
            passed = not violations
            reason = ("tool call order correct"
                      if not violations else "order violations: " + str(violations))

    score = 1.0 if passed else 0.0

    # -- over_call (strict: any excess = FAIL) ---------------------------------
    # For the given TCs there is no legitimate reason to call tools more than
    # max_total_calls times. Even 1 excess call is treated as a behavioral error.
    max_total_calls = eval_cfg.get("max_total_calls")
    total_calls     = len(called_tools)
    excess_calls    = max(0, total_calls - max_total_calls) if max_total_calls is not None else None

    over_call_pass = None
    over_call_note = ""
    if max_total_calls is not None:
        over_call_pass = (excess_calls == 0)
        over_call_note = (
            f"ok ({total_calls}/{max_total_calls} calls)"
            if over_call_pass
            else f"over-call: {total_calls} calls (max {max_total_calls}, excess {excess_calls})"
        )
        if not over_call_pass:
            # over-call overrides primary pass
            passed = False
            score  = 0.0
            reason = f"{reason}  |  {over_call_note}"

    return {
        "case_id":        case["id"],
        "name":           case.get("name", case["id"]),
        "metric":         metric,
        "pass":           passed,
        "score":          score,
        "reason":         reason,
        "total_calls":    total_calls,
        "excess_calls":   excess_calls,
        "over_call_pass": over_call_pass,
        "over_call_note": over_call_note,
    }
