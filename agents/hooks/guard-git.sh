#!/usr/bin/env bash
# guard-git.sh — refuse risky git commands issued by an agent.
#
# Input: a shell command as $1, or a Claude Code PreToolUse JSON payload on
# stdin (tool_input.command). Exit 2 blocks the command; stderr is shown to
# the agent so it can adjust.
set -euo pipefail

if [ $# -gt 0 ]; then
    cmd="$1"
else
    cmd="$(jq -r '.tool_input.command // empty')"
fi

case "$cmd" in
    *"git push"*) ;;
    *) exit 0 ;;
esac

protected='^(main|master)$'

if printf '%s' "$cmd" | grep -Eq -- '(--force([^-]|$)|[[:space:]]-f([[:space:]]|$))'; then
    echo "Blocked: force push. Use --force-with-lease, and only on your own branch." >&2
    exit 2
fi

if printf '%s' "$cmd" | grep -Eq -- 'git push.*[[:space:]:](main|master)([[:space:]]|$)'; then
    echo "Blocked: pushing to main/master. Push a feature branch and open a PR." >&2
    exit 2
fi

# Without an explicit refspec, `git push` on main pushes main.
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
if [[ "$branch" =~ $protected ]]; then
    push_args="${cmd#*git push}"
    push_args="${push_args%%[;&|]*}"
    positional=0
    read -ra words <<< "$push_args"
    for w in "${words[@]}"; do
        [[ "$w" == -* ]] || positional=$((positional + 1))
    done
    if [ "$positional" -lt 2 ]; then
        echo "Blocked: current branch is $branch. Create a feature branch before pushing." >&2
        exit 2
    fi
fi

exit 0
