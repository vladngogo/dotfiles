# dotfiles

Portable nvim and tmux configuration.

## Setup

```bash
git clone git@github.com:jlucas/dotfiles.git ~/github/dotfiles
cd ~/github/dotfiles
chmod +x install.sh
./install.sh
```

The install script symlinks configs into place, backing up any existing files first.

## Structure

```
nvim/
  init.lua          — single-file nvim config (lazy.nvim, telescope, gitsigns, lsp, etc.)
  lazy-lock.json    — plugin lockfile
tmux/
  tmux.conf         — tmux config (Ctrl-a prefix, vim keys, tokyonight theme)
```
