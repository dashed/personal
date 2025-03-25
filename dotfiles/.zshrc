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

# find-in-[files-and-open-with-]vscode - usage: fiv [path]
# Fuzzy find in files and open with vscode.
# By default searches in current directory.
fiv() {
    # Requires vscode to be in path: /usr/local/bin/code
    local _fiv_rg_path="${1:-.}"
    
    if [[ -d "$_fiv_rg_path" ]]; then
        rg --line-number --no-heading . "$_fiv_rg_path" |
        fzf --color "hl:-1:reverse,hl+:-1:underline:reverse" \
            --delimiter : \
            --preview 'bat --color=always {1} --highlight-line {2}' \
            --preview-window 'up,60%,border-bottom,+{2}+3/3,~3' \
            --nth=1,3.. \
            --bind 'enter:become(code --goto {1}:{2})'
    else
        rg --line-number --no-heading . "$_fiv_rg_path" |
        fzf --color "hl:-1:reverse,hl+:-1:underline:reverse" \
            --delimiter : \
            --preview "bat --color=always '$_fiv_rg_path' --highlight-line {1}" \
            --preview-window 'up,60%,border-bottom,+{1}+3/3,~3' \
            --nth=2.. \
            --bind "enter:become(code --goto '$_fiv_rg_path':{1})"
    fi
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

# GitHub function to check recently merged branches and if they exist locally
gh_merged_branches() {
  # Help message
  local usage="
Usage: gh_merged_branches [LIMIT] [STATE] [--help|-h]

Check GitHub branches that were recently merged or closed and their local status.

Arguments:
  LIMIT                 Number of branches to display (default: 15)
  STATE                 State of PRs to check (default: merged_closed)
                        Options: merged_closed, merged, closed, all

Options:
  -h, --help            Show this help message

Examples:
  gh_merged_branches                  # Show 15 most recent merged and closed branches
  gh_merged_branches 30               # Show 30 most recent merged and closed branches
  gh_merged_branches 15 merged        # Show only merged branches
  gh_merged_branches 15 closed        # Show only closed branches
  gh_merged_branches 15 all           # Show all PR states
"

  # Check for help flag
  if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "$usage"
    return 0
  fi

  local limit=${1:-15}
  local state=${2:-"merged_closed"}
  local query="sort:updated-desc"

  if [[ "$state" == "merged_closed" ]]; then
    # Fetch both merged and closed PRs and combine them
    GH_PAGER= gh pr list --author "@me" --state merged --limit $limit --search "$query" --json headRefName,number,mergedAt,closedAt,updatedAt,state > /tmp/merged_prs.json
    GH_PAGER= gh pr list --author "@me" --state closed --limit $limit --search "$query" --json headRefName,number,mergedAt,closedAt,updatedAt,state > /tmp/closed_prs.json

    # Combine and deduplicate by PR number, then sort by updatedAt
    jq -s '[.[] | .[] | select(.state == "MERGED" or .state == "CLOSED")] | unique_by(.number) | sort_by(.updatedAt) | reverse | .[0:'$limit']' /tmp/merged_prs.json /tmp/closed_prs.json > /tmp/combined_prs.json

    echo "Recent merged and closed branches status:"
    jq -r '.[] | "\(.headRefName)|\(.mergedAt)|\(.closedAt)|\(.updatedAt)|\(.state)"' /tmp/combined_prs.json > /tmp/merged_branches.txt
  else
    # Original behavior for other states
    GH_PAGER= gh pr list --author "@me" --state "$state" --limit $limit --search "$query" --json headRefName,mergedAt,closedAt,updatedAt,state | \
    jq -r '.[] | "\(.headRefName)|\(.mergedAt)|\(.closedAt)|\(.updatedAt)|\(.state)"' > /tmp/merged_branches.txt
    echo "Recent $state branches status:"
  fi

  # Count the number of lines in the file to check if it's empty
  local line_count=$(wc -l < /tmp/merged_branches.txt | tr -d ' ')
  if [[ $line_count -eq 0 ]]; then
    echo "No branches found with state: $state"
    return 0
  fi

  while IFS="|" read -r branch mergedate closedate updatedate ghstate; do
    if [[ "$mergedate" != "null" ]]; then
      action_date=$mergedate
      action_verb="merged"
    elif [[ "$closedate" != "null" ]]; then
      action_date=$closedate
      action_verb="closed"
    else
      action_date=$updatedate
      action_verb="updated"
    fi

    action_days_ago=$(printf "%.0f" $(echo "scale=0; ($(date +%s) - $(date -jf %Y-%m-%dT%H:%M:%SZ "$action_date" +%s)) / 86400" | bc))
    updated_days_ago=$(printf "%.0f" $(echo "scale=0; ($(date +%s) - $(date -jf %Y-%m-%dT%H:%M:%SZ "$updatedate" +%s)) / 86400" | bc))

    if git rev-parse --verify "$branch" >/dev/null 2>&1; then
      echo "✅ $branch ($action_verb $action_days_ago days ago, updated $updated_days_ago days ago, still exists locally)"
    else
      echo "❌ $branch ($action_verb $action_days_ago days ago, updated $updated_days_ago days ago, deleted locally)"
    fi
  done < /tmp/merged_branches.txt
}
