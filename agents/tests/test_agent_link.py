"""Tests for agents/bin/agent-link."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "agent-link"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout


class AgentLinkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.dotfiles = base / "dotfiles"
        (self.dotfiles / "agents" / "repos").mkdir(parents=True)
        self.repo = base / "checkout-dir"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "remote", "add", "origin", "git@github.com:me/team-app.git")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@t",
            "commit", "-q", "--allow-empty", "-m", "init")
        self.notes = self.dotfiles / "agents" / "repos" / "team-app.md"
        self.link = self.repo / "CLAUDE.local.md"

    def tearDown(self):
        self.tmp.cleanup()

    def run_link(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        env = {**os.environ, "DOTFILES": str(self.dotfiles)}
        return subprocess.run([str(SCRIPT), *args], cwd=cwd or self.repo, env=env,
                              capture_output=True, text=True)

    def test_missing_notes_requires_init(self):
        r = self.run_link()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--init", r.stderr)
        self.assertFalse(self.link.exists())

    def test_installed_symlink_resolves_checkout_without_gnu_readlink(self):
        script = self.dotfiles / "agents/bin/agent-link"
        script.parent.mkdir()
        shutil.copy2(SCRIPT, script)
        launcher = Path(self.tmp.name) / "agent-link"
        launcher.symlink_to(script)
        env = {k: v for k, v in os.environ.items() if k != "DOTFILES"}
        result = subprocess.run([str(launcher), "--init"], cwd=self.repo, env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.notes.exists())

    def test_init_links_and_excludes_idempotently(self):
        self.assertEqual(self.run_link("--init").returncode, 0)
        self.assertTrue(self.notes.exists())  # named after the remote, not the dir
        self.assertEqual(os.readlink(self.link), str(self.notes))
        self.assertEqual(self.run_link().returncode, 0)
        exclude = (self.repo / ".git" / "info" / "exclude").read_text()
        self.assertEqual(exclude.count("/CLAUDE.local.md"), 1)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_worktree_shares_notes_and_exclude(self):
        self.run_link("--init")
        wt = Path(self.tmp.name) / "wt"
        git(self.repo, "worktree", "add", "-q", "--detach", str(wt))
        self.assertEqual(self.run_link(cwd=wt).returncode, 0)
        self.assertEqual(os.readlink(wt / "CLAUDE.local.md"), str(self.notes))
        self.assertEqual(git(wt, "status", "--porcelain"), "")

    def test_refuses_to_clobber_regular_file(self):
        self.notes.write_text("mine\n")
        self.link.write_text("existing\n")
        r = self.run_link()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.link.read_text(), "existing\n")

    def test_refuses_committed_file(self):
        self.notes.write_text("mine\n")
        self.link.write_text("team\n")
        git(self.repo, "add", "CLAUDE.local.md")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x")
        r = self.run_link()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("team-owned", r.stderr)

    def test_unlink_keeps_notes(self):
        self.run_link("--init")
        self.assertEqual(self.run_link("--unlink").returncode, 0)
        self.assertFalse(self.link.is_symlink())
        self.assertTrue(self.notes.exists())


if __name__ == "__main__":
    unittest.main()
