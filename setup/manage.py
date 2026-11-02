#!/usr/bin/env python3
"""User-space setup after Homebrew has supplied the shared toolchain."""
import hashlib
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
FONT_VERSION = "3.5.1"
FONT_SHA256 = "04d5e8f903693f9dd13e16f867e994834e681eb3c72c0d337a770dcda09010cf"
BEGIN = "# >>> dotfiles environment >>>"
END = "# <<< dotfiles environment <<<"
VERSIONS = {"python3": (3, 11), "nvim": (0, 12), "tree-sitter": (0, 26, 1),
            "opencode": (2,)}


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def check_tools(commands):
    ok = True
    for command in commands:
        path = shutil.which(command)
        if not path:
            print(f"MISSING {command}")
            ok = False
            continue
        try:
            flag = "version" if command == "go" else "--version"
            result = subprocess.run([path, flag], capture_output=True, text=True, timeout=30)
            text = (result.stdout or result.stderr).strip().splitlines()
            version = re.search(r"\d+(?:\.\d+)+", text[0] if text else "")
            minimum = VERSIONS.get(command)
            valid = result.returncode == 0 and (not minimum or (
                version and tuple(map(int, version[0].split("."))) >= minimum))
            print(f"{'OK' if valid else 'FAIL'} {command}: {text[0] if text else 'no version'} ({path})")
            ok = bool(valid) and ok
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"FAIL {command}: {exc}")
            ok = False
    return ok


def shell_setup(home):
    config = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "dotfiles"
    config.mkdir(parents=True, exist_ok=True)
    target = config / "env.sh"
    source = ROOT / "shell/env.sh"
    if target.is_symlink() and target.resolve() == source:
        pass
    else:
        if target.exists() or target.is_symlink():
            target.rename(target.with_name(f"env.sh.bak.{uuid.uuid4().hex}"))
        target.symlink_to(source)
    block = f"{BEGIN}\n. {shlex.quote(str(target))}\n{END}"
    zsh = Path(os.environ.get("ZDOTDIR") or home) / ".zshrc"
    # Bash reads only the first existing login file, unlike interactive bashrc.
    login = next((home / name for name in (".bash_profile", ".bash_login", ".profile")
                  if (home / name).exists()), home / ".profile")
    for path in dict.fromkeys((home / ".bashrc", login, zsh)):
        text = path.read_text() if path.exists() else ""
        if text.count(BEGIN) != text.count(END) or text.count(BEGIN) > 1:
            raise ValueError(f"Malformed dotfiles block in {path}; repair it before setup")
        if BEGIN in text:
            updated = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END),
                             lambda _: block, text, flags=re.S)
        else:
            updated = text + ("\n" if text and not text.endswith("\n") else "") + block + "\n"
        if text != updated:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                # copy2 creates its destination with the umask before copying modes.
                fd, backup = tempfile.mkstemp(prefix=f"{path.name}.bak.", dir=path.parent)
                try:
                    with os.fdopen(fd, "wb") as target, path.open("rb") as source:
                        shutil.copyfileobj(source, target)
                    shutil.copystat(path, backup)
                except BaseException:
                    Path(backup).unlink(missing_ok=True)
                    raise
            path.write_text(updated)


def install_font(home):
    if platform.system() != "Linux":
        return  # Homebrew installs the same family as a cask on macOS.
    data = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    dest = data / "fonts/dotfiles-jetbrains-mono"
    marker = dest / ".version"
    if marker.exists() and marker.read_text() == FONT_VERSION and list(dest.glob("*.ttf")):
        return
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "font.tar.xz"
        run("curl", "--disable", "-fsSL", "--proto", "=https", "--proto-redir", "=https",
            "--connect-timeout", "10", "--max-time", "300",
            f"https://github.com/ryanoasis/nerd-fonts/releases/download/v{FONT_VERSION}/JetBrainsMono.tar.xz",
            "-o", archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != FONT_SHA256:
            raise ValueError("Font checksum mismatch; refusing to install")
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as fonts:
            count = 0
            for member in fonts:
                if member.isfile() and Path(member.name).suffix == ".ttf":
                    with fonts.extractfile(member) as source:
                        (dest / Path(member.name).name).write_bytes(source.read())
                    count += 1
            if not count:
                raise ValueError("Font archive contains no TTF files")
        run("fc-cache", "-f", dest)
        marker.write_text(FONT_VERSION)


def doctor():
    ok = check_tools(("python3", "nvim", "tree-sitter", "git", "gh", "jq", "rg",
                      "shellcheck", "node", "npm", "go", "opencode", "claude", "codex"))
    for command in ("cc", "gopls", "corgi", "corgi-annotate", "keystash", "agent-eval", "agent-link"):
        found = shutil.which(command)
        print(f"{'OK' if found else 'MISSING'} {command}: {found or 'run ./setup.sh'}")
        ok = bool(found) and ok
    clipboard = ("pbcopy", "pbpaste") if platform.system() == "Darwin" else ("wl-copy", "wl-paste", "xclip")
    for command in clipboard:
        found = shutil.which(command)
        print(f"{'OK' if found else 'MISSING'} clipboard tool: {command}")
        ok = bool(found) and ok
    print("Select JetBrainsMono Nerd Font in your terminal; run dotfiles connections for local sign-in steps.")
    print("Credential contents and authentication state were not inspected.")
    return 0 if ok else 1


def cleanup():
    packages = []
    for kind in ("--formula", "--cask"):
        result = subprocess.run(["brew", "bundle", "list", f"--file={ROOT / 'Brewfile'}", kind],
                                capture_output=True, text=True, check=True)
        packages.extend(result.stdout.splitlines())
    if packages:
        run("brew", "cleanup", "--prune=all", *packages)


def main(action):
    if action == "doctor":
        return doctor()
    if not check_tools(VERSIONS):
        raise ValueError("Toolchain requirements not met; run dotfiles update or upgrade the failing formula")
    home = Path.home()
    npm = home / ".local/share/dotfiles/npm"
    # npm converges both missing and outdated packages. Keep its download cache
    # temporary so failures clean up too, without touching the user's npm cache.
    with tempfile.TemporaryDirectory(prefix="dotfiles-npm-") as cache:
        run("npm", "install", "--global", "--prefix", npm, "--cache", cache,
            "--no-audit", "--no-fund", "@anthropic-ai/claude-code@latest", "@openai/codex@latest")
    run("bash", ROOT / "install.sh")
    shell_setup(home)
    install_font(home)
    run("corgi", "update")
    run("corgi-annotate", "setup")
    # Restore the reviewed lockfile rather than silently moving plugin versions.
    run("env", "DOTFILES_SETUP=1", "nvim", "--headless", "-S", ROOT / "setup/plugins.lua")
    run("env", "DOTFILES_SETUP=1", "nvim", "--headless", "-S", ROOT / "setup/parsers.lua")
    result = doctor()
    if result == 0:
        cleanup()
        print("Setup complete. Open a new terminal; use corgi in a project and nvim to edit.")
    return result


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1]))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit(f"Setup stopped: {exc}. Fix the error and rerun ./setup.sh.")
