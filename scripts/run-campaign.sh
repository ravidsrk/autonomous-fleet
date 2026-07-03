#!/usr/bin/env bash
# Mechanical campaign driver: validate outcomes between nodes, invoke headless missions.
#
# Threat model: --repo and --campaign are operator-supplied paths. Campaign YAML can name
# arbitrary missions and repos. With --yolo, agents auto-approve all tool calls against that
# repo — treat untrusted inputs as a full RCE surface; keep yolo off unless you trust both.
#
# Usage:
#   ./scripts/run-campaign.sh grok --preset repo-health [--dry-run]
#   ./scripts/run-campaign.sh grok --campaign docs/composition-e2e-campaign.yaml
#   ./scripts/run-campaign.sh claude --preset repo-health --max-turns 60
#   ./scripts/run-campaign.sh grok --preset ship-with-proof --repo /tmp/gemoji
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUNTIME=""
CAMPAIGN_FILE=""
PRESET=""
REPO_ROOT=""
DRY_RUN=0
PROBE_FAIL=0
MAX_TURNS=50
TIMEOUT_SECS=""
SKIP_AUTH_CHECK=0
YOLO=0
YOLO_ACK=0

usage() {
  cat <<'EOF'
Usage: run-campaign.sh <grok|claude|codex> (--preset NAME | --campaign PATH) [options]

Options:
  --preset NAME       Built-in under scripts/campaigns/<NAME>.yaml
  --campaign PATH     Campaign YAML file
  --repo PATH         Target git repo for missions (default: autonomous-fleet clone)
  --dry-run           Print plan only; do not invoke agents
  --probe-fail        With --dry-run: plan with FAILURE-shaped metrics (findings_open=1,
                      p0_open=1, status=blocked) so the failure/blocked branch of every
                      conditional gate is reachability-checked, not just the benign branch
  --max-turns N       Per-node turn budget (default: 50; Grok/Codex only)
  --timeout SECONDS   Per-node runtime watchdog passed to run-mission-headless.sh
                      (default: its 5400; 0 disables)
  --skip-auth-check   Skip the per-node runtime auth pre-check
  --yolo              Auto-approve agent tools (Grok: --yolo; Codex: --dangerously-bypass-approvals-and-sandbox; default: off)
  --no-yolo           Deprecated alias for default (no auto-approve)
  --yolo-untrusted-acknowledged  Required with --yolo when --repo is outside this clone (accepts RCE risk)

Runtimes:
  grok, claude, codex — supported headless drivers.
  orca — interactive only (Orca orchestration + /goal); not accepted by this script.
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

RUNTIME="$1"
shift

case "$RUNTIME" in
  grok|claude|codex) ;;
  *) echo "error: unsupported runtime '$RUNTIME' (expected grok|claude|codex)" >&2; exit 1 ;;
esac

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset)
      PRESET="${2:?}"
      shift 2
      ;;
    --campaign)
      CAMPAIGN_FILE="${2:?}"
      shift 2
      ;;
    --repo)
      REPO_ROOT="${2:?}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --probe-fail)
      PROBE_FAIL=1
      shift
      ;;
    --max-turns)
      MAX_TURNS="${2:?}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECS="${2:?}"
      shift 2
      ;;
    --skip-auth-check)
      SKIP_AUTH_CHECK=1
      shift
      ;;
    --yolo)
      YOLO=1
      shift
      ;;
    --no-yolo)
      YOLO=0
      shift
      ;;
    --yolo-untrusted-acknowledged)
      YOLO_ACK=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -n "$PRESET" ]]; then
  CAMPAIGN_FILE="$ROOT/scripts/campaigns/${PRESET}.yaml"
fi

if [[ -z "$CAMPAIGN_FILE" || ! -f "$CAMPAIGN_FILE" ]]; then
  echo "error: campaign file not found (use --preset or --campaign)" >&2
  exit 1
fi

# --probe-fail is a STATIC planning probe (failure-shaped metrics). It must never drive a
# paid/real run — a real run derives metrics from the actual fleet-outcome, not a forced shape.
if [[ "$PROBE_FAIL" -eq 1 && "$DRY_RUN" -ne 1 ]]; then
  echo "error: --probe-fail only applies to --dry-run planning (it forces failure-shaped metrics)" >&2
  exit 1
fi

if [[ -n "$REPO_ROOT" ]]; then
  REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
else
  REPO_ROOT="$ROOT"
fi

if ! git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "error: --repo '$REPO_ROOT' is not a git repository" >&2
  exit 1
fi

# RCE guard: --yolo auto-approves every tool call. Against an external --repo that is a full
# remote-code-execution surface, so require explicit acknowledgement (or run under the sandbox).
if [[ "$YOLO" -eq 1 && "$REPO_ROOT" != "$ROOT" && "$YOLO_ACK" -ne 1 ]]; then
  echo "error: --yolo against an external --repo auto-approves every tool call — a full RCE surface." >&2
  echo "       Run under scripts/run-sandboxed.sh, or pass --yolo-untrusted-acknowledged to accept the risk." >&2
  exit 2
fi

# Bootstrap the venv via the shared helper: it RE-CHECKS `import yaml, pytest, coverage` and reinstalls from
# requirements.txt, so a stale venv (binary present but pyyaml missing) self-heals instead of
# crashing the runner with a raw ModuleNotFoundError traceback.
source "$ROOT/scripts/lib/venv-bootstrap.sh"
bootstrap_validation_venv "$ROOT"

CAMPAIGN_INFO="$("$VENV_PYTHON" - <<'PY' "$CAMPAIGN_FILE" "$ROOT"
import sys, yaml
from pathlib import Path

data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
root = Path(sys.argv[2])
if not isinstance(data, dict):
    print("error: campaign YAML must be a mapping", file=sys.stderr)
    raise SystemExit(1)
if "start" not in data:
    print("error: campaign missing 'start'", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(data.get("nodes"), dict):
    print("error: campaign 'nodes' must be a mapping", file=sys.stderr)
    raise SystemExit(1)
allow_exploratory = data.get("allow_exploratory_nodes") is True
for node, spec in (data.get("nodes") or {}).items():
    if not isinstance(spec, dict) or "mission" not in spec:
        print(f"error: node '{node}' missing 'mission'", file=sys.stderr)
        raise SystemExit(1)
    # Exec-time exploratory gate (issue #94): author-time lint alone let any
    # hand-written --campaign YAML run an unproven mission. A node whose
    # mission is not shipped (skills/) but exists under
    # docs/exploratory/missions/ requires the campaign to opt in explicitly.
    mission = spec["mission"]
    shipped = (root / "skills" / mission / "SKILL.md").is_file()
    exploratory = (
        root / "docs" / "exploratory" / "missions" / mission / "SKILL.md"
    ).is_file()
    if not shipped and exploratory:
        if not allow_exploratory:
            print(
                f"error: node '{node}' runs EXPLORATORY mission '{mission}' "
                f"(docs/exploratory/missions/, no shipped run-evidence). Set "
                f"'allow_exploratory_nodes: true' in the campaign YAML to opt in.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        print(
            f"warning: node '{node}' runs EXPLORATORY mission '{mission}' "
            f"(allow_exploratory_nodes: true — unproven, expect gaps)",
            file=sys.stderr,
        )
print(data["start"])
for node, spec in data.get("nodes", {}).items():
    print(f"{node}\t{spec['mission']}")
PY
)"

START="$(echo "$CAMPAIGN_INFO" | head -1)"

mission_for_node() {
  local nid="$1"
  echo "$CAMPAIGN_INFO" | awk -F'\t' -v n="$nid" 'NF>=2 && $1==n {print $2; exit}'
}

validate_mission() {
  local mission="$1"
  "$VENV_PYTHON" -c 'import sys; sys.path.insert(0, sys.argv[1]+"/scripts"); from lib.mission_registry import MISSION_DOCS; mission=sys.argv[2]; sys.exit(0 if mission in MISSION_DOCS else 1)' "$ROOT" "$mission" \
    || { echo "error: unknown mission '$mission' (not in mission registry)" >&2; return 1; }
}

readiness_for_mission() {
  # Post-run discovery: a run-keyed run writes <mission>-<run_short>-readiness.md
  # the driver cannot predict — resolve the NEWEST on-disk match in the target
  # repo (falls back to the exact registry path when none exists yet).
  local mission="$1"
  "$VENV_PYTHON" -c 'import sys; sys.path.insert(0, sys.argv[1]+"/scripts"); from lib.mission_registry import resolve_readiness_file; print(resolve_readiness_file(sys.argv[2], sys.argv[3]))' "$ROOT" "$mission" "$REPO_ROOT"
}

dry_run_next_node() {
  local current="$1"
  "$VENV_PYTHON" - <<'PY' "$CAMPAIGN_FILE" "$current" "$ROOT" "$PROBE_FAIL"
import sys, yaml
from pathlib import Path

sys.path.insert(0, sys.argv[3] + "/scripts")
from lib.fleet_outcome import MISSION_METRICS, pick_next_node

campaign = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
current = sys.argv[2]
probe_fail = sys.argv[4] == "1"
# Static dry-run: pre-populate every known mission metric so edges that
# reference metrics outside the current node's mission don't blow up with
# "metric not found" ValueError during dry-run planning.
metrics: dict[str, int] = {}
for metric_set in MISSION_METRICS.values():
    for name in metric_set:
        metrics.setdefault(name, 0)
if probe_fail:
    # FAILURE-shaped probe: drive the failure/blocked branch of conditional gates
    # (e.g. `if: findings_open > 0`) that the benign all-zero pass can never reach.
    # Override the open-finding axes; pick_next_node still skips edges whose
    # metric is absent, so only edges keyed on these axes flip branch.
    metrics["findings_open"] = 1
    metrics["p0_open"] = 1
    status = "blocked"
else:
    status = "done"
outcome = {
    "status": status,
    "metrics": metrics,
    "deferred_missions": [],
}
nxt = pick_next_node(campaign, current, outcome)
print(nxt or "")
PY
}

if [[ "$YOLO" -eq 1 ]]; then
  echo "warning: --yolo auto-approves all agent tool calls; untrusted --repo/--campaign + yolo = full RCE surface" >&2
fi

# Campaign-level synthetic archive (progress excerpt + lifecycle trace, no runtime
# transcript). Complements run-mission-headless.sh which keeps the capture with
# headless-runtime-response.* — AC1 requires both entry points to emit; distinct run_ids.
emit_campaign_node_archive() {
  local mission="$1"
  local emit_mission out archive
  emit_mission="$("$VENV_PYTHON" -c 'import sys; sys.path.insert(0, sys.argv[1]+"/scripts"); from lib.mission_registry import headless_emit_mission; print(headless_emit_mission(sys.argv[2]))' "$ROOT" "$mission")"
  out="$("$VENV_PYTHON" "$ROOT/scripts/emit_headless_dryrun_trace.py" \
    --mission "$emit_mission" --repo "$REPO_ROOT" --runtime "$RUNTIME" --fleet-root "$ROOT" 2>&1)" || {
    echo "  warn: campaign node archive emit failed (non-fatal)" >&2
    return 0
  }
  echo "$out" | sed 's/^/  /'
  archive="$(echo "$out" | sed -n 's/^emit_headless_dryrun_trace: archive=//p' | head -1)"
  if [[ -n "$archive" && -d "$archive" ]]; then
    echo "  campaign archive kept: $archive"
  fi
  return 0
}

echo "== run-campaign =="
echo "runtime:  $RUNTIME"
echo "repo:     $REPO_ROOT"
echo "campaign: $CAMPAIGN_FILE"
echo "start:    $START"
echo "dry-run:  $DRY_RUN"
if [[ "$PROBE_FAIL" -eq 1 ]]; then
  echo "probe:    fail (findings_open=1, p0_open=1, status=blocked)"
fi
echo ""

CURRENT="$START"
STEP=0
VISITED=""

while [[ -n "$CURRENT" ]]; do
  # Per-node REVISIT BUDGET, not an unconditional cycle abort: campaigns may have DESIGNED back-edges
  # (e.g. deps->audit, bugs->docs in handoff-to-product) that revisit a node a few times to converge.
  # Allow up to 3 entries per node; the STEP>20 global cap below still stops a non-converging loop.
  VISITS=0
  for _v in $VISITED; do [[ "$_v" == "$CURRENT" ]] && VISITS=$((VISITS + 1)); done
  if [[ "$VISITS" -ge 3 ]]; then
    echo "error: node $CURRENT revisited too many times (budget 3) — non-converging loop" >&2
    exit 1
  fi

  STEP=$((STEP + 1))
  MISSION="$(mission_for_node "$CURRENT")"
  if [[ -z "$MISSION" ]]; then
    echo "error: unknown node '$CURRENT'" >&2
    exit 1
  fi

  validate_mission "$MISSION"

  READINESS="$(readiness_for_mission "$MISSION")"

  echo "--- step $STEP: node=$CURRENT mission=$MISSION ---"

  READINESS_ABS="$REPO_ROOT/$READINESS"

  adapter_for_runtime() {
    case "$1" in
      grok) echo "grok" ;;
      claude) echo "claude-code" ;;
      codex) echo "codex" ;;
      *) echo "$1" ;;
    esac
  }

  adapter_rt="$(adapter_for_runtime "$RUNTIME")"
  echo "  == adapter preflight =="
  if [[ ! -d "$ROOT/skills/autonomous-fleet-adapter-$adapter_rt" ]]; then
    echo "  preflight: skip (no fleet adapter skills under $ROOT/skills)"
  elif [[ "$DRY_RUN" -eq 1 ]]; then
    "$ROOT/scripts/preflight.sh" "$adapter_rt" --wiring-only
  else
    "$ROOT/scripts/preflight.sh" "$adapter_rt" --scm
  fi
  echo "  == community preflight =="
  if [[ ! -f "$ROOT/skills/$MISSION/SKILL.md" && ! -f "$ROOT/docs/exploratory/missions/$MISSION/SKILL.md" ]]; then
    echo "  preflight-community: skip (mission SKILL.md not under $ROOT)"
  elif [[ "$DRY_RUN" -eq 1 ]]; then
    "$ROOT/scripts/preflight-community.sh" "$MISSION" --dry-run
  else
    "$ROOT/scripts/preflight-community.sh" "$MISSION"
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    # Print the REAL flag set the child would receive (incl. --yolo and its
    # codex bypass mapping) — a dry-run that hides the dangerous flags
    # defeats its purpose as the operator's preflight.
    DRY_EXTRA=""
    [[ -n "$TIMEOUT_SECS" ]] && DRY_EXTRA+=" --timeout $TIMEOUT_SECS"
    [[ "$SKIP_AUTH_CHECK" -eq 1 ]] && DRY_EXTRA+=" --skip-auth-check"
    [[ "$YOLO" -eq 1 ]] && DRY_EXTRA+=" --yolo"
    [[ "$YOLO_ACK" -eq 1 ]] && DRY_EXTRA+=" --yolo-untrusted-acknowledged"
    echo "  would run: run-mission-headless.sh $RUNTIME $MISSION --repo $REPO_ROOT --max-turns $MAX_TURNS${DRY_EXTRA} --dry-run"
    [[ "$YOLO" -eq 1 && "$RUNTIME" == "codex" ]] && \
      echo "  note:      --yolo maps to codex --dangerously-bypass-approvals-and-sandbox in the child"
    echo "  expect:    $READINESS_ABS with fleet-outcome.status done"
    if [[ -f "$ROOT/scripts/emit_headless_dryrun_trace.py" ]]; then
      SCRATCH_REPO="$(mktemp -d "${TMPDIR:-/tmp}/fleet-campaign-dryrun-XXXXXX")"
      git -C "$SCRATCH_REPO" init -q 2>/dev/null || true
      EMIT_OUT="$("$VENV_PYTHON" "$ROOT/scripts/emit_headless_dryrun_trace.py" \
        --mission "$MISSION" --repo "$SCRATCH_REPO" --runtime "$RUNTIME" --fleet-root "$ROOT" 2>&1)" || {
        echo "  warn: emit_headless_dryrun_trace failed (non-fatal in dry-run)" >&2
        EMIT_OUT=""
      }
      rm -rf "$SCRATCH_REPO"
      if [[ -n "$EMIT_OUT" ]]; then
        echo "$EMIT_OUT" | sed 's/^/  /'
      fi
    fi
  else
    EXTRA=(--repo "$REPO_ROOT")
    [[ -n "$TIMEOUT_SECS" ]] && EXTRA+=(--timeout "$TIMEOUT_SECS")
    [[ "$SKIP_AUTH_CHECK" -eq 1 ]] && EXTRA+=(--skip-auth-check)
    [[ "$YOLO" -eq 1 ]] && EXTRA+=(--yolo)
    # Propagate the acknowledgement so the child's RCE gate doesn't re-fire on an external repo.
    [[ "$YOLO_ACK" -eq 1 ]] && EXTRA+=(--yolo-untrusted-acknowledged)
    NODE_RC=0
    "$ROOT/scripts/run-mission-headless.sh" "$RUNTIME" "$MISSION" --max-turns "$MAX_TURNS" "${EXTRA[@]}" || NODE_RC=$?
    emit_campaign_node_archive "$MISSION" || true
    if [[ "$NODE_RC" -ne 0 ]]; then
      if [[ -d "$REPO_ROOT/.fleet/runs" ]] && compgen -G "$REPO_ROOT/.fleet/runs/*" >/dev/null; then
        echo "warn: node $CURRENT runtime exited $NODE_RC (archives under $REPO_ROOT/.fleet/runs/)" >&2
      else
        echo "warn: node $CURRENT runtime exited $NODE_RC" >&2
      fi
      exit "$NODE_RC"
    fi
    if [[ -f "$READINESS_ABS" ]]; then
      ./scripts/validate-fleet-outcome.sh "$READINESS_ABS"
      # A node that finished BLOCKED must halt the campaign (GOAL_BLOCKED -> status:blocked), not
      # fall through to "Campaign complete". status:blocked is a VALID outcome that passes validation.
      # parse_readiness takes a Path, not a str (it calls .read_text). Passing a str raised an
      # AttributeError that the old `2>/dev/null || true` SILENTLY swallowed, so this halt never
      # fired. Pass Path(...) and let errors surface (validate already parsed the doc above).
      NODE_STATUS="$("$VENV_PYTHON" -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]+"/scripts"); from lib.fleet_outcome import parse_readiness; print(parse_readiness(Path(sys.argv[2])).get("status", ""))' "$ROOT" "$READINESS_ABS" || true)"
      if [[ "$NODE_STATUS" == "blocked" ]]; then
        echo "" >&2
        echo "Campaign BLOCKED at node $CURRENT (fleet-outcome.status: blocked). Halting; this is a human gate, not a completed campaign." >&2
        exit 2
      fi
    else
      echo "warn: $READINESS_ABS not found after node $CURRENT" >&2
    fi
  fi

  VISITED="${VISITED:+$VISITED }$CURRENT"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    NEXT="$(dry_run_next_node "$CURRENT")"
    echo "  next:     ${NEXT:-<campaign done>}"
    CURRENT="$NEXT"
  elif [[ ! -f "$READINESS_ABS" ]]; then
    echo "error: cannot pick next node without $READINESS_ABS" >&2
    exit 1
  else
    NEXT_JSON="$(./scripts/eval-campaign-edge.sh --readiness "$READINESS_ABS" --campaign "$CAMPAIGN_FILE" --current-node "$CURRENT")"
    NEXT="$(echo "$NEXT_JSON" | "$VENV_PYTHON" -c "import sys,json; print(json.load(sys.stdin).get('next') or '')")"
    echo "  next:     ${NEXT:-<campaign done>}"
    CURRENT="$NEXT"
  fi

  if [[ "$STEP" -gt 20 ]]; then
    echo "error: campaign step limit exceeded (cycle?)" >&2
    exit 1
  fi
done

echo ""
# `${DRY_RUN:+...}` is truthy for the string "0", so it wrongly printed "dry-run" on real runs.
DRYTAG=""; [[ "$DRY_RUN" -eq 1 ]] && DRYTAG="dry-run "
echo "Campaign ${DRYTAG}complete. Nodes visited: ${VISITED:-none}"