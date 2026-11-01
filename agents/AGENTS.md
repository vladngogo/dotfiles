# Global agent instructions

Applies in every repo. A repo's own `AGENTS.md` overrides anything here.

## Environment

- Linux (Pop!_OS, apt-based). Other machines vary, so check `uname` before
  assuming paths or package managers.
- Primary languages: Python and SQL.

## How I work

- Plan from the end goal backwards.
- Prefer efficient, repeatable workflows over one-off fixes.
- Analogies help when introducing a new concept.

## Communication

- Concise by default. Expand only when asked or when the topic needs it.
- No preamble, no recap of what I just said, no flattery.
- Push back directly when an approach has problems, and offer an alternative.
  If I'm asking the wrong question, say so before answering it.

## Code

- For edits, show only the changed function or block, not the whole file.
- Comment only where the "why" isn't obvious.
- Brief explanation after the code, not before.

## Working rules

- Check before building: look for a built-in command, an installed skill or
  plugin, a packaged tool, or something in my dotfiles that already does the
  job, and propose reuse first.
- Check facts about the machine (hardware, distro, versions) with a command
  before relying on them.
- Verify before claiming done: run the repo's tests/linters on what you changed
  and report failures as they are.
- One change at a time when tuning agent behaviour; measure before and after.
- Hard rules belong in tools, hooks, or CI, not only in prose. If a rule here
  matters enough to never break, it should also be enforced somewhere.
- Never commit secrets, credentials, or machine-specific paths.

## Commands I run

- sudo can't prompt in your shell, so don't try it. Give me every root command
  in one copy-paste block per host, labelled with the host, and wait for me to
  confirm I ran it.
- Single-quote anything containing `!`: my interactive shell does history
  expansion.

## Responding to review

- Fixed as suggested: don't reply; resolve the thread. The commit shows the fix.
- Declined, partly fixed, or fixed differently: reply in the thread with the
  reason, then resolve it. The reply is the decision record.
- Reviewer was wrong: reply with the evidence (a test, a counter-example), then
  resolve.
- Never resolve a thread you didn't address. One reply per thread; no
  "thanks" or restating the comment.

## Pull requests

Opening a PR means seeing it through to merge, without waiting to be asked:

- Work in a worktree on its own branch, never in a checkout another session
  may be using.
- Before opening the PR, verify as in "Working rules", get a local code review
  of the whole branch (Claude Code: `/code-review`; Codex: `/review`), fix what
  it finds, and re-read your diff looking for what's wrong. Before each later
  push, do the same for just the new commits. CI review should confirm, not
  discover.
- After pushing, watch the PR: wait for checks (`gh pr checks <n> --watch`)
  and for the review of the current head commit.
- Handle each review as above, push, and wait for the re-review. If you only
  replied (declined a finding, no push), re-run the review job instead
  (`gh run rerun <run-id>`).
- Turn on auto-merge (`gh pr merge <n> --auto --merge --delete-branch`).
  Branch protection merges only when the checks and the review job pass, and
  the review job fails unless the verdict is "looks good". Never bypass it with
  `--admin`.
- Stop and ask instead of merging when a fix would change scope or a decision
  I made, the reviewer and you still disagree after replying, or a third
  round of review still finds new issues.
