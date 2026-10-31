---
name: build-evals
description: Build a small end-to-end eval set for an agent workflow from real past runs (issues, PRs, transcripts). Use before changing an agent's structure, prompts, skills, or model, so the change can be measured.
---

# Build evals

Goal: a set of ~10 golden tasks that can be re-run against any version of the
workflow and graded the same way each time.

## Steps

1. **Collect real cases.** Pull finished work: issue text, the merged diff,
   review comments, and any decision recorded afterwards. Prefer cases that
   needed a correction or a judgment call; easy ones don't discriminate.
2. **Write one file per case** under `evals/cases/<id>.md` (or the repo's
   existing eval location) with:
   - `input`: exactly what the agent receives (issue text, repo ref).
   - `rubric`: 3–6 checkable statements about the final result. Grade the
     outcome, not the path taken.
   - `must_not_break`: hard rules the run must respect (gated paths, migration
     rules, no secrets). Any violation fails the case outright.
3. **Add the must-not-break cases deliberately.** Every hard rule in the repo's
   `AGENTS.md` needs at least one case that would tempt the agent to break it.
4. **Record a baseline.** Run the current workflow on every case at least 3
   times; agent runs are noisy and a single run hides intermittent failures.
   Save per-case pass/fail plus cost and wall time.
5. **Report per case, not just the aggregate.** A flat average can hide a
   case that went from always-pass to sometimes-fail.

## Grading

Use a script for anything mechanical (tests pass, file untouched, PR opened).
Use a model grader with the rubric only for judgment items, and spot-check
its grades by hand on the first run.
