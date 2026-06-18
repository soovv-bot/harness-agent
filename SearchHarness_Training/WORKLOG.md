# SearchHarness_0413_v3 Work Log

## 1. Purpose

This directory is the active workspace for the next round of BrowseComp debugging and improvement.

The current optimization target is:

- pseudo-candidate elimination
- candidate state management

The practical goal is to improve answer quality on the fixed BrowseComp sample that was previously run under seed `123`.

## 2. Directory Status

- Active directory for new work:
  - `D:\research\search_data_systhesis\SearchHarness_0413_v3`
- Python environment:
  - `D:\anaconda3\envs\agent_safety`
- Earlier baseline directory:
  - `D:\research\search_data_systhesis\SearchHarness_0412`
- Earlier copied experiment directory:
  - `D:\research\search_data_systhesis\SearchHarness_0413_v2`

Current expectation:

- all new code edits should go into `0413_v3`
- old directories should be treated as baselines/reference only

## 3. What We Were Trying To Fix

The earlier pipeline was no longer failing mainly because of infrastructure. It could already:

- initialize planner and executor
- run multiple search / visit steps
- finish full tasks end to end

But the quality problems were still serious. The main failure patterns observed from the fixed sample were:

1. Strong but false candidates were not being eliminated aggressively enough.
   Example:
   - `Mark Selby` chosen instead of `Ding Junhui`
   - `Opium: A Portrait of the Heavenly Demon` chosen instead of the correct full title

2. Plausible candidates appeared during the run, but were not tracked in a durable, structured way.
   Result:
   - later planning rounds behaved as if the system had to “guess again”

3. Wrap-up and finalization were too willing to converge on a candidate that still had an unresolved hard contradiction.

4. Some tasks reached a nearly-correct state but still ended in `Unknown` because the candidate state did not stay clean and explicit through the final phase.

This is why the current `v3` work focuses on:

- structured candidate bookkeeping
- explicit hard-conflict recording
- more conservative solved/finalize behavior

## 4. Fixed Sample Configuration

The fixed BrowseComp sample used for comparison is:

- seed: `123`
- sample size: `10`

The manifest file is:

- `D:\research\search_data_systhesis\SearchHarness_0413_v3\docs\seed123_k10_manifest.json`

Important sampling note:

- sample position `0` is the skipped reference item
- sample positions `1-9` are the main items we care about when comparing to the earlier `tasks1to9` runs

## 5. Fixed Sample Answer Key

The current known fixed sample positions and gold answers are:

- `0`: `Achimota School.`
- `1`: `Marguerite Smith`
- `2`: `Abangan 2024`
- `3`: `Whitesnake`
- `4`: `Ding Junhui`
- `5`: `In the Arms of Morpheus: The Tragic History of Laudanum, Morphine and Patent Medicines`
- `6`: `University of Aberdeen`
- `7`: `Michael Reed Holzer`
- `8`: `Porz Goret`
- `9`: `Cigarette`

## 6. Important Historical Results

### 6.1 Earlier single-item validation that succeeded

In the earlier unified-`visit_urls` phase, one validation run succeeded on:

- `position=1`
- gold answer: `Marguerite Smith`

This showed that the toolchain itself could now solve at least some previously failing cases.

### 6.2 Earlier fixed-sample run on positions `2-9`

An earlier batch run was completed in `0412` on the fixed positions `2-9`.

Manual answer comparison showed:

- correct:
  - `8 -> Porz Goret`

- incorrect or `Unknown`:
  - `2 -> Unknown` instead of `Abangan 2024`
  - `3 -> Unknown` instead of `Whitesnake`
  - `4 -> Mark Selby` instead of `Ding Junhui`
  - `5 -> Opium: A Portrait of the Heavenly Demon` instead of the correct full title
  - `6 -> Unknown` instead of `University of Aberdeen`
  - `7 -> Unknown` instead of `Michael Reed Holzer`
  - `9 -> Unknown` instead of `Cigarette`

Important grading note:

- the external grader configuration in that run was unreliable because a grader model mismatch caused `Model Not Exist` errors
- therefore, answer correctness should be checked by comparing extracted answers to gold answers, not by trusting the saved `is_correct` field from that broken run

## 7. Why v3 Exists

`0413_v3` was created specifically to test a new hypothesis:

- better candidate-state tracking and better false-candidate elimination may improve more tasks than a narrowly targeted “final hop only” fix

The idea is:

- do not just let the planner/executor mention candidate names in prose
- force candidate-like entities to be recorded as structured state
- if a candidate gets a decisive contradiction, mark it clearly and stop letting it dominate wrap-up

## 8. Code Changes Already Made In v3

### 8.1 `search_memory.py`

Main change:

- introduced `candidate_records`

What `candidate_records` stores per candidate:

- candidate name
- status such as `active` or `eliminated`
- `supporting_constraints`
- `unresolved_constraints`
- `hard_conflicts`
- short `reason`
- timestamps / recent evidence snippets

Behavioral effect:

- candidate information is no longer just a pair of flat name lists
- the state store can preserve why a candidate is promising or why it should be discarded
- hard conflicts can actively push a candidate into eliminated state

### 8.2 `search_agent_v3.py`

Main change:

- executor prompt now explicitly encourages structured candidate reporting

New expectation from executor findings:

- `candidate_updates.candidate_assessments`

Each candidate assessment can include:

- `name`
- `status`
- `supporting_constraints`
- `unresolved_constraints`
- `hard_conflicts`
- `reason`

Behavioral effect:

- executor has a clearer channel to say:
  - this candidate fits these constraints
  - this candidate still has these unknowns
  - this candidate is actually contradicted by this fact

### 8.3 `search_finalizer.py`

Main change:

- finalizer now treats `candidate_records` as the best available summary of candidate quality

Behavioral effect:

- a candidate with unresolved `hard_conflicts` should not be an easy final answer
- support and conflict information can influence final answer selection

### 8.4 `search_harness_pipeline_v4.py`

Main change:

- solved gating was tightened using candidate viability

Behavioral effect:

- the run is less likely to be treated as confidently solved if candidate state still contains unresolved conflict or multiple viable contenders

## 9. Small Bug Already Fixed During v3 Work

While preparing validation, one prompt-formatting bug was found and fixed:

- `search_agent_v3.py` included a JSON example inside an f-string
- braces were not escaped
- this caused:
  - `ValueError: Invalid format specifier`

That issue is already fixed in `0413_v3`.

## 10. Current Blocker

The current blocker is search capacity:

- Serper appears to have no remaining quota / balance

Effect:

- new validation runs cannot complete normally right now

There was also an interrupted attempt to rerun `position=4`, but it should not be treated as a real evaluation result.

Most recent verification history:

- previous key `7fcd7093e3c9e3a4300dd63f15511374c930bc19`
  - request reached Serper successfully
  - Serper response was:
    - `{"message":"Not enough credits","statusCode":400}`

- current key `68f5b68f5a1f001b8f1e05fef6f3007c4ff27de4`
  - root `.env` has been updated
  - a live request to `https://google.serper.dev/search` returned normal search results
  - this confirms the local Serper setup is now usable again

## 11. Commands To Reuse Later

### 11.1 Full fixed-sample run for positions `2-9`

```powershell
& 'D:\anaconda3\envs\agent_safety\python.exe' `
  'D:\research\search_data_systhesis\SearchHarness_0413_v3\run_browsecomp_fixed_sample.py' `
  --seed 123 `
  --sample-size 10 `
  --positions 2-9 `
  --output 'results\seed123_fixed_positions2to9_candidate_v3.json' `
  --trajectory-dir 'logs\trajectories_candidate_v3' `
  --max-iterations 6 `
  --max-crawl-calls 12 `
  --max-planner-searches 10 `
  --max-executor-searches 30 `
  --max-total-searches 80
```

### 11.2 Single-item validation for the high-confidence wrong-answer case

Recommended first validation target:

- `position=4`
- gold answer: `Ding Junhui`
- previous wrong answer: `Mark Selby`

Command:

```powershell
$env:GRADER_MODEL_NAME='deepseek-chat'
& 'D:\anaconda3\envs\agent_safety\python.exe' `
  'D:\research\search_data_systhesis\SearchHarness_0413_v3\run_browsecomp_fixed_sample.py' `
  --seed 123 `
  --sample-size 10 `
  --positions 4 `
  --output 'results\seed123_position4_candidate_v3.json' `
  --trajectory-dir 'logs\trajectories_candidate_v3' `
  --max-iterations 6 `
  --max-crawl-calls 12 `
  --max-planner-searches 10 `
  --max-executor-searches 30 `
  --max-total-searches 80
```

### 11.3 Single-item validation for the wrong-book-title case

Recommended second validation target:

- `position=5`
- previous wrong answer: `Opium: A Portrait of the Heavenly Demon`

Command:

```powershell
$env:GRADER_MODEL_NAME='deepseek-chat'
& 'D:\anaconda3\envs\agent_safety\python.exe' `
  'D:\research\search_data_systhesis\SearchHarness_0413_v3\run_browsecomp_fixed_sample.py' `
  --seed 123 `
  --sample-size 10 `
  --positions 5 `
  --output 'results\seed123_position5_candidate_v3.json' `
  --trajectory-dir 'logs\trajectories_candidate_v3' `
  --max-iterations 6 `
  --max-crawl-calls 12 `
  --max-planner-searches 10 `
  --max-executor-searches 30 `
  --max-total-searches 80
```

### 11.4 Single-item validation for the near-complete `Unknown` case

Recommended third validation target:

- `position=9`
- gold answer: `Cigarette`
- earlier behavior: likely close to the right poet/work, but still ended as `Unknown`

Command:

```powershell
$env:GRADER_MODEL_NAME='deepseek-chat'
& 'D:\anaconda3\envs\agent_safety\python.exe' `
  'D:\research\search_data_systhesis\SearchHarness_0413_v3\run_browsecomp_fixed_sample.py' `
  --seed 123 `
  --sample-size 10 `
  --positions 9 `
  --output 'results\seed123_position9_candidate_v3.json' `
  --trajectory-dir 'logs\trajectories_candidate_v3' `
  --max-iterations 6 `
  --max-crawl-calls 12 `
  --max-planner-searches 10 `
  --max-executor-searches 30 `
  --max-total-searches 80
```

## 12. Recommended Test Order

Once search quota is available again, use this order:

1. `position=4`
   - best test for false-candidate elimination
   - success means the new hard-conflict logic is actually changing answer selection

2. `position=5`
   - another false-candidate elimination test
   - good for book-title disambiguation behavior

3. `position=9`
   - checks whether better candidate state also helps endgame behavior on near-complete tasks

4. `position=2`
   - harder case
   - useful after the first three because it mixes candidate discovery failure with false-path dominance

5. mini batch: `4,5,9`

6. full batch: `2-9`

## 13. What To Look For In New Results

When rerunning, do not only check final answer. Also inspect whether:

- `candidate_records` appear in compact state / snapshots
- clearly false candidates accumulate `hard_conflicts`
- wrong candidates get downgraded or eliminated instead of staying “strong”
- finalizer avoids converging on a candidate that still carries unresolved hard conflict
- `Unknown` outcomes happen for cleaner reasons, rather than because state became muddy

## 14. Suggested Manual Evaluation Checklist

For each rerun:

1. Compare extracted answer to gold answer manually.
2. Check whether the run still converged on the old false candidate.
3. Inspect trajectory for whether candidate conflicts were explicitly written.
4. Inspect whether candidate state became cleaner near wrap-up.
5. Note whether failure mode changed:
   - wrong answer
   - `Unknown`
   - improved but still incomplete

## 15. Short Resume Summary

If someone resumes this work later, the shortest accurate summary is:

- `0413_v3` is the active workspace
- environment is `D:\anaconda3\envs\agent_safety`
- fixed BrowseComp seed is `123`
- main sample positions are `1-9` with `0` skipped
- current code changes focus on structured candidate tracking and hard-conflict elimination
- current blocker is Serper quota
- first rerun to try after quota returns is `position=4`
