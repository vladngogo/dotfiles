#!/usr/bin/env bash
# review-verdict.sh — read the reviewer's structured output on stdin and exit 0
# only if its verdict is "looks good". Lets branch protection gate merges on
# the verdict, not just on the review job having run.
set -euo pipefail

verdict="$(jq -r '.verdict // empty' 2>/dev/null || true)"
case "$verdict" in
    "looks good") echo "Review verdict: looks good" ;;
    "needs changes") echo "Review verdict: needs changes" >&2; exit 1 ;;
    *) echo "No review verdict in the structured output" >&2; exit 1 ;;
esac
