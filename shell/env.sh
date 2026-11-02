# Shared by bash and zsh. Credentials belong to each application's local store.
# shellcheck shell=sh
dotfiles_prefix=""
for dotfiles_brew in /opt/homebrew /home/linuxbrew/.linuxbrew; do
    if [ -x "$dotfiles_brew/bin/brew" ]; then
        dotfiles_prefix="$dotfiles_brew/opt/python@3.13/libexec/bin:$dotfiles_brew/bin:$dotfiles_brew/sbin:"
        break
    fi
done
dotfiles_prefix="$HOME/.local/share/dotfiles/npm/bin:$dotfiles_prefix$HOME/.local/bin"
case "$PATH" in "$dotfiles_prefix":*) ;; *) PATH="$dotfiles_prefix:$PATH" ;; esac
export PATH
export EDITOR=nvim
export VISUAL=nvim
unset dotfiles_brew dotfiles_prefix
