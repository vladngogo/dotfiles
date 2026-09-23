#!/usr/bin/env bash
# install.sh — symlink dotfiles into place
set -euo pipefail

DOTFILES="$(cd "$(dirname "$0")" && pwd)"

# Back up $1 to a timestamped path so repeated runs never clobber an earlier backup.
backup() {
    local target="$1"
    if [ -e "$target" ] && [ ! -L "$target" ]; then
        local dest
        dest="${target}.bak.$(date +%Y%m%d%H%M%S)"
        echo "Backing up existing $target → $dest"
        mv "$target" "$dest"
    fi
}

# ── nvim ──────────────────────────────────────────────────────
NVIM_DIR="$HOME/.config/nvim"
mkdir -p "$NVIM_DIR"

for f in init.lua lazy-lock.json; do
    target="$NVIM_DIR/$f"
    backup "$target"
    ln -sf "$DOTFILES/nvim/$f" "$target"
    echo "Linked $target → $DOTFILES/nvim/$f"
done

# ── tmux ──────────────────────────────────────────────────────
TMUX_TARGET="$HOME/.tmux.conf"
backup "$TMUX_TARGET"
ln -sf "$DOTFILES/tmux/tmux.conf" "$TMUX_TARGET"
echo "Linked $TMUX_TARGET → $DOTFILES/tmux/tmux.conf"

# ── treesitter prerequisites ──────────────────────────────────
# nvim-treesitter (main branch) shells out to `tree-sitter build` for every
# parser, so a matching CLI must exist before nvim first starts. These are
# warnings, not failures: the symlinks above are still valid without them.
TS_CLI_MIN="0.26.1"

version_lt() {
    [ "$1" = "$2" ] && return 1
    [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)" = "$1" ]
}

echo ""
if ! command -v tree-sitter >/dev/null 2>&1; then
    echo "WARNING: tree-sitter CLI not found — parsers cannot be built."
    echo "  Without it nvim starts fine but has no syntax highlighting."
    echo "  Install (>= $TS_CLI_MIN, via a package manager, NOT npm):"
    echo "    macOS:  brew install tree-sitter-cli"
    echo "    Linux:  cargo install tree-sitter-cli   # or your distro package"
else
    ts_path="$(command -v tree-sitter)"
    ts_version="$(tree-sitter --version 2>/dev/null | awk '{print $2}')"

    if [ -n "$ts_version" ] && version_lt "$ts_version" "$TS_CLI_MIN"; then
        echo "WARNING: tree-sitter $ts_version is older than $TS_CLI_MIN ($ts_path)."
        echo "  The nvim-treesitter main branch requires >= $TS_CLI_MIN. Upgrade it."
    else
        echo "tree-sitter ${ts_version:-unknown} OK ($ts_path)"
    fi

    # An x86_64 CLI on an arm64 host builds parsers nvim cannot dlopen. This is
    # the Rosetta/Apple-Silicon trap: everything looks installed but nothing loads.
    # Only inspect real executables — version-manager shims are wrapper scripts
    # with no architecture of their own, and would report a false mismatch.
    host_arch="$(uname -m)"
    if command -v file >/dev/null 2>&1; then
        ts_file_type="$(file -b "$ts_path" 2>/dev/null || true)"
        case "$ts_file_type" in
            *Mach-O*|*ELF*)
                if ! printf '%s' "$ts_file_type" | grep -q "$host_arch"; then
                    echo "WARNING: $ts_path is not $host_arch — parsers it builds will fail"
                    echo "  to load with \"incompatible architecture\". Reinstall for $host_arch."
                fi
                ;;
        esac
    fi
fi

echo ""
echo "Done! Restart tmux and nvim to pick up changes."
echo ""
echo "On a new machine nvim auto-installs parsers on first launch. If highlighting"
echo "is missing, run :checkhealth vim.treesitter and :TSUpdate."
