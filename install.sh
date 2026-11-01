#!/usr/bin/env bash
# install.sh — install Corgi and put dotfiles into place
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

# ── corgi ─────────────────────────────────────────────────────
install_corgi() (
    # Pin both the release URL and the script bytes before executing upstream code.
    local version="20261030T200700Z-f539bbadd798"
    local expected="f839bd299f8846d274acfdd08ddcc2dc10acf068be745f119976f56c572660f5"
    local tmp actual
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    curl --disable -fsSL --proto '=https' --proto-redir '=https' \
        --connect-timeout 10 --max-time 60 \
        "https://corgi.computer/releases/$version/install.sh" -o "$tmp/install.sh"
    if command -v sha256sum >/dev/null 2>&1; then
        actual="$(sha256sum "$tmp/install.sh")"
    elif command -v shasum >/dev/null 2>&1; then
        actual="$(shasum -a 256 "$tmp/install.sh")"
    else
        echo "Corgi installation requires sha256sum or shasum." >&2
        exit 1
    fi
    if [ "${actual%% *}" != "$expected" ]; then
        echo "Corgi installer checksum mismatch; refusing to execute it." >&2
        exit 1
    fi
    # Plain output also disables the upstream installer's interactive launch.
    TERM=dumb bash "$tmp/install.sh"
)

if ! command -v corgi >/dev/null 2>&1 && [ ! -x "${CORGI_INSTALL_BIN:-$HOME/.local/bin/corgi}" ]; then
    echo "Installing Corgi…"
    install_corgi
else
    echo "Corgi already installed"
fi

# Corgi rewrites viewer.json atomically, so seed it rather than symlinking it.
# Keep existing preferences (and all runtime/session state) on subsequent runs.
CORGI_STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/corgi"
CORGI_VIEWER="$CORGI_STATE_DIR/viewer.json"
if [ ! -e "$CORGI_VIEWER" ] && [ ! -L "$CORGI_VIEWER" ]; then
    mkdir -p "$CORGI_STATE_DIR"
    install -m 600 "$DOTFILES/corgi/viewer.json" "$CORGI_VIEWER"
    echo "Seeded $CORGI_VIEWER ← $DOTFILES/corgi/viewer.json"
else
    echo "Keeping existing $CORGI_VIEWER"
fi

# Retire only the link created by this repo's old installer, even if dangling.
if [ -L "$HOME/.tmux.conf" ] && [ "$(readlink "$HOME/.tmux.conf")" = "$DOTFILES/tmux/tmux.conf" ]; then
    rm "$HOME/.tmux.conf"
    echo "Removed legacy dotfiles link $HOME/.tmux.conf"
fi

# ── nvim ──────────────────────────────────────────────────────
NVIM_DIR="$HOME/.config/nvim"
mkdir -p "$NVIM_DIR"

for f in init.lua lazy-lock.json; do
    target="$NVIM_DIR/$f"
    backup "$target"
    ln -sf "$DOTFILES/nvim/$f" "$target"
    echo "Linked $target → $DOTFILES/nvim/$f"
done

# ── agents (tool-agnostic) ────────────────────────────────────
# agents/ holds instructions, skills and hooks that any agent can use. Each
# tool gets per-item links, never a link to its whole config dir: those dirs
# also hold credentials, history and session state that must stay local.
link() {
    local src="$1" target="$2"
    mkdir -p "$(dirname "$target")"
    backup "$target"
    ln -sfn "$src" "$target"
    echo "Linked $target → $src"
}

AGENTS_SRC="$DOTFILES/agents"

link "$DOTFILES/corgi/bin/corgi-annotate" "$HOME/.local/bin/corgi-annotate"
link "$DOTFILES/bin/keystash" "$HOME/.local/bin/keystash"

# Claude Code: CLAUDE.md just imports AGENTS.md so the content stays generic.
CLAUDE_DIR="$HOME/.claude"
link "$AGENTS_SRC/AGENTS.md" "$CLAUDE_DIR/AGENTS.md"
link "$DOTFILES/claude/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
# Claude Code and Corgi rewrite settings.json, so merge the repo's entries into
# the local file instead of linking it.
python3 "$DOTFILES/claude/merge-settings" "$DOTFILES/claude/settings.json" "$CLAUDE_DIR/settings.json"
for skill in "$AGENTS_SRC"/skills/*/; do
    skill="${skill%/}"
    link "$skill" "$CLAUDE_DIR/skills/$(basename "$skill")"
done
for hook in "$AGENTS_SRC"/hooks/*; do
    link "$hook" "$CLAUDE_DIR/hooks/$(basename "$hook")"
done

for bin in "$AGENTS_SRC"/bin/*; do
    link "$bin" "$HOME/.local/bin/$(basename "$bin")"
done
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) echo "WARNING: ~/.local/bin is not on PATH — add it to run corgi and the agent tools." ;;
esac

# Codex reads ~/.codex/AGENTS.md directly.
link "$AGENTS_SRC/AGENTS.md" "$HOME/.codex/AGENTS.md"


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
echo "Done! Run corgi in your project directory; restart nvim to pick up changes."
echo ""
echo "On a new machine nvim auto-installs parsers on first launch. If highlighting"
echo "is missing, run :checkhealth vim.treesitter and :TSUpdate."
