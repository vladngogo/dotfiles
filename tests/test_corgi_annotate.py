"""Annotation workflows against a deterministic Corgi/Plannotator subprocess contract."""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "corgi/bin/corgi-annotate"
loader = importlib.machinery.SourceFileLoader("annotate", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
annotate = importlib.util.module_from_spec(spec)
loader.exec_module(annotate)


class AnnotateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.fixture = self.root / "snapshot.json"
        self.log = self.root / "calls.jsonl"
        self.state = {
            "server_pid": 800,
            "workspaces": [{"id": 1, "name": "demo", "cwd": str(self.root)}],
            "panes": [{"id": 7, "binding": 2, "pid": 42, "workspace": 1,
                       "cwd": str(self.root), "agent": {
                           "provider": "claude", "session": "session-one", "transcript": "/exact/session.jsonl",
                           "state": "idle", "attention": "none"}},
                      {"id": 8, "binding": 1, "pid": 43, "workspace": 1,
                       "cwd": str(self.root), "agent": {"provider": None, "state": "unknown"}}],
        }
        self.viewers = [{"id": 1, "pane": 7, "workspace": 1}]
        self.save_snapshot()
        self.fake_corgi = self.root / "fake corgi"
        self.fake_corgi.write_text(f"#!{sys.executable}\n" + '''
import json, os, pathlib, sys
args = [a for a in sys.argv[1:] if a not in ('--json', '--no-agent')]
data = sys.stdin.read() if '--stdin' in args else None
with open(os.environ['FAKE_LOG'], 'a') as f:
    f.write(json.dumps({'args': args, 'text': data}) + '\\n')
if args == ['list']:
    print(pathlib.Path(os.environ['FAKE_SNAPSHOT']).read_text())
elif args[:2] == ['pane', 'split']:
    print(json.dumps({'ok': True, 'result': {'pane': 99}}))
elif args[:2] == ['pane', 'read']:
    print(json.dumps({'ok': True, 'result': {'text': 'terminal output\\n'}}))
elif args[:2] == ['pane', 'send'] and os.environ.get('FAIL_SEND'):
    print('connection lost', file=sys.stderr)
    sys.exit(1)
else:
    print(json.dumps({'ok': True, 'result': {}}))
''')
        self.fake_corgi.chmod(0o755)
        self.fake_tui = self.root / "fake tui"
        self.fake_tui.write_text(f"#!{sys.executable}\n" + '''
import json, os, pathlib, subprocess, sys
pathlib.Path(os.environ['TUI_LOG']).write_text(json.dumps({'args': sys.argv[1:], 'env': dict(os.environ)}))
if os.environ.get('TUI_SEND'):
    result = subprocess.run([os.environ['HERDR_BIN_PATH'], 'agent', 'prompt',
                             os.environ['PLANNOTATOR_TUI_DELIVER_TO'], 'review feedback'])
    sys.exit(result.returncode)
''')
        self.fake_tui.chmod(0o755)
        self.env = {"HOME": str(self.root), "PATH": os.environ["PATH"],
                    "XDG_STATE_HOME": str(self.root / "state"), "XDG_DATA_HOME": str(self.root / "data"),
                    "CORGI_ANNOTATE_CORGI": str(self.fake_corgi), "CORGI_ANNOTATE_TUI": str(self.fake_tui),
                    "FAKE_SNAPSHOT": str(self.fixture), "FAKE_LOG": str(self.log),
                    "TUI_LOG": str(self.root / "tui.json"), "CORGI_PANE": "7"}
        self.target = annotate.identity(self.state, self.state["panes"][0])
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()

    def save_snapshot(self):
        self.fixture.write_text(json.dumps({"ok": True, "result": self.state, "viewers": self.viewers}))

    def cli(self, *args, stdin=None, success=True):
        result = subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin,
                                capture_output=True, text=True, env=dict(os.environ), timeout=20)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def calls(self, prefix):
        return [r for r in map(json.loads, self.log.read_text().splitlines()) if r["args"][:len(prefix)] == prefix]

    def capture(self):
        self.cli("capture", "--text", "selected λ\nsecond line", "--comment", "explain this")

    def test_capture_export_archive_restore(self):
        self.capture()
        text = self.cli("export").stdout
        self.assertIn("> selected λ\n> second line", text)
        self.assertIn("explain this", text)
        self.cli("archive", "1")
        self.assertNotIn("explain this", self.cli("export").stdout)
        self.assertIn("explain this", self.cli("export", "--archived").stdout)
        self.cli("restore", "1")
        self.assertIn("explain this", self.cli("export").stdout)

    def test_stdin_capture_and_empty_input(self):
        self.cli("annotate.capture", "--stdin", "--comment", "fix", stdin="quoted text")
        self.assertIn("quoted text", self.cli("export").stdout)
        self.cli("capture", "--stdin", "--comment", "fix", stdin="  ", success=False)

    def test_send_archives_only_successfully_delivered_notes(self):
        self.capture()
        os.environ["FAIL_SEND"] = "1"
        result = self.cli("send-archive", success=False)
        self.assertIn("inspect the pane", result.stderr)
        self.assertEqual(len(self.calls(["pane", "send"])), 1)
        self.assertIn("explain this", self.cli("export").stdout)
        os.environ.pop("FAIL_SEND")
        self.cli("send-archive")
        sent = self.calls(["pane", "send"])[-1]
        self.assertIn("--enter", sent["args"])
        self.assertIn("selected λ", sent["text"])
        self.assertNotIn("explain this", self.cli("export").stdout)

    def test_paste_does_not_submit(self):
        self.capture()
        self.cli("paste-archive")
        self.assertNotIn("--enter", self.calls(["pane", "send"])[0]["args"])

    def test_shell_target_refused_without_losing_notes(self):
        self.capture()
        self.cli("send-archive", "--pane", "8", success=False)
        self.assertFalse(self.calls(["pane", "send"]))
        self.assertIn("explain this", self.cli("export").stdout)
        self.cli("send-archive", "--pane", "8", "--to", "7")

    def add_agent(self, pane_id=9, workspace=1):
        pane = copy.deepcopy(self.state["panes"][0])
        pane.update(id=pane_id, workspace=workspace)
        pane["agent"].update(name="Second agent", session="second-session", transcript="/exact/second.jsonl")
        self.state["panes"].append(pane)
        self.save_snapshot()

    def test_shell_automatically_targets_workspace_agent(self):
        os.environ["CORGI_PANE"] = "8"
        self.cli("terminal", "--here")
        env = json.loads((self.root / "tui.json").read_text())["env"]
        self.assertEqual(env["PLANNOTATOR_TUI_TERMINAL_PANE"], "8")
        self.assertEqual(env["PLANNOTATOR_TUI_DELIVER_TO"], "7")
        self.cli("last-newest", "--here")
        call = json.loads((self.root / "tui.json").read_text())
        self.assertIn("/exact/session.jsonl", call["args"])
        self.assertEqual(call["env"]["PLANNOTATOR_TUI_DELIVER_TO"], "7")
        self.capture()
        self.cli("send-archive")
        self.assertEqual(self.calls(["pane", "send"])[0]["args"][2], "7")

    def test_open_keeps_shell_directory_and_split_source(self):
        os.environ["CORGI_PANE"] = "8"
        folder = self.root / "shell-folder"
        folder.mkdir()
        self.state["panes"][1]["cwd"] = str(folder)
        self.save_snapshot()
        self.cli("open")
        call = self.calls(["pane", "split"])[0]["args"]
        self.assertEqual(call[2], "8")
        job_path = shlex.split(call[call.index("--command") + 1])[-1]
        job = json.loads(Path(job_path).read_text())
        self.assertEqual(job["args"]["path"], str(folder))
        self.assertEqual(job["context"]["target"]["pane"], 7)

    def test_agent_caller_and_explicit_overrides_bypass_picker(self):
        self.add_agent()
        self.cli("last", "--here")
        os.environ["CORGI_PANE"] = "8"
        self.cli("terminal", "--to", "9", "--here")
        env = json.loads((self.root / "tui.json").read_text())["env"]
        self.assertEqual(env["PLANNOTATOR_TUI_DELIVER_TO"], "9")
        self.assertEqual(env["PLANNOTATOR_TUI_TERMINAL_PANE"], "8")
        self.cli("terminal", "--pane", "current", "--here")
        env = json.loads((self.root / "tui.json").read_text())["env"]
        self.assertNotIn("PLANNOTATOR_TUI_DELIVER_TO", env)

    def test_selection_ignores_other_workspaces_and_exited_agents(self):
        os.environ["CORGI_PANE"] = "8"
        self.add_agent(workspace=2)
        self.add_agent(pane_id=10)
        self.state["panes"][-1]["exited"] = True
        self.save_snapshot()
        self.cli("last", "--here")
        self.state["panes"][0]["exited"] = True
        self.save_snapshot()
        self.cli("terminal", "--here")
        env = json.loads((self.root / "tui.json").read_text())["env"]
        self.assertNotIn("PLANNOTATOR_TUI_DELIVER_TO", env)
        self.assertIn("no detected agent", self.cli("last", "--here", success=False).stderr)

    def test_capture_and_export_do_not_require_recipient_selection(self):
        os.environ["CORGI_PANE"] = "8"
        self.add_agent()
        self.capture()
        self.assertIn("explain this", self.cli("export").stdout)

    def test_ambiguous_agents_without_terminal_require_override(self):
        os.environ["CORGI_PANE"] = "8"
        self.add_agent()
        result = subprocess.run([sys.executable, str(SCRIPT), "terminal", "--here"],
                                capture_output=True, text=True, start_new_session=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--to ID", result.stderr)
        self.assertFalse((self.root / "tui.json").exists())

    def picker(self, answer, *args):
        """Run a review through the real terminal picker; return (exit code, output)."""
        (self.root / "tui.json").unlink(missing_ok=True)
        pid, fd = pty.fork()
        if pid == 0:
            os.execv(sys.executable, [sys.executable, str(SCRIPT), *(args or ("last", "--here"))])
        output = b""
        sent = False
        status = None
        deadline = time.monotonic() + 15
        try:
            while time.monotonic() < deadline:
                if select.select([fd], [], [], 0.1)[0]:
                    try:
                        chunk = os.read(fd, 65536)
                    except OSError:
                        chunk = b""
                    output += chunk
                if b"Agent number" in output and not sent:
                    os.write(fd, answer)
                    sent = True
                finished, status_value = os.waitpid(pid, os.WNOHANG)
                if finished:
                    status = status_value
                    break
            self.assertIsNotNone(status, output.decode())
            return os.waitstatus_to_exitcode(status), output.decode()
        finally:
            os.close(fd)
            if status is None:
                os.kill(pid, 9)
                os.waitpid(pid, 0)

    def delivered_to(self):
        return json.loads((self.root / "tui.json").read_text())["env"]["PLANNOTATOR_TUI_DELIVER_TO"]

    def test_real_terminal_picker_selects_named_agent_and_cancels(self):
        os.environ["CORGI_PANE"] = "8"
        self.add_agent()
        for answer, expected in ((b"bad\n2\n", 0), (b"q\n", 1)):
            with self.subTest(answer=answer):
                code, output = self.picker(answer)
                self.assertEqual(code, expected, output)
                self.assertIn("Second agent", output)
                if expected == 0:
                    call = json.loads((self.root / "tui.json").read_text())
                    self.assertIn("/exact/second.jsonl", call["args"])
                    self.assertEqual(call["env"]["PLANNOTATOR_TUI_DELIVER_TO"], "9")

    def test_picker_offers_last_choice_as_enter_default(self):
        os.environ["CORGI_PANE"] = "8"
        self.add_agent()
        code, output = self.picker(b"\n")
        self.assertEqual(code, 1, output)  # nothing remembered yet: Enter cancels
        self.assertEqual(self.picker(b"2\n")[0], 0)
        code, output = self.picker(b"\n", "terminal", "--here")
        self.assertEqual(code, 0, output)
        self.assertIn("Enter for 2", output)
        self.assertEqual(self.delivered_to(), "9")
        # Choosing another agent replaces the default.
        self.assertEqual(self.picker(b"1\n")[0], 0)
        self.assertEqual(self.picker(b"\n")[0], 0)
        self.assertEqual(self.delivered_to(), "7")

    def test_picker_eof_cancels_even_with_default(self):
        os.environ["CORGI_PANE"] = "8"
        self.add_agent()
        self.assertEqual(self.picker(b"2\n")[0], 0)
        code, output = self.picker(b"\x04")
        self.assertEqual(code, 1, output)
        self.assertFalse((self.root / "tui.json").exists())

    def test_picker_drops_default_for_exited_agent(self):
        os.environ["CORGI_PANE"] = "8"
        self.add_agent()
        self.add_agent(pane_id=10)
        self.assertEqual(self.picker(b"3\n")[0], 0)
        self.state["panes"][-1]["exited"] = True
        self.save_snapshot()
        code, output = self.picker(b"\n")
        self.assertEqual(code, 1, output)
        self.assertNotIn("Enter for", output)

    def test_workspaces_sharing_a_folder_keep_separate_defaults(self):
        os.environ["CORGI_PANE"] = "8"
        self.add_agent()
        self.state["workspaces"].append({"id": 2, "name": "same folder", "cwd": str(self.root)})
        self.state["panes"].append(dict(copy.deepcopy(self.state["panes"][1]), id=11, workspace=2))
        self.add_agent(pane_id=12, workspace=2)
        self.add_agent(pane_id=13, workspace=2)
        self.assertEqual(self.picker(b"2\n")[0], 0)
        os.environ["CORGI_PANE"] = "11"
        self.assertEqual(self.picker(b"1\n")[0], 0)
        os.environ["CORGI_PANE"] = "8"
        self.assertEqual(self.picker(b"\n")[0], 0)
        self.assertEqual(self.delivered_to(), "9")

    def test_picker_default_is_scoped_to_runtime(self):
        # Pane IDs restart in each Corgi runtime, so another socket must not reuse the choice.
        os.environ["CORGI_PANE"] = "8"
        self.add_agent()
        self.assertEqual(self.picker(b"2\n")[0], 0)
        os.environ["CORGI_SOCKET"] = str(self.root / "other.sock")
        code, output = self.picker(b"\n")
        self.assertEqual(code, 1, output)
        self.assertNotIn("Enter for", output)

    def test_busy_blocked_and_unknown_agents_refused(self):
        for state, attention in (("working", "none"), ("blocked", "none"), ("idle", "needs_input"),
                                 ("initializing", "none"), ("unknown", "none")):
            with self.subTest(state=state, attention=attention):
                self.state["panes"][0]["agent"].update(state=state, attention=attention)
                self.save_snapshot()
                with self.assertRaisesRegex(annotate.Error, "busy"):
                    annotate.deliver(self.target, "feedback")
        self.assertFalse(self.calls(["pane", "send"]))

    def test_stale_session_binding_pid_or_runtime_refused(self):
        original = copy.deepcopy(self.state)
        for kind in ("session", "provider", "binding", "pid", "server_pid"):
            with self.subTest(kind=kind):
                self.state = copy.deepcopy(original)
                if kind in ("session", "provider"):
                    self.state["panes"][0]["agent"][kind] = "changed"
                elif kind == "server_pid":
                    self.state[kind] = 801
                else:
                    self.state["panes"][0][kind] += 1
                self.save_snapshot()
                with self.assertRaisesRegex(annotate.Error, "changed"):
                    annotate.deliver(self.target, "feedback")
        self.assertFalse(self.calls(["pane", "send"]))

    def test_workspace_and_socket_scope_are_isolated(self):
        self.capture()
        os.environ["CORGI_SOCKET"] = "/other/runtime.sock"
        self.assertNotIn("explain this", self.cli("export").stdout)
        os.environ["CORGI_SOCKET"] = f"/tmp/corgi-{os.getuid()}/control.sock"
        self.assertIn("explain this", self.cli("export").stdout)
        self.state["workspaces"][0]["cwd"] = "/other/project"
        self.save_snapshot()
        self.assertNotIn("explain this", self.cli("export").stdout)

    def test_ambiguous_viewers_need_explicit_selection(self):
        os.environ.pop("CORGI_PANE")
        self.viewers.append({"id": 2, "pane": 8, "workspace": 1})
        self.save_snapshot()
        self.cli("export", success=False)
        self.cli("capture", "--viewer", "1", "--text", "quote", "--comment", "note")
        self.assertIn("note", self.cli("export", "--viewer", "1").stdout)

    def test_open_uses_native_tui_and_delivery_adapter(self):
        doc = self.root / "plan with spaces.md"
        doc.write_text("a plan\n")
        os.environ["TUI_SEND"] = "1"
        self.cli("open", str(doc), "--here")
        call = json.loads((self.root / "tui.json").read_text())
        self.assertEqual(call["args"], [str(doc)])
        self.assertEqual(call["env"]["HERDR_BIN_PATH"], str(SCRIPT))
        self.assertEqual(self.calls(["pane", "send"])[0]["text"], "review feedback")

    def test_bare_path_opens_document(self):
        (self.root / "plan.md").write_text("a plan\n")
        for argv in (["plan.md", "--here"], ["--here", "--pane", "7", "plan.md"], ["--to=7", "--here", "plan.md"],
                     ["--pa", "7", "--here", "plan.md"]):
            (self.root / "tui.json").unlink(missing_ok=True)
            result = subprocess.run([sys.executable, str(SCRIPT), *argv], cwd=self.root,
                                    capture_output=True, text=True, env=dict(os.environ), timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            call = json.loads((self.root / "tui.json").read_text())
            self.assertEqual(call["args"], [str(self.root / "plan.md")])

    def test_bare_path_with_command_prefix_is_not_stripped(self):
        (self.root / "annotate.notes.md").write_text("notes\n")
        (self.root / "notes.md").write_text("wrong file\n")
        result = subprocess.run([sys.executable, str(SCRIPT), "annotate.notes.md", "--here"], cwd=self.root,
                                capture_output=True, text=True, env=dict(os.environ), timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        call = json.loads((self.root / "tui.json").read_text())
        self.assertEqual(call["args"], [str(self.root / "annotate.notes.md")])
        self.cli("annotate.capture", "--text", "legacy", "--comment", "note")
        self.assertIn("legacy", self.cli("export").stdout)

    def test_mistyped_command_still_lists_choices(self):
        result = self.cli("termnal", success=False)
        self.assertIn("invalid choice: 'termnal'", result.stderr)
        result = self.cli("missing.md", success=False)
        self.assertIn("No such file or folder", result.stderr)
        (self.root / "sel.md").write_text("selected\n")
        self.cli("--fi", str(self.root / "sel.md"), "capture", "--comment", "note")
        self.assertIn("selected", self.cli("export").stdout)

    def test_last_uses_exact_transcript_and_opencode_session_id(self):
        self.cli("last-newest", "--here")
        call = json.loads((self.root / "tui.json").read_text())
        self.assertEqual(call["args"], ["last", "--host", "claude", "--session", "/exact/session.jsonl",
                                       "--session-id", "session-one", "--newest"])
        self.state["panes"][0]["agent"].update(provider="opencode2", transcript="", session="ses_exact")
        self.save_snapshot()
        self.cli("last", "--here")
        call = json.loads((self.root / "tui.json").read_text())
        self.assertEqual(call["args"], ["last", "--host", "opencode", "--session-id", "ses_exact"])
        self.state["panes"][0]["agent"]["session"] = ""
        self.save_snapshot()
        self.assertIn("exact session", self.cli("last", "--here", success=False).stderr)

    def test_database_transcript_includes_exact_session(self):
        self.state["panes"][0]["agent"].update(provider="opencode2", transcript="/exact/opencode.db", session="ses_exact")
        self.save_snapshot()
        self.cli("last-newest", "--here")
        call = json.loads((self.root / "tui.json").read_text())
        self.assertEqual(call["args"], ["last", "--host", "opencode", "--session", "/exact/opencode.db",
                                       "--session-id", "ses_exact", "--newest"])

    def test_multiline_quote_does_not_leak_into_edited_comment(self):
        with patch.object(annotate.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            self.assertEqual(annotate.edit("existing comment", "Comment on: first\nsecond"), "existing comment")

    def test_terminal_review_and_native_read_transport(self):
        self.cli("terminal", "--here", "--lines", "75")
        call = json.loads((self.root / "tui.json").read_text())
        self.assertEqual(call["args"], ["herdr", "pane"])
        self.assertEqual(call["env"]["PLANNOTATOR_TUI_TERMINAL_PANE"], "7")
        result = self.cli("pane", "read", "7", "--source", "recent-unwrapped", "--lines", "75", "--format", "text")
        self.assertEqual(result.stdout, "terminal output\n")

    def test_split_launch_quotes_command_and_preserves_context(self):
        os.environ["OPENCODE_DB"] = "/custom/session.db"
        self.cli("terminal")
        call = self.calls(["pane", "split"])[0]
        command = shlex.split(call["args"][call["args"].index("--command") + 1])
        self.assertEqual(command[:3], [sys.executable, str(SCRIPT), "_run"])
        job = json.loads(Path(command[3]).read_text())
        self.assertEqual(job["context"]["target"], self.target)
        self.assertEqual(job["env"]["CORGI_ANNOTATE_TUI"], str(self.fake_tui))
        self.assertEqual(job["env"]["OPENCODE_DB"], "/custom/session.db")
        self.assertEqual(self.calls(["focus"])[0]["args"], ["focus", "99", "--viewer", "1"])
        self.cli("_run", command[3])
        self.assertFalse(Path(command[3]).exists())

    def test_bridge_refuses_a_different_destination(self):
        os.environ["CORGI_ANNOTATE_TARGET"] = json.dumps(self.target)
        result = self.cli("agent", "prompt", "8", "feedback", success=False)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "agent_not_found")

    def test_copy_failure_does_not_archive(self):
        notes = annotate.Notes("test")
        notes.add("source", "quote", "note")
        with patch.object(annotate, "clipboard", side_effect=annotate.Error("unavailable")):
            with self.assertRaises(annotate.Error):
                notes.handoff("copy-archive", self.target)
        self.assertEqual(len(notes.rows()), 1)
        with patch.object(annotate, "clipboard") as copied:
            notes.handoff("copy-archive", self.target)
        self.assertIn("quote", copied.call_args.args[0])
        self.assertEqual(len(notes.rows(True)), 1)

    def test_copy_does_not_wait_for_forked_clipboard_owner(self):
        # xclip and wl-copy fork a child that keeps serving the selection.
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        copied, owner = self.root / "copied.txt", self.root / "owner.pid"
        fake = bin_dir / "xclip"
        fake.write_text(f"#!{sys.executable}\n" + f'''
import os, pathlib, sys, time
pathlib.Path({str(copied)!r}).write_text(sys.stdin.read())
if os.fork() == 0:
    pathlib.Path({str(owner)!r}).write_text(str(os.getpid()))
    time.sleep(30)
''')
        fake.chmod(0o755)
        def stop_owner():
            if owner.exists():
                try:
                    os.kill(int(owner.read_text()), 9)
                except (OSError, ValueError):
                    pass
        self.addCleanup(stop_owner)
        os.environ["PATH"] = str(bin_dir)
        started = time.monotonic()
        with patch.object(annotate.sys, "platform", "linux"):
            annotate.clipboard("notes")
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(copied.read_text(), "notes")

    def test_unexpected_snapshot_is_reported_without_traceback(self):
        del self.state["workspaces"]
        self.save_snapshot()
        result = self.cli("export", success=False)
        self.assertIn("corgi-annotate: Unsupported Corgi snapshot", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_workspace_is_reported_without_traceback(self):
        self.state["workspaces"] = []
        self.save_snapshot()
        result = self.cli("export", success=False)
        self.assertIn("corgi-annotate: Workspace 1", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_launch_removes_stale_jobs_only(self):
        jobs = self.root / "state/corgi-annotate/jobs"
        jobs.mkdir(parents=True)
        stale, recent = jobs / "stale.json", jobs / "recent.json"
        for job in (stale, recent):
            job.write_text("{}")
        old = time.time() - 2 * 86400
        os.utime(stale, (old, old))
        self.cli("open", str(self.root))
        self.assertFalse(stale.exists())
        self.assertTrue(recent.exists())

    def test_concurrent_captures_keep_every_note(self):
        processes = [subprocess.Popen([sys.executable, str(SCRIPT), "capture", "--text", str(i), "--comment", "note"],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(os.environ)) for i in range(6)]
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, stderr.decode())
        self.assertEqual(self.cli("export").stdout.count("## Annotation"), 6)

    def test_backend_rejects_changed_download(self):
        os.environ.pop("CORGI_ANNOTATE_TUI")
        def download(argv, **kwargs):
            Path(argv[-1]).write_bytes(b"not the release")
        with patch.object(annotate, "run", side_effect=download):
            with self.assertRaisesRegex(annotate.Error, "checksum mismatch"):
                annotate.backend()
        self.assertFalse(list((self.root / "data").rglob("plannotator-tui-*")))


if __name__ == "__main__":
    unittest.main()
