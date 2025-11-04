#!/usr/bin/env bash
set -euo pipefail

# Find stale local branches based on last commit date
stale_local_branches() {
  # Help message
  local usage="
Usage: stale_local_branches [DAYS] [LIMIT] [--help|-h]

Find local branches that haven't been updated recently.

Arguments:
  DAYS                  Minimum age in days (default: 30)
  LIMIT                 Number of branches to display (default: 50)

Options:
  -h, --help            Show this help message

Examples:
  stale_local_branches                # Show branches older than 30 days
  stale_local_branches 60             # Show branches older than 60 days
  stale_local_branches 30 20          # Show 20 branches older than 30 days
"

  # Check for help flag
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "$usage"
    return 0
  fi

  local min_days=${1:-30}
  local limit=${2:-50}

  # Check if we're in a git repo
  if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "Error: Not in a git repository"
    return 1
  fi

  # Prevent git from opening a pager
  export GIT_PAGER=cat

  local current_branch
  current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

  # Determine main branch (master or main)
  local main_branch
  if git rev-parse --verify --quiet main >/dev/null 2>&1; then
    main_branch=main
  elif git rev-parse --verify --quiet master >/dev/null 2>&1; then
    main_branch=master
  else
    main_branch=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
    [[ -z "$main_branch" ]] && main_branch=master
  fi

  # Build set of merged branches using associative array
  declare -A is_merged
  while IFS= read -r b; do
    [[ -n "$b" ]] && is_merged[$b]=1
  done < <(git branch --merged "$main_branch" 2>/dev/null | sed 's/^[* ]*//')

  # Get current Unix timestamp
  local now
  now=$(date +%s)
  local -a lines=()

  # Get all local branches with Unix timestamps (no date parsing needed!)
  while IFS='|' read -r branch ts; do
    [[ -z "$branch" || -z "$ts" ]] && continue

    # Skip current branch and protected branches
    case "$branch" in
      "$current_branch"|main|master|develop|development) continue ;;
    esac

    # Calculate days since last commit
    local days=$(( (now - ts) / 86400 ))
    (( days < min_days )) && continue

    # Check if merged
    if [[ -n ${is_merged[$branch]:-} ]]; then
      lines+=("${days}|${branch}|merged")
    else
      lines+=("${days}|${branch}|not_merged")
    fi
  done < <(git for-each-ref --format='%(refname:short)|%(committerdate:unix)' refs/heads/)

  # Check if any branches were found
  if (( ${#lines[@]} == 0 )); then
    echo "No stale branches found (older than $min_days days)"
    return 0
  fi

  echo "Stale local branches (older than $min_days days):"

  # Sort by days (oldest first), limit results, and display
  printf '%s\n' "${lines[@]}" \
  | sort -rn -t'|' -k1,1 \
  | head -n "$limit" \
  | while IFS='|' read -r days branch merge_status; do
      if [[ "$merge_status" == "merged" ]]; then
        printf '✅ %s (merged into %s, last commit %s days ago)\n' "$branch" "$main_branch" "$days"
      else
        printf '⚠️  %s (not merged, last commit %s days ago)\n' "$branch" "$days"
      fi
    done
}

# Call the function with all passed arguments
stale_local_branches "$@"
