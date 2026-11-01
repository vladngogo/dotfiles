#!/usr/bin/env python3
"""Opt-in real Corgi/Plannotator smoke test; all panes and data are disposable.

Run after corgi-annotate setup: python3 tests/smoke_corgi_annotate.py
Only agent detection is simulated. Splits, rendering, keys, reads and delivery
use the installed Corgi and Plannotator binaries, with no live agent recipient.
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

SCRIPT = Path(__file__).resolve().parents[1] / "corgi/bin/corgi-annotate"


def main():
    corgi = shutil.which("corgi")
    assert corgi, "Install Corgi first"
    backend = subprocess.check_output([sys.executable, str(SCRIPT), "setup"], text=True).strip()
    temp_parent = "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None
    with tempfile.TemporaryDirectory(prefix="annotate-smoke-", dir=temp_parent) as tmp:
        root = Path(tmp)
        env = {"HOME": tmp, "PATH": os.environ["PATH"], "SHELL": "/bin/sh", "TERM": "xterm-256color",
               "LANG": "C.UTF-8", "CORGI_SOCKET": str(root / "control.sock"),
               "XDG_STATE_HOME": str(root / "state"), "XDG_CONFIG_HOME": str(root / "config"),
               "XDG_DATA_HOME": str(root / "data"), "PLANNOTATOR_DATA_DIR": str(root / "plannotator"),
               "CORGI_ANNOTATE_TUI": backend}
        received = root / "received.txt"
        received.touch()
        recipient = root / "recipient.py"
        recipient.write_text("import os, tty\n"
                             "tty.setraw(0)\n"
                             "print('SMOKE recipient ready', flush=True)\n"
                             f"with open({str(received)!r}, 'ab', buffering=0) as f:\n"
                             "    while True: f.write(os.read(0, 65536))\n")
        document = root / "sample.md"
        document.write_text("# Smoke document\n\nReview this implementation.\n")
        transcript = root / "reply.jsonl"
        transcript.write_text(json.dumps({"type": "assistant", "uuid": "smoke-message", "message": {
            "role": "assistant", "content": [{"type": "text", "text": "Smoke assistant reply."}]}}) + "\n")
        database = root / "data/opencode/opencode.db"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE session_v2 (id TEXT PRIMARY KEY)")
            db.execute("INSERT INTO session_v2 VALUES ('ses_smoke')")
            db.execute("CREATE TABLE session_message (id TEXT, session_id TEXT, type TEXT, data TEXT, time_created INTEGER, seq INTEGER)")
            db.execute("INSERT INTO session_message VALUES (?, ?, ?, ?, ?, ?)",
                       ("msg_smoke", "ses_smoke", "assistant", json.dumps({"content": [
                           {"type": "text", "text": "Smoke OpenCode reply."}]}), 1793404800000, 1))
        metadata = root / "agent.json"
        metadata.write_text(json.dumps({"provider": "claude", "session": "smoke-session", "transcript": str(transcript)}))
        target_file = root / "target.txt"
        wrapper = root / "corgi-test-wrapper"
        wrapper.write_text(f"#!{sys.executable}\n" + f"""
import json, pathlib, subprocess, sys
args = sys.argv[1:]
if args == ['list', '--json']:
    reply = json.loads(subprocess.check_output([{corgi!r}, *args]))
    target = int(pathlib.Path({str(target_file)!r}).read_text())
    for pane in reply['result']['panes']:
        if pane['id'] == target:
            pane['agent'].update(json.loads(pathlib.Path({str(metadata)!r}).read_text()))
            pane['agent'].update(state='idle', attention='none',
                                 paused=False, tool_active=False, compacting=False)
    print(json.dumps(reply))
else:
    sys.exit(subprocess.call([{corgi!r}, *args]))
""")
        wrapper.chmod(0o755)
        env["CORGI_ANNOTATE_CORGI"] = str(wrapper)

        def command(*args):
            result = subprocess.run([corgi, "--no-agent", *map(str, args), "--json"],
                                    env=env, cwd=tmp, capture_output=True, text=True, timeout=15)
            assert result.returncode == 0, result.stderr
            reply = json.loads(result.stdout)
            assert reply["ok"], reply
            return reply["result"]

        def wait_for(check, label):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                value = check()
                if value:
                    return value
                time.sleep(0.1)
            raise AssertionError(f"Timed out: {label}")

        def cli(*args):
            result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                    env=env, cwd=tmp, capture_output=True, text=True, timeout=20)
            assert result.returncode == 0, result.stdout + result.stderr
            return result.stdout

        def screen(pane):
            return command("pane", "read", pane)["text"]

        with (root / "server.log").open("w") as log:
            server = subprocess.Popen([corgi, "serve"], env=env, cwd=tmp, stdout=log, stderr=log)
            try:
                wait_for(lambda: (root / "control.sock").exists(), "isolated runtime")
                state = command("list")
                workspace = state["workspaces"][0]["id"] if state["workspaces"] else command(
                    "workspace", "new", "smoke", "--cwd", tmp)["workspace"]
                target = command("tab", "new", "--workspace", workspace, "--command",
                                 shlex.join([sys.executable, str(recipient)]))["pane"]
                target_file.write_text(str(target))
                wait_for(lambda: "SMOKE recipient ready" in screen(target), "recipient startup")
                source = command("tab", "new", "--workspace", workspace, "--command",
                                 "printf 'SMOKE shell output\\n'; exec /bin/sh")['pane']
                env["CORGI_PANE"] = str(source)
                wait_for(lambda: "SMOKE shell output" in screen(source), "source shell startup")

                for args, title, comment in [
                    (("open", str(document)), "Smoke document", "document-smoke-comment"),
                    (("terminal",), "SMOKE shell output", "terminal-smoke-comment"),
                    (("last-newest",), "Smoke assistant reply", "reply-smoke-comment"),
                    (("last-newest",), "Smoke OpenCode reply", "opencode-smoke-comment"),
                ]:
                    if comment == "opencode-smoke-comment":
                        metadata.write_text(json.dumps({"provider": "opencode2", "session": "ses_smoke",
                                                        "transcript": str(database)}))
                    opened = cli(*args)
                    pane = int(opened.strip().split()[-1])
                    wait_for(lambda: title in screen(pane), f"{args[0]} rendering")
                    command("pane", "keys", pane, "c")
                    wait_for(lambda: "save" in screen(pane).lower(), "comment editor")
                    command("pane", "send", pane, comment)
                    command("pane", "keys", pane, "enter")
                    wait_for(lambda: comment in screen(pane), "saved annotation")
                    command("pane", "keys", pane, "E")
                    try:
                        wait_for(lambda: comment in received.read_text(), "feedback delivery")
                    except AssertionError:
                        print(screen(pane), file=sys.stderr)
                        raise
                    command("pane", "keys", pane, "q")
                    print(f"PASS {args[0]}: automatic agent selection from shell, real review and delivery")

                cli("capture", "--text", "captured terminal quote", "--comment", "capture-smoke-comment")
                assert "capture-smoke-comment" in cli("export")
                cli("send-archive")
                wait_for(lambda: "capture-smoke-comment" in received.read_text(), "captured note delivery")
                assert "capture-smoke-comment" not in cli("export")
                assert "capture-smoke-comment" in cli("export", "--archived")
                print("PASS capture: persistent note, real delivery, archive after success")
                assert list((root / "plannotator").rglob("annotations.json")), "document notes not persisted"
                print("PASS document annotations persisted by real Plannotator")
            finally:
                if server.poll() is None:
                    try:
                        subprocess.run([corgi, "shutdown"], env=env, capture_output=True, timeout=15, check=True)
                    finally:
                        try:
                            server.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            server.terminate()
                            server.wait(timeout=5)


if __name__ == "__main__":
    main()
