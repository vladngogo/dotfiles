#!/usr/bin/env bash
# Bootstrap uses only the system shell; Python comes from the shared Brewfile.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
action="${1:-install}"
case "$action" in
    install|update|apply-update|doctor|plan|connections) ;;
    *) echo "Usage: ./setup.sh [install|update|doctor|plan|connections]" >&2; exit 64 ;;
esac
[ "$#" -le 1 ] || { echo "Expected one command" >&2; exit 64; }

os="$(uname -s)"
arch="$(uname -m)"
case "$os:$arch" in
    Darwin:arm64) ;;
    Darwin:*) echo "Use a native Apple Silicon terminal (uname -m must be arm64), not Rosetta." >&2; exit 1 ;;
    Linux:x86_64|Linux:aarch64)
        # shellcheck disable=SC1091
        . /etc/os-release
        case "$ID" in ubuntu|pop) ;; *) echo "Supported Linux distributions: Ubuntu and Pop!_OS." >&2; exit 1 ;; esac
        ;;
    *) echo "Unsupported platform: $os $arch" >&2; exit 1 ;;
esac

if [ "$action" = connections ]; then
    cat "$ROOT/setup/connections.txt"
    exit 0
fi
if [ "$action" = plan ]; then
    printf 'Platform: %s %s\n' "$os" "$arch"
    cat "$ROOT/Brewfile"
    echo "Also: Claude Code, Codex (user-local npm), Corgi, Plannotator, shell/config links."
    echo "Linux prerequisites: build-essential procps curl file git unzip fontconfig wl-clipboard xclip."
    echo "No provider accounts, endpoints, keys or login sessions are copied."
    exit 0
fi

if [ "$action" = update ]; then
    if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
        echo "Checkout has local changes; commit or stash them before dotfiles update." >&2
        exit 1
    fi
    git -C "$ROOT" pull --ff-only
    exec bash "$ROOT/setup.sh" apply-update
fi

brew_bin="$(command -v brew || true)"
if [ -z "$brew_bin" ]; then
    for candidate in /opt/homebrew/bin/brew /home/linuxbrew/.linuxbrew/bin/brew; do
        if [ -x "$candidate" ]; then brew_bin="$candidate"; break; fi
    done
fi
if [ -z "$brew_bin" ]; then
    echo "Homebrew is required. On this host, run the bootstrap commands in README.md, then rerun ./setup.sh." >&2
    exit 1
fi
prefix="$("$brew_bin" --prefix)"
if [ "$os" = Darwin ] && [ "$prefix" != /opt/homebrew ]; then
    echo "Apple Silicon requires native Homebrew at /opt/homebrew (found $prefix)." >&2
    exit 1
fi
if [ "$os" = Linux ] && [ "$prefix" != /home/linuxbrew/.linuxbrew ]; then
    echo "Use Homebrew's supported Linux prefix /home/linuxbrew/.linuxbrew (found $prefix)." >&2
    exit 1
fi
export PATH="$HOME/.local/share/dotfiles/npm/bin:$prefix/opt/python@3.13/libexec/bin:$prefix/bin:$prefix/sbin:$HOME/.local/bin:$PATH"

if [ "$action" != doctor ]; then
    if [ "$os" = Linux ]; then
        missing=0
        for package in build-essential procps curl file git unzip fontconfig wl-clipboard xclip; do
            if [ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" != "install ok installed" ]; then
                missing=1
            fi
        done
        if [ "$missing" = 1 ]; then
            cat >&2 <<'EOF'
Linux host — run this block yourself, then rerun ./setup.sh:
sudo apt-get update
sudo apt-get install -y build-essential procps curl file git unzip fontconfig wl-clipboard xclip
EOF
            exit 1
        fi
    elif ! xcode-select -p >/dev/null 2>&1; then
        echo "Mac host — run xcode-select --install, complete the installer, then rerun ./setup.sh." >&2
        exit 1
    fi
    export HOMEBREW_NO_INSTALL_CLEANUP=1
    "$brew_bin" update
    "$brew_bin" bundle --file="$ROOT/Brewfile"
fi
exec python3 "$ROOT/setup/manage.py" "$action"
