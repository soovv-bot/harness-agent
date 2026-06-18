# SearchHarness Training Notes

This directory contains training-data utilities for adapting SearchHarness.

## Planner SFT First

The safest first training target is still SFT from successful stronger-model trajectories, but the harness now records all trainable agent calls separately:

1. Use a stronger model to run SearchHarness and produce successful trajectories.
2. Extract planner, executor, query critic, subtask critic, and finalizer turns as needed.
3. Train smaller role-specific models to map:

```text
question + compact harness state + execution feedback -> next planner output
```

The harness still owns candidate-state merging, execution history, budgets, and task-level orchestration.

## Export Script

`export_planner_sft.py` converts merged SearchHarness trajectories into verl-style `messages` samples.

Default behavior:

- scans `training_trajectories/**/task_*.json`,
- keeps only completed successful trajectories,
- treats a trajectory as successful when `metadata.is_correct` is true or the final `<answer>` matches `docs/seed123_k10_full.json`,
- removes partial/running snapshots,
- replaces old trajectory system prompts with the current `planning_agent_prompt_v3.md` prompt,
- keeps only current-schema planning targets unless `--allow-legacy-planning-schema` is set,
- writes both JSONL for auditing and parquet for verl SFT.

Example:

```powershell
D:\anaconda3\envs\agent_safety\python.exe training\export_planner_sft.py `
  --trajectory-glob "training_trajectories/**/task_*.json" `
  --output-jsonl training\data\planner_sft_current_schema_completed.jsonl `
  --output-parquet training\data\planner_sft_current_schema_completed.parquet `
  --answer-file docs\seed123_k10_full.json `
  --success-policy answer_match_or_correct `
  --system-prompt-file planning_agent_prompt_v3.md
```

## Trajectory Layout

New runs write merged compatibility files plus per-agent message files:

- `training_trajectories/<model>/task_000003.json`
- `training_trajectories/task_000003/planner/turn_000.json`
- `training_trajectories/task_000003/executor/turn_000.json`
- `training_trajectories/task_000003/query_critic/turn_000.json`
- `training_trajectories/task_000003/subtask_critic/turn_000.json`
- `training_trajectories/task_000003/finalizer/turn_000.json`
