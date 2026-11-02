"""Portable setup orchestration, isolated from package managers and accounts."""
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("setup_manage", ROOT / "setup/manage.py")
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class SetupTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.home = self.base / "home with spaces"
        self.home.mkdir()
        self.env = patch.dict(os.environ, {"HOME": str(self.home)}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_shell_setup_preserves_local_settings_and_is_idempotent(self):
        bashrc = self.home / ".bashrc"
        original = "export LOCAL_SETTING=keep\n"
        bashrc.write_text(original)
        login = self.home / ".bash_profile"
        login.write_text("# existing login\n")
        config = self.home / "custom config"
        zsh = self.home / "custom zsh"
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "ZDOTDIR": str(zsh)}):
            manage.shell_setup(self.home)
            before = sorted(str(p) for p in self.home.rglob("*"))
            manage.shell_setup(self.home)
        self.assertEqual(before, sorted(str(p) for p in self.home.rglob("*")))
        self.assertTrue(bashrc.read_text().startswith(original))
        self.assertEqual(next(self.home.glob(".bashrc.bak.*")).read_text(), original)
        self.assertIn(manage.BEGIN, login.read_text())
        self.assertFalse((self.home / ".profile").exists())
        self.assertTrue((zsh / ".zshrc").exists())
        result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-c",
                                 '. "$HOME/.bashrc"; . "$HOME/.bashrc"; printf "%s\\n%s" "$EDITOR" "$PATH"'],
                                env={**os.environ, "PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("nvim\n"))
        self.assertTrue(result.stdout.split("\n", 1)[1].startswith(str(self.home / ".local/share/dotfiles/npm/bin") + ":"))
        self.assertEqual(result.stdout.count(str(self.home / ".local/bin")), 1)

    def test_malformed_shell_block_is_not_overwritten(self):
        path = self.home / ".bashrc"
        path.write_text(manage.BEGIN + "\nlocal content\n")
        with self.assertRaisesRegex(ValueError, "Malformed"):
            manage.shell_setup(self.home)
        self.assertEqual(path.read_text(), manage.BEGIN + "\nlocal content\n")

    def test_private_shell_backup_is_private_before_metadata_is_copied(self):
        path = self.home / ".bashrc"
        original = "export EXAMPLE_TOKEN=synthetic-test-value\n"
        path.write_text(original)
        path.chmod(0o600)
        copystat = shutil.copystat
        observed = []

        def inspect_backup(source, target, **kwargs):
            backup = Path(target)
            self.assertEqual(backup.read_text(), original)
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
            observed.append(backup)
            return copystat(source, target, **kwargs)

        previous = os.umask(0o022)
        try:
            with patch.object(manage.shutil, "copystat", side_effect=inspect_backup):
                manage.shell_setup(self.home)
        finally:
            os.umask(previous)
        self.assertEqual(observed, list(self.home.glob(".bashrc.bak.*")))
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].stat().st_mode & 0o777, 0o600)

    def test_failed_shell_backup_preserves_original_and_removes_partial_copy(self):
        path = self.home / ".bashrc"
        original = "export EXAMPLE_TOKEN=synthetic-test-value\n"
        path.write_text(original)
        path.chmod(0o600)
        with patch.object(manage.shutil, "copystat", side_effect=OSError("backup failed")):
            with self.assertRaisesRegex(OSError, "backup failed"):
                manage.shell_setup(self.home)
        self.assertEqual(path.read_text(), original)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(list(self.home.glob(".bashrc.bak.*")))

    def test_empty_xdg_and_zdotdir_use_home_defaults(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "", "XDG_DATA_HOME": "", "ZDOTDIR": ""}):
            manage.shell_setup(self.home)
            marker = self.home / ".local/share/fonts/dotfiles-jetbrains-mono/.version"
            marker.parent.mkdir(parents=True)
            marker.write_text(manage.FONT_VERSION)
            (marker.parent / "font.ttf").touch()
            with patch.object(manage.platform, "system", return_value="Linux"), \
                    patch.object(manage, "run") as run:
                manage.install_font(self.home)
                run.assert_not_called()
        target = self.home / ".config/dotfiles/env.sh"
        self.assertTrue(target.is_symlink())
        self.assertIn(str(target), (self.home / ".zshrc").read_text())

    def test_versions_fail_old_tools_and_failed_processes(self):
        versions = {"nvim": "NVIM v0.11.5", "tree-sitter": "tree-sitter 0.26.1",
                    "python3": "Python 3.13.7", "opencode": "2.1.0"}
        def version(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, versions[args[0]], "")
        with patch.object(manage.shutil, "which", side_effect=lambda name: name), \
                patch.object(manage.subprocess, "run", side_effect=version), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(manage.check_tools(manage.VERSIONS))
            versions["nvim"] = "NVIM v0.12.0"
            self.assertTrue(manage.check_tools(manage.VERSIONS))

    def test_setup_preserves_credentials_and_installs_both_agents_without_login(self):
        credentials = self.home / ".claude/.credentials.json"
        credentials.parent.mkdir()
        credentials.write_text('LOCAL-ONLY-CREDENTIAL-SENTINEL')
        with patch.object(manage, "check_tools", return_value=True), \
                patch.object(manage, "run") as run, \
                patch.object(manage, "shell_setup"), patch.object(manage, "install_font"), \
                patch.object(manage, "doctor", return_value=0), patch.object(manage, "cleanup"):
            self.assertEqual(manage.main("install"), 0)
        calls = [call.args for call in run.call_args_list]
        self.assertEqual(sum(args[0] == "npm" for args in calls), 1)
        npm = next(args for args in calls if args[0] == "npm")
        self.assertIn("@anthropic-ai/claude-code@latest", npm)
        self.assertIn("@openai/codex@latest", npm)
        self.assertFalse(Path(npm[npm.index("--cache") + 1]).exists())
        self.assertIn(("corgi-annotate", "setup"), calls)
        self.assertFalse(any("login" in args for args in calls))
        self.assertIn(("corgi", "update"), calls)
        self.assertEqual(credentials.read_text(), 'LOCAL-ONLY-CREDENTIAL-SENTINEL')

    def test_existing_npm_agents_are_reconciled_on_install_and_update(self):
        for name in ("claude", "codex"):
            path = self.home / ".local/share/dotfiles/npm/bin" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        with patch.object(manage, "check_tools", return_value=True), \
                patch.object(manage, "run") as run, \
                patch.object(manage, "shell_setup"), patch.object(manage, "install_font"), \
                patch.object(manage, "doctor", return_value=0), patch.object(manage, "cleanup"):
            manage.main("install")
            self.assertEqual(sum(call.args[0] == "npm" for call in run.call_args_list), 1)
            run.reset_mock()
            manage.main("apply-update")
            self.assertEqual(sum(call.args[0] == "npm" for call in run.call_args_list), 1)
            run.assert_any_call("corgi", "update")

    def test_font_checksum_and_safe_extraction(self):
        archive = self.base / "fixture.tar.xz"
        with tarfile.open(archive, "w:xz") as fonts:
            for name in ("font.ttf", "../../outside.ttf"):
                info = tarfile.TarInfo(name)
                info.size = 4
                fonts.addfile(info, io.BytesIO(b"font"))
        def download(*args):
            if args[0] == "curl":
                shutil.copyfile(archive, args[-1])
        with patch.object(manage.platform, "system", return_value="Linux"), \
                patch.object(manage, "run", side_effect=download):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                manage.install_font(self.home)
            with patch.object(manage, "FONT_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()):
                manage.install_font(self.home)
        dest = self.home / ".local/share/fonts/dotfiles-jetbrains-mono"
        self.assertEqual((dest / "outside.ttf").read_bytes(), b"font")
        self.assertFalse((self.home / ".local/share/outside.ttf").exists())

    def test_failed_npm_install_removes_its_cache_before_config_changes(self):
        caches = []
        def fail(*args):
            self.assertEqual(args[0], "npm")
            cache = Path(args[args.index("--cache") + 1])
            self.assertTrue(cache.exists())
            caches.append(cache)
            raise subprocess.CalledProcessError(1, args)
        with patch.object(manage, "check_tools", return_value=True), \
                patch.object(manage, "run", side_effect=fail), \
                patch.object(manage, "shell_setup") as setup:
            with self.assertRaises(subprocess.CalledProcessError):
                manage.main("install")
            setup.assert_not_called()
        self.assertTrue(caches)
        self.assertTrue(all(not path.exists() for path in caches))

    def test_cleanup_is_scoped_to_the_manifest(self):
        def packages(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "neovim\nnode\n" if args[-1] == "--formula" else "", "")
        with patch.object(manage.subprocess, "run", side_effect=packages), \
                patch.object(manage, "run") as run:
            manage.cleanup()
        run.assert_called_once_with("brew", "cleanup", "--prune=all", "neovim", "node")


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        for command in ("bash", "dirname", "cat"):
            (self.bin / command).symlink_to(shutil.which(command))
        # Isolated os-release fixture; no test depends on the host distribution.
        release = self.base / "os-release"
        release.write_text("ID=pop\n")
        self.script = self.base / "setup.sh"
        self.script.write_text((ROOT / "setup.sh").read_text().replace("/etc/os-release", str(release)))
        (self.base / "Brewfile").symlink_to(ROOT / "Brewfile")
        (self.base / "setup").symlink_to(ROOT / "setup")
        self.env = {"PATH": str(self.bin), "HOME": str(self.home), "TEST_OS": "Linux",
                    "TEST_ARCH": "x86_64", "TEST_PREFIX": "/home/linuxbrew/.linuxbrew"}
        self.stub("uname", 'case "$1" in -s) echo "$TEST_OS";; -m) echo "$TEST_ARCH";; esac')
        self.stub("brew", 'if [ "$1" = --prefix ]; then echo "$TEST_PREFIX"; else echo "$*" >> "$HOME/brew.log"; exit "${BREW_FAIL:-0}"; fi')
        self.stub("dpkg-query", 'echo "${PACKAGE_STATE:-install ok installed}"')
        self.stub("xcode-select", 'exit 0')

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def invoke(self, action="install"):
        return subprocess.run([str(self.bin / "bash"), str(self.script), action],
                              env=self.env, capture_output=True, text=True, timeout=10)

    def test_platform_plans_are_read_only(self):
        for system, arch in (("Darwin", "arm64"), ("Linux", "x86_64"), ("Linux", "aarch64")):
            self.env.update(TEST_OS=system, TEST_ARCH=arch)
            result = self.invoke("plan")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(system + " " + arch, result.stdout)
            self.assertFalse(list(self.home.iterdir()))

    def test_rosetta_and_unsupported_distribution_are_rejected(self):
        self.env.update(TEST_OS="Darwin", TEST_ARCH="x86_64")
        self.assertIn("Rosetta", self.invoke().stderr)
        self.env.update(TEST_OS="Linux", TEST_ARCH="x86_64")
        (self.base / "os-release").write_text("ID=fedora\n")
        self.assertIn("Supported Linux distributions", self.invoke().stderr)
        self.assertFalse(list(self.home.iterdir()))

    def test_update_refuses_dirty_checkout_and_non_fast_forward(self):
        self.stub("git", 'case "$*" in *status*) echo modified;; *) exit 99;; esac')
        result = self.invoke("update")
        self.assertIn("commit or stash", result.stderr)
        self.assertFalse((self.home / "brew.log").exists())
        self.stub("git", 'case "$*" in *status*) exit 0;; *"pull --ff-only"*) exit 18;; *) exit 99;; esac')
        result = self.invoke("update")
        self.assertEqual(result.returncode, 18)
        self.assertFalse((self.home / "brew.log").exists())

    def test_missing_linux_packages_print_one_manual_root_block(self):
        self.env["PACKAGE_STATE"] = "not installed"
        # PATH is extended with the real brew prefix; force the fixture commands
        # there too by using the preflight's exact executable name through a shell function.
        script = self.script.read_text().replace('export PATH=', 'export ORIGINAL_PATH="$PATH"\nexport PATH=', 1)
        script = script.replace('if [ "$action" != doctor ]; then', 'PATH="$ORIGINAL_PATH"\nif [ "$action" != doctor ]; then')
        self.script.write_text(script)
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sudo apt-get update\nsudo apt-get install", result.stderr)
        self.assertFalse((self.home / "brew.log").exists())

    def test_brew_failure_stops_before_configuration_on_each_os(self):
        self.env["BREW_FAIL"] = "17"
        for system, arch, prefix in (("Linux", "x86_64", "/home/linuxbrew/.linuxbrew"),
                                      ("Darwin", "arm64", "/opt/homebrew")):
            self.env.update(TEST_OS=system, TEST_ARCH=arch, TEST_PREFIX=prefix)
            # Keep the subprocesses hermetic despite a real Homebrew on the host.
            text = (ROOT / "setup.sh").read_text().replace("/etc/os-release", str(self.base / "os-release"))
            self.script.write_text(text.replace('export PATH=', '# test disables PATH activation\n# export PATH='))
            result = self.invoke()
            self.assertEqual(result.returncode, 17, result.stdout + result.stderr)
            self.assertFalse((self.home / ".claude").exists())


if __name__ == "__main__":
    unittest.main()
