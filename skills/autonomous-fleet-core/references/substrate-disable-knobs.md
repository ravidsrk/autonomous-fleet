# Substrate kill-switch convention

Each of the 4 verification-substrate layers exposes a `FLEET_DISABLE_*`
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

| Layer | Script | Env var |
|---|---|---|
| 1 — review-findings | `scripts/verify_findings.py` | `FLEET_DISABLE_VERIFY_FINDINGS` |
| 2 — stop-verify | `scripts/stop_verify.py` | `FLEET_DISABLE_STOP_VERIFY` |
| 3 — blind-fix | `scripts/verify_blind_fix.py` | `FLEET_DISABLE_BLIND_FIX` |
| 4 — run-archive | `scripts/validate_run_archive.py` | `FLEET_DISABLE_RUN_ARCHIVE` |

There is exactly ONE env var per layer. No legacy aliases, no
fallbacks. The substrate has no installed-user base yet — shipping a
back-compat surface now would lock us into immediate technical debt.
If you find any other name in the codebase (e.g. `STOP_VERIFY_DISABLED`)
it's stale; delete on sight.

# Truthy semantics

Case-insensitive: `1`, `true`, `yes`, `on`.
Everything else (`0`, `false`, `no`, `off`, empty string, unset,
arbitrary strings) leaves the layer enabled.

The strict allow-list is intentional. We do NOT accept "anything
non-empty as truthy" because that turns typos into silent disables —
the failure mode we're trying to avoid is "operator thought they were
running the substrate but quietly weren't."

# Disable contract

When the env var is truthy, the CLI must:

1. Exit code **0** (success / no-op).
2. Print exactly `<layer-label>: DISABLED via <ENV_VAR>=1 (no-op exit 0)`
   to stderr. The format is pinned by tests so dashboards can grep it.
3. Short-circuit **before** arg parsing — invalid arguments must NOT
   produce a nonzero exit when the layer is disabled.

The semantics: "disabled" means "treat the substrate's verdict as PASS
for this run." If you want fail-closed behavior instead, do not use
the disable knob — fix the upstream problem.

# Bench-driver wiring

`scripts/bench-adversarial.sh` sets the env vars with `export` (not
bare assignment) so they reach the child adapter process. On
substrate-on mode it `unset`s them, so a stale value from a prior
off-run doesn't leak into the on-run.

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
