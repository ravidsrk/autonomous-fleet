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
#      gh pr merge, terraform/tofu apply|destroy, shred, dd to a device, chmod/chown -R of a
#      system path, find <system-path> -delete/-exec) or ASK (outward/destructive-but-recoverable:
#      ordinary git push, gh release, rm -rf of a scoped path, npm/cargo publish, aws/gcloud
#      destructive verbs, curl|wget piped to a shell). This wrapper is non-interactive, so an ASK
#      has no human to prompt: it refuses too, and the operator re-runs the command by hand once
#      they've eyeballed it.
#   3. With `--role reviewer`, runs the command after classification with the candidate git tree
#      read-only and `.fleet/runs/<run_id>/` writable. It prefers macOS sandbox-exec, then Linux
#      bwrap. If neither exists, the reviewer role REFUSES unless
#      FLEET_SECURITY_OVERRIDE_ACK=1 (then a post-exec tracked-file hash assertion runs).
#
# What it is NOT: an OS sandbox. It does not confine filesystem, network, or syscall reach. Run it
# INSIDE a container / VM / restricted user account when the target is genuinely untrusted, and
# never let production credentials reach this script's ambient environment in the first place.
#
# RESIDUAL RISK: the classifier is a STATIC heuristic over tokens, not a security boundary. A
# command CONSTRUCTED AT SHELL RUNTIME cannot be resolved from its text, so it deliberately does NOT
# model: command substitution `$(...)`/backticks, `eval` of a built string, base64/encoded payloads,
# positional/parameter expansion that injects args (`bash -c 'rm "$@"' _ -rf x`), or a binary that
# re-shells internally. Where such a construct is DETECTABLE (e.g. a `-c` string referencing `$@`/
# `$1`) it FAILS SAFE to ASK; where it is not, a determined caller CAN evade it. It is a net against
# accidental / obvious damage. Pair it with real OS-level sandboxing (container-use) for untrusted
# targets — that, not this script, is the boundary.
# Reviewer-role without sandbox-exec/bwrap REFUSES by default (SEC-005). With
# FLEET_SECURITY_OVERRIDE_ACK=1 the post-exec hash audit runs — detect-only, not prevention.
# It FAILS SAFE: on an ambiguous wrapper construction (e.g. an unknown wrapper's positional operand
# preceding the real command) it errs toward DENY/ASK rather than ALLOW. Refusing a rare safe
# command is acceptable; silently running an irreversible one is not.
#
# This wrapper is code-only. It does NOT run anything against a live target on its own.
#
# Usage:
#   ./scripts/run-sandboxed.sh <command> [args...]
#   ./scripts/run-sandboxed.sh --classify <command> [args...]   # print verdict, do not exec
#   ./scripts/run-sandboxed.sh --role reviewer [--run-id <run_id>] -- <command> [args...]
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
       run-sandboxed.sh --role reviewer [--run-id <run_id>] -- <command> [args...]

Best-effort safety wrapper. Scrubs credential-shaped env vars and classifies the command line by
blast radius (ported from omnigent nessie blast_radius) before exec.

Env scrub: strips AWS_*, *_TOKEN, *_KEY, *_SECRET, *_PASSWORD, GH_TOKEN, GITHUB_TOKEN,
  XAI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, and FLEET_DISABLE_* (substrate kill switches —
  a stray one must not ride into a sandboxed child and silently no-op its guard). Keeps PATH, HOME,
  USER, SHELL, LANG, LC_*, TERM, TMPDIR.

Blast-radius verdicts:
  DENY (refused, exit 2)  — irreversible: force-push (--force / -f / +refspec / --mirror),
                            remote-branch delete (--delete / --prune / -d / :refspec),
                            rm -rf of / ~ $HOME or a system dir (any flag spelling),
                            git reset --hard origin/*, gh pr merge / gh repo delete,
                            terraform|tofu|kubectl|helm|databricks apply|deploy|destroy|delete,
                            shred, dd of=/dev/*, chmod|chown|chgrp -R of an absolute system path,
                            find <abs-system-path> with -delete / -exec / -ok.
  ASK  (refused, exit 3)  — outward / recoverable: ordinary git push, gh release,
                            rm -rf of a scoped path, npm|pnpm|yarn|cargo publish,
                            aws|gcloud destructive verbs (delete/rm/terminate/...),
                            curl|wget piped into a shell. Non-interactive: re-run by hand.
  ALLOW                   — reads, tests, edits, local git (commit/merge/worktree): exec.

Evasions handled: leading sudo (incl. value-taking options and a `--` terminator), shell env
assignments (CI=1 ...), command chaining (; && || |), git -C <dir>/global options, combined and
split rm flags (-rf, -r -f, --recursive --force), and +/: push refspecs.

--classify  print the verdict (DENY|ASK|ALLOW) on stdout and exit 0 without exec. For tests.
--role reviewer
            after blast-radius classification, run with the candidate git tree read-only and only
            .fleet/runs/<run_id>/ writable. Uses sandbox-exec on macOS, bwrap on Linux. Without
            either binary, REFUSES unless FLEET_SECURITY_OVERRIDE_ACK=1 (then post-exec hash
            audit). The bwrap mount binds ONLY the repo (ro), the run dir (rw), and minimal
            system paths (ro) — no host RW of $HOME or /.
--run-id    run archive id for reviewer writable output. Must match fleet_run.RUN_ID_PATTERN
            (rejects /, .., and other path escapes). Defaults to FLEET_RUN_ID, then a generated
            reviewer-sandbox id.

This is NOT a general sandbox. It does not confine fs/network/syscalls. Combine with a
container / VM / restricted user for untrusted targets.
EOF
}

# --- Argument handling ----------------------------------------------------------------------
classify_only=0
role=""
run_id="${FLEET_RUN_ID:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --classify)
      classify_only=1
      shift
      ;;
    --role)
      if [[ $# -lt 2 ]]; then
        echo "run-sandboxed: --role requires a value" >&2
        exit 1
      fi
      role="$2"
      shift 2
      ;;
    --run-id)
      if [[ $# -lt 2 ]]; then
        echo "run-sandboxed: --run-id requires a value" >&2
        exit 1
      fi
      run_id="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [[ -n "$role" && "$role" != "reviewer" ]]; then
  echo "run-sandboxed: unsupported --role '$role' (supported: reviewer)" >&2
  exit 1
fi

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
_CMD_WRAPPERS=" command builtin exec eval nohup nice ionice time timeout stdbuf setsid setarch env xargs flock doas chrt taskset unbuffer "

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
  # shellcheck disable=SC2016  # match the LITERAL token a user typed (e.g. rm -rf '$HOME')
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
  while [[ $i -lt $n ]]; do
    local w="${argv[$i]}" wb="${argv[$i]##*/}"
    if _is_env_assignment "$w"; then i=$((i + 1)); continue; fi
    if [[ "$wb" == "sudo" ]] || _in_set "$wb" "$_CMD_WRAPPERS"; then
      i=$((i + 1))
      # Skip the wrapper's own options so `time -p echo` resolves to echo (a data-consumer), not
      # `-p`. Operand-taking opts leave their operand as the head, but the scan / data-consumer
      # guard below handle whatever resolves.
      while [[ $i -lt $n && "${argv[$i]}" == -?* ]]; do
        # `env -S '<cmd>'` / `env --split-string=<cmd>` runs <cmd> as a command — classify it.
        if [[ "$wb" == "env" ]]; then
          local ssev=""
          case "${argv[$i]}" in
            -S|--split-string) [[ $((i + 1)) -lt $n ]] && ssev="$(classify "${argv[$((i + 1))]}")" ;;
            -S?*)              ssev="$(classify "${argv[$i]#-S}")" ;;
            --split-string=*)  ssev="$(classify "${argv[$i]#--split-string=}")" ;;
          esac
          [[ "$ssev" == "DENY" || "$ssev" == "ASK" ]] && { echo "$ssev"; return 0; }
        fi
        i=$((i + 1))
      done
      continue
    fi
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

  # 3a') shred: irreversible by design — it overwrites then (usually) unlinks, with no recovery.
  #      DENY unconditionally; there is no recoverable spelling worth an ASK tier.
  if [[ "$cmd" == "shred" ]]; then
    echo DENY
    return 0
  fi

  # 3a'') dd writing to a device node: `dd of=/dev/sda ...` overwrites a raw disk — catastrophic and
  #       irreversible. Match `of=/dev/...` in any argument position (dd takes `key=value` operands
  #       in any order). A plain `of=file` (no /dev/) is an ordinary write → not flagged here.
  if [[ "$cmd" == "dd" ]]; then
    local j=$((i + 1)) t
    while [[ $j -lt $n ]]; do
      t="${argv[$j]}"
      case "$t" in
        of=/dev/*) echo DENY; return 0 ;;
      esac
      j=$((j + 1))
    done
    return 0
  fi

  # 3a''') chmod / chown -R on an absolute system path: a recursive ownership/permission rewrite of
  #        /, /etc, /usr, … (or a path under one) bricks the host as surely as rm -rf does. DENY when
  #        BOTH the recursive flag and an absolute-system-path operand are present; otherwise no
  #        verdict (a scoped `chmod -R 755 build/` is ordinary). Reuses _rm_target_is_catastrophic
  #        for the same critical-dir / system-parent set rm uses, so the two stay consistent.
  if [[ "$cmd" == "chmod" || "$cmd" == "chown" || "$cmd" == "chgrp" ]]; then
    local recursive=0 positional_only=0 catastrophic=0 t
    local j=$((i + 1))
    while [[ $j -lt $n ]]; do
      t="${argv[$j]}"
      if [[ $positional_only -eq 1 ]]; then
        _rm_target_is_catastrophic "$t" && catastrophic=1
      elif [[ "$t" == "--" ]]; then
        positional_only=1
      elif [[ "$t" == "--recursive" ]]; then
        recursive=1
      elif [[ "$t" == --* ]]; then
        :
      elif [[ "$t" == -?* ]]; then
        case "$t" in *[rR]*) recursive=1 ;; esac
      else
        # Test EVERY non-flag operand (mode/owner AND path). A mode like 000 / u+x or an owner like
        # root:root can never be an absolute system path, so _rm_target_is_catastrophic never matches
        # it — no need to single out the first operand, which would mis-handle `chmod -R+x /usr`.
        _rm_target_is_catastrophic "$t" && catastrophic=1
      fi
      j=$((j + 1))
    done
    if [[ $recursive -eq 1 && $catastrophic -eq 1 ]]; then echo DENY; fi
    return 0
  fi

  # 3a'''') find <abs-path> ... with -delete / -exec / -execdir: `find / -delete`, `find /etc -exec
  #         rm {} +` walk an absolute system tree and destroy it. DENY when the starting path is an
  #         absolute system path AND a destructive action (-delete / -exec / -execdir) is present.
  #         A relative root (`find . -delete`) or a pure query (`find / -name x`) is not flagged.
  if [[ "$cmd" == "find" ]]; then
    local has_action=0 abs_system=0 seen_expr=0 t
    local j=$((i + 1))
    while [[ $j -lt $n ]]; do
      t="${argv[$j]}"
      case "$t" in
        # Destructive actions: -delete removes matches; -exec/-execdir/-ok/-okdir RUN a command per
        # match (the interactive -ok* still runs it). A write-a-listing primary like -fprint is NOT
        # destructive, so it is deliberately excluded.
        -delete|-exec|-execdir|-ok|-okdir) has_action=1; seen_expr=1 ;;
        -*) seen_expr=1 ;;  # any other primary/option marks the start of the expression
        *)
          # Path operands precede the expression. Flag if any starting path is absolute-system.
          if [[ $seen_expr -eq 0 ]]; then
            _rm_target_is_catastrophic "$t" && abs_system=1
          fi
          ;;
      esac
      j=$((j + 1))
    done
    if [[ $has_action -eq 1 && $abs_system -eq 1 ]]; then echo DENY; fi
    return 0
  fi

  # 3a''''') Package publish: npm publish / cargo publish / yarn publish / pnpm publish push an
  #          artifact to a public registry — outward and effectively irreversible (a published
  #          version can be deprecated but not un-published cleanly). ASK so a human re-runs it
  #          deliberately. Structural per resolved command so `echo "npm publish"` does not match.
  case "$cmd" in
    npm|pnpm|yarn|cargo)
      local jp=$((i + 1)) tp
      while [[ $jp -lt $n ]]; do
        tp="${argv[$jp]}"
        [[ "$tp" == -* ]] && { jp=$((jp + 1)); continue; }
        case "$tp" in
          publish) echo ASK; return 0 ;;
          *) break ;;   # first non-flag subcommand is not publish → no verdict here
        esac
      done
      ;;
  esac

  # 3a'''''') Cloud CLIs: aws / gcloud destructive verbs. These reach a LIVE account, so the wrapper
  #           refuses (ASK) rather than ALLOW even though some are individually recoverable. Matched
  #           on the resolved command + a destructive verb token, not by substring.
  if [[ "$cmd" == "aws" ]]; then
    local ja=$((i + 1)) ta
    while [[ $ja -lt $n ]]; do
      ta="${argv[$ja]}"
      case "$ta" in
        # aws <service> <verb>: rm/delete-*/terminate-*/destroy verbs hit live resources.
        rm|delete|delete-*|terminate-instances|remove-*|reset-*|empty)
          echo ASK; return 0 ;;
      esac
      ja=$((ja + 1))
    done
    return 0
  fi
  if [[ "$cmd" == "gcloud" ]]; then
    local jg=$((i + 1)) tg
    while [[ $jg -lt $n ]]; do
      tg="${argv[$jg]}"
      case "$tg" in
        delete|destroy|remove) echo ASK; return 0 ;;
      esac
      jg=$((jg + 1))
    done
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

  # 3d) Shell -c "<string>": re-classify the embedded command string recursively. Matches a bundled
  #     short option containing c too (`-ec`, `-xc`), since `bash -ec '<cmd>'` also runs <cmd>.
  case "$cmd" in
    sh|bash|zsh|dash|ash)
      local jc=$((i + 1))
      while [[ $jc -lt $n ]]; do
        case "${argv[$jc]}" in
          -c|-[A-Za-z]*c*)
            if [[ $((jc + 1)) -lt $n ]]; then
              local cstr="${argv[$((jc + 1))]}" sev2
              # A -c script whose behavior depends on caller-supplied POSITIONAL args ($@ $* $# $1..$9)
              # cannot be resolved from the string alone, e.g. `bash -c 'rm "$@"' _ -rf /path` runs
              # `rm -rf /path`. Static analysis can't see the runtime args, so FAIL SAFE: refuse (ASK)
              # rather than judge only the literal string. (Same reason $()/eval are out of scope.)
              if printf '%s' "$cstr" | grep -Eq '\$[@*#0-9]|\$\{[@*#0-9]'; then
                echo ASK; return 0
              fi
              sev2="$(classify "$cstr")"
              [[ "$sev2" == "DENY" || "$sev2" == "ASK" ]] && { echo "$sev2"; return 0; }
            fi
            break
            ;;
        esac
        jc=$((jc + 1))
      done
      ;;
  esac

  # 3e) Defense in depth. If the resolved head is NEITHER a command classified above NOR a pure
  #     data-consumer (echo/printf/test/... which take their args as DATA, not as a command), it may
  #     be an unrecognized wrapper (timeout/flock/doas/...), a leading redirection, or a stray option
  #     hiding the real binary. Scan the tail for a dangerous command head and re-classify there.
  #     The data-consumer skip is what keeps `env echo rm -rf /` (safe) from false-positiving.
  case "$cmd" in
    rm|shred|dd|chmod|chown|chgrp|find|npm|pnpm|yarn|cargo|aws|gcloud) ;;
    git|gh|kubectl|helm|terraform|tofu|databricks|sh|bash|zsh|dash|ash) ;;
    echo|printf|:|true|false|test|'['|export|unset|read|cd|pwd|alias|set|source|.) ;;
    *)
      local p worst="" s b
      for (( p = i + 1; p < n; p++ )); do
        b="${argv[$p]##*/}"
        case "$b" in
          rm|shred|dd|chmod|chown|chgrp|find|npm|pnpm|yarn|cargo|aws|gcloud|git|gh|kubectl|helm|terraform|tofu|databricks|sh|bash|zsh|dash|ash)
            s="$(_classify_statement_tokens "${argv[@]:p}")"
            [[ "$s" == "DENY" ]] && { echo DENY; return 0; }
            [[ "$s" == "ASK" ]] && worst="ASK"
            ;;
        esac
      done
      [[ -n "$worst" ]] && { echo "$worst"; return 0; }
      ;;
  esac

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
  # curl|wget piped into a shell: `curl https://x | bash`, `wget -qO- u | sh`, `curl u | sudo bash`.
  # This is the classic remote-code-execution one-liner: a downloaded script runs unreviewed. It is
  # cross-statement (the `|` splits it into `curl …` and `bash`, neither dangerous alone), so it
  # cannot be caught per-statement and lives here as a backstop over the JOINED line. ASK: the
  # operator must fetch, READ, then run by hand. The pipe target may be sh/bash/zsh/dash/ash,
  # optionally via sudo and with a trailing `-` / `-s` arg.
  printf '%s' "$line" \
    | grep -Eq '(curl|wget)[[:space:]].*\|[[:space:]]*(sudo[[:space:]]+)?(sh|bash|zsh|dash|ash)([[:space:]]|$)' \
    && return 0
  # gh (pr merge / repo delete / release) and infra tools (terraform/tofu/kubectl/helm/databricks
  # apply|destroy|...) are classified STRUCTURALLY per resolved command in _classify_statement_tokens
  # (3c/3c'), not by substring, so a string merely mentioning them no longer false-positives.
  return 1
}

# classify <argv...> -> echoes DENY|ASK|ALLOW (highest severity across all statements).
classify() {
  local verdict="ALLOW" joined sev
  local -a stmt=()

  if [[ $# -eq 1 ]]; then
    # ONE arg = a command STRING (tests, or a caller passing a whole line). First remove shell
    # line-continuations (a backslash immediately before a newline) so `rm \<newline>-rf x` is the
    # single command it really is; a BARE newline remains a statement separator. Then split on
    # operators, tokenize each statement (respecting quotes), and classify.
    local body="${1//\\$'\n'/}"
    joined="$body"
    local statements
    # Split on every shell statement separator, including a single `&` (background) and `|&` — the
    # argv path already splits on `&`, so the string path must match it or `cd x & rm -rf y` slips.
    statements=$(printf '%s' "$body" | sed -E 's/(&&|\|\||\|&|;|\||&)/\
/g')
    local s
    while IFS= read -r s; do
      s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"
      [[ -z "$s" ]] && continue
      local -a toks=(); local tok
      while IFS= read -r tok; do [[ -n "$tok" ]] && toks+=("$tok"); done < <(_tokenize_statement "$s")
      [[ ${#toks[@]} -eq 0 ]] && continue
      sev=$(_classify_statement_tokens "${toks[@]}")
      [[ "$sev" == "DENY" ]] && { echo DENY; return 0; }
      [[ "$sev" == "ASK" ]] && verdict="ASK"
    done <<EOF
$statements
EOF
  else
    # REAL argv: $@ are already shell-split tokens. Use them VERBATIM — a quoted argument like
    # `bash -c '<cmd string>'` stays ONE token (the bash -c handler re-classifies it). Do NOT
    # re-join + re-tokenize: that loses the quoting and splits the -c command string (the bug
    # that let `bash -c 'rm -rf /etc'` reach exec). Split statements only at standalone operators.
    joined="$*"
    local t
    for t in "$@"; do
      case "$t" in
        ";"|"&&"|"||"|"|"|"&")
          if [[ ${#stmt[@]} -gt 0 ]]; then
            sev=$(_classify_statement_tokens "${stmt[@]}")
            [[ "$sev" == "DENY" ]] && { echo DENY; return 0; }
            [[ "$sev" == "ASK" ]] && verdict="ASK"
            stmt=()
          fi
          ;;
        *) stmt+=("$t") ;;
      esac
    done
    if [[ ${#stmt[@]} -gt 0 ]]; then
      sev=$(_classify_statement_tokens "${stmt[@]}")
      [[ "$sev" == "DENY" ]] && { echo DENY; return 0; }
      [[ "$sev" == "ASK" ]] && verdict="ASK"
    fi
  fi

  # Regex backstop over the joined line (reset --hard to a remote ref); structural checks cover rest.
  if _regex_deny "$joined"; then echo DENY; return 0; fi
  if [[ "$verdict" == "ALLOW" ]] && _regex_ask "$joined"; then verdict="ASK"; fi
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
  echo "run-sandboxed: infra destroy, shred, dd to a device, recursive chmod/chown of a system" >&2
  echo "run-sandboxed: path, and find -delete/-exec on a system path are blocked. Will not run." >&2
  exit 2
fi

if [[ "$verdict" == "ASK" ]]; then
  echo "run-sandboxed: REFUSED (ASK): outward / destructive-but-recoverable command — ${*}" >&2
  echo "run-sandboxed: this wrapper is non-interactive and cannot prompt for approval." >&2
  echo "run-sandboxed: review it, then re-run by hand outside the wrapper if it is intended." >&2
  exit 3
fi

# Must stay identical to fleet_run.RUN_ID_PATTERN (SEC-002: path-escape via --run-id / FLEET_RUN_ID).
_RUN_ID_RE='^[0-9]{8}T[0-9]{6}Z-[a-z][a-z0-9-]*[a-z0-9]-[0-9a-f]{6}$'

_generated_run_id() {
  # Regex-compatible enough for run-archive naming, but only used when the caller has not supplied
  # the real run id yet.
  printf '%s-reviewer-sandbox-%06x' "$(date -u +%Y%m%dT%H%M%SZ)" "$(( $$ & 0xffffff ))"
}

_validate_run_id() {
  # Reject path traversal / malformed ids before any mkdir or bwrap bind (SEC-002).
  local rid="$1"
  if [[ -z "$rid" ]]; then
    echo "run-sandboxed: REFUSED: empty run_id" >&2
    exit 1
  fi
  # Fast rejects for path metacharacters (defense in depth ahead of the regex).
  # Note: bash case patterns cannot reliably match embedded NUL; the RUN_ID regex
  # below is the authoritative shape check.
  case "$rid" in
    */*|*..*)
      echo "run-sandboxed: REFUSED: invalid run_id (path characters): ${rid@Q}" >&2
      exit 1
      ;;
  esac
  if [[ ! "$rid" =~ $_RUN_ID_RE ]]; then
    echo "run-sandboxed: REFUSED: run_id does not match RUN_ID_PATTERN: ${rid@Q}" >&2
    exit 1
  fi
}

_repo_root() {
  local root
  if root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    (cd "$root" && pwd -P)
  else
    pwd -P
  fi
}

_sha256_path() {
  local path="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$path" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  else
    git hash-object "$path"
  fi
}

_snapshot_worktree_hashes() {
  local repo="$1" rel abs
  {
    git -C "$repo" ls-files -z | while IFS= read -r -d '' rel; do
      case "$rel" in
        .fleet/runs/*) continue ;;
      esac
      abs="$repo/$rel"
      if [[ -f "$abs" ]]; then
        printf 'file %s %s\n' "$(_sha256_path "$abs")" "$rel"
      else
        printf 'missing %s\n' "$rel"
      fi
    done
    git -C "$repo" ls-files -z --others --exclude-standard | while IFS= read -r -d '' rel; do
      case "$rel" in
        .fleet/runs/*) continue ;;
      esac
      abs="$repo/$rel"
      if [[ -f "$abs" ]]; then
        printf 'untracked %s %s\n' "$(_sha256_path "$abs")" "$rel"
      fi
    done
  } | LC_ALL=C sort
}

_sbpl_string() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  printf '"%s"' "$s"
}

_reviewer_env() {
  local kv name
  reviewer_filtered=()
  for kv in "${filtered[@]}"; do
    name="${kv%%=*}"
    case "$name" in
      HOME|TMPDIR|FLEET_ROLE|FLEET_RUN_ID|FLEET_RUN_DIR|FLEET_TEST_OUTPUT_DIR)
        continue
        ;;
    esac
    reviewer_filtered+=("$kv")
  done
  reviewer_filtered+=(
    "HOME=$reviewer_home"
    "TMPDIR=$reviewer_tmp"
    "FLEET_ROLE=reviewer"
    "FLEET_RUN_ID=$run_id"
    "FLEET_RUN_DIR=$reviewer_run_dir"
    "FLEET_TEST_OUTPUT_DIR=$reviewer_test_output"
  )
}

_exec_reviewer_sandbox() {
  local run_q tmp_q test_q home_q profile
  if command -v sandbox-exec >/dev/null 2>&1; then
    run_q="$(_sbpl_string "$reviewer_run_dir")"
    tmp_q="$(_sbpl_string "$reviewer_tmp")"
    test_q="$(_sbpl_string "$reviewer_test_output")"
    home_q="$(_sbpl_string "$reviewer_home")"
    # Reviewer role: deny by default, then grant only what a read-only reviewer needs.
    # Network is DROPPED — a reviewer reads a candidate tree and emits findings; it has no business
    # reaching the network, and an outbound channel is exactly the exfiltration path the sandbox is
    # meant to close.
    #
    # macOS note: on recent darwin builds, `(allow file-read* (subpath ...))` profiles abort at
    # launch (SIGABRT) because dyld and system services need broader read reach than an enumerated
    # subpath list can express. We therefore allow file-read* host-wide but keep file-write*
    # scoped to the run dir ($TMPDIR, $HOME, test-output) plus /dev — the repo stays read-only in
    # practice because writes outside those subpaths are denied.
    profile="$(cat <<EOF
(version 1)
(deny default)
(allow process*)
(allow sysctl*)
(allow mach-lookup)
(allow file-read*)
(allow file-write*
  (subpath $run_q)
  (subpath $tmp_q)
  (subpath $test_q)
  (subpath $home_q)
  (subpath "/dev")
)
EOF
)"
    exec sandbox-exec -p "$profile" env -i "${reviewer_filtered[@]}" "${reviewer_cmd[@]}"
  fi

  if command -v bwrap >/dev/null 2>&1; then
    # Narrowed reviewer mount. The old form `--bind / /` handed the child the WHOLE host
    # read-write (only the repo was re-bound read-only afterwards), so a reviewer could scribble
    # over $HOME, /etc, sibling worktrees — anything outside the repo. Instead, build the namespace
    # from nothing and bind ONLY what a read-only reviewer legitimately needs:
    #   - the candidate repo, READ-ONLY (the artifact under review must not be mutated);
    #   - the run dir, READ-WRITE (the one place reviewer output, $TMPDIR and $HOME live — see
    #     _reviewer_env, which points HOME/TMPDIR/FLEET_TEST_OUTPUT_DIR inside it);
    #   - a minimal set of system paths READ-ONLY (/usr /bin /sbin /lib* /etc) so interpreters and
    #     CA certs resolve. `--ro-bind-try` skips any that are absent on this host.
    # No host RW of $HOME and no blanket RW of /. /proc and a minimal /dev are synthesized rather
    # than bound from the host. Run-dir binds come LAST so they layer over the read-only repo even
    # when the run dir lives under it (.fleet/runs/<id> is inside the repo).
    #
    # Drop ambient/inheritable capabilities before entering bwrap. A reviewer namespace that
    # inherited CAP_SYS_ADMIN et al. would be a weaker boundary, not a stronger one; and bwrap
    # itself refuses to start ("Unexpected capabilities but not setuid") when launched with an
    # ambient cap set, which is exactly the posture inside a privileged CI container. `setpriv`
    # (util-linux) is preferred, `capsh` (libcap) is the fallback; if neither is present we exec
    # bwrap directly (hosts without an ambient cap set need no prefix).
    local -a cap_drop=()
    if command -v setpriv >/dev/null 2>&1; then
      cap_drop=(setpriv --inh-caps=-all --ambient-caps=-all --)
    elif command -v capsh >/dev/null 2>&1; then
      cap_drop=(capsh --inh= --drop=all --)
    fi
    # --unshare-net drops the host network namespace so the reviewer cannot open outbound
    # sockets (exfiltration). Matches the "Network is DROPPED" contract documented above for
    # sandbox-exec; without this flag bwrap would inherit the host netns.
    exec "${cap_drop[@]}" bwrap \
      --unshare-net \
      --ro-bind /usr /usr \
      --ro-bind /bin /bin \
      --ro-bind-try /sbin /sbin \
      --ro-bind-try /lib /lib \
      --ro-bind-try /lib64 /lib64 \
      --ro-bind-try /etc /etc \
      --proc /proc \
      --dev /dev \
      --ro-bind "$repo_root" "$repo_root" \
      --bind "$reviewer_run_dir" "$reviewer_run_dir" \
      --chdir "$PWD" \
      env -i "${reviewer_filtered[@]}" "${reviewer_cmd[@]}"
  fi

  # SEC-005: no real sandbox binary — refuse by default. Override ack enables the
  # post-exec hash-audit fallback (detects mutations; does not prevent them).
  case "${FLEET_SECURITY_OVERRIDE_ACK:-}" in
    1|true|TRUE|yes|YES|on|ON) ;;
    *)
      echo "run-sandboxed: REFUSED: --role reviewer requires sandbox-exec or bwrap" >&2
      echo "  Install bubblewrap (Linux) or use macOS sandbox-exec, or set" >&2
      echo "  FLEET_SECURITY_OVERRIDE_ACK=1 to acknowledge the degraded post-exec" >&2
      echo "  hash-audit fallback (audit only — not prevention)." >&2
      exit 4
      ;;
  esac
  echo "run-sandboxed: WARNING: no sandbox-exec/bwrap; using post-exec hash audit (FLEET_SECURITY_OVERRIDE_ACK=1)" >&2

  local before after child_status=0
  before="$(mktemp "${TMPDIR:-/tmp}/reviewer-before.XXXXXX")"
  after="$(mktemp "${TMPDIR:-/tmp}/reviewer-after.XXXXXX")"
  _snapshot_worktree_hashes "$repo_root" >"$before"
  set +e
  env -i "${reviewer_filtered[@]}" "${reviewer_cmd[@]}"
  child_status=$?
  set -e
  _snapshot_worktree_hashes "$repo_root" >"$after"
  if ! cmp -s "$before" "$after"; then
    echo "run-sandboxed: reviewer modified tracked/untracked files outside .fleet/runs" >&2
    diff -u "$before" "$after" >&2 || true
    rm -f "$before" "$after"
    exit 4
  fi
  rm -f "$before" "$after"
  exit "$child_status"
}

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
#
# FLEET_DISABLE_* are the substrate kill switches (see references/substrate-disable-knobs.md). They
# are NOT credentials, but they are just as dangerous to forward: a single truthy value silently
# turns a verification layer into a no-op. If one rode into a sandboxed child (e.g. a nested fleet
# run the wrapped command spawns) it would quietly drop that child's guard. The allowlist already
# excludes them — they are not in keep_vars — but scrub them EXPLICITLY so a future widening of the
# allowlist (say, a `FLEET_*` keep rule) can never let a disable knob ride into the sandbox.
filtered=()
for kv in "${preserved[@]}"; do
  name="${kv%%=*}"
  case "$name" in
    GH_TOKEN|GITHUB_TOKEN|XAI_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|AWS_*|*_TOKEN|*_KEY|*_SECRET|*_PASSWORD)
      continue
      ;;
    FLEET_DISABLE_*)
      continue
      ;;
  esac
  filtered+=("$kv")
done

if [[ "$role" == "reviewer" ]]; then
  repo_root="$(_repo_root)"
  if [[ -z "$run_id" ]]; then
    run_id="$(_generated_run_id)"
  fi
  # SEC-002: validate --run-id / FLEET_RUN_ID before mkdir or sandbox mounts.
  _validate_run_id "$run_id"
  runs_root="$repo_root/.fleet/runs"
  mkdir -p "$runs_root"
  runs_root="$(cd "$runs_root" && pwd -P)"
  reviewer_run_dir="$runs_root/$run_id"
  reviewer_run_dir="$(mkdir -p "$reviewer_run_dir" && cd "$reviewer_run_dir" && pwd -P)"
  # Containment: resolved path must stay under .fleet/runs/ (realpath check).
  case "$reviewer_run_dir" in
    "$runs_root"|"$runs_root"/*) ;;
    *)
      echo "run-sandboxed: REFUSED: resolved run dir escapes .fleet/runs/: $reviewer_run_dir" >&2
      exit 1
      ;;
  esac
  reviewer_tmp="$reviewer_run_dir/tmp"
  reviewer_test_output="$reviewer_run_dir/test-output"
  reviewer_home="$reviewer_run_dir/home"
  mkdir -p "$reviewer_tmp" "$reviewer_test_output" "$reviewer_home"

  reviewer_filtered=()
  reviewer_cmd=("$@")
  _reviewer_env
  _exec_reviewer_sandbox
fi

exec env -i "${filtered[@]}" "$@"
