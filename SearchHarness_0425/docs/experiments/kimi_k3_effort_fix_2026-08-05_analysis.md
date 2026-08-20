# Kimi K3 Effort-Mapping Fix — Verification Test (2026-08-05)

## TL;DR
**Effort-mapping fix (minimal→low for Kimi K3) is a clear win.** Planner 0-content
eliminated (74%→0%), planner reasoning concise (30k→900c mean), test correct in
805s. Profile system (model_profiles.yaml) added so future model switches need
only a YAML edit — no code changes.

## Test
- Model: Kimi-K3, EXECUTOR_THINKING=high, LLM_THINKING_BUDGET_TOKENS=0
- Question (pos 3): "A musical band released their third studio album between
  1980 and 2000... One of the songs describes the narrator's unrealized romance..."
- Correct answer: **Abangan 2024**
- Result: **CORRECT** ✓, 805.0s, 4 iterations, finished naturally
- Output: results/kimi_k3_effort_fix_pos3_20260804.json
- Log: logs/test_kimi_k3_effort_fix_20260804.log

## Effort-mapping impact (the fix under test)

| Metric | Before (Kimi K3 "max" fallback) | After (minimal→low) |
|--------|-------------------------------|---------------------|
| Planner reasoning (mean) | 30,000+ chars | **900 chars** |
| Planner 0-content rate | 59–74% | **0%** |
| Planner always produces content | no | **yes (9/9)** |
| Planner latency (mean) | 60–80s | **13.2s** |

The root cause was confirmed: Kimi K3 only honors `low|high|max`. Sending
`minimal` (budget=0) was silently remapped to `max` (strongest), filling the
token budget with 30k reasoning and starving content. Snapping `minimal→low`
makes the planner produce concise reasoning + real content every turn.

## Per-role stats (this run)

### PLANNER (9 calls, effort="low")
- reasoning: min=159 max=2119 mean=900c
- content: min=781 max=3362 mean=1841c  ← all calls produced content
- true 0-content (content=0 & tool_calls=0): **0/9 (0%)**
- latency: min=5.3 max=23.5 mean=13.2s

### EXECUTOR (24 calls, effort="high")
- reasoning: min=47 max=4829 mean=1965c
- content: min=0 max=5631 mean=386c
- true 0-content: 2/24 (8%) — recovered by structurer/next-turn
- content=0 with tool_calls (normal tool-first): 12/24 (50%)
- latency: min=4.3 max=34.4 mean=15.6s
- Worst case: 98.8s, 17466c reasoning, 0 content (executor "high" starved once)

## Other findings
- **force-tool-call fix: 0 triggers** this run. The 2 executor 0-content cases
  occurred in verification phase (not candidate_generation), where force-tool
  doesn't apply; structurer/next-turn recovered them.
- **AnswerVerifier**: inconclusive verdict → failure-safe kept correct answer.
  Planner produced a detailed chain: Eraserheads → "Ang Huling El Bimbo"
  (Cutterpillow 1995) → the jukebox musical (2018) → final show Jul 23 2023 →
  screen flashed "Abangan 2024".
- **Note**: this run's question (Abangan 2024) differs from the prior force-tool
  run (Whitesnake) despite both being `--positions 3` — the fixed sample mapped
  position 3 to a different question (sample/dataset changed between runs).
  Times are therefore not directly comparable across those two runs.

## Profile system (new)
Replaced hardcoded `_is_kimi_model` + `_snap_effort_for_model` with a
data-driven config:
- `model_profiles.yaml` — per-model: thinking_enabled, supported_efforts,
  effort_mapping, preserve_reasoning_history, minimal_effort_is_honored
- `model_profiles.py` — loader + ModelProfile + substring matching (longest
  wins, "default" fallback, built-in defaults if YAML missing)
- `llm_reasoning_compat.py` — build_chat_completion_kwargs and
  _requested_effort_is_minimal now read from profiles
- Unit tests confirm profile-based behavior == previous hardcoded behavior
- **Adding a new model = edit YAML only, no code changes**

## Recommendation
Keep Kimi-K3 + effort-fix (minimal→low) + executor=high as the default config.
The planner is now efficient (0% 0-content, concise reasoning) and the executor
recovers from its rare 0-content. For further speed, could experiment with
executor="low" for Kimi K3, but risk tool-call starvation (the original
problem executor=high solved).
