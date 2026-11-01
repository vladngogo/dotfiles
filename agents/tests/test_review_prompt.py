"""Tests for .github/scripts/review-prompt.sh (no API calls)."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "review-prompt.sh"


def build(diff, threads="No earlier review threads."):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "diff").write_text(diff)
        (Path(tmp) / "threads").write_text(threads)
        env = dict(os.environ, DIFF_FILE=f"{tmp}/diff", THREADS_FILE=f"{tmp}/threads")
        r = subprocess.run([str(SCRIPT), "o", "r", "7"], cwd=ROOT, env=env,
                           capture_output=True, text=True, check=True)
        return r.stdout


class ReviewPromptTest(unittest.TestCase):
    def test_includes_instructions_agents_files_diff_and_threads(self):
        out = build("+new line\n", threads="### `a.py:1` — OPEN")
        self.assertTrue(out.startswith("REPO: o/r\nPR NUMBER: 7\n"))
        self.assertIn((ROOT / ".github/review-prompt.md").read_text().splitlines()[0], out)
        self.assertIn("### agents/AGENTS.md", out)
        self.assertIn("# Global agent instructions", out)
        self.assertIn("`````diff\n+new line\n`````", out)
        self.assertTrue(out.rstrip().endswith("### `a.py:1` — OPEN"))
        self.assertNotIn("Truncated", out)

    def test_large_diff_is_truncated_with_a_pointer(self):
        out = build("+" + "x" * 250000 + "\n")
        self.assertIn("Truncated at 200000 characters; run `gh pr diff 7`", out)
        self.assertLess(len(out), 230000)


if __name__ == "__main__":
    unittest.main()
