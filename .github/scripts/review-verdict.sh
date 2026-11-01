#!/usr/bin/env bash
# review-verdict.sh REPO PR SINCE — exit 0 if the review posted since SINCE
# (ISO 8601 UTC) says "looks good", 1 otherwise. Lets branch protection gate
# merges on the verdict, not just on the review job having run.
#
# With --format-only SINCE, reads the issue-comments JSON array on stdin
# instead of calling the API (used by tests).
set -euo pipefail

# The prompt asks for a first line of exactly "Verdict: looks good" or
# "Verdict: needs changes"; tolerate markdown emphasis and case around it.
# shellcheck disable=SC2016  # jq's $since, not shell
JQ_VERDICT='
  .[]
  | select(.user.login == "github-actions[bot]" and .created_at >= $since)
  | .body | gsub("\r"; "") | split("\n")[0]
  | capture("^\\W*verdict\\W*(?<v>looks good|needs changes)"; "i").v
  | ascii_downcase'

verdict_from() {
    local verdict
    verdict="$(jq -r --arg since "$1" "$JQ_VERDICT" | tail -n 1)"
    case "$verdict" in
        "looks good") echo "Review verdict: looks good" ;;
        "needs changes") echo "Review verdict: needs changes" >&2; return 1 ;;
        *) echo "No review verdict posted since $1" >&2; return 1 ;;
    esac
}

if [ "${1:-}" = "--format-only" ]; then
    verdict_from "$2"
    exit
fi

[ $# -eq 3 ] || { echo "usage: $0 REPO PR SINCE" >&2; exit 64; }

# --slurp wraps the pages in one outer array ([[page1...], [page2...]]); add
# flattens it so tail sees comments in order across all of them.
gh api --paginate --slurp "repos/$1/issues/$2/comments" | jq 'add // []' | verdict_from "$3"
