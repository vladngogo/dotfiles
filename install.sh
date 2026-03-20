#!/usr/bin/env bash
# install.sh — symlink dotfiles into place
set -euo pipefail

DOTFILES="$(cd "$(dirname "$0")" && pwd)"

# ── nvim ──────────────────────────────────────────────────────
NVIM_DIR="$HOME/.config/nvim"
mkdir -p "$NVIM_DIR"

for f in init.lua lazy-lock.json; do
    target="$NVIM_DIR/$f"
    if [ -e "$target" ] && [ ! -L "$target" ]; then
        echo "Backing up existing $target → ${target}.bak"
        mv "$target" "${target}.bak"
    fi
    ln -sf "$DOTFILES/nvim/$f" "$target"
    echo "Linked $target → $DOTFILES/nvim/$f"
done

# ── tmux ──────────────────────────────────────────────────────
TMUX_TARGET="$HOME/.tmux.conf"
if [ -e "$TMUX_TARGET" ] && [ ! -L "$TMUX_TARGET" ]; then
    echo "Backing up existing $TMUX_TARGET → ${TMUX_TARGET}.bak"
    mv "$TMUX_TARGET" "${TMUX_TARGET}.bak"
fi
ln -sf "$DOTFILES/tmux/tmux.conf" "$TMUX_TARGET"
echo "Linked $TMUX_TARGET → $DOTFILES/tmux/tmux.conf"

echo ""
echo "Done! Restart tmux and nvim to pick up changes."
