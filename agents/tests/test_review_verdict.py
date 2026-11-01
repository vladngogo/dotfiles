"""Tests for .github/scripts/review-verdict.sh parsing (no API calls)."""
import json
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "review-verdict.sh"
SINCE = "2026-10-31T18:00:00Z"
BOT = "github-actions[bot]"


def comment(body, at="2026-10-31T18:10:00Z", user=BOT):
    return {"user": {"login": user}, "created_at": at, "body": body}


def verdict(comments):
    return subprocess.run([str(SCRIPT), "--format-only", SINCE], input=json.dumps(comments),
                          capture_output=True, text=True)


class ReviewVerdictTest(unittest.TestCase):
    def test_looks_good_passes(self):
        r = verdict([comment("Verdict: looks good\r\n\r\nNothing found.")])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_needs_changes_fails(self):
        r = verdict([comment("**Verdict: Needs changes**\n\n1. bug")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("needs changes", r.stderr)

    def test_latest_verdict_wins(self):
        good, bad = comment("Verdict: looks good"), comment("Verdict: needs changes")
        self.assertEqual(verdict([good, bad]).returncode, 1)
        self.assertEqual(verdict([bad, good]).returncode, 0)

    def test_ignores_old_runs_other_users_and_progress_comments(self):
        r = verdict([
            comment("Verdict: looks good", at="2026-10-31T17:59:59Z"),
            comment("Verdict: looks good", user="vladngogo"),
            comment("**Claude finished** ... Verdict: looks good"),
        ])
        self.assertEqual(r.returncode, 1)
        self.assertIn("No review verdict", r.stderr)


if __name__ == "__main__":
    unittest.main()
