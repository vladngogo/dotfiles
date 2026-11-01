"""End-to-end tests for agents/bin/agent-eval using a fake agent and grader."""
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "agent-eval"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


class AgentEvalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "app.txt").write_text("hello\n")
        (self.repo / "billing.txt").write_text("do not touch\n")
        git(self.repo, "add", ".")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")

        cases = self.repo / "evals" / "cases"
        cases.mkdir(parents=True)
        (cases / "greet.toml").write_text(textwrap.dedent('''\
            id = "greet"
            prompt = "append world to app.txt"
            checks = ["grep -q world app.txt"]
            must_not_break = ["git diff --quiet {base} -- billing.txt"]
            rubric = ["app.txt says hello world"]
        '''))
        (cases / "fail.toml").write_text(textwrap.dedent('''\
            id = "fail"
            prompt = "make app.txt say goodbye"
            checks = ["grep -q goodbye app.txt"]
        '''))

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, agent: str) -> None:
        grader = ("echo '{\"results\": [{\"item\": \"x\", \"pass\": true, "
                  "\"reason\": \"ok\"}]}'")
        (self.repo / "evals" / "config.toml").write_text(
            f"agent = {json.dumps(agent)}\ngrader = {json.dumps(grader)}\n"
            'runs = 2\njobs = 2\n[env]\nPORT = "{slot}"\n')

    def run_eval(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.repo,
                              capture_output=True, text=True)

    def summary(self, label: str) -> dict:
        path = self.repo / "evals" / "results" / label / "summary.json"
        return json.loads(path.read_text())["cases"]

    def test_run_grade_and_compare(self):
        self.config("echo world >> app.txt; echo '{\"total_cost_usd\": 0.5}'")
        r = self.run_eval("run", "--label", "base")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = self.summary("base")
        self.assertEqual(s["greet"]["passed"], 2)
        self.assertEqual(s["greet"]["mean_cost_usd"], 0.5)
        self.assertEqual(s["fail"]["passed"], 0)

        # Candidate touches the gated file: must be flagged and compare must fail.
        self.config("echo world >> app.txt; echo oops >> billing.txt")
        self.assertEqual(self.run_eval("run", "--label", "cand").returncode, 0)
        s = self.summary("cand")
        self.assertEqual(s["greet"]["violations"], 2)
        self.assertEqual(s["greet"]["passed"], 0)
        cmp = self.run_eval("compare", "base", "cand")
        self.assertEqual(cmp.returncode, 1)
        self.assertIn("VIOLATION", cmp.stdout)
        self.assertIn("REGRESSION", cmp.stdout)

        # Worktrees cleaned up; main checkout untouched.
        wt = subprocess.run(["git", "worktree", "list"], cwd=self.repo,
                            capture_output=True, text=True).stdout
        self.assertEqual(len(wt.strip().splitlines()), 1)
        self.assertEqual((self.repo / "billing.txt").read_text(), "do not touch\n")

    def test_compare_flags_missing_case(self):
        self.config("echo world >> app.txt")
        self.assertEqual(self.run_eval("run", "--label", "full", "--runs", "1").returncode, 0)
        self.assertEqual(self.run_eval("run", "--label", "subset", "--runs", "1",
                                       "-k", "greet").returncode, 0)
        cmp = self.run_eval("compare", "full", "subset")
        self.assertEqual(cmp.returncode, 1)
        self.assertIn("MISSING", cmp.stdout)
        # Reverse direction: a case with no baseline is reported, not a regression.
        cmp = self.run_eval("compare", "subset", "full")
        self.assertEqual(cmp.returncode, 0, cmp.stdout)
        self.assertIn("new (no baseline)", cmp.stdout)

    def test_failed_agent_with_null_cost_is_recorded(self):
        # An agent that died before reporting a cost must fail its run, not
        # abort the whole batch.
        self.config("echo '{\"total_cost_usd\": null}'; exit 1")
        r = self.run_eval("run", "--label", "crash", "-k", "greet", "--runs", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = self.summary("crash")
        self.assertEqual(s["greet"]["passed"], 0)
        self.assertIsNone(s["greet"]["mean_cost_usd"])

    def test_filter_and_label_reuse(self):
        self.config("true")
        self.assertEqual(self.run_eval("run", "--label", "a", "-k", "greet").returncode, 0)
        self.assertEqual(set(self.summary("a")), {"greet"})
        self.assertNotEqual(self.run_eval("run", "--label", "a").returncode, 0)

    def test_new_scaffolds_case(self):
        self.assertEqual(self.run_eval("new", "eng-1").returncode, 0)
        text = (self.repo / "evals" / "cases" / "eng-1.toml").read_text()
        self.assertIn('id = "eng-1"', text)


if __name__ == "__main__":
    unittest.main()
