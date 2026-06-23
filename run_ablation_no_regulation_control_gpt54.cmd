@echo off
rem ============================================================
rem  Ablation: SCL minus Regulation + Control (Memory retained)
rem  Purpose: isolate the combined effect of removing behavioral
rem  constraints (regulation) and execution gating (control)
rem  while keeping memory accumulation intact.
rem  Compare with no_regulation / no_control individually and
rem  with bare_llm (all three removed) to show additive effects.
rem ============================================================

cd /d %~dp0..

pip install -r requirements.txt

set SCL_MAX_TOKENS=4096
set SCL_MIN_CALL_INTERVAL=0.1
set SCL_ABLATION=regulation, control

set SCL_RETRIEVAL_ENABLED=True
set SCL_RETRIEVAL_THRESHOLD=0.20
set SCL_RETRIEVAL_EXTRA_INDEX_PATHS=%~dp0..\extra_indexes.pkz
set SCL_RETRIEVAL_MODE=gated
set SCL_PGR_THRESHOLD=0.50
set SCL_PGR_TOP_N=5

rem -- gpt-5.4 --
set SCL_LLM_PROVIDER=openai
set SCL_MODEL=gpt-5.4

echo.
echo  [Ablation] SCL minus Regulation+Control (Memory on) - port 8001
echo.

python -m uvicorn gateway.scl_api_server:app --host 0.0.0.0 --port 8001 --timeout-keep-alive 3600 --ws-ping-interval 20 --ws-ping-timeout 60
