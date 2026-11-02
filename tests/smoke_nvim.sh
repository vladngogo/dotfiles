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
nvim --headless '+Lazy! restore' '+qa'
nvim --headless -S "$ROOT/setup/parsers.lua"
# A second run exercises the already-installed path too.
nvim --headless -S "$ROOT/setup/parsers.lua"
# Simulate an unusable existing parser (for example, copied from another CPU).
printf 'broken parser\n' > "$XDG_DATA_HOME/nvim/site/parser/python.so"
nvim --headless -S "$ROOT/setup/parsers.lua"
