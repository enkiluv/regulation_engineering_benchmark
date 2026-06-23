# Regulation Engineering Ablation Experiment

논문 **S6. Ablation Experiment** 실험 가이드입니다.

## 파일 구성

```
bench/
  bench_config.py              서버 주소, 가중치 설정
  re_evaluator.py              평가 로직 (BSA / PTR / TCCR / KGRR / BI)
  run_re_bench.py              단일 조건 실험 러너
  run_re_meta.py               전체 결과 집계·비교
  cases/
    regulation_engineering.py  6개 테스트 케이스 (TC-1 ~ TC-6)
  results/                     실험 결과 JSON 저장 위치
```

## 실험 절차

> **모든 스크립트는 `bench\` 폴더 안에 있습니다.**  
> scl-core 루트에는 아무 파일도 생성되지 않습니다.

### 1단계 — 조건별 서버 시작 + 실험 실행

각 조건에 대해 아래를 반복합니다 (서버 창 따로, 벤치 창 따로):

```batch
:: 창 1: bench\ 폴더 안 CMD를 더블클릭하거나 아래와 같이 실행
bench\run_ablation_full.cmd               ← Full SCL
bench\run_ablation_no_regulation.cmd      ← SCL − Regulation
bench\run_ablation_no_control.cmd         ← SCL − Control
bench\run_ablation_no_memory.cmd          ← SCL − Memory
bench\run_ablation_bare_llm.cmd           ← Bare LLM
:: (CMD 내부에서 cd /d %~dp0.. 로 scl-core 루트로 이동 후 서버 기동)

:: 창 2: scl-core 루트에서 실행
python bench\run_re_bench.py --condition full --model gpt-4o --reps 5
python bench\run_re_bench.py --condition no_regulation --model gpt-4o --reps 5
python bench\run_re_bench.py --condition no_control --model gpt-4o --reps 5
python bench\run_re_bench.py --condition no_memory --model gpt-4o --reps 5
python bench\run_re_bench.py --condition bare_llm --model gpt-4o --reps 5
```

Claude Sonnet 4.6로도 동일하게 반복 (CMD 파일에서 모델 전환 후 재시작):

```batch
python bench\run_re_bench.py --condition full --model claude-sonnet-4-6 --reps 5
:: ... 나머지 조건도 동일
```

### 2단계 — 집계 및 비교 테이블 출력

모든 조건 실험 완료 후:

```batch
python bench\run_re_meta.py
```

## 측정 지표

| 지표 | 약어 | 정의 |
|------|------|------|
| Premature Termination Rate | PTR↓ | 필수 도구 미호출 비율 (낮을수록 좋음) |
| Branch Isolation | BI | 금지 분기 도구 미호출 비율 |
| KGRR Compliance | KGRR | gap 후 재시도 억제 비율 |
| Tool Order | Order | 도구 순서 준수 비율 |

## 테스트 케이스

| ID | 이름 | 측정 대상 |
|----|------|-----------|
| re_tc1 | 비 조건 분기 | PTR (조기 종료) |
| re_tc2 | 3단계 기온 분기 | BI (분기 격리) |
| re_tc3 | 미존재 개체 | KGRR |
| re_tc4 | 혼합 조회 | KGRR |
| re_tc5 | 도구 순서 제약 | Tool Order |
| re_tc6 | 사용자 제공 사실 | KGRR |

## 예상 결과 (논문 S6.5)

- **Full SCL**: 전 지표 고득점 (두 모델 동일 → Structural Reproducibility)
- **SCL − Regulation**: re_tc1 PTR 상승, re_tc2 BI 저하 (규제 제거 효과 직접 확인)
- **SCL − Control**: re_tc2 BI 저하 (분기 강제 없음)
- **SCL − Memory**: re_tc4, tc6 KGRR 저하
- **Bare LLM**: 전반적 저하
