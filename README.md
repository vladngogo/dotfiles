# dotfiles

Portable Neovim and [Corgi](https://corgi.computer/) setup. Tokyonight in Neovim;
Corgi's native theme and shortcuts with a Ctrl-a prefix for terminals and agents.

## Requirements

- **Neovim 0.12.0+** — `nvim-treesitter` tracks its `main` branch, which requires 0.12
  and does not work on 0.11.
- **`tree-sitter` CLI >= 0.26.1**, matching your CPU architecture — install via a
  package manager, *not npm*. The `main` branch shells out to `tree-sitter build`
  for every parser, so highlighting silently does nothing without it.
  ```bash
  brew install tree-sitter-cli      # macOS
  cargo install tree-sitter-cli     # Linux (or your distro package)
  ```
- **A C compiler**, plus `tar` and `curl` on PATH — used to fetch and compile parsers.
- **A Nerd Font** in your terminal — `nvim-web-devicons`, `lualine`, and the
  gitsigns delete glyph all render icon codepoints that a regular font doesn't
  have. Without one they show as boxes/tofu instead of icons. Grab one from
  [nerdfonts.com](https://www.nerdfonts.com/) and set it as your terminal's font.
- **A clipboard tool**, for Neovim's `unnamedplus` to reach the system
  clipboard — `pbcopy` (macOS, built in), `wl-clipboard` (Wayland), or
  `xclip`/`xsel` (X11). Neovim autodetects whichever is installed.
- **macOS Apple Silicon, Linux amd64/arm64, or WSL** for Corgi's official
  binaries. `install.sh` installs Corgi when it is missing using its
  [official installer](https://corgi.computer/install.sh), pinned to a release and
  SHA-256 checksum before execution. This requires `curl` and `sha256sum` or `shasum`.
- **Python 3.11+** for `corgi-annotate`, the terminal/document annotation CLI.

`install.sh` warns if the tree-sitter CLI is missing, too old, or built for the wrong
architecture, but does not install it for you.

## Setup

```bash
git clone git@github.com:vladngogo/dotfiles.git ~/github/dotfiles
cd ~/github/dotfiles
./install.sh
```

The install script installs Corgi if needed, seeds its preferences, and symlinks
the Neovim and agent configs, backing up existing regular files first.
On first launch nvim installs its plugins and treesitter parsers automatically —
give it a minute before expecting highlighting to work.

### Corgi setup and migration

Run `corgi` in your project directory. First-run setup starts with the **Corgi**
shortcut preset and **Ctrl-a** prefix from `corgi/viewer.json`; complete setup to
keep them. Use `corgi onboard` (or `Ctrl-a i`) to revisit setup and import existing
tmux or Herdr sessions. Start Corgi in a terminal outside the session being migrated.
The [import guide](https://github.com/tals/corgi/blob/main/docs/reference.md#set-up-and-import)
explains layout copies and supported Herdr process handoffs.

Preferences are copied once to `${XDG_STATE_HOME:-$HOME/.local/state}/corgi/viewer.json`.
Corgi rewrites this file when settings change, so it is a local file rather than
a symlink. Re-running `install.sh` preserves existing preferences; use setup to
select **Corgi**, **Ctrl-a**, and the **Corgi** theme on an existing installation.
Workspace layouts, recovery data and accounts remain local. Changes to the
tracked defaults apply to fresh installations.

The installer removes `~/.tmux.conf` only when it is the old symlink into this
checkout. There are no Herdr install scripts or settings tracked in this repo.
If your shell startup files launch tmux or Herdr automatically, change that command
to `corgi` too.

Corgi normally installs its launcher at `~/.local/bin/corgi`. Ensure
`~/.local/bin` is on PATH (open a new shell after the upstream installer updates
your shell configuration). Run `corgi update` to update an existing installation.
Fresh installations bootstrap release `20261030T200700Z-f539bbadd798`. To bump
that baseline, review the new versioned `releases/<version>/install.sh`, update
both `version` and `expected` in `install_corgi()`, and rerun the checks below.

### Annotations with Corgi

The installer also links `corgi-annotate`, a Herdr Annotate-style replacement using
Plannotator TUI. Run `corgi-annotate setup` to install its checksum-pinned backend.

```bash
corgi-annotate plan.md               # review a document in a new split (same as open plan.md)
corgi-annotate last-newest           # annotate the latest assistant reply
corgi-annotate terminal              # annotate this pane's terminal output
```

Run from a Corgi shell: the workspace's sole agent is selected automatically;
multiple agents get a named picker, where Enter repeats your last choice. `--pane`
and `--to` provide explicit overrides.

Use `c` to comment, Enter to save, and `E` to send feedback. In Neovim, **Space A**
reviews the current file and visual-mode **Space a** captures selected text as a
persistent note. See the
[annotation guide](corgi/ANNOTATE.md) for capture management, targeting, SSH,
clipboard support, and migration details.

### Secrets and keys

`keystash` stores API keys and other secrets in `~/.secrets` (override with
`KEYSTASH_DIR`). The secret is read from stdin with echo off, so it never shows
on screen, in shell history, or in `ps`. The directory is 700, files are 600 from
the moment they are created, and existing names are never overwritten without `--force`.

```bash
keystash save openai                   # paste (multi-line is fine), then Ctrl-D
wl-paste -n | keystash save openai     # or pipe it from the clipboard
export OPENAI_API_KEY="$(cat "$(keystash path openai)")"
keystash rsa deploy                    # 4096-bit RSA pair; prompts for a passphrase
ssh -i "$(keystash path deploy)" host
keystash list                          # names only, never contents
```

`keystash rsa` uses `ssh-keygen` (`--bits N` for a larger key, minimum 3072). For new SSH keys
where RSA isn't required, `ssh-keygen -t ed25519` is smaller and faster.
Input is stored byte for byte, so pressing Enter before Ctrl-D adds a trailing newline.
`settings.json` and `guard-bash` guard against agents accidentally reading the default
`~/.secrets` path; like the other credential rules, they don't cover a custom
`KEYSTASH_DIR` or a path hidden behind `$(keystash path …)`.

## Structure

```
bin/keystash        — save secrets and generate RSA keys privately (→ ~/.local/bin)
nvim/
  init.lua          — single-file nvim config (lazy.nvim, telescope, gitsigns, lsp, etc.)
  lazy-lock.json    — plugin lockfile
corgi/
  viewer.json       — first-run preferences (Corgi preset/theme, Ctrl-a prefix)
  bin/corgi-annotate — document/reply reviews and persistent terminal notes (→ ~/.local/bin)
  ANNOTATE.md       — annotation commands, targeting and migration guide
tests/              — installer/annotation regression tests and opt-in live smoke test
agents/             — tool-agnostic agent config (the source of truth)
  AGENTS.md         — global instructions, linked for every agent tool
  skills/<name>/    — SKILL.md skills (build-evals, fold-or-keep)
  hooks/guard-bash  — blocks pushes to main/master, force pushes, and credential-path access
  hooks/lint-edit   — runs shellcheck on shell scripts right after an agent edits them
  bin/agent-eval    — eval loop: run cases in parallel worktrees, grade, compare (→ ~/.local/bin)
  bin/agent-link    — attach repos/<repo>.md to a repo as CLAUDE.local.md, uncommitted
  repos/<repo>.md   — personal notes for one repo
  tests/            — `python3 -m unittest discover -s agents/tests`
claude/             — thin Claude Code adapter
  CLAUDE.md         — imports `~/.claude/AGENTS.md` and, if present, `~/.claude/local.md`
  settings.json     — deny reads of secrets, allow read-only system queries, wires the guard and lint hooks
  merge-settings    — merge settings.json into ~/.claude/settings.json (install.sh)
opencode/           — thin OpenCode V2 adapter
  install           — link shared instructions/skills and archive stale integrations
```

### Agents

Write anything generic in `agents/`; per-tool directories stay thin adapters.
Instructions come in three layers:

| Layer | Where | Committed to the repo? |
|---|---|---|
| Personal, every repo | `agents/AGENTS.md` → `~/.claude/CLAUDE.md` | no |
| Team, one repo | that repo's `AGENTS.md` (+ `CLAUDE.md` containing `@AGENTS.md`) | yes |
| Personal, one repo | `agents/repos/<repo>.md` → `CLAUDE.local.md` via `agent-link` | no |
| Personal, one machine | `~/.claude/local.md`, outside this repo (Claude Code only) | no |

Test for where a line goes: would a teammate on a different OS, who's never
seen your setup, get worse results without it? Then it's the repo's. If it
would be wrong or irrelevant for them, it's personal. Rules that must never
break go in CODEOWNERS, branch protection, hooks or CI, not only in prose.

Machine facts (hostnames, hardware, local doc paths) go in `~/.claude/local.md`,
which never enters the repo. Claude Code skips the import when the file is missing.

Run `agent-link --init` in a fresh clone to attach (or create) your notes. It
hides the link with `.git/info/exclude`, so the team's `.gitignore` is untouched.

`install.sh` links individual items into `~/.claude/`, `~/.codex/`, and
`${XDG_CONFIG_HOME:-~/.config}/opencode/`, never
the whole directory, because those also hold credentials and session history.
`settings.json` is the exception: Claude Code (`/config`) and Corgi rewrite it,
so `claude/merge-settings` adds the repo's permission rules and hooks to the local
file instead, keeping everything already there. To share a new setting, add it
to `claude/settings.json` and re-run `install.sh`; removing one from the repo
does not remove it locally, and a repo hook deleted locally comes back on the
next install (remove it from the repo to opt out).

OpenCode gets `AGENTS.md` and individual shared skill links. Server configuration
and `cli.json` preferences stay local; no custom agents or plugins are required.
The installer archives dangling links to this checkout's old OpenCode files and
Herdr-marked integrations under the OpenCode config directory's `retired/` folder,
removing their CLI plugin references while preserving other preferences. Original
CLI settings are backed up there. Unrelated plugins and configuration are preserved.

Skills go stale as models improve. Before adding one, check the model doesn't
already do the task well without it, and prune ones that no longer earn their
place.

`guard-bash` and the `settings.json` deny rules stop *accidents*, not a determined
agent: a script or `eval` can hide any command. Server-side branch protection
and a sandbox are the real boundaries.

### Checks

```bash
shellcheck install.sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s agents/tests -v
```

---

## Neovim Cheat Sheet

Leader key is **Space**.

### Navigation

| Key | Mode | Action |
|-----|------|--------|
| `Ctrl-h/j/k/l` | Normal | Move between splits |
| `gd` | Normal | Go to definition (LSP) |
| `gr` | Normal | Go to references (LSP) |
| `K` | Normal | Hover docs (LSP) |
| `[d` / `]d` | Normal | Prev / next diagnostic |
| `[h` / `]h` | Normal | Prev / next git hunk |
| `jk` | Insert | Escape to normal mode |
| `Esc` | Normal | Clear search highlight |

### File Tree (nvim-tree)

| Key | Action |
|-----|--------|
| `Space e` | Toggle file tree |
| `Space o` | Focus file tree |

### Telescope (Fuzzy Finder)

| Key | Action |
|-----|--------|
| `Space ff` | Find files |
| `Space fg` | Live grep (search content) |
| `Space fb` | Open buffers |
| `Space fh` | Help tags |

### LSP / Code

| Key | Action |
|-----|--------|
| `Space rn` | Rename symbol |
| `Space ca` | Code action |
| `Space f` | Format file |
| `Space a` (visual mode) | Capture selection as a Corgi annotation |
| `Space A` | Review the current file in a Corgi split |

### Git

| Key | Action |
|-----|--------|
| `Space gs` | Git status (fugitive) |
| `Space gc` | Git commit |
| `Space gp` | Git push |
| `Space gl` | Git log |
| `Space hp` | Preview hunk (gitsigns) |
| `Space hr` | Reset hunk (gitsigns) |

### Autocomplete (nvim-cmp)

| Key | Action |
|-----|--------|
| `Ctrl-Space` | Trigger completion |
| `Tab` / `Shift-Tab` | Navigate completion items |
| `Enter` | Confirm selection |

---

## Corgi Cheat Sheet

These shortcuts use the **Corgi** preset with **Ctrl-a** as the prefix. Press and
release the prefix, then the next key; `Ctrl-a Ctrl-a` sends a literal Ctrl-a.
`Ctrl-a ?` shows your current keymap; `corgi keys corgi` prints the preset's table.

### Workspaces and agents

| Key / command | Action |
|-----|--------|
| `corgi` | Start or reconnect (shell) |
| `corgi list` | List workspaces, tabs and panes (shell) |
| `Ctrl-a N` | New workspace (name and folder) |
| `Ctrl-a w` | Choose workspace |
| `Ctrl-a a` | Choose agent |
| `Ctrl-a g` | Find agent |
| `F1` / `Ctrl-a f` | Jump to an agent needing attention |
| `Ctrl-a d` / `Ctrl-a q` | Detach, leaving processes running |

### Tabs and panes

| Key | Action |
|-----|--------|
| `Ctrl-t` / `Ctrl-a c` | New tab: agent or terminal picker |
| `Ctrl-a p` / `Ctrl-a n` | Previous / next tab |
| `Ctrl-a 1-9` | Select tab |
| `Ctrl-a ,` | Rename tab |
| `Ctrl-a X` | Close tab and its processes |
| `Ctrl-a v` | Split right |
| `Ctrl-a -` | Split down |
| `Ctrl-a h/j/k/l` | Focus left / down / up / right |
| `Ctrl-a r`, then `h/j/k/l` | Resize pane; another key exits resize mode |
| `Ctrl-a x` | Close pane and its processes |
| `Ctrl-a z` | Toggle pane zoom |
| `Ctrl-a u` | Reopen the last recoverable closed agent |

### Copy, review and settings

| Key | Action |
|-----|--------|
| `Ctrl-a s` / mouse wheel | Enter scroll / copy mode |
| `j/k`, `g/G`, PageUp/PageDown | Navigate scrollback |
| `/`, then `n/N` | Search scrollback, next / previous match |
| `y` / Enter | Copy in scroll mode |
| `q` | Exit scroll mode |
| `Ctrl-a e` | Open / focus / close the review panel |
| `Ctrl-a b` | Toggle sidebar |
| `Ctrl-a m` | Mute / unmute sounds |
| `Ctrl-a i` | Open setup |

---

## Common Workflows

### Quick project session

```bash
cd ~/github/myproject
corgi
# Ctrl-a v to split right, then open nvim on one side
# Ctrl-a d to detach; run corgi again to reconnect
```

### Fuzzy find + jump to definition

1. `Space ff` to find and open a file
2. Navigate to a function call
3. `gd` to jump to its definition
4. `Ctrl-o` to jump back

### Code review flow in nvim

1. `Space gs` to open git status (fugitive)
2. Move cursor to a changed file, press `=` to inline diff
3. `]h` / `[h` to jump between hunks
4. `Space hp` to preview a hunk, `Space hr` to reset it

### Search and replace across files

1. `Space fg` to live grep for a pattern
2. Send results to quickfix: `Ctrl-q` in Telescope
3. `:cdo s/old/new/g | update` to replace across all matches

### Multi-pane dev layout

```bash
# Terminal: start Corgi, split into 3 panes
corgi
# Ctrl-a v → split right (editor | terminal)
# Ctrl-a - → split down in the right pane (terminal on top, logs on bottom)
# Ctrl-a h/j/k/l to move between panes; Ctrl-h/j/k/l for Neovim splits
```

---

## Tips and Tricks

- **Clipboard** — nvim uses `unnamedplus`; drag terminal text in Corgi to copy it. Hold Shift over mouse-aware applications.
- **Mouse navigation** — click tabs, panes or sidebar agents to focus them; drag split dividers to resize.
- **Tab shortcuts start at 1** with the Corgi preset.
- **Inline git blame** is always on via gitsigns — see who wrote each line without leaving nvim.
- **`:Lazy`** opens the plugin manager UI — update plugins with `U`, check status, sync lockfile.
- **`:Mason`** manages LSP servers — currently auto-installs `gopls`. Add more in `init.lua`.
- **Relative line numbers** make `5j` / `12k` jumps easy — just read the number next to the target line.
- **`Ctrl-a z`** zooms a Corgi pane and back — great for temporarily focusing on one pane.
- **Agent integration** — run your agent in a Corgi pane; Corgi detects it and handles its integration. `corgi integration status` reports hook status.
- **Remote sessions** — `ssh -t host corgi` reconnects to the runtime on that host.

---

## Troubleshooting

### No syntax highlighting

Start with `:checkhealth vim.treesitter` — it lists every parser it found, its ABI
version, and its path. Parsers install to `~/.local/share/nvim/site/parser/`.

**`attempt to call field 'get_installed' (a nil value)` on startup**

`nvim-treesitter` is on the archived `master` branch instead of `main`. The two have
incompatible APIs, and lazy.nvim aborts the whole plugin config on this error.

The spec in `init.lua` pins `branch = "main"` — if that pin is ever dropped,
lazy.nvim checks out the plugin's default branch (`master`) and rewrites
`lazy-lock.json`, so the problem returns on every sync. Verify with:

```bash
grep treesitter nvim/lazy-lock.json     # must read "branch": "main"
```

Then `:Lazy sync` to correct it.

**`incompatible architecture (have 'x86_64', need 'arm64')`**

Parsers were compiled for a different CPU than your nvim — typically leftovers from
an Intel → Apple Silicon migration. Highlighting fails even though the parsers look
installed. Check what you have, then rebuild:

```bash
file "$(command -v tree-sitter)"                        # must match `uname -m`
file ~/.local/share/nvim/site/parser/*.so | grep -c arm64

rm -f ~/.local/share/nvim/site/parser/*.so              # clear stale parsers
nvim -c 'TSUpdate'                                      # rebuild for this arch
```

Fix the CLI's architecture *first* — rebuilding with an x86_64 CLI just reproduces
the same broken parsers. Note that stale `.so` files inside the plugin directory are
untracked, so they survive branch switches and shadow correct parsers via
`runtimepath`; delete them rather than assuming a reinstall clears them.

**Highlighting works in some filetypes but not others**

The parser for that language isn't installed. `init.lua` installs a fixed list —
add the language there, or run `:TSInstall <lang>` for a one-off.

---

## Remap CapsLock to Escape

CapsLock is wasted real estate. Remapping it to Escape makes vim/nvim significantly more comfortable — no more reaching for the corner of the keyboard.

### macOS

1. **System Settings** (built-in, no install needed):
   - System Settings → Keyboard → Keyboard Shortcuts → Modifier Keys
   - Set CapsLock to Escape
   - Done. Works globally, survives reboots.

2. **Alternative — [Karabiner-Elements](https://karabiner-elements.pqrs.org/)** (more powerful):
   ```bash
   brew install --cask karabiner-elements
   ```
   - Open Karabiner-Elements → Simple Modifications
   - Map `caps_lock` → `escape`
   - Karabiner also supports dual-purpose keys (CapsLock = Esc on tap, Ctrl on hold) via Complex Modifications.

### Linux (X11)

Add to your `~/.profile` or `~/.bashrc`:

```bash
setxkbmap -option caps:escape
```

Or make it permanent in `/etc/default/keyboard`:

```
XKBOPTIONS="caps:escape"
```

Then run `sudo dpkg-reconfigure keyboard-configuration` and reboot.

**Dual-purpose** (Esc on tap, Ctrl on hold) — install [xcape](https://github.com/alols/xcape):

```bash
sudo apt install xcape
setxkbmap -option ctrl:nocaps       # CapsLock becomes Ctrl
xcape -e 'Control_L=Escape'         # tapping Ctrl fires Escape
```

### Linux (Wayland / GNOME)

```bash
gsettings set org.gnome.desktop.input-sources xkb-options "['caps:escape']"
```

### WSL

WSL inherits keyboard input from Windows, so you remap on the Windows side:

1. **PowerToys** (recommended):
   - Install [Microsoft PowerToys](https://github.com/microsoft/PowerToys)
   - Open PowerToys → Keyboard Manager → Remap a Key
   - Map `CapsLock` → `Esc`
   - Takes effect immediately, persists across reboots.

2. **Registry edit** (no install needed, requires reboot):
   Open PowerShell as Administrator:
   ```powershell
   $hexified = "00,00,00,00,00,00,00,00,02,00,00,00,01,00,3a,00,00,00,00,00".Split(',') | % { "0x$_" }
   $kMap = 'HKLM:\SYSTEM\CurrentControlSet\Control\Keyboard Layout'
   New-ItemProperty -Path $kMap -Name "Scancode Map" -PropertyType Binary -Value ([byte[]]$hexified)
   ```
   Reboot to apply. To undo, delete the `Scancode Map` value from that registry key and reboot.
