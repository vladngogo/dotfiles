"""Repo policy: dotfiles tracks no agent rulesets.

Global instructions are machine-local (README, "Agents" section). A tracked
AGENTS.md/CLAUDE.md would drift back into the repo, so this test fails the
build if one appears. agents/seed.md is the only instruction content allowed:
a small, agnostic starter seeded onto new machines.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RULESET_NAMES = {"AGENTS.md", "CLAUDE.md", "AGENTS.local.md", "CLAUDE.local.md"}


class RepoRulesTest(unittest.TestCase):
    def test_no_agent_rulesets_are_tracked(self):
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
            check=True).stdout.splitlines()
        rulesets = [t for t in tracked if Path(t).name in RULESET_NAMES]
        self.assertEqual(rulesets, [])

    def test_seed_is_small_and_agnostic(self):
        seed = ROOT / "agents/seed.md"
        self.assertTrue(seed.is_file())
        text = seed.read_text()
        self.assertLess(len(text.splitlines()), 20)
        self.assertIn("machine-local", text)


if __name__ == "__main__":
    unittest.main()
