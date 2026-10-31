---
name: fold-or-keep
description: Decide whether a subagent, pipeline stage, or orchestration step should be folded into the main agent loop as a skill or tool, or kept separate. Use when simplifying a multi-agent workflow or reviewing harness logic after a model upgrade.
---

# Fold or keep

Default: one agent loop with skills (procedure) and tools (hard limits,
lookups). A separate agent has to earn its place with eval results.

## Keep it separate only if

- The work is self-contained and parallel (e.g. one issue per worktree), and a
  fresh context window helps, or
- Folding it in measurably degrades results through context bloat, or
- It must talk to the user directly.

Split by **context**, not by job title. "Worker" and "reviewer" passing the
same task back and forth is a split by job title: each handoff loses detail.

## Procedure

1. Make sure an eval set and baseline exist (see the `build-evals` skill).
   No baseline, no change.
2. Interim step: call the subagent as a **tool** from the main loop instead of
   handing off control. Re-run evals.
3. Fold it: its prompt becomes a skill, its API calls become tools, its hard
   rules become tool-side checks that return a refusal the model can read.
4. Re-run every eval case 3+ times. Compare per case, especially
   `must_not_break` cases.
5. Keep the fold if it's no worse on quality. Revert if any case got worse
   and you can't fix it in the skill or tool.
6. One subagent per change. Never fold two at once.

## What stays in code

Cheap, nearly-always-needed loading and mechanical work (payload building,
setup, uploading evidence) stays as plain code or a tool, not a skill.
