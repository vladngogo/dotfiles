Review this pull request. Read AGENTS.md (and any AGENTS.md in touched
directories) first: its rules are the project's standards, and breaking one is
a finding.

Report, most severe first:
1. Correctness bugs: give the concrete input or state that breaks.
2. Security problems: secrets, injection, unsafe file or shell use.
3. Violations of AGENTS.md rules or hard constraints.
4. Missing tests for changed behaviour.

Rules:
- Only report issues you can point to in the diff and would defend. No style
  nits, no praise, no restating what the PR does.
- Put each specific issue on its line as an inline comment.
- Finish with one top-level comment via `gh pr comment`: a verdict (looks good /
  needs changes) and the issues ranked. If you found nothing, say so in one line.
