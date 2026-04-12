# cf - Natural Language Shell Command Finder
# Source this file in your ~/.zshrc:
#   source /path/to/cf/shell/cf.zsh

# Wrapper function: calls cf --print, injects result into zsh edit buffer
cf() {
    local result
    # --print so Python outputs to stdout; </dev/tty so curses UI works inside $(...)
    result=$(command cf --print "$@" </dev/tty 2>/dev/tty)
    if [[ -n "$result" ]]; then
        # print -z pushes text onto the zsh line editor buffer
        print -z "$result"
    fi
}

# ZLE widget: for keybinding integration (injected directly into BUFFER)
cf-widget() {
    local result
    result=$(command cf --print </dev/tty 2>/dev/tty)
    if [[ -n "$result" ]]; then
        BUFFER="$result"
        CURSOR=$#BUFFER
        zle reset-prompt
    fi
}
zle -N cf-widget

# Bind Ctrl+K to open cf interactively
# Change this keybinding if Ctrl+K conflicts with your setup
bindkey '^K' cf-widget
