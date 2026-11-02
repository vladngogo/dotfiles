#!/usr/bin/env bash
# Networked smoke check: real locked plugins and parser builds in a disposable home.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_STATE_HOME="$HOME/.local/state"
export XDG_CACHE_HOME="$HOME/.cache"
export DOTFILES_SETUP=1
unset NVIM_APPNAME VIMINIT EXINIT
mkdir -p "$XDG_CONFIG_HOME/nvim"
cp "$ROOT/nvim/init.lua" "$ROOT/nvim/lazy-lock.json" "$XDG_CONFIG_HOME/nvim/"
nvim --headless -S "$ROOT/setup/plugins.lua"
echo "Plugin restore passed"
nvim --headless -S "$ROOT/setup/parsers.lua"
echo "Fresh parsers passed"
# A second run exercises the already-installed path too.
nvim --headless -S "$ROOT/setup/parsers.lua"
echo "Repeated parsers passed"
# Simulate an unusable existing parser (for example, copied from another CPU).
printf 'broken parser\n' > "$XDG_DATA_HOME/nvim/site/parser/python.so"
nvim --headless -S "$ROOT/setup/parsers.lua"
echo "Parser repair passed"
# Usable existing plugins must not hide a failed restore's fetch task.
DOTFILES_TEST_GIT="$(command -v git)"
DOTFILES_TEST_FETCH="$tmp/fetch-failed"
export DOTFILES_TEST_GIT DOTFILES_TEST_FETCH
mkdir -p "$tmp/bin"
cat > "$tmp/bin/git" <<'EOF'
#!/bin/sh
case " $* " in
    *" fetch "*)
        echo "Intentional test fetch failure" >&2
        printf 'observed\n' > "$DOTFILES_TEST_FETCH"
        exit 23
        ;;
esac
exec "$DOTFILES_TEST_GIT" "$@"
EOF
chmod +x "$tmp/bin/git"
if PATH="$tmp/bin:$PATH" nvim --headless \
    -c 'lua require("lazy.core.config").options.git.cooldown = 0' \
    -S "$ROOT/setup/plugins.lua" > "$tmp/restore-failure.log" 2>&1; then
    echo "Failed plugin fetch was incorrectly accepted" >&2
    exit 1
fi
if [ ! -f "$DOTFILES_TEST_FETCH" ]; then
    cat "$tmp/restore-failure.log" >&2
    exit 1
fi
echo "Failed plugin fetch correctly stops setup"
