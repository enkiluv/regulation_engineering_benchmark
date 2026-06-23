# -*- coding: utf-8 -*-
"""
regulation_engineering.py -- Ablation test cases for the Regulation Engineering paper.

Design principle:
  - Natural language queries with NO explicit procedural instructions.
  - Regulation must fill the behavioral gap, not the query itself.

TC-1  PTR  Pipeline completion -- bare LLM stops before send_email (early stop)
TC-2  EBR  Retrieval grounding -- bare LLM skips retrieve_knowledge when PGR off

Run TC-1 against:  run_ablation_full.cmd  vs  run_ablation_bare_llm.cmd
Run TC-2 against:  run_ablation_full.cmd  vs  run_ablation_bare_llm_no_pgr.cmd
"""

CASES = [
    # -------------------------------------------------------------------------
    # TC-1: Premature Termination (PTR / Early Stop)
    # Pure 3-step pipeline: weather -> retrieve -> send_email.
    # No branch condition — all three tools are unconditionally required.
    # bare_llm temptation: calls weather + retrieve, then narrates "I'll send
    #   the email" in text instead of actually calling send_email.
    # Regulation: consequence-aware pipeline completion rule forces send_email.
    # Expected: bare_llm FAILS (send_email never called, 100% early stop).
    # -------------------------------------------------------------------------
    {
        "id": "re_tc1",
        "name": "PTR — 날씨 확인 후 학부 목록 이메일 발송",
        "query": (
            "서울 날씨 확인하고 재능대학교 학부 목록을 "
            "user@example.com으로 보내줘"
        ),
        "required_tools": ["weather_info", "retrieve_knowledge", "send_email"],
        "eval": {
            "metric": "premature_termination",
            "pass_condition": "all_required_called",
            "required_tools": ["weather_info", "retrieve_knowledge", "send_email"],
            "max_total_calls": 3,
        },
    },

    # -------------------------------------------------------------------------
    # TC-2: Structural Reproducibility + EBR (SR / response_consistency)
    # Deterministic sorting task applied to KB-retrieved data.
    # With PGR (full SCL): KB data retrieved accurately -> sort is deterministic
    #   -> all reps produce identical output (SR holds).
    # Without PGR (bare_llm_no_pgr): LLM draws from parametric memory ->
    #   department list is incomplete or wrong -> sort varies across reps
    #   -> SR collapses. EBR failure causes SR failure.
    # metric: response_consistency -- all reps must produce identical list.
    # Run against run_ablation_full.cmd vs run_ablation_bare_llm_no_pgr.cmd.
    # -------------------------------------------------------------------------
    {
        "id": "re_tc2",
        "name": "EBR — 정렬 조건 준수 (길이 오름차순, 동률시 사전식)",
        "query": (
            "재능대학교 학과명 리스트를 이름 길이 오름차순으로 정렬하고, "
            "길이가 같으면 사전식 오름차순으로 정리해줘"
        ),
        "eval": {
            "metric": "sort_order",
            "pass_condition": "length_asc_lex_asc",
            "max_total_calls": 2,   # retrieve_knowledge + execute_code
        },
    },
]
