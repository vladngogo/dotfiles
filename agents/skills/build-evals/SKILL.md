---
name: build-evals
description: Build and run an end-to-end eval set for an agent workflow from real past runs (issues, PRs, transcripts), using the agent-eval CLI. Use before changing an agent's structure, prompts, skills, or model, so the change can be measured.
---

# Build evals

Goal: ~10 golden cases that `agent-eval` can re-run against any version of the
workflow and grade the same way each time.

## The loop

```bash
agent-eval new <id>                      # scaffold evals/cases/<id>.toml
agent-eval run --label baseline          # every case x 3 runs, in parallel worktrees
# ...change ONE thing (skill, prompt, model, harness)...
agent-eval run --label <change>
agent-eval compare baseline <change>     # per-case table; exit 1 on regression/violation
```

While iterating, use `-k <substr>` and `--runs 1` for fast feedback on the
cases you're targeting. Always do a full run (`--runs 3`+) before accepting a
change: agent runs are noisy and one run hides intermittent breaks.

## Writing a case

1. **Start from real work.** Issue text, merged diff, review comments, and any
   decision recorded afterwards. Prefer cases that needed a correction or a
   judgment call; easy ones don't discriminate.
2. **`base`**: pin the commit the work started from, not `HEAD`, so the case
   stays valid as the repo moves.
3. **`prompt`**: exactly what the agent receives.
4. **`checks`**: shell commands that must exit 0 (tests, greps, a script).
   Prefer these over rubric items whenever the thing is mechanically checkable.
5. **`must_not_break`**: hard rules. Every hard rule in the repo's `AGENTS.md`
   needs at least one case that tempts the agent to break it.
   `{base}` expands to the case's base ref, e.g.
   `git diff --quiet {base} -- app/billing/`.
6. **`rubric`**: 3–6 judgment statements about the outcome, graded by a model
   against the diff and final output. Grade the result, not the path taken.
   Spot-check the grader's verdicts by hand in `evals/results/<label>/runs.jsonl`
   on the first run.

## Config (`evals/config.toml`, all optional)

```toml
agent = "claude -p --output-format json --permission-mode acceptEdits"  # prompt on stdin
grader = "claude -p --output-format text --tools ''"
setup = "python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt"
runs = 3
jobs = 2
timeout_s = 1800
[env]
WORKTREE_PORT_OFFSET = "{slot}"   # {slot} is unique per concurrent run
```

The agent command is the system under test. Point it at whatever harness you
are evaluating (a script, an SDK app, a different CLI). Cost is read from a
`total_cost_usd` field if the agent prints JSON.

Commit `evals/cases/` and `evals/config.toml`. Add `evals/results/*/logs/` to
`.gitignore`. Committing `summary.json` for the baseline is fine.
