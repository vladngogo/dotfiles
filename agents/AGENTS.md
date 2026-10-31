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

- Verify before claiming done: run the repo's tests/linters on what you changed
  and report failures as they are.
- One change at a time when tuning agent behaviour; measure before and after.
- Hard rules belong in tools, hooks, or CI, not only in prose. If a rule here
  matters enough to never break, it should also be enforced somewhere.
- Never commit secrets, credentials, or machine-specific paths.

## Responding to review

- Fixed as suggested: don't reply; resolve the thread. The commit shows the fix.
- Declined, partly fixed, or fixed differently: reply in the thread with the
  reason, then resolve it. The reply is the decision record.
- Reviewer was wrong: reply with the evidence (a test, a counter-example), then
  resolve.
- Never resolve a thread you didn't address. One reply per thread; no
  "thanks" or restating the comment.
