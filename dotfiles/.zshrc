# https://github.com/ohmyzsh/ohmyzsh

# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:/usr/local/bin:$PATH

# Path to your oh-my-zsh installation.
export ZSH="/Users/me/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
#
# This is the default theme for ohmyzsh
# ZSH_THEME="robbyrussell"
#
# Using this instead.
# https://starship.rs/guide/#%F0%9F%9A%80-installation
ZSH_THEME=""
SPACESHIP_EXIT_CODE_SHOW="true"

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment the following line to disable bi-weekly auto-update checks.
# DISABLE_AUTO_UPDATE="true"

# Uncomment the following line to automatically update without prompting.
# DISABLE_UPDATE_PROMPT="true"

# Uncomment the following line to change how often to auto-update (in days).
# export UPDATE_ZSH_DAYS=13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
# 
# install zsh-autosuggestions with:
#    cd $ZSH_CUSTOM/plugins
#    git clone git@github.com:zsh-users/zsh-autosuggestions.git
# 
plugins=(git zsh-autosuggestions)

source $ZSH/oh-my-zsh.sh

# User configuration

# https://superuser.com/questions/1245273/iterm2-version-3-individual-history-per-tab
unsetopt inc_append_history
unsetopt share_history

export PATH="/Users/me/.local/bin:$PATH"
# export MANPATH="/usr/local/man:$MANPATH"

# Personal exports that contain secrets
source "$HOME/.exports"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='mvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch x86_64"

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"
alias aaa="cd ~/aaa/"
alias ledger="cd ~/aaa/ledger"
alias github="cd ~/aaa/github"
alias notes="cd ~/aaa/notes"
# https://github.com/aria2/aria2
alias aria2cdl="aria2c -x16 -s20 -k1M"
alias tailscale="/Applications/Tailscale.app/Contents/MacOS/Tailscale"


# Things added externally

# (start) For sentry development
export VOLTA_HOME="$HOME/.volta"
export PATH="$VOLTA_HOME/bin:$PATH"
eval "$(starship init zsh)"
eval "$(pyenv init -)"
eval "$(direnv hook zsh)"
# (end) For sentry development

# https://www.haskell.org/ghcup/install/
# ghcup-env
[ -f "/Users/me/.ghcup/env" ] && source "/Users/me/.ghcup/env" 

# https://github.com/mitsuhiko/rye
source "$HOME/.rye/env"

# brew install fzf
# To install useful key bindings and fuzzy completion:
# $(brew --prefix)/opt/fzf/install
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# https://github.com/junegunn/fzf-git.sh
[ -f ~/.fzf-git.sh ] && source ~/.fzf-git.sh

# brew install bat
# https://github.com/sharkdp/bat
export BAT_THEME="OneHalfDark"

# find-in-file - usage: fif [directory]
# Use current directory as default.
fif() {
    rg --line-number --no-heading "${1:-.}" |
    fzf --color "hl:-1:reverse,hl+:-1:underline:reverse" \
        --delimiter : \
        --preview 'bat --color=always {1} --highlight-line {2}' \
        --preview-window 'up,60%,border-bottom,+{2}+3/3,~3' \
        --nth=1,3.. |
    sed 's/[^:]*:[^:]*://' |
    sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' |
    tr -d '\n' |
    pbcopy

}

# find-in-[files-and-open-with-]vscode - usage: fiv [directory]
# Use current directory as default.
fiv() {
    # Requires in path: /usr/local/bin/code
    rg --line-number --no-heading "${1:-.}" |
    fzf --color "hl:-1:reverse,hl+:-1:underline:reverse" \
        --delimiter : \
        --preview 'bat --color=always {1} --highlight-line {2}' \
        --preview-window 'up,60%,border-bottom,+{2}+3/3,~3' \
        --nth=1,3.. \
        --bind 'enter:become(code --goto {1}:{2})'

}

# find-in-directory - usage: fid
fid() {
    fd |
    fzf --color "hl:-1:reverse,hl+:-1:underline:reverse" \
        --preview 'bat --color=always {1}' \
        --preview-window 'up,60%,border-bottom,~3' \
}

export FZF_CTRL_T_OPTS="
    --preview 'bat -n --color=always {}'
    --preview-window 'up,60%,border-bottom,~3'"

export FZF_CTRL_R_OPTS="
    --preview 'echo {}' --preview-window up:3:hidden:wrap
    --bind 'ctrl-/:toggle-preview'
    --bind 'ctrl-y:execute-silent(echo -n {2..} | pbcopy)+abort'
    --color header:italic
    --header 'Press CTRL-Y to copy command into clipboard. Press CTRL-/ to toggle preview.'"
