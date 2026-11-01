#!/usr/bin/env bash
# review-agent.sh — agent-eval's system under test: replay one PR into the
# reviewer offline, with no tools that can reach GitHub.
#
# Runs in the case worktree, checked out at the PR head. stdin is the case
# prompt; its first line is "PR_BASE=<commit>". Env:
#   REVIEW_EVAL_ROOT  checkout whose reviewer prompt is under test (required)
#   REVIEW_MODEL      DeepSeek model (default deepseek-v4-pro)
#   DEEPSEEK_KEY_FILE file holding the API key (default ~/.config/deepseek/api_key)
#
# Prints the review, then one JSON line with cost, turns and verdict. The
# verdict also goes to $(git rev-parse --git-dir)/eval-verdict for checks.
set -euo pipefail

: "${REVIEW_EVAL_ROOT:?set to the checkout whose reviewer is under test}"
model="${REVIEW_MODEL:-deepseek-v4-pro}"
key_file="${DEEPSEEK_KEY_FILE:-$HOME/.config/deepseek/api_key}"

case_prompt="$(cat)"
base="$(sed -n '1s/^PR_BASE=//p' <<<"$case_prompt")"
[ -n "$base" ] || { echo "case prompt must start with PR_BASE=<commit>" >&2; exit 64; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
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

# Only this process gets the key, and only project settings load, so the
# user's own hooks and plugins stay out of the run.
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic \
ANTHROPIC_API_KEY="$(<"$key_file")" \
env -u ANTHROPIC_AUTH_TOKEN -u CLAUDE_CODE_OAUTH_TOKEN \
claude -p --model "$model" --max-turns 15 --setting-sources project \
    --tools Read,Grep,Glob --allowedTools Read,Grep,Glob \
    --json-schema '{"type":"object","properties":{"verdict":{"type":"string","enum":["looks good","needs changes"]}},"required":["verdict"]}' \
    --output-format stream-json --verbose < "$tmp/prompt" > "$tmp/stream.jsonl" || true

# With a schema the final result holds only the verdict, so take the review
# text from the assistant messages instead.
jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "text") | .text' \
    "$tmp/stream.jsonl"
echo
jq -s 'map(select(.type == "result")) | last // {}' "$tmp/stream.jsonl" > "$tmp/out.json"
jq -r '.structured_output.verdict // "none"' "$tmp/out.json" > "$(git rev-parse --git-dir)/eval-verdict"
jq -c '{total_cost_usd, num_turns, duration_ms, subtype, verdict: (.structured_output.verdict // null)}' "$tmp/out.json"
