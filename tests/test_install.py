"""Exercise the installer in isolated homes without network or host installs."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home with spaces"
        self.home.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.tmpdir = self.base / "downloads"
        self.tmpdir.mkdir()
        # An allowlisted PATH prevents a host Corgi or tree-sitter from masking
        # the fresh-install path, and ensures curl can never reach the network.
        for command in ("bash", "basename", "dirname", "date", "mkdir", "mv",
                        "ln", "rm", "readlink", "install", "cat", "chmod", "mktemp"):
            (self.bin / command).symlink_to(shutil.which(command))
        for command in ("sha256sum", "shasum"):
            if path := shutil.which(command):
                (self.bin / command).symlink_to(path)
        self.env = {
            "HOME": str(self.home),
            "PATH": str(self.bin),
            "TERM": "xterm-256color",
            "SHELL": str(self.bin / "bash"),
            "TMPDIR": str(self.tmpdir),
        }
        self.viewer = self.home / ".local/state/corgi/viewer.json"
        self.launcher = self.home / ".local/bin/corgi"
        self.installer = self.home / "fake-installer.sh"
        self.installer.write_text("""set -eu
printf 'ran\n' > "$HOME/installer-ran"
[ "$TERM" = dumb ]
[ "${FAKE_INSTALL_FAIL:-0}" = 0 ]
mkdir -p "$HOME/.local/bin"
printf '#!/bin/sh\nexit 0\n' > "$HOME/.local/bin/corgi"
chmod 755 "$HOME/.local/bin/corgi"
""")
        # Substitute only the pinned digest in an isolated checkout so tests
        # exercise real hashing of the fixture rather than mocking verification.
        self.dotfiles = self.base / "dotfiles"
        self.dotfiles.mkdir()
        for directory in ("corgi", "nvim", "agents", "claude"):
            (self.dotfiles / directory).symlink_to(ROOT / directory)
        digest = hashlib.sha256(self.installer.read_bytes()).hexdigest()
        script, replacements = re.subn(r'expected="[0-9a-f]{64}"',
                                      f'expected="{digest}"', (ROOT / "install.sh").read_text())
        self.assertEqual(replacements, 1)
        (self.dotfiles / "install.sh").write_text(script)
        self.executable(self.bin / "curl", """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$HOME/curl.log"
while [ "$#" -gt 0 ]; do
    if [ "$1" = -o ]; then
        output=$2
        shift
    fi
    shift
done
cat "$HOME/fake-installer.sh" > "$output"
exit "${FAKE_CURL_FAIL:-0}"
""")

    def executable(self, path, content="#!/bin/sh\nexit 0\n"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o755)

    def run_install(self, success=True):
        result = subprocess.run(
            [str(self.bin / "bash"), str(self.dotfiles / "install.sh")],
            env=self.env, capture_output=True, text=True, timeout=30,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(list(self.tmpdir.iterdir()), "download staging directory leaked")
        return result

    def test_fresh_install_seeds_preferences_and_links_configs(self):
        self.run_install()
        self.assertTrue(os.access(self.launcher, os.X_OK))
        self.assertRegex((self.home / "curl.log").read_text(),
                         r"https://corgi\.computer/releases/[^/]+/install\.sh")
        self.assertEqual(json.loads(self.viewer.read_text()), {
            "preset": "corgi", "prefix": "ctrl_a", "theme": "corgi",
            "onboarding_complete": False,
        })
        self.assertFalse(self.viewer.is_symlink())
        self.assertEqual(self.viewer.stat().st_mode & 0o777, 0o600)
        for target, source in ((".config/nvim/init.lua", "nvim/init.lua"),
                               (".local/bin/corgi-annotate", "corgi/bin/corgi-annotate"),
                               (".claude/settings.json", "claude/settings.json"),
                               (".codex/AGENTS.md", "agents/AGENTS.md")):
            self.assertEqual((self.home / target).resolve(), ROOT / source)
        self.assertFalse((self.home / ".tmux.conf").is_symlink())

    def test_existing_corgi_on_path_skips_download(self):
        self.executable(self.bin / "corgi")
        self.run_install()
        self.assertFalse((self.home / "curl.log").exists())
        self.assertTrue(self.viewer.exists())

    def test_existing_local_launcher_off_path_skips_download(self):
        self.executable(self.launcher)
        self.run_install()
        self.assertFalse((self.home / "curl.log").exists())

    def test_xdg_preferences_and_session_state_survive_repeated_installs(self):
        self.executable(self.launcher)
        state = self.base / "custom state" / "corgi"
        state.mkdir(parents=True)
        self.env["XDG_STATE_HOME"] = str(state.parent)
        self.run_install()
        viewer = state / "viewer.json"
        self.assertTrue(viewer.is_file())
        self.assertFalse(self.viewer.exists())
        saved = '{"prefix":"ctrl_b","onboarding_complete":true,"future_option":42}\n'
        viewer.write_text(saved)
        workspace = state / "workspaces.json"
        workspace.write_text('{"local":"session"}\n')
        self.run_install()
        self.run_install()
        self.assertEqual(viewer.read_text(), saved)
        self.assertEqual(workspace.read_text(), '{"local":"session"}\n')
        self.assertFalse(list(state.glob("*.bak.*")))

    def test_removes_old_repo_link_even_when_dangling(self):
        self.executable(self.launcher)
        old = self.home / ".tmux.conf"
        old.symlink_to(self.dotfiles / "tmux/tmux.conf")
        self.run_install()
        self.assertFalse(old.is_symlink())
        self.assertFalse(old.exists())

    def test_preserves_unmanaged_tmux_config_and_links(self):
        self.executable(self.launcher)
        old = self.home / ".tmux.conf"
        old.write_text("personal configuration\n")
        self.run_install()
        self.assertEqual(old.read_text(), "personal configuration\n")
        old.unlink()
        custom = self.home / "custom-tmux.conf"
        custom.write_text("personal configuration\n")
        old.symlink_to(custom)
        self.run_install()
        self.assertTrue(old.is_symlink())
        self.assertEqual(old.resolve(), custom)
        self.assertEqual(custom.read_text(), "personal configuration\n")

    def test_preserves_existing_viewer_symlink(self):
        self.executable(self.launcher)
        self.viewer.parent.mkdir(parents=True)
        missing = self.home / "external-viewer.json"
        self.viewer.symlink_to(missing)
        self.run_install()
        self.assertTrue(self.viewer.is_symlink())
        self.assertEqual(os.readlink(self.viewer), str(missing))
        self.assertFalse(missing.exists())

    def test_download_or_install_failure_stops_before_config_changes(self):
        old = self.home / ".tmux.conf"
        old.symlink_to(self.dotfiles / "tmux/tmux.conf")
        for failure in ("FAKE_CURL_FAIL", "FAKE_INSTALL_FAIL"):
            with self.subTest(failure=failure):
                self.env[failure] = "1"
                self.run_install(success=False)
                self.env.pop(failure)
                self.assertFalse(self.viewer.exists())
                self.assertTrue(old.is_symlink())
                self.assertFalse((self.home / ".config/nvim").exists())
                self.assertEqual((self.home / "installer-ran").exists(),
                                 failure == "FAKE_INSTALL_FAIL")

    def test_checksum_mismatch_never_executes_download(self):
        self.installer.write_text(self.installer.read_text() + "# changed upstream\n")
        result = self.run_install(success=False)
        self.assertIn("checksum mismatch", result.stderr)
        self.assertFalse((self.home / "installer-ran").exists())
        self.assertFalse(self.viewer.exists())

    def test_missing_checksum_tools_never_executes_download(self):
        for command in ("sha256sum", "shasum"):
            (self.bin / command).unlink(missing_ok=True)
        result = self.run_install(success=False)
        self.assertIn("requires sha256sum or shasum", result.stderr)
        self.assertFalse((self.home / "installer-ran").exists())
        self.assertFalse(self.viewer.exists())

    def test_shasum_fallback_verifies_download(self):
        if not (self.bin / "shasum").exists():
            self.skipTest("shasum is not installed")
        (self.bin / "sha256sum").unlink(missing_ok=True)
        self.run_install()
        self.assertTrue(os.access(self.launcher, os.X_OK))


if __name__ == "__main__":
    unittest.main()
