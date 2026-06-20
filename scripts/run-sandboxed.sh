#!/usr/bin/env bash
# run-sandboxed.sh — best-effort safety wrapper for headless fleet runs against untrusted repos.
#
# What it does (and does NOT do):
#   1. Scrubs credential-shaped variables from the environment before exec-ing the wrapped command
#      (strips AWS_*, *_TOKEN, *_KEY, *_SECRET, *_PASSWORD, plus a few well-known names).
#      Keeps PATH, HOME, USER, SHELL, LANG, LC_*, TERM, TMPDIR.
#   2. Refuses (exit non-zero) if the wrapped command line matches a deny-list of production /
#      publish patterns (terraform apply, kubectl, aws, gcloud, npm publish, cargo publish,
#      gh release, git push --tags / git push origin --tags).
#
# What it is NOT: an OS sandbox. It does not confine filesystem, network, or syscall reach. Run it
# INSIDE a container / VM / restricted user account when the target is genuinely untrusted, and
# never let production credentials reach this script's ambient environment in the first place.
#
# This wrapper is code-only. It does NOT run anything against a live target on its own.
#
# Usage:
#   ./scripts/run-sandboxed.sh <command> [args...]
#   ./scripts/run-sandboxed.sh --help
#
# Examples:
#   ./scripts/run-sandboxed.sh ./scripts/run-mission-headless.sh grok doc-sync --yolo
#   ./scripts/run-sandboxed.sh env             # show the scrubbed environment
#   ./scripts/run-sandboxed.sh terraform apply # refused: deny-list hit, exit non-zero
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: run-sandboxed.sh <command> [args...]

Best-effort safety wrapper. Scrubs credential-shaped env vars and refuses a deny-list of
production / publish command lines before exec.

Env scrub: strips AWS_*, *_TOKEN, *_KEY, *_SECRET, *_PASSWORD, GH_TOKEN, GITHUB_TOKEN,
  XAI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY. Keeps PATH, HOME, USER, SHELL, LANG,
  LC_*, TERM, TMPDIR.

Deny-list (refused, exit 2):
  terraform apply
  kubectl ...
  aws ...
  gcloud ...
  npm publish
  cargo publish
  gh release ...
  git push --tags
  git push origin --tags

This is NOT a general sandbox. It does not confine fs/network/syscalls. Combine with a
container / VM / restricted user for untrusted targets.
EOF
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
esac

# --- Deny-list check on the joined command line ---------------------------------------------
# Join argv into a single space-delimited string for pattern matching. We deliberately match on
# the joined string so that flag order doesn't let callers smuggle a denied command past us.
joined="$*"

deny() {
  echo "run-sandboxed: REFUSED: command line matches deny-list pattern: $1" >&2
  echo "run-sandboxed: this wrapper does not run production / publish commands." >&2
  exit 2
}

# Whole-command matches (anchored on the executable token).
case "$1" in
  kubectl) deny "kubectl ..." ;;
  aws)     deny "aws ..." ;;
  gcloud)  deny "gcloud ..." ;;
esac

# Subcommand matches (executable + first arg).
if [[ $# -ge 2 ]]; then
  case "$1 $2" in
    "terraform apply") deny "terraform apply" ;;
    "npm publish")     deny "npm publish" ;;
    "cargo publish")   deny "cargo publish" ;;
    "gh release")      deny "gh release ..." ;;
  esac
fi

# git push --tags (any position after `git push`).
if [[ "$1" == "git" && "${2:-}" == "push" ]]; then
  for arg in "$@"; do
    if [[ "$arg" == "--tags" ]]; then
      deny "git push ... --tags"
    fi
  done
fi

# Also catch the joined form for safety (e.g. `bash -c "terraform apply"` — joined string check).
case " $joined " in
  *" terraform apply "*) deny "terraform apply (joined)" ;;
  *" npm publish "*)     deny "npm publish (joined)" ;;
  *" cargo publish "*)   deny "cargo publish (joined)" ;;
  *" gh release "*)      deny "gh release (joined)" ;;
  *" git push --tags "*|*" git push origin --tags "*) deny "git push --tags (joined)" ;;
esac

# --- Env scrub ------------------------------------------------------------------------------
# Build an allowlist of names to KEEP, then exec the command via `env -i` with only those.
keep_vars=(PATH HOME USER LOGNAME SHELL LANG TERM TMPDIR PWD)

# LC_* are locale, keep them all.
while IFS='=' read -r name _; do
  case "$name" in
    LC_*) keep_vars+=("$name") ;;
  esac
done < <(env)

# Build `env -i NAME=value ... NAME=value -- cmd args`.
preserved=()
for name in "${keep_vars[@]}"; do
  if [[ -n "${!name+x}" ]]; then
    preserved+=("$name=${!name}")
  fi
done

# Sanity: explicitly drop credential-shaped vars from the preserved list (defense in depth — the
# allowlist above already excludes them, but be explicit for readers / future edits).
filtered=()
for kv in "${preserved[@]}"; do
  name="${kv%%=*}"
  case "$name" in
    AWS_*|*_TOKEN|*_KEY|*_SECRET|*_PASSWORD|GH_TOKEN|GITHUB_TOKEN|XAI_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY)
      continue
      ;;
  esac
  filtered+=("$kv")
done

exec env -i "${filtered[@]}" "$@"
