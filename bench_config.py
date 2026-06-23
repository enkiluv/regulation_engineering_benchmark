# -*- coding: utf-8 -*-
"""
bench_config.py — Regulation Engineering ablation 실험 설정
"""

# ablation 서버 (run_ablated_gateway.cmd → port 8001)
SCL_SERVER_HOST = "http://127.0.0.1:8001"

# 평가 지표 가중치 (논문 S6 기준)
METRIC_WEIGHTS = {
    "branch_selection":      0.25,   # BSA — 조건 분기 정확률
    "premature_termination": 0.25,   # PTR — 조기 종료율 (1 - pass_rate)
    "kgrr_compliance":       0.20,   # KGRR — gap 후 재시도 억제
    "branch_isolation":      0.20,   # BI — 분기 격리
    "tool_order":            0.10,   # 도구 호출 순서 준수
    "sort_order":            0.25,   # EBR — 정렬 조건 준수 (근거기반 조회 간접 측정)
}

MAX_CYCLES = 15
LANGUAGE   = "Korean"
AUTO_HITL  = "skip"
TIMEOUT_SEC = 120
RESULTS_DIR = "bench/results"
