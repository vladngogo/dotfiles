#!/usr/bin/env bash
# review-threads.sh OWNER REPO PR — print a PR's review threads as markdown,
# for the reviewer prompt. Read-only. Requires gh with GH_TOKEN set.
#
# With --format-only, reads the GraphQL JSON response on stdin instead of
# calling the API (used by tests).
set -euo pipefail

# shellcheck disable=SC2016  # jq's \(...) and $t, not shell
JQ_FORMAT='
  .data.repository.pullRequest.reviewThreads.nodes as $t
  | if ($t | length) == 0 then "No earlier review threads."
    else $t | map(
      "### `\(.path):\(.line // .originalLine // "?")` — "
      + (if .isResolved then "RESOLVED" else "OPEN" end)
      + (if .isOutdated then ", outdated" else "" end)
      + "\n"
      + (.comments.nodes | map(
          "- **\(.author.login // "ghost")**: "
          + (.body | gsub("\r"; "") | gsub("\n+"; " ") | .[0:600])
        ) | join("\n"))
    ) | join("\n\n")
    end'

if [ "${1:-}" = "--format-only" ]; then
    jq -r "$JQ_FORMAT"
    exit 0
fi

[ $# -eq 3 ] || { echo "usage: $0 OWNER REPO PR" >&2; exit 64; }

# shellcheck disable=SC2016  # $o/$r/$n are GraphQL variables, not shell
QUERY='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){
  reviewThreads(first:100){nodes{isResolved isOutdated path line originalLine
    comments(first:30){nodes{author{login} body}}}}}}}'

gh api graphql -f query="$QUERY" -F o="$1" -F r="$2" -F n="$3" | jq -r "$JQ_FORMAT"
