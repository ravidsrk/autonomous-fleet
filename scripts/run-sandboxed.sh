#!/usr/bin/env bash
# run-sandboxed.sh — best-effort safety wrapper for headless fleet runs against untrusted repos.
#
# What it does (and does NOT do):
#   1. Scrubs credential-shaped variables from the environment before exec-ing the wrapped command
#      (strips AWS_*, *_TOKEN, *_KEY, *_SECRET, *_PASSWORD, plus a few well-known names).
#      Keeps PATH, HOME, USER, SHELL, LANG, LC_*, TERM, TMPDIR.
#   2. Classifies the wrapped command line by blast radius (ported from omnigent's nessie
#      blast_radius policy) and REFUSES (exit non-zero) before exec when the verdict is DENY
#      (irreversible: force-push, rm -rf of a critical path, hard-reset to a remote ref,
#      gh pr merge, terraform/tofu apply|destroy) or ASK (outward/destructive-but-recoverable:
#      ordinary git push, gh release, rm -rf of a scoped path). This wrapper is non-interactive,
#      so an ASK has no human to prompt: it refuses too, and the operator re-runs the command by
#      hand once they've eyeballed it.
#
# What it is NOT: an OS sandbox. It does not confine filesystem, network, or syscall reach. Run it
# INSIDE a container / VM / restricted user account when the target is genuinely untrusted, and
# never let production credentials reach this script's ambient environment in the first place.
#
# RESIDUAL RISK: the classifier is a heuristic over the joined command line, not a security
# boundary. It deliberately does NOT model subshells, command substitution, eval, base64-decoded
# payloads, or a binary that re-shells internally. A determined caller CAN evade it; it is a net
# against accidental / obvious damage. Pair it with real OS-level sandboxing for untrusted targets.
#
# This wrapper is code-only. It does NOT run anything against a live target on its own.
#
# Usage:
#   ./scripts/run-sandboxed.sh <command> [args...]
#   ./scripts/run-sandboxed.sh --classify <command> [args...]   # print verdict, do not exec
#   ./scripts/run-sandboxed.sh --help
#
# Examples:
#   ./scripts/run-sandboxed.sh ./scripts/run-mission-headless.sh grok doc-sync --yolo
#   ./scripts/run-sandboxed.sh env                       # show the scrubbed environment
#   ./scripts/run-sandboxed.sh terraform apply           # refused: ASK verdict, exit non-zero
#   ./scripts/run-sandboxed.sh --classify rm -rf /etc    # prints DENY, exit 0
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: run-sandboxed.sh <command> [args...]
       run-sandboxed.sh --classify <command> [args...]

Best-effort safety wrapper. Scrubs credential-shaped env vars and classifies the command line by
blast radius (ported from omnigent nessie blast_radius) before exec.

Env scrub: strips AWS_*, *_TOKEN, *_KEY, *_SECRET, *_PASSWORD, GH_TOKEN, GITHUB_TOKEN,
  XAI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY. Keeps PATH, HOME, USER, SHELL, LANG,
  LC_*, TERM, TMPDIR.

Blast-radius verdicts:
  DENY (refused, exit 2)  — irreversible: force-push (--force / -f / +refspec / --mirror),
                            remote-branch delete (--delete / --prune / -d / :refspec),
                            rm -rf of / ~ $HOME or a system dir (any flag spelling),
                            git reset --hard origin/*, gh pr merge / gh repo delete,
                            terraform|tofu|kubectl|helm|databricks apply|deploy|destroy|delete.
  ASK  (refused, exit 3)  — outward / recoverable: ordinary git push, gh release,
                            rm -rf of a scoped path. Non-interactive: re-run by hand.
  ALLOW                   — reads, tests, edits, local git (commit/merge/worktree): exec.

Evasions handled: leading sudo (incl. value-taking options and a `--` terminator), shell env
assignments (CI=1 ...), command chaining (; && || |), git -C <dir>/global options, combined and
split rm flags (-rf, -r -f, --recursive --force), and +/: push refspecs.

--classify  print the verdict (DENY|ASK|ALLOW) on stdout and exit 0 without exec. For tests.

This is NOT a general sandbox. It does not confine fs/network/syscalls. Combine with a
container / VM / restricted user for untrusted targets.
EOF
}

# --- Argument handling ----------------------------------------------------------------------
classify_only=0
case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  --classify)
    classify_only=1
    shift
    ;;
esac

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

# ════════════════════════════════════════════════════════════════════════════════════════════
# BLAST-RADIUS CLASSIFIER (ported from omnigent inner/nessie/policies.py: blast_radius)
# ════════════════════════════════════════════════════════════════════════════════════════════
# The classifier works on the JOINED command line so that already-split argv (the common case)
# and an embedded command string (`bash -c "cd repo && rm -rf /etc"`) are treated the same. It
# splits into per-statement token lists, unwraps env-assignment + sudo prefixes, resolves the git
# subcommand past global options, and classifies rm / git push by flag and refspec form. Whole
# verdict is the most severe across all statements: DENY > ASK > ALLOW.

# Critical dirs whose recursive-force rm is catastrophic (the directory ITSELF).
_RM_CRITICAL_DIRS=" / /etc /usr /bin /sbin /lib /lib64 /var /boot /root /home /opt /dev /proc /sys "
# System parents: a recursive-force rm of any path UNDER one of these is catastrophic too.
# /home /opt /root are excluded (a path under them is scoped/recoverable → ASK tier).
_RM_SYSTEM_PARENTS=" /etc /usr /bin /sbin /lib /lib64 /var /boot /dev /proc /sys "
# sudo options that consume the NEXT argv token as their value.
_SUDO_VALUE_OPTS=" -C -D -g -h -p -R -r -T -t -U -u --chdir --chroot --close-from --command-timeout --group --host --other-user --prompt --role --type --user "
# git global options that consume the NEXT argv token as their value (e.g. git -C <dir> push ...).
_GIT_GLOBAL_VALUE_OPTS=" -C -c --git-dir --work-tree --namespace --exec-path "
# Transparent command wrappers that run their argument as a command without changing its blast
# radius (`command rm -rf /`, `env git push --force`, `xargs rm`...). Stripped so the classifier
# resolves to the real binary instead of the wrapper word — failing CLOSED.
_CMD_WRAPPERS=" command builtin exec eval nohup nice ionice time stdbuf setsid env xargs "

# _membership $needle $haystack-with-leading-and-trailing-spaces -> 0 if present.
_in_set() {
  case "$2" in
    *" $1 "*) return 0 ;;
  esac
  return 1
}

# _is_env_assignment <tok> -> 0 if it matches NAME=... (a shell env assignment prefix).
_is_env_assignment() {
  case "$1" in
    [A-Za-z_]*=*)
      # Reject names with shell-illegal characters before the '='.
      local name="${1%%=*}"
      case "$name" in
        *[!A-Za-z0-9_]*) return 1 ;;
        *) return 0 ;;
      esac
      ;;
  esac
  return 1
}

# Tokenize a single statement into NUL-free lines on stdout. Shlex-like via xargs (honors quotes);
# falls back to whitespace split on a quoting error, mirroring the omnigent shlex/whitespace path.
_tokenize_statement() {
  local stmt="$1" out
  if out=$(printf '%s' "$stmt" | xargs -n1 printf '%s\n' 2>/dev/null); then
    printf '%s\n' "$out"
  else
    printf '%s' "$stmt" | tr -s '[:space:]' '\n'
  fi
}

# _rm_target_is_catastrophic <target> -> 0 if a recursive rm of it is catastrophic.
_rm_target_is_catastrophic() {
  local target="$1" norm top
  # Strip a trailing slash (but keep a bare "/").
  norm="${target%/}"
  [[ -z "$norm" ]] && norm="/"
  case "$norm" in
    '~'|'$HOME'|'${HOME}') return 0 ;;
  esac
  case "$target" in
    '/*'|'/*'*) return 0 ;;
  esac
  if _in_set "$norm" "$_RM_CRITICAL_DIRS"; then
    return 0
  fi
  case "$target" in
    /*)
      # top = "/" + first path segment under root.
      top="${target#/}"     # strip leading slash
      top="${top%%/*}"      # first segment
      top="/$top"
      if _in_set "$top" "$_RM_SYSTEM_PARENTS"; then
        return 0
      fi
      ;;
  esac
  return 1
}

# Classify ONE tokenized statement. Reads tokens from "$@". Echoes DENY|ASK|<empty>.
# Empty means this statement carries no rm/git-push blast radius (regex tiers handle the rest).
_classify_statement_tokens() {
  local -a argv=("$@")
  local n=${#argv[@]}
  local i=0

  # 1) Skip leading shell env assignments.
  while [[ $i -lt $n ]] && _is_env_assignment "${argv[$i]}"; do
    i=$((i + 1))
  done

  # 2) Unwrap a leading sudo (with its value-taking options and an optional `--` terminator).
  if [[ $i -lt $n && "${argv[$i]}" == "sudo" ]]; then
    i=$((i + 1))
    while [[ $i -lt $n ]]; do
      local tok="${argv[$i]}"
      if [[ "$tok" == "--" ]]; then
        i=$((i + 1))
        while [[ $i -lt $n ]] && _is_env_assignment "${argv[$i]}"; do i=$((i + 1)); done
        break
      fi
      if [[ "$tok" == --* ]]; then
        if _in_set "$tok" "$_SUDO_VALUE_OPTS" && [[ "$tok" != *=* && $((i + 1)) -lt $n ]]; then
          i=$((i + 2))
        else
          i=$((i + 1))
        fi
        continue
      fi
      if [[ "$tok" == -?* ]]; then
        # Bundled short options. If any consumes a value, decide whether it is attached.
        local rest="${tok#-}" pos=0 valpos=-1 ch
        while [[ $pos -lt ${#rest} ]]; do
          ch="${rest:$pos:1}"
          if _in_set "-$ch" "$_SUDO_VALUE_OPTS"; then valpos=$pos; break; fi
          pos=$((pos + 1))
        done
        if [[ $valpos -lt 0 ]]; then
          i=$((i + 1))
        elif [[ $valpos -lt $(( ${#rest} - 1 )) ]]; then
          i=$((i + 1))   # value is attached in the same token
        else
          i=$((i + 2))   # value is the next token
        fi
        continue
      fi
      break
    done
  fi

  # 2b) Strip transparent command wrappers (command/exec/env/xargs/nice/nohup/...) so a prefix
  #     cannot hide the real binary. Basename-matched, so `/usr/bin/env` counts too. We do NOT try
  #     to parse each wrapper's own options here (operand-taking opts like `env -u X`, `nice -n 5`
  #     differ per tool); instead `wrapper_seen` triggers the defense-in-depth scan below.
  local wrapper_seen=0
  while [[ $i -lt $n ]]; do
    local w="${argv[$i]}" wb="${argv[$i]##*/}"
    if _is_env_assignment "$w"; then i=$((i + 1)); continue; fi
    if [[ "$wb" == "sudo" ]]; then i=$((i + 1)); wrapper_seen=1; continue; fi
    if _in_set "$wb" "$_CMD_WRAPPERS"; then i=$((i + 1)); wrapper_seen=1; continue; fi
    break
  done

  [[ $i -ge $n ]] && return 0
  local cmd="${argv[$i]##*/}"

  # 3a) rm severity.
  if [[ "$cmd" == "rm" ]]; then
    local recursive=0 positional_only=0 t catastrophic=0
    local j=$((i + 1))
    while [[ $j -lt $n ]]; do
      t="${argv[$j]}"
      if [[ $positional_only -eq 1 ]]; then
        _rm_target_is_catastrophic "$t" && catastrophic=1
      elif [[ "$t" == "--" ]]; then
        positional_only=1
      elif [[ "$t" == "--force" ]]; then
        :
      elif [[ "$t" == "--recursive" ]]; then
        recursive=1
      elif [[ "$t" == --* ]]; then
        :
      elif [[ "$t" == -?* ]]; then
        case "$t" in *[rR]*) recursive=1 ;; esac
      else
        _rm_target_is_catastrophic "$t" && catastrophic=1
      fi
      j=$((j + 1))
    done
    if [[ $recursive -eq 1 ]]; then
      if [[ $catastrophic -eq 1 ]]; then echo DENY; else echo ASK; fi
    fi
    return 0
  fi

  # 3b) git push severity. Resolve the subcommand past git global options.
  if [[ "$cmd" == "git" ]]; then
    local j=$((i + 1))
    while [[ $j -lt $n && "${argv[$j]}" == -* ]]; do
      if _in_set "${argv[$j]}" "$_GIT_GLOBAL_VALUE_OPTS" && [[ $((j + 1)) -lt $n ]]; then
        j=$((j + 2))
      else
        j=$((j + 1))
      fi
    done
    if [[ $j -lt $n && "${argv[$j]}" == "push" ]]; then
      local k=$((j + 1)) t
      while [[ $k -lt $n ]]; do
        t="${argv[$k]}"
        case "$t" in
          --force*|--delete|--mirror|--prune) echo DENY; return 0 ;;
        esac
        if [[ "$t" == -?* && "$t" != --* ]]; then
          # Bundled short options: -f / -d force/delete. -o takes a value and stops parsing.
          local rest="${t#-}" pos=0 ch destructive=0
          while [[ $pos -lt ${#rest} ]]; do
            ch="${rest:$pos:1}"
            if [[ "$ch" == "f" || "$ch" == "d" ]]; then destructive=1; break; fi
            if [[ "$ch" == "o" ]]; then break; fi
            pos=$((pos + 1))
          done
          if [[ $destructive -eq 1 ]]; then echo DENY; return 0; fi
        fi
        # +refspec (force) / :refspec (delete).
        if [[ ${#t} -gt 1 ]]; then
          case "$t" in
            +*|:*) echo DENY; return 0 ;;
          esac
        fi
        k=$((k + 1))
      done
      echo ASK
      return 0
    fi
    # 3b') git reset --hard <ref>: DENY when ref is remote-tracking / upstream (discards local AND
    #      matches a remote), ASK otherwise. Structural so bare `origin` and `@{upstream}` are caught
    #      (the regex tier only matched refs containing a literal '/').
    if [[ $j -lt $n && "${argv[$j]}" == "reset" ]]; then
      local has_hard=0 ref="" k=$((j + 1)) t
      while [[ $k -lt $n ]]; do
        t="${argv[$k]}"
        if [[ "$t" == "--hard" ]]; then has_hard=1
        elif [[ "$t" != -* && -z "$ref" ]]; then ref="$t"; fi
        k=$((k + 1))
      done
      if [[ $has_hard -eq 1 && -n "$ref" ]]; then
        case "$ref" in
          origin|upstream|*/*|*@\{u\}*|*@\{upstream\}*|*@\{push\}*) echo DENY; return 0 ;;
          *) echo ASK; return 0 ;;
        esac
      fi
    fi
  fi

  # 3c) Infra tools: ASK only when the infra tool is the RESOLVED command (not a substring), so
  #     `echo "terraform apply"` no longer false-positives.
  case "$cmd" in
    kubectl|helm|terraform|tofu|databricks)
      local jj=$((i + 1)) tt
      while [[ $jj -lt $n ]]; do
        tt="${argv[$jj]}"
        case "$tt" in apply|deploy|destroy|delete) echo ASK; return 0 ;; esac
        jj=$((jj + 1))
      done
      ;;
  esac

  # 3c') gh: pr merge / repo delete -> DENY; release -> ASK. Structural per resolved command so a
  #      string mentioning them (echo gh pr merge) no longer false-positives.
  if [[ "$cmd" == "gh" ]]; then
    local jg=$((i + 1))
    while [[ $jg -lt $n && "${argv[$jg]}" == -* ]]; do jg=$((jg + 1)); done
    local g="${argv[$jg]:-}" v="${argv[$((jg + 1))]:-}"
    case "$g $v" in
      "pr merge"|"repo delete") echo DENY; return 0 ;;
    esac
    [[ "$g" == "release" ]] && { echo ASK; return 0; }
  fi

  # 3d) Shell -c "<string>": re-classify the embedded command string recursively.
  case "$cmd" in
    sh|bash|zsh|dash|ash)
      local jc=$((i + 1))
      while [[ $jc -lt $n ]]; do
        if [[ "${argv[$jc]}" == "-c" && $((jc + 1)) -lt $n ]]; then
          local sev2
          sev2="$(classify "${argv[$((jc + 1))]}")"
          [[ "$sev2" == "DENY" || "$sev2" == "ASK" ]] && { echo "$sev2"; return 0; }
          break
        fi
        jc=$((jc + 1))
      done
      ;;
  esac

  # 3e) Defense in depth: a wrapper was present but we did not resolve to a known command (its own
  #     option parsing may have hidden the real binary, e.g. `env -u X rm`, `nice -n 5 git push`,
  #     `nohup sudo -u root rm`). Re-classify the tail at each command-like head; take worst severity.
  if [[ $wrapper_seen -eq 1 ]]; then
    local p worst="" s b
    for (( p = i; p < n; p++ )); do
      b="${argv[$p]##*/}"
      case "$b" in
        rm|git|gh|kubectl|helm|terraform|tofu|databricks|sh|bash|zsh|dash|ash)
          s="$(_classify_statement_tokens "${argv[@]:p}")"
          [[ "$s" == "DENY" ]] && { echo DENY; return 0; }
          [[ "$s" == "ASK" ]] && worst="ASK"
          ;;
      esac
    done
    [[ -n "$worst" ]] && { echo "$worst"; return 0; }
  fi

  return 0
}

# Regex tiers over the JOINED command line (mirrors omnigent _DENY_PATTERNS / _ASK_PATTERNS).
# DENY: hard-reset to a remote ref, gh pr merge / repo delete.
# ASK : gh release, infra-tool apply|deploy|destroy|delete.
_regex_deny() {
  local line="$1"
  printf '%s' "$line" | grep -Eq 'git[[:space:]].*reset[[:space:]]+--hard[[:space:]]+[A-Za-z0-9_./-]+/' && return 0
  return 1
}
_regex_ask() {
  local line="$1"
  # gh (pr merge / repo delete / release) and infra tools (terraform/tofu/kubectl/helm/databricks
  # apply|destroy|...) are classified STRUCTURALLY per resolved command in _classify_statement_tokens
  # (3c/3c'), not by substring, so a string merely mentioning them no longer false-positives.
  return 1
}

# classify <argv...> -> echoes DENY|ASK|ALLOW (highest severity across all statements).
classify() {
  local joined="$*"
  local verdict="ALLOW"

  # Split the joined line into statements on ; && || | and newline, then classify each.
  # A literal newline separator is emitted by sed; read consumes it line by line.
  local statements
  statements=$(printf '%s' "$joined" | sed -E 's/(&&|\|\||;|\|)/\
/g')

  local stmt sev
  while IFS= read -r stmt; do
    # Trim leading/trailing whitespace.
    stmt="${stmt#"${stmt%%[![:space:]]*}"}"
    stmt="${stmt%"${stmt##*[![:space:]]}"}"
    [[ -z "$stmt" ]] && continue
    # Tokenize into an array (bash 3.2: read -a from the newline-delimited token stream).
    local -a toks=()
    local tok
    while IFS= read -r tok; do
      [[ -z "$tok" ]] && continue
      toks+=("$tok")
    done < <(_tokenize_statement "$stmt")
    [[ ${#toks[@]} -eq 0 ]] && continue
    sev=$(_classify_statement_tokens "${toks[@]}")
    if [[ "$sev" == "DENY" ]]; then
      echo DENY
      return 0
    elif [[ "$sev" == "ASK" ]]; then
      verdict="ASK"
    fi
  done <<EOF
$statements
EOF

  # Regex tiers over the whole joined line.
  if _regex_deny "$joined"; then
    echo DENY
    return 0
  fi
  if [[ "$verdict" == "ALLOW" ]] && _regex_ask "$joined"; then
    verdict="ASK"
  fi

  echo "$verdict"
}

verdict="$(classify "$@")"

if [[ "$classify_only" -eq 1 ]]; then
  echo "$verdict"
  exit 0
fi

if [[ "$verdict" == "DENY" ]]; then
  echo "run-sandboxed: REFUSED (DENY): irreversible command — ${*}" >&2
  echo "run-sandboxed: force-push, rm -rf of a critical path, hard-reset to remote, gh pr merge," >&2
  echo "run-sandboxed: and infra destroy are blocked. This wrapper will not run them." >&2
  exit 2
fi

if [[ "$verdict" == "ASK" ]]; then
  echo "run-sandboxed: REFUSED (ASK): outward / destructive-but-recoverable command — ${*}" >&2
  echo "run-sandboxed: this wrapper is non-interactive and cannot prompt for approval." >&2
  echo "run-sandboxed: review it, then re-run by hand outside the wrapper if it is intended." >&2
  exit 3
fi

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
