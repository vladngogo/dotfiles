"""Tests for .github/scripts/review-verdict.sh (no API calls)."""
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "review-verdict.sh"


def verdict(stdin):
    return subprocess.run([str(SCRIPT)], input=stdin, capture_output=True, text=True)


class ReviewVerdictTest(unittest.TestCase):
    def test_looks_good_passes(self):
        r = verdict('{"verdict":"looks good"}')
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_needs_changes_fails(self):
        r = verdict('{"verdict":"needs changes"}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("needs changes", r.stderr)

    def test_missing_or_malformed_output_fails(self):
        for stdin in ("", "not json", "{}", '{"verdict":"LGTM"}', "[]"):
            with self.subTest(stdin=stdin):
                r = verdict(stdin)
                self.assertEqual(r.returncode, 1)
                self.assertIn("No review verdict", r.stderr)


if __name__ == "__main__":
    unittest.main()
