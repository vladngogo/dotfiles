"""Tests for agents/hooks/lint-edit."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "lint-edit"

BAD = '#!/usr/bin/env bash\nrm -rf $1/tmp\n'  # SC2086: unquoted variable
GOOD = '#!/usr/bin/env bash\nrm -rf "$1/tmp"\n'


def run(payload=None, arg=None):
    args = ["python3", str(HOOK)] + ([arg] if arg else [])
    stdin = json.dumps(payload) if payload is not None else ""
    return subprocess.run(args, input=stdin, capture_output=True, text=True)


@unittest.skipUnless(shutil.which("shellcheck"), "shellcheck not installed")
class LintEditTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text)
        return str(path)

    def payload(self, path):
        return {"tool_name": "Edit", "tool_input": {"file_path": path}}

    def test_blocks_shell_script_with_problems(self):
        result = run(self.payload(self.write("x.sh", BAD)))
        self.assertEqual(result.returncode, 2)
        self.assertIn("SC2086", result.stderr)

    def test_passes_clean_script(self):
        self.assertEqual(run(self.payload(self.write("x.sh", GOOD))).returncode, 0)

    def test_checks_extensionless_script_by_shebang(self):
        self.assertEqual(run(self.payload(self.write("tool", BAD))).returncode, 2)

    def test_checks_sh_shebang(self):
        self.assertEqual(run(arg=self.write("tool", "#!/bin/sh\nrm $1\n")).returncode, 2)

    def test_ignores_non_shell_files(self):
        self.assertEqual(run(self.payload(self.write("x.py", "rm $1\n"))).returncode, 0)
        self.assertEqual(run(self.payload(self.write("tool", "#!/usr/bin/env python3\n$x\n"))).returncode, 0)

    def test_ignores_missing_file_and_bad_input(self):
        self.assertEqual(run(self.payload(str(self.dir / "gone.sh"))).returncode, 0)
        self.assertEqual(run({"tool_input": {}}).returncode, 0)
        self.assertEqual(subprocess.run(["python3", str(HOOK)], input="not json",
                                        capture_output=True, text=True).returncode, 0)

    def test_passes_when_shellcheck_missing(self):
        env = {**os.environ, "PATH": str(self.dir)}  # no shellcheck on PATH
        result = subprocess.run([sys.executable, str(HOOK), self.write("x.sh", BAD)],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
