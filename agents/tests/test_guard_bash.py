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
    # sudo can't prompt in an agent shell
    ("sudo apt install foo", True, True),
    ("cd /tmp && sudo -n true", True, True),
    ("FOO=1 sudo make install", True, True),
    ("if sudo -n true; then echo ok; fi", True, True),
    ("echo x | sudo tee /etc/foo", True, True),
    ("ls\nsudo reboot", True, True),
    ("ls # list\nsudo reboot", True, True),
    ("echo $(sudo cat /etc/hostname)", True, True),
    ("foo |& sudo tee /etc/foo", True, True),
    ("time -p sudo ls", True, True),
    ("env -i sudo ls", True, True),
    ("/usr/bin/sudo ls", True, True),
    ("echo 'sudo apt install foo'", False, False),
    ("apt-cache policy sudo", False, False),
    ("command -v sudo", False, False),
    ("grep -r sudo README.md", False, False),
    ("ls # sudo reboot", False, False),
    # root commands written out for the user are text, not a sudo call
    ("cat > root.sh <<'EOF'\nsudo apt install foo\nEOF", False, False),
    ("cat > root.sh <<\\EOF\nsudo apt install foo\nEOF", False, False),
    ("cat > root.sh <<'END-ROOT'\nsudo apt install foo\nEND-ROOT", False, False),
    ("cat <<EOF | sudo tee /etc/foo\nx\nEOF", True, True),
    ("printf '%s\\n' \"run:\nsudo apt install foo\"", False, False),
    # pkill -f matches the agent's own shell
    ("pkill -f 'python server.py'", True, True),
    ("pkill -9 -f server", True, True),
    ("pkill --full server", True, True),
    ("/usr/bin/pkill -f server", True, True),
    ("sleep 1; pkill -fx 'python server.py'", True, True),
    ("pkill -x nvim", False, False),
    ("pkill -TERM firefox", False, False),
    ("pkill -INFO firefox", False, False),  # signal name, not -f
    ("pgrep -af server", False, False),
    ("kill 1234", False, False),
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
