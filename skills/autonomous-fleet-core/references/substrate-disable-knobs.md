# Substrate kill-switch convention

Each verification/integrity layer exposes a `FLEET_DISABLE_*`
env var that, when set truthy, makes the layer's CLI early-exit with
code 0 and a one-line stderr notice.

This exists for two reasons:

1. **Operator escape hatch.** When a layer is flagging a known false
   positive and blocking ship, the operator needs a single-run override
   without re-deploying the substrate.
2. **Falsifiable comparator for the adversarial bench.** The
   substrate-off vs substrate-on delta IS the value the substrate must
   defend. Without real kill switches the bench's "off mode" is fiction.
   See `docs/external-dogfood/adversarial-bench-2026-06.md` § Methodology.

# Env-var registry

The substrate ships **nine** live knobs across three classes. There is
exactly ONE env var per layer, and the helper
(`scripts/lib/substrate_disable.py`) is the only place the truthy rule
and the stderr-notice format live.

## Verification-substrate layers (operator escape hatch)

These four are the original adversarial-bench comparator. A truthy knob
treats the layer's verdict as PASS for that run.

| Layer | Script | Env var |
|---|---|---|
| 1 — review-findings | `scripts/verify_findings.py` | `FLEET_DISABLE_VERIFY_FINDINGS` |
| 2 — stop-verify | `scripts/stop_verify.py` | `FLEET_DISABLE_STOP_VERIFY` |
| 3 — blind-fix | `scripts/verify_blind_fix.py` | `FLEET_DISABLE_BLIND_FIX` |
| 4 — run-archive | `scripts/validate_run_archive.py` | `FLEET_DISABLE_RUN_ARCHIVE` |

## Contract/budget verifiers (operator escape hatch)

Same plain-disable semantics as the four above — a known false positive
can be waved through for a single run.

| Layer | Script | Env var |
|---|---|---|
| registry-lint | `scripts/registry_lint.py` | `FLEET_DISABLE_REGISTRY_LINT` |
| round-budget | `scripts/verify_round_budget.py` | `FLEET_DISABLE_ROUND_BUDGET` |

## Security / integrity knobs (FAIL-CLOSED — explicit operator override required)

These three guard supply-chain and isolation invariants, not advisory
quality gates. They do **not** silently no-op on a bare truthy value:
disabling them requires an explicit operator override (per the integrity
agents' fail-closed change), so a stray env var in CI cannot quietly
drop a security check. Treat a request to disable one of these as an
operator decision that must be recorded in `DECISIONS.md`.

| Layer | Script | Env var |
|---|---|---|
| sha-pin | `scripts/verify_sha_pin.py` | `FLEET_DISABLE_SHA_PIN` |
| reviewer-sandbox | `scripts/verify_reviewer_sandbox.py` | `FLEET_DISABLE_REVIEWER_SANDBOX` |
| namespacing | `scripts/validate_namespacing.py` | `FLEET_DISABLE_NAMESPACING` |

There is exactly ONE env var per layer; no legacy aliases, no fallbacks.
Do not invent additional `FLEET_DISABLE_*` names — the registry above is
the complete, authoritative set. (`FLEET_DISABLE_X` /
`FLEET_DISABLE_MY_LAYER` that appear in the bench driver comment and the
helper docstring are illustrative placeholders, not live knobs.)

# Truthy semantics

Case-insensitive: `1`, `true`, `yes`, `on`.
Everything else (`0`, `false`, `no`, `off`, empty string, unset,
arbitrary strings) leaves the layer enabled.

The strict allow-list is intentional. We do NOT accept "anything
non-empty as truthy" because that turns typos into silent disables —
the failure mode we're trying to avoid is "operator thought they were
running the substrate but quietly weren't."

# Disable contract

For the **verification-substrate** and **contract/budget** classes
(the six escape-hatch knobs), when the env var is truthy the CLI must:

1. Exit code **0** (success / no-op).
2. Print exactly `<layer-label>: DISABLED via <ENV_VAR>=1 (no-op exit 0)`
   to stderr. The format is pinned by tests so dashboards can grep it.
3. Short-circuit **before** arg parsing — invalid arguments must NOT
   produce a nonzero exit when the layer is disabled.

The semantics: "disabled" means "treat the substrate's verdict as PASS
for this run." If you want fail-closed behavior instead for one of these
six, do not use the disable knob — fix the upstream problem.

For the **security / integrity** class (`FLEET_DISABLE_SHA_PIN`,
`FLEET_DISABLE_REVIEWER_SANDBOX`, `FLEET_DISABLE_NAMESPACING`) the
contract is different — these knobs FAIL CLOSED. A bare truthy value is
not sufficient to drop the check; the layer requires the integrity
agents' explicit operator-override gate and records the decision rather
than silently no-opping to PASS. (The runtime fail-closed behaviour is
owned by those scripts under the integrity package; this doc states the
contract, it does not implement it.)

# Bench-driver wiring

`scripts/bench-adversarial.sh` sets the env vars with `export` (not
bare assignment) so they reach the child adapter process. On
substrate-on mode it `unset`s them, so a stale value from a prior
off-run doesn't leak into the on-run. The driver toggles only the four
verification-substrate layers below — the contract/budget verifiers and
the fail-closed security/integrity knobs are not part of the bench's
off/on comparator.

```bash
# substrate-off mode (inside the per-target run loop)
export FLEET_DISABLE_VERIFY_FINDINGS=1
export FLEET_DISABLE_STOP_VERIFY=1
export FLEET_DISABLE_BLIND_FIX=1
export FLEET_DISABLE_RUN_ARCHIVE=1

# substrate-on mode
unset FLEET_DISABLE_VERIFY_FINDINGS
unset FLEET_DISABLE_STOP_VERIFY
unset FLEET_DISABLE_BLIND_FIX
unset FLEET_DISABLE_RUN_ARCHIVE
```

A regression test (`tests/test_substrate_disable.py::
test_bench_driver_actually_exports_disable_vars`) asserts that both
`export FLEET_DISABLE_*=1` AND `unset FLEET_DISABLE_*` literals
appear in the driver — the original Commit C bug was that the driver
built the env string and only echo'd it, never exporting it.

# Library helper

Use `scripts/lib/substrate_disable.py`:

```python
from lib.substrate_disable import announce_disabled, is_disabled

def main() -> int:
    if is_disabled("FLEET_DISABLE_MY_LAYER"):
        return announce_disabled("my-layer", "FLEET_DISABLE_MY_LAYER")
    # ... normal arg parsing and execution ...
```

The helper is the single source of truth for the truthy rule and the
stderr-notice format. Layers MUST NOT roll their own check.

# Mutations covering this convention

In `tests/mutations.yaml`:

- `kill-switch-truthy-relaxed` — flipping truthy check to always-true
  breaks falsy-value tests.
- `kill-switch-truthy-strict` — flipping truthy check to always-false
  breaks short-circuit tests.

# Lineage

- Follow-up commit for `docs/plans/way-ahead-2026-06-23.md` § Commit C.
- Adversarial review found that Commit C's bench driver referenced
  env vars that didn't exist in any verifier. This doc + the
  `substrate_disable.py` library + `tests/test_substrate_disable.py` close the gap.
