@echo off
rem ============================================================
rem  Ablation: SCL minus Memory layer
rem  Run from bench\ folder - cd up to scl-core root first
rem ============================================================

cd /d %~dp0..

pip install -r requirements.txt

set SCL_MAX_TOKENS=4096
set SCL_MIN_CALL_INTERVAL=0.1
set SCL_ABLATION=memory

set SCL_RETRIEVAL_ENABLED=True
set SCL_RETRIEVAL_THRESHOLD=0.20
set SCL_RETRIEVAL_EXTRA_INDEX_PATHS=%~dp0..\extra_indexes.pkz
set SCL_RETRIEVAL_MODE=gated
set SCL_PGR_THRESHOLD=0.50
set SCL_PGR_TOP_N=5

rem === Model selection: uncomment ONE block ===
rem -- gpt-4o (default) --
rem set SCL_LLM_PROVIDER=openai
rem set SCL_MODEL=gpt-4o

rem -- gpt-5.5 thinking mode --
set SCL_LLM_PROVIDER=openai
set SCL_MODEL=gpt-5.5

rem -- Claude Sonnet 4.6 --
rem set SCL_LLM_PROVIDER=anthropic
rem set SCL_MODEL=claude-sonnet-4-6

echo.
echo  [Ablation] SCL minus Memory - port 8001
echo.

python -m uvicorn gateway.scl_api_server:app --host 0.0.0.0 --port 8001 --timeout-keep-alive 3600 --ws-ping-interval 20 --ws-ping-timeout 60
