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
# If text is already on the line, use it as the query
cf-widget() {
    local query="$BUFFER"
    local result

    if [[ -z "$query" ]]; then
        # Empty line: prompt for input
        zle -I  # invalidate display
        echo -n "cf> " > /dev/tty
        read -r query < /dev/tty
        [[ -z "$query" ]] && return
    fi

    result=$(command cf --print "$query" </dev/tty 2>/dev/tty)
    if [[ -n "$result" ]]; then
        BUFFER="$result"
        CURSOR=$#BUFFER
    fi
    zle reset-prompt
}
zle -N cf-widget

# Bind Ctrl+F to open cf search widget
bindkey '^F' cf-widget
