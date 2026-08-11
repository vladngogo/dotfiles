# dotfiles

Portable nvim and tmux configuration. Tokyonight theme across both.

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

`install.sh` warns if the CLI is missing, too old, or built for the wrong
architecture, but does not install it for you.

## Setup

```bash
git clone git@github.com:vladngogo/dotfiles.git ~/github/dotfiles
cd ~/github/dotfiles
./install.sh
```

The install script symlinks configs into place, backing up any existing files first.
On first launch nvim installs its plugins and treesitter parsers automatically —
give it a minute before expecting highlighting to work.

## Structure

```
nvim/
  init.lua          — single-file nvim config (lazy.nvim, telescope, gitsigns, lsp, etc.)
  lazy-lock.json    — plugin lockfile
tmux/
  tmux.conf         — tmux config (Ctrl-a prefix, vim keys, tokyonight theme)
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

## Tmux Cheat Sheet

Prefix is **Ctrl-a** (not the default Ctrl-b).

### Sessions

| Key | Action |
|-----|--------|
| `tmux new -s name` | New named session (shell) |
| `tmux a -t name` | Attach to session (shell) |
| `tmux ls` | List sessions (shell) |
| `Ctrl-a d` | Detach from session |
| `Ctrl-a s` | Switch session |

### Windows

| Key | Action |
|-----|--------|
| `Ctrl-a c` | New window |
| `Alt-h` / `Alt-l` | Previous / next window (no prefix) |
| `Ctrl-a 1-9` | Jump to window by number |
| `Ctrl-a ,` | Rename window |
| `Ctrl-a &` | Close window |

### Panes

| Key | Action |
|-----|--------|
| `Ctrl-a \|` | Split horizontal |
| `Ctrl-a -` | Split vertical |
| `Ctrl-h/j/k/l` | Move between panes (no prefix) |
| `Ctrl-a H/J/K/L` | Resize pane (5 cells) |
| `Ctrl-a x` | Close pane |
| `Ctrl-a z` | Toggle pane zoom (fullscreen) |

### Copy Mode (vi keys)

| Key | Action |
|-----|--------|
| `Ctrl-a [` | Enter copy mode |
| `v` | Begin selection |
| `Ctrl-v` | Toggle rectangle select |
| `y` | Yank to clipboard |
| `q` | Exit copy mode |

### Other

| Key | Action |
|-----|--------|
| `Ctrl-a r` | Reload tmux config |

---

## Common Workflows

### Quick project session

```bash
tmux new -s myproject
# opens a new tmux session named "myproject"
# Ctrl-a | to split, then open nvim on one side
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
# Terminal: start a session, split into 3 panes
tmux new -s dev
# Ctrl-a | → vertical split (editor | terminal)
# Ctrl-a - → horizontal split the right pane (terminal on top, logs on bottom)
# Ctrl-h/j/k/l to move between them
```

---

## Tips and Tricks

- **System clipboard works everywhere** — nvim uses `unnamedplus`, tmux yanks pipe to `xclip`. Copy in one, paste in the other.
- **Mouse is on** in tmux — click to select panes, scroll to see history. But keyboard is faster.
- **Escape has no delay** — `escape-time 0` in tmux means nvim mode switches are instant.
- **Windows start at 1** — both tmux windows and panes are 1-indexed (not 0).
- **Inline git blame** is always on via gitsigns — see who wrote each line without leaving nvim.
- **`:Lazy`** opens the plugin manager UI — update plugins with `U`, check status, sync lockfile.
- **`:Mason`** manages LSP servers — currently auto-installs `gopls`. Add more in `init.lua`.
- **Relative line numbers** make `5j` / `12k` jumps easy — just read the number next to the target line.
- **`Ctrl-a z`** zooms a tmux pane to fullscreen and back — great for temporarily focusing on one pane.
- **Splits open in the current directory** — `Ctrl-a |` and `Ctrl-a -` inherit the working directory of the current pane.

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
