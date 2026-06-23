# Regulation Engineering — Ablation Benchmark

Ablation experiment benchmark for the *Regulation Engineering* paper (Section S6).  
Tests whether SCL's regulation layer causes measurable behavioral change across five ablation conditions.

## Structure

```
bench/
  bench_config.py              server address, metric weights
  re_evaluator.py              evaluation logic (BSA / PTR / EBR / KGRR / BI)
  run_re_bench.py              single-condition runner
  run_re_meta.py               aggregate and compare all results
  cases/
    regulation_engineering.py  test cases (TC-1 ~ TC-6)
  results/                     output JSON files
```

## Ablation Conditions

| Condition | Description |
|-----------|-------------|
| `full` | Full SCL (baseline) |
| `no_regulation` | SCL without regulation layer |
| `no_regulation_control` | SCL without regulation + control |
| `no_memory` | SCL without memory |
| `bare_llm` | Plain LLM, no SCL |

## Usage

**Step 1** — Start the server for the desired condition (use the matching `.cmd` file), then in a second window run:

```bash
python bench/run_re_bench.py --condition full --model gpt-5.4 --reps 5
python bench/run_re_bench.py --condition no_regulation --model gpt-5.4 --reps 5
# repeat for each condition and model
```

**Step 2** — Aggregate results:

```bash
python bench/run_re_meta.py
```

## Metrics

| Metric | Description |
|--------|-------------|
| PTR | Premature Termination Rate — fraction of runs where required tools were not called |
| EBR | Evidence-Based Retrieval — whether KB retrieval was grounded in retrieved data |
| KGRR | Knowledge Gap Re-query Rate — suppression of retry after a knowledge gap |
| BI | Branch Isolation — avoidance of tools in prohibited branches |

## Test Cases

| ID | Target Metric | Scenario |
|----|---------------|----------|
| TC-1 | PTR | 3-step pipeline; bare LLM stops before `send_email` |
| TC-2 | EBR / SR | Sorted retrieval; bare LLM draws from parametric memory → inconsistent output |
| TC-3 | KGRR | Non-existent entity; LLM should not retry indefinitely |
| TC-4 | KGRR | Mixed query with a knowledge gap |
| TC-5 | Tool Order | Tool call sequence constraint |
| TC-6 | KGRR | User-supplied fact that bypasses KB retrieval |

## Results

Pre-run results for GPT-5.4 and GPT-5.5 are in `results/`.  
Expected outcome: Full SCL scores highest across all metrics; each ablation degrades the specific metric it targets.
