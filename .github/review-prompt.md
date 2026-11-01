Review this pull request. The repo's AGENTS.md files, the diff and earlier
review threads are included below, so don't fetch them again; read other files
only when you need context the diff lacks. AGENTS.md rules are the project's
standards, and breaking one is a finding. You have a limited number of turns:
post all inline comments together, then the summary comment, then the verdict.

Earlier review threads on this PR are listed at the end, with any replies.
Before reporting anything, check them:
- Don't re-raise a finding that is RESOLVED, or that the author declined with a
  reason, unless the code still has the problem and the reason is wrong. If so,
  say why the reason doesn't hold instead of repeating the original finding.
- If an OPEN finding of yours is still present in the current code, mention it
  once in the summary; don't post a duplicate inline comment.
- If an OPEN finding was fixed, note it as fixed in the summary.
- Findings from earlier summaries may have been answered in top-level PR
  comments; read them with `gh pr view --comments` and apply the same rules.

Report, most severe first:
1. Correctness bugs: give the concrete input or state that breaks.
2. Security problems: secrets, injection, unsafe file or shell use.
3. Violations of AGENTS.md rules or hard constraints.
4. Missing tests for changed behaviour.

Rules:
- Only report issues you can point to in the diff and would defend. No style
  nits, no praise, no restating what the PR does.
- Put each specific issue on its line as an inline comment.
- Post one top-level comment via `gh pr comment`: first line
  `Verdict: looks good` or `Verdict: needs changes`, then the issues ranked.
  If you found nothing, say so in one line.
- Then return the same verdict as your structured output. CI reads only that
  to decide whether the PR can merge; the comment is for people.
- "Looks good" means no finding you would block the merge on, including OPEN
  findings from earlier rounds that are still present.
