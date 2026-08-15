# SearchHarness_0425 Smoke Test Report

Date: 2026-07-30

## Scope

This round focused on the `SearchHarness_0425` directory only.

Goals:

- verify whether the LLM endpoint is reachable from the current config
- verify whether Serper search still works
- run one minimal end-to-end fixed-sample task
- separate infrastructure failures from pipeline-quality failures

## Commands Run

From `SearchHarness_0425`:

```bash
python3 debug_llm_smoke.py --no-proxy
python3 debug_serper_smoke.py
GRADER_MODEL_NAME=deepseek-chat python3 run_browsecomp_fixed_sample.py \
  --seed 123 \
  --sample-size 10 \
  --positions 3 \
  --output results/smoke_pos3_20260730.json \
  --trajectory-dir logs/trajectories_smoke_pos3_20260730 \
  --max-iterations 4 \
  --max-crawl-calls 10 \
  --max-planner-searches 5 \
  --max-executor-searches 10 \
  --max-total-searches 20
```

## Result Summary

### 1. LLM smoke test

Status: passed after config correction

Observed behavior:

- `GET /models` returned HTTP 200
- `POST /chat/completions` returned HTTP 200
- the current key can access `GLM-5.2`
- the current key cannot access `deepseek-chat`; attempts to use that model return a model-access denial

Interpretation:

- the LLM route and key are valid
- the real compatibility constraint is model access: `GLM-5.2` is available, `deepseek-chat` is not
- 0425 must therefore run on `GLM-5.2` unless the provider grants additional model access

### 2. Serper smoke test

Status: passed

Observed behavior:

- HTTP 200 returned from `https://google.serper.dev/search`
- 3 organic results were returned
- no auth error
- no quota error
- no timeout in this round

Interpretation:

- search infrastructure is currently usable
- the immediate blocker is not Serper

### 3. Fixed-sample end-to-end task

First attempt:

- fixed sample: `seed=123`, `sample_size=10`, `position=3`
- gold answer: `Whitesnake`

Status: failed early before auth/model corrections

Artifacts:

- `results/smoke_pos3_20260730.json`
- `logs/trajectories_smoke_pos3_20260730/GLM-5.2/task_000003.json`

Observed behavior:

- task finished in about `0.5s`
- pipeline status was `unfinished`
- iteration count stayed at `0`
- no search query was issued
- final answer fell back to a `best_effort` payload with `answer = Unknown`
- finalizer failure reason contained the same 401 `invalid_api_key`
- grader also failed with the same 401 `invalid_api_key`

Interpretation:

- this run does not provide useful evidence about planning quality, candidate quality, or search budget behavior
- the run was blocked before the actual search loop could start

Second attempt after auth/model fixes and harness adjustments:

- positions rerun individually: `1`, `3`, `4`
- all runs completed and produced JSON results
- all three runs ended with `pipeline_status = infra_error`
- all three runs were classified as `failure_category = network_error`

Artifacts:

- `results/smoke_pos1_20260730.json`
- `results/smoke_pos3_20260730.json`
- `results/smoke_pos4_20260730.json`

Observed behavior:

- position `1`: elapsed `483.3s`, finalizer timed out, output classified as `infra_error`
- position `3`: elapsed `683.5s`, finalizer timed out, output classified as `infra_error`
- position `4`: elapsed `518.4s`, finalizer timed out, output classified as `infra_error`
- the grader itself completed and explained that the answer was missing because the pipeline terminated with infrastructure failure

Interpretation:

- auth is no longer the blocker
- the dominant blocker is now runtime instability under long multi-turn prompts: planner/executor/finalizer calls still time out often enough to prevent meaningful quality evaluation
- the new `infra_error` status is doing useful work: these runs are now clearly separated from ordinary search-quality failures

## Confirmed Problems In 0425

### P0. Long-running GLM calls still time out under 0425 prompt/load shape

Evidence from this round:

- standalone smoke script now passes on `GLM-5.2`
- individual reruns for positions `1`, `3`, and `4` all finished as `infra_error`
- finalizer failures reported `Request timed out`
- long planning/execution loops still showed repeated planner-format retries and crawl-heavy loops before termination

Impact:

- the system can start and run, but still cannot produce stable quality measurements under realistic prompt/context load
- evaluation remains dominated by infrastructure/runtime behavior rather than search correctness

### P1. Grader config names are inconsistent across 0425 entrypoints

Observed in code:

- `run_browsecomp.py` reads `GRADER_MODEL`
- `run_browsecomp_fixed_sample.py` reads `GRADER_MODEL_NAME`
- `regrade_results.py` accepts both and falls back across names

Status update:

- this has now been normalized in the harness code by resolving grader config from one shared path with backward-compatible fallbacks

Impact before fix:

- the same `.env` can behave differently depending on which launcher is used
- fixing grader config in one path may silently not fix another path

Why this matters:

- this is exactly the kind of drift that previously caused `Model Not Exist` grading failures
- even after auth is fixed, this inconsistency can still poison evaluation results

### P1. GLM planner output is not protocol-stable enough for the original planner loop

Observed in output:

- planner responses repeatedly contained reasoning without a parseable closed `<planning>...</planning>` block
- some assistant messages contained opening `<planning>` content without a closing tag
- the harness needed extra retries and now also benefits from a fallback local plan path

Impact:

- planner turns are wasted on format recovery instead of progress
- GLM can be usable here, but the prompts and parsing assumptions are still tuned for another model family

### P1. Infrastructure failures are now separated from ordinary search failures

Observed in code and output:

- finalizer failures are now emitted as `status = infra_error`
- pipeline outputs now carry `failure_category`, such as `network_error`
- result JSON files for positions `1`, `3`, and `4` clearly report `pipeline_status = infra_error`

Impact:

- evaluation output is now more honest and easier to triage
- infrastructure incidents are less likely to be mistaken for weak reasoning or poor candidate handling

### P2. Search-quality hypotheses are still not testable with confidence

Observed in trajectory output:

- after the fallback and timeout adjustments, runs do progress further than iteration zero
- however, the final status for all three sampled tasks is still `infra_error`
- because all sampled tasks end in infrastructure timeout, there is still no trustworthy quality signal for candidate generation, verification ordering, or finalization accuracy

Impact:

- there is still no trustworthy evidence about actual answer quality under the current runtime profile

## What Is Working

- `SearchHarness_0425` Python files are importable enough to launch the smoke scripts and fixed-sample runner
- Serper search is currently healthy
- the Tenyun endpoint is reachable and usable through OpenAI-style `/chat/completions`
- the harness now resolves to `GLM-5.2` correctly
- result and trajectory artifacts are still being written correctly when a run fails
- `infra_error` and `failure_category` now appear in results, which is useful for downstream evaluation

## Recommended Next Fix Order

### 1. Reduce runtime timeout pressure first

Checklist:

- shorten planner and executor prompts or compact more aggressively before each turn
- keep `GLM-5.2` as the active model unless additional model access is granted
- consider lower-turn / lower-budget smoke profiles for fast regression checks
- consider forcing `html2text` during smoke runs to avoid Jina-induced crawl delays

Success condition:

- a one-position smoke run should complete without `infra_error`

### 2. Normalize grader env names

Recommended direction:

- keep the new shared grader config resolver and avoid reintroducing split env-name behavior

Minimum target:

- both launchers should accept the same `GRADER_API_BASE`, `GRADER_API_KEY`, and one canonical grader model variable

### 3. Split infra failure from search failure in outputs

Recommended direction:

- keep using the explicit `infra_error` status
- extend the same classification to planner/executor/parser failure clusters when useful

Minimum target:

- preserve `failure_category` in all result writers and downstream regrading/evaluation tools

### 4. Re-run a small quality check after auth is fixed

Recommended follow-up sample set:

- `position=1` as an easier sanity check
- `position=3` as a previously difficult band-identification case
- `position=4` as a candidate-verification-heavy case

Suggested second-round command pattern:

```bash
LLM_TIMEOUT_S=120 \
PLANNER_MAX_TURNS=4 \
EXECUTOR_MAX_TURNS=4 \
PLANNER_MAX_TOKENS=700 \
EXECUTOR_MAX_TOKENS=900 \
CRAWLER_ENGINE=html2text \
python3 run_browsecomp_fixed_sample.py \
  --seed 123 \
  --sample-size 10 \
  --positions 1 \
  --output results/smoke_pos1_next.json \
  --trajectory-dir logs/trajectories_smoke_pos1_next \
  --max-iterations 1 \
  --max-crawl-calls 2 \
  --max-planner-searches 3 \
  --max-executor-searches 4 \
  --max-total-searches 6 \
  --disable-query-critic
```

Then repeat the same command for positions `3` and `4`.

## Bottom Line

This test round first exposed an auth/model-access problem, and after fixing that, exposed the next real bottleneck.

- Auth is now fixed for the available model path: `GLM-5.2` works.
- The main blocker is now runtime instability and timeout behavior under 0425's long planning/execution loop.
- Grader env drift has been normalized in code.
- Infrastructure failures are now surfaced explicitly as `infra_error` with `failure_category`.

Until timeout behavior is brought under control, further 0425 evaluation will still mostly measure runtime stability rather than search quality.

## Finalizer Protocol Tightening (2026-07-30, round 2)

### Problem

After the planner protocol tightening, the ultra-small smoke (`max_iterations=0`)
still produced `pipeline_status=unfinished` with an opaque finalizer failure:

```
Finalizer LLM failed: No JSON object found in finalizer response
```

Root cause: `GLM-5.2` puts its analysis in `reasoning_content` and returns an
empty `content`. The finalizer only read `content`, found no JSON, raised
`ValueError`, and the except branch returned `best_effort` with
`error_type=""`. The pipeline then mapped that to the ambiguous `unfinished`
status, which is indistinguishable from a genuine best-effort "Unknown" answer.

### Fix

Applied the same fail-fast + fallback pattern used for the planner:

1. **Strict output contract** in `FINALIZER_SYSTEM_PROMPT`:
   - content must begin with `{` and end with `}`
   - no markdown fences, prose, or tags
   - no separate reasoning field; final JSON goes directly in content

2. **`reasoning_content` fallback parsing** in `SearchFinalizer.finalize()`:
   - when `content` yields no JSON, try `_parse_payload` on `reasoning_content`
   - this recovers cases where GLM emits JSON inside the reasoning field

3. **Local fallback finalization** via `_local_fallback_answer()`:
   - when both `content` and `reasoning_content` fail to parse, derive a
     best-guess answer from `candidate_records` / `current_candidates`
   - returns `"Unknown"` when no candidate is available
   - marks `error_type="protocol_error"` so the pipeline can distinguish it

4. **Explicit `protocol_error` pipeline status** in
   `search_harness_pipeline_v4.py::_best_effort_finish`:
   - `final.error_type == "protocol_error"` -> `pipeline_status="protocol_error"`
   - this is now a first-class status alongside `infra_error` / `finished` /
     `unfinished`

### Validation

All runs use the tightened env profile and exit 0 with stable JSON output:

| Run | Position | Budget | pipeline_status | failure_category | elapsed |
|-----|----------|--------|-----------------|------------------|---------|
| ultra smoke r1 | 3 | max_iter=0 | protocol_error | protocol_error | 33.5s |
| ultra smoke r2 | 3 | max_iter=0 | protocol_error | protocol_error | 34.5s |
| small smoke | 3 | max_iter=1 | protocol_error | protocol_error | 93.4s |
| small smoke | 1 | max_iter=1 | protocol_error | protocol_error | 50.7s |

The ultra smoke (init + planner + finalizer only) is now stable at
`protocol_error` instead of the ambiguous `unfinished`. The small smoke
(full planner -> executor -> finalizer cycle) back-ports the same fix and is
also stable.

### Interpretation

`protocol_error` is the honest, stable status for the current `GLM-5.2`
finalizer path: the model does not emit parseable JSON in either `content` or
`reasoning_content` for the finalizer prompt, so the harness falls back to a
local answer and flags the protocol mismatch explicitly. This is preferable to
the previous ambiguous `unfinished`, because:

- it is distinguishable from a genuine best-effort "Unknown"
- it points at the exact failure layer (finalizer output protocol)
- it does not require a large budget to reproduce

### Reproduction

Ultra smoke:

```bash
env LLM_TIMEOUT_S=120 PLANNER_MAX_TURNS=2 EXECUTOR_MAX_TURNS=2 \
  PLANNER_MAX_TOKENS=700 EXECUTOR_MAX_TOKENS=900 \
  CRAWLER_ENGINE=html2text PLANNER_FAIL_FAST_ON_MALFORMED_PLAN=1 \
  python3 run_browsecomp_fixed_sample.py \
    --seed 123 --sample-size 10 --positions 3 \
    --output results/position3_ultra_smoke_20260730.json \
    --trajectory-dir logs/trajectories_position3_ultra_smoke_20260730 \
    --max-iterations 0 --max-crawl-calls 0 \
    --max-planner-searches 1 --max-executor-searches 1 --max-total-searches 1 \
    --disable-query-critic
```

Small smoke (same env, larger budget):

```bash
env LLM_TIMEOUT_S=120 PLANNER_MAX_TURNS=4 EXECUTOR_MAX_TURNS=4 \
  PLANNER_MAX_TOKENS=700 EXECUTOR_MAX_TOKENS=900 \
  CRAWLER_ENGINE=html2text PLANNER_FAIL_FAST_ON_MALFORMED_PLAN=1 \
  python3 run_browsecomp_fixed_sample.py \
    --seed 123 --sample-size 10 --positions 3 \
    --output results/position3_small_smoke_20260730.json \
    --trajectory-dir logs/trajectories_position3_small_smoke_20260730 \
    --max-iterations 1 --max-crawl-calls 2 \
    --max-planner-searches 3 --max-executor-searches 4 --max-total-searches 6 \
    --disable-query-critic
```