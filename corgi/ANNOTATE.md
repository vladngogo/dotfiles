# Corgi Annotate

`corgi-annotate` brings Herdr Annotate-style workflows to Corgi: review Markdown
documents, annotate an agent's reply or terminal output, and send feedback to an
agent pane. It uses [Plannotator TUI](https://github.com/plannotator/plannotator-tui)
for visual reviews and a local SQLite store for captured terminal notes.

## Install

Requirements: Corgi, Python 3.9+, and `curl` for the first backend download.

```bash
./install.sh
corgi-annotate setup
```

The installer links `~/.local/bin/corgi-annotate` into this checkout. Put that
directory on PATH. `setup` downloads Plannotator TUI **v0.9.9**, checks its pinned
SHA-256, and installs it locally; the first visual review also does this if needed.
Linux amd64/arm64 and macOS arm64/x86_64 backend builds are supported.

## Quick start

Run these from a shell inside your Corgi workspace:

```bash
corgi-annotate open plan.md    # review a document
corgi-annotate last            # choose a recent assistant reply
corgi-annotate last-newest     # review the newest reply directly
corgi-annotate terminal        # review this pane's recent terminal output
```

Agent selection is automatic: use the calling agent, or the sole running agent
in the current workspace. If there are several, a numbered picker shows their
names, providers and states. Choose a number, or `q` to cancel. No pane-ID lookup
is needed. `last` reads the selected agent's reply; `terminal` keeps reading the
calling pane and sends feedback to the selected agent. `open` keeps the calling
pane's working directory.

Interactive commands open a new split beside the source pane. `--here` uses the
calling terminal instead. `open` without a path browses Markdown files in the
source pane's working directory.

In the review UI:

| Key | Action |
|---|---|
| `j` / `k`, or click | Select a document block |
| `v`, then movement keys; `Enter` | Select and confirm a range; mouse dragging also works |
| `c` | Comment on the block or selection |
| `Enter` in comment editor | Save comment |
| `Alt+Enter` or `Ctrl+j` in comment editor | Insert a newline |
| `E` | Send feedback to the selected agent (clipboard when targeting a shell) |
| `S` in reply review | Send and quit |
| `m` in file/folder review | Resend, finish/archive, undo, or browse history |
| `q` | Quit review |

File reviews retain notes and send only new or edited feedback by default.
Terminal/reply reviews are transient; send feedback before quitting.

## Capture selected text and keep notes

Copy terminal text, then run:

```bash
corgi-annotate capture
```

This opens `$VISUAL`, `$EDITOR`, or `vi` in a split for your comment. Save and quit
the editor to keep it; an empty comment cancels. Lines beginning with `#` in this
editor are instructions and are omitted from the saved comment.

For SSH or automation, pass the quote directly:

```bash
corgi-annotate capture --text 'unexpected output' --comment 'Explain this'
corgi-annotate capture --file output.txt
some-command | corgi-annotate capture --stdin
```

In Neovim running inside Corgi, select text in visual mode and press **Space a**.
The selection goes straight to `capture`, without requiring a clipboard.

Manage captured notes from any pane in the same workspace folder/runtime:

```bash
corgi-annotate manage
corgi-annotate export                 # Markdown on stdout
corgi-annotate copy-context           # copy active notes, keep them active
corgi-annotate copy-archive           # copy, then archive
corgi-annotate paste-archive          # insert into agent input; no Enter
corgi-annotate send-archive           # insert and submit to the agent
corgi-annotate export --archived
corgi-annotate restore 1              # use an ID shown by manage
corgi-annotate archive 1
```

The manager accepts `e ID` (edit), `a ID` (archive), `u ID` (restore), `h`
(history), `y` (copy active notes), `p` (paste and archive active notes), `s`
(send and archive active notes), and `q`.

## Choosing the source and recipient

- `--pane ID` explicitly selects the source and default recipient, bypassing
  automatic agent selection. `--pane current` uses `CORGI_PANE`. Use
  `corgi-annotate panes` to find IDs when you want an explicit override.
- Without `--pane`, `--viewer ID` selects that viewer's focused pane; otherwise
  the calling Corgi pane is used, then the sole attached viewer's focused pane.
  Ambiguous selection requires an explicit pane or viewer.
- `--to ID` sends feedback to a different detected agent. For example, review
  build output in shell pane 10 and send comments to agent pane 7:
  `corgi-annotate terminal --pane 10 --to 7`.
- `manage`, `paste-archive`, and `send-archive` also select an agent automatically.
  Capturing, exporting, copying, and archiving notes need no recipient or picker.
- With no agents in the workspace, document/terminal reviews use the clipboard;
  `last` requires an agent, and paste/send commands require an agent recipient.
- The picker reads your controlling terminal, leaving piped input and stdout
  untouched. Without an interactive terminal, ambiguous selection requires
  `--pane ID` for replies or `--to ID` for delivery. Agents in other workspaces
  and exited panes are excluded. Readiness is checked when sending, so a busy
  agent can still be selected for a review.
- `CORGI_SOCKET` selects the runtime. A selected viewer is focused on the new
  review split; without an unambiguous viewer, select the split manually.
- `terminal --lines N` reads 1–10000 recent lines (default 200).

Before each delivery, the adapter rechecks the runtime PID, pane binding, process,
provider, session, and agent readiness. A busy agent or dialog leaves feedback
pending. If a delivery response is lost, inspect the recipient before retrying;
the adapter never retries automatically. Corgi's readiness check and input send
are separate operations, so a small race remains between them.

## Clipboard and SSH

Capture reads the host clipboard with `pbpaste`, `wl-paste`, `xclip`, or `xsel`.
Over SSH, the remote host usually cannot read your local clipboard; use the
Neovim mapping, `--text`, `--file`, `--stdin`, or `terminal` instead.

Captured-note copying uses the host clipboard when available, then OSC 52 when
stdout is a terminal. Plannotator's clipboard delivery uses OSC 52. Your terminal
must permit it; OSC 52 has no delivery acknowledgement. `export` always provides
plain Markdown and works with redirection.

## Migrating from Herdr Annotate

Use `corgi-annotate` for the workflows above. Command names prefixed with
`annotate.` are also accepted, for example `corgi-annotate annotate.capture`.
The replacement uses Corgi's numeric pane IDs and `CORGI_SOCKET`.

Corgi currently exposes shortcut presets rather than arbitrary annotation
actions. Launch from a shell, a terminal/OS command binding with `--viewer ID`,
or the Neovim mapping. Herdr overlay/popup integration and its native selection
shortcuts are not available. Captured notes start in the new SQLite store;
existing Herdr captures are not automatically imported.

`last` requires Corgi to identify an exact transcript or session and a provider
supported by Plannotator. OpenCode 2 maps to Plannotator's `opencode` reader.
If detection is incomplete or the host's transcript format is unsupported, use
`terminal` to review visible output.

## Storage and configuration

| Item | Location / override |
|---|---|
| Captured notes | `${XDG_STATE_HOME:-~/.local/state}/corgi-annotate/annotations.sqlite3` |
| Pending split launch context | Same directory, `jobs/`; consumed when the review starts |
| Backend binary | `${XDG_DATA_HOME:-~/.local/share}/corgi-annotate/bin/plannotator-tui-v0.9.9` |
| Document notes/history | Plannotator data directory; override with `PLANNOTATOR_DATA_DIR` |
| Custom backend executable | `CORGI_ANNOTATE_TUI` |
| Custom Corgi executable | `CORGI_ANNOTATE_CORGI` |

Captured notes are scoped by socket path and workspace folder, so they survive
pane changes. Two workspaces using the same folder/runtime share captured notes.
Document notes use Plannotator's file-based persistence and do not appear in
`manage` or the captured-note `export` command. The backend's
`--export file.md` can export those separately.

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 tests/smoke_corgi_annotate.py
```

The opt-in smoke test starts a disposable Corgi runtime with an isolated HOME and
socket. It drives the real review UI and checks feedback received by a dummy
process. Only the dummy's agent-detection metadata is simulated. It exercises
document, terminal, Claude-transcript and OpenCode-database reply reviews with
automatic agent selection from a shell, plus persistent captures and archiving.
