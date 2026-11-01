#!/usr/bin/env bash
# review-agent.sh — agent-eval's system under test: replay one PR into the
# reviewer offline, with no tools that can reach GitHub.
#
# Runs in the case worktree, which agent-eval creates at the PR's base; it
# checks out the PR head itself, so agent-eval's `git diff {base}` (what the
# grader sees) is the PR diff. stdin is the case prompt; its first line is
# "PR_HEAD=<commit>". Env:
#   REVIEW_EVAL_ROOT  checkout whose reviewer prompt is under test (required)
#   REVIEW_MODEL      DeepSeek model (default deepseek-flash, as in CI)
#   REVIEW_MAX_TURNS  optional turn cap (none by default, as in CI)
#   DEEPSEEK_KEY_FILE file holding the API key (default ~/.config/deepseek/api_key)
#
# Prints the review, then one JSON line with model, cost, turns and verdict.
# The verdict also goes to $(git rev-parse --git-dir)/eval-verdict for checks.
# Exits non-zero if the reviewer run didn't finish cleanly.
set -euo pipefail

: "${REVIEW_EVAL_ROOT:?set to the checkout whose reviewer is under test}"
model="${REVIEW_MODEL:-deepseek-flash}"
max_turns="${REVIEW_MAX_TURNS:-}"
[[ "$max_turns" =~ ^[0-9]*$ ]] || { echo "REVIEW_MAX_TURNS must be a whole number" >&2; exit 64; }
key_file="${DEEPSEEK_KEY_FILE:-$HOME/.config/deepseek/api_key}"

case_prompt="$(cat)"
head="$(sed -n '1s/^PR_HEAD=//p' <<<"$case_prompt")"
[ -n "$head" ] || { echo "case prompt must start with PR_HEAD=<commit>" >&2; exit 64; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
base="$(git rev-parse HEAD)"
git checkout -q --detach "$head"
git diff "$base...HEAD" > "$tmp/diff"
echo "No earlier review threads." > "$tmp/threads"

# Use the reviewer instructions under test, not the ones at the PR's commit;
# restore the file afterwards so the case worktree stays as the PR left it.
cp "$REVIEW_EVAL_ROOT/.github/review-prompt.md" .github/review-prompt.md
DIFF_FILE="$tmp/diff" THREADS_FILE="$tmp/threads" \
    "$REVIEW_EVAL_ROOT/.github/scripts/review-prompt.sh" eval eval 0 > "$tmp/prompt"
git checkout -q -- .github/review-prompt.md
cat >> "$tmp/prompt" <<'EOF'

## Offline evaluation run

You can't post to GitHub in this run, so ignore the instructions about inline
comments and `gh pr comment`. Write your whole review as your final answer:
each finding as `path:line — issue`, most severe first, then a one-line
summary. Then return the verdict as structured output.
EOF

# Only this process gets the key. It runs with an empty config dir and only
# that dir's (empty) user settings, so neither the user's hooks nor any
# .claude/ settings in the replayed commit can run code alongside it.
rc=0
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic \
ANTHROPIC_API_KEY="$(<"$key_file")" \
CLAUDE_CONFIG_DIR="$tmp/claude-config" \
env -u ANTHROPIC_AUTH_TOKEN -u CLAUDE_CODE_OAUTH_TOKEN \
claude -p --model "$model" ${max_turns:+--max-turns "$max_turns"} --setting-sources user \
    --tools Read,Grep,Glob --allowedTools Read,Grep,Glob \
    --json-schema '{"type":"object","properties":{"verdict":{"type":"string","enum":["looks good","needs changes"]}},"required":["verdict"]}' \
    --output-format stream-json --verbose < "$tmp/prompt" > "$tmp/stream.jsonl" || rc=$?

# With a schema the final result holds only the verdict, so take the review
# text from the assistant messages instead.
jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "text") | .text' \
    "$tmp/stream.jsonl"
echo
jq -s 'map(select(.type == "result")) | last // {}' "$tmp/stream.jsonl" > "$tmp/out.json"
jq -r '.structured_output.verdict // "none"' "$tmp/out.json" > "$(git rev-parse --git-dir)/eval-verdict"
jq -c --arg model "$model" --arg max_turns "$max_turns" \
    '{model: $model, max_turns: ($max_turns | if . == "" then null else tonumber end), total_cost_usd, num_turns, duration_ms, subtype,
      verdict: (.structured_output.verdict // null)}' "$tmp/out.json"

# A crash, API error or turn cap fails the run even if review text came out.
# An API error can still report subtype "success", so require a verdict too.
[ "$rc" -eq 0 ] && [ "$(jq -r '.subtype // ""' "$tmp/out.json")" = success ] \
    && [ "$(jq -r '.structured_output.verdict // ""' "$tmp/out.json")" != "" ] || exit 1
