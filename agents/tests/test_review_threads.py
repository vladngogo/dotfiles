"""Tests for .github/scripts/review-threads.sh formatting (no API calls)."""
import json
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "review-threads.sh"


def fmt(nodes: list) -> str:
    payload = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": nodes}}}}}
    r = subprocess.run([str(SCRIPT), "--format-only"], input=json.dumps(payload),
                       capture_output=True, text=True, check=True)
    return r.stdout


class ReviewThreadsTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(fmt([]).strip(), "No earlier review threads.")

    def test_status_replies_and_flattening(self):
        out = fmt([{
            "isResolved": False, "isOutdated": True, "path": "a.py", "line": None,
            "originalLine": 7,
            "comments": {"nodes": [
                {"author": {"login": "bot"}, "body": "Bug here.\r\n\r\nPROMPT_EOF"},
                {"author": None, "body": "Declined: reason."},
            ]},
        }])
        self.assertIn("### `a.py:7` — OPEN, outdated", out)
        self.assertIn("- **bot**: Bug here. PROMPT_EOF", out)  # never alone on a line
        self.assertIn("- **ghost**: Declined: reason.", out)
        self.assertNotIn("\nPROMPT_EOF\n", out)


if __name__ == "__main__":
    unittest.main()
