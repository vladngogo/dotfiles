#!/usr/bin/env bash
# review-prompt.sh OWNER REPO PR — print the reviewer's full prompt: the
# instructions, every tracked AGENTS.md, the diff and earlier review threads.
# Inlining them saves the reviewer several slow tool-call turns. Run from the
# repo root. Requires gh with GH_TOKEN set.
#
# DIFF_FILE and THREADS_FILE override the gh calls (used by tests).
set -euo pipefail

[ $# -eq 3 ] || { echo "usage: $0 OWNER REPO PR" >&2; exit 64; }

# Step outputs are capped at 1 MB; past this the reviewer fetches the rest.
MAX_DIFF_CHARS=200000

if [ -n "${DIFF_FILE:-}" ]; then diff="$(cat "$DIFF_FILE")"
else diff="$(gh pr diff "$3" --repo "$1/$2")"; fi
if [ -n "${THREADS_FILE:-}" ]; then threads="$(cat "$THREADS_FILE")"
else threads="$("$(dirname "$0")/review-threads.sh" "$1" "$2" "$3")"; fi

echo "REPO: $1/$2"
echo "PR NUMBER: $3"
echo
cat .github/review-prompt.md
echo
echo "## AGENTS.md files"
found=0
while IFS= read -r f; do
    found=1
    printf '\n### %s\n\n' "$f"
    cat "$f"
done < <(git ls-files -- 'AGENTS.md' '**/AGENTS.md')
[ "$found" = 1 ] || printf '\nNone.\n'
echo
echo "## Diff"
echo
if [ "${#diff}" -gt "$MAX_DIFF_CHARS" ]; then
    echo "(Truncated at $MAX_DIFF_CHARS characters; run \`gh pr diff $3\` for the rest.)"
    echo
fi
# Five backticks so fences inside a diffed markdown file can't close it.
echo '`````diff'
printf '%s\n' "${diff:0:$MAX_DIFF_CHARS}"
echo '`````'
echo
echo "## Earlier review threads on this PR"
echo
echo "$threads"
