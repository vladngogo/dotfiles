"""Table tests for agents/hooks/guard-bash."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "guard-bash"

# (command, blocked on branch main, blocked on branch feat)
CASES = [
    ("ls -la", False, False),
    ("echo 'git push origin main'", False, False),  # quoted text, not a push
    ("git status && git log", False, False),
    # bare push follows the current branch
    ("git push", True, False),
    ("git push origin", True, False),
    ("git push -u origin", True, False),
    ("git push origin HEAD", True, False),
    ("git push origin @", True, False),
    # explicit destinations
    ("git push origin main", True, True),
    ("git push origin refs/heads/main", True, True),
    ("git push origin HEAD:main", True, True),
    ("git push origin HEAD:refs/heads/master", True, True),
    ("git push origin :main", True, True),
    ("git push origin --delete main", True, True),
    ("git push -u origin feat", False, False),
    ("git push origin feat:feat", False, False),
    ("git push origin refs/tags/main", False, False),
    ("git push --tags origin", False, False),  # tags only
    ("git push --tags origin main", True, True),
    # force
    ("git push --force origin feat", True, True),
    ("git push -f origin feat", True, True),
    ("git push -uf origin feat", True, True),
    ("git push origin +feat", True, True),
    ("git push origin +HEAD:refs/heads/main", True, True),
    ("git push --force-with-lease origin feat", False, False),
    ("git push --force-with-lease --force-if-includes origin feat", False, False),
    ("git push -o ci.skip origin feat", False, False),
    # git treats the first positional as the repository even with --repo, so
    # `--repo origin main` pushes to a repo named "main" and fails harmlessly.
    ("git push --repo origin main", True, False),  # main: bare-push rule
    ("git push --repo origin origin main", True, True),
    ("git push --repo=origin origin +main", True, True),
    # everything at once
    ("git push --all origin", True, True),
    ("git push --mirror origin", True, True),
    # git global options and compound commands
    ("git -C . push origin +feat", True, True),
    ("git -c push.default=current push origin main", True, True),
    ("cd repo && git push origin main", True, True),
    ("git add -A; git commit -m 'x' && git push origin main", True, True),
    ("git commit -m 'git push origin main'", False, False),
    # credential paths
    ("cat ~/.ssh/id_ed25519", True, True),
    ("ls $HOME/.aws/", True, True),
    ("cat ~/.secrets/openai", True, True),
    ("keystash save openai", False, False),
    ("cat ~/.config/gh/hosts.yml", True, True),
    ("cat .env", True, True),
    ("source app/.env.local", True, True),
    ("grep KEY < .env", True, True),
    ("cp .env.example .env.sample", False, False),
    ("python3 -m venv .venv && .venv/bin/pip install -r requirements.txt", False, False),
    ("ssh-keygen -l -f key.pub", False, False),
]


class GuardBashTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repos = {}
        for branch in ("main", "feat"):
            repo = Path(cls.tmp.name) / branch
            repo.mkdir()
            for args in (["init", "-q", "-b", branch],
                         ["-c", "user.name=t", "-c", "user.email=t@t",
                          "commit", "-q", "--allow-empty", "-m", "init"]):
                subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
            cls.repos[branch] = repo

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def blocked(self, cmd: str, branch: str) -> bool:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        r = subprocess.run([str(HOOK)], cwd=self.repos[branch], input=payload,
                           capture_output=True, text=True)
        self.assertIn(r.returncode, (0, 2), r.stderr)
        if r.returncode == 2:
            self.assertTrue(r.stderr.startswith("Blocked:"), r.stderr)
        return r.returncode == 2

    def test_table(self):
        for cmd, on_main, on_feat in CASES:
            with self.subTest(cmd=cmd, branch="main"):
                self.assertEqual(self.blocked(cmd, "main"), on_main)
            with self.subTest(cmd=cmd, branch="feat"):
                self.assertEqual(self.blocked(cmd, "feat"), on_feat)

    def test_argv_input_and_bad_json(self):
        r = subprocess.run([str(HOOK), "git push origin main"], capture_output=True)
        self.assertEqual(r.returncode, 2)
        r = subprocess.run([str(HOOK)], input=b"not json", capture_output=True)
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
