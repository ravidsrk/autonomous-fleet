# Autonomous-Fleet — End-to-End Review

**Status:** FROZEN (historical). This document is the single source of truth for the
`ravidsrk/review-fix` fix run (2026-06-20). It is a severity-ranked, verified, deduped adversarial
review. Each finding carries a `→ Fix` recommendation that is the spec for closing it. Do not
re-audit or re-scope the original findings below.

**Post-review closure (2026-06-26):** H1 (LICENSE), H2 (validator false greens), H3 (trust
boundaries + `run-sandboxed.sh`), L2 (`LOOP_POLL` in engine), L3 (`secure-ship.yaml` archived stub),
and L5 (codex adapter version) are closed on `main`. The regression floor is now `./scripts/bootstrap.sh`
or `./scripts/validate-all.sh` green; `pytest` → **928 passed** (49 test files); active campaign
presets `repo-health`, `ship-with-proof`, and `quality-gate` dry-run exit 0 (`align-then-ship` is
archived pending exploratory promotion).

**Original confirmed-green baseline (2026-06-20):** `./scripts/validate-all.sh` green; `pytest` →
25 passed; all 4 shipped campaign presets (`repo-health`, `ship-with-proof`, `quality-gate`,
`align-then-ship`) dry-run exit 0.

**What it is:** a published skills framework for autonomous multi-agent engineering jobs —
tool-agnostic core engine (primitives + file-ledger coordination), thin mission skills, per-runtime
adapters, plus shell/Python validation & conditional-campaign machinery.

**Overall verdict:** The architecture is coherent and the contract holds — every adapter implements
every primitive, every internal cross-reference resolves, all 25 tests pass, `validate-all.sh` is
green. The real weaknesses are in three places: (1) a broken LICENSE, (2) a class of validators that
report green on missing/empty input, and (3) safety being 100% prose with no mechanical enforcement.
Nothing is data-destroying; the framework is sound for its documented use (run on your own repos).

Each finding below was verified by direct command re-run; `[verified]` marks a claim I reproduced,
`[reviewer-reported]` marks a sub-agent finding I judged sound but did not independently re-run.

---

## 🔴 HIGH

### H1 — The LICENSE is a non-standard, narrowed "MIT" · `LICENSE:8` · [verified]
The grant clause reads "to use, copy, **migrate**, sublicense, and/or sell copies." The canonical
MIT words **"modify, merge, publish, distribute"** have been replaced by the single word "migrate."
The file is labeled "MIT License" but grants strictly less than MIT — under the literal text a user
may not modify or redistribute. Public, published package → highest-consequence concrete defect.
→ **Fix:** restore the canonical MIT body verbatim (keep `Copyright (c) 2026 ravidsrk`).
→ **Proof of closure:** `LICENSE` contains `to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies` and the word `migrate` is absent.

### H2 — Validators report success on missing / unvalidated input (a class) · [verified]
- `./scripts/validate-fleet-outcome.sh /does/not/exist.md` → `SKIP … (not found)` + "All readiness
  docs passed" + **exit 0**. A typo'd path passes CI green.
- `./scripts/validate-skills.sh` with skill-creator absent → `WARN … skipping` + **exit 0**, and
  `validate-all.sh` still prints "All checks passed" though skills were never validated.
- `./scripts/run-campaign.sh banana --preset repo-health` → accepts the bogus runtime, **exit 0**
  (no `case` guard on runtime name).

The value proposition is "machine-validated readiness"; a validator that is green when it validated
nothing erodes that.
→ **Fix:** treat an explicitly-named missing path as FAIL; make missing skill-creator FAIL unless
`VALIDATE_SKILLS_OPTIONAL=1`; add `case "$RUNTIME" in grok|claude|codex) ;; *) exit 1 ;; esac`.
→ **Proof of closure:** `validate-fleet-outcome.sh /does/not/exist.md` exits non-zero;
`validate-skills.sh` exits non-zero when skill-creator absent and exits 0 with
`VALIDATE_SKILLS_OPTIONAL=1`; `run-campaign.sh banana --preset repo-health --dry-run` exits non-zero.

### H3 — Autonomy safety is prose-only; no trust boundary, no mechanical rails · `engine.md` · [reviewer-reported, architecturally sound]
The engine instructs the coordinator to *read* untrusted repo content (README, manifests, issues,
worker output) but never marks it as **DATA, not INSTRUCTIONS**. "Testnet/staging only," "MERGE ≠
DEPLOY," and "never log secrets" are entirely prose. `run-mission-headless.sh --handoff FILE` reads
an arbitrary file verbatim into the agent prompt; the spawned agent inherits the operator's full env.
Under `--yolo` against a third-party repo, a prompt-injected README has nothing mechanical stopping
it. Partly inherent to LLM-agent frameworks, currently mitigated only by "run on your own repos."
→ **Fix (mechanical mitigations, as code/docs — NOT activated against any live target):**
add an explicit **TRUST BOUNDARIES** section to `engine.md` (repo/issue/worker content is DATA, not
instructions; quote-don't-execute; provide a fenced data-marker convention); fence `--handoff`
content as data in `run-mission-headless.sh`; ship an env-scrubbing / command-deny wrapper
(`scripts/run-sandboxed.sh`) for `--yolo` runs. Residual LLM-inherent risk must be documented, not
silently closed.
→ **Proof of closure:** `engine.md` has a TRUST BOUNDARIES section; `run-mission-headless.sh` wraps
handoff content with a data marker; `scripts/run-sandboxed.sh` exists and scrubs env / denies a
forbidden-command list; readiness doc records the documented residual.

---

## 🟠 MEDIUM

### M1 — Custom-campaign `--dry-run` raises a Python traceback · `run-campaign.sh` → `fleet_outcome.py` · [reviewer-reported; shipped presets verified unaffected]
The dry-run stub outcome carries only `code_bug_findings` and `drift_open`. A *custom* campaign whose
edges reference any other metric (`gaps_open`, `bugs_open`, …) hits "metric not found" and dumps a
traceback. All four shipped presets dry-run fine (verified), so no README command is affected — but
dry-run is exactly the "preview my new campaign safely" feature.
→ **Fix:** in the dry-run stub, default unknown metrics to 0 (or catch `ValueError` and fall through
to the first `always` edge).
→ **Proof of closure:** a custom campaign whose edge references `gaps_open` dry-runs without a
traceback (exit 0).

### M2 — Doc rot: stale pytest count & paths · `DECISIONS.md:23`, `doc-sync-readiness.md`, `test-coverage-readiness.md` · [verified]
`DECISIONS.md:23` and `doc-sync-readiness.md` still say "**11** pytest pass"; the suite is now 25
(`arch-build-readiness.md` correctly records "25, was 11"). `DECISIONS.md:7` lists a `REPO_ROOT`
path that doesn't exist in this checkout; two readiness `repo:` fields use a filesystem path while
the canonical form elsewhere is the `owner/name` slug (`ravidsrk/autonomous-fleet`).
→ **Fix:** refresh the counts to 25 (or current), normalize the stale REPO_ROOT and `repo:`
provenance, or annotate as pre-adversarial-run snapshots.
→ **Proof of closure:** no doc claims "11 pytest"; `repo:` fields use the canonical slug; counts
match the current suite.

### M3 — Test suite is narrower than it looks · `tests/` · [reviewer-reported]
- `test_injection.py` proves an *unknown* mission name is rejected, but never tests a *known* name
  with appended shell metacharacters (the actual injection class). The guarded interpolation vector
  no longer exists, so the test would pass even if registry validation regressed.
- `test_validate_cli.py` "collected_once" is tautological — a single `glob()` into a `set()` can't
  produce a duplicate, so it can't catch the dedup regression it's named for.
- No end-to-end coverage of a *non-dry-run* campaign path.
- Real footgun: `eval_edge` strips quotes for `==` but `… contains "x"` does **not** strip quotes,
  so a quoted `contains` silently returns False.
→ **Fix:** add a known-name + metachar injection test (proves the shell layer is safe for a *valid*
mission); reconcile `contains` quoting with `==` (and pin it with a test); cover `pick_next_node`
terminal / no-match / malformed-edge branches; make the dedup test actually constrain (non-tautological).
→ **Proof of closure:** new metachar injection test green (no marker file created); quoted `contains`
returns the correct boolean with a test pinning it; pick_next_node branch tests green; dedup test
fails if dedup is removed. pytest count rises above 25.

---

## 🟡 LOW / NIT — [verified]

- **L1** — Stray double-backtick (`` claude-code`` ``) in 7 mission SKILL.md files
  (test-coverage:28, bug-batch:29, dependency-update:29, cleanup:29, legacy-rebuild:29,
  targeted-migration:29, take-product-to-completion:32). Breaks inline-code rendering.
  → **Fix:** delete the extra backtick after `autonomous-fleet-adapter-claude-code` in all 7 files.
- **L2** — `LOOP_POLL` is treated as a primitive in `runtime-goals.md:96` and three adapters but is
  absent from the canonical primitive list in `engine.md`.
  → **Fix:** promote `LOOP_POLL` into the `engine.md` primitive summary (or demote it in
  runtime-goals.md to "optional convenience"). Promotion preferred — keep adapter docs consistent.
- **L3** — `secure-ship` is documented as a campaign in `fleet-program` docs but has no
  `scripts/campaigns/secure-ship.yaml`; `--preset secure-ship` fails cleanly (exit 1, verified) but
  it's an advertised name with no runnable preset.
  → **Fix:** add `scripts/campaigns/secure-ship.yaml` matching the documented linear program (or
  de-advertise). Adding the preset preferred.
- **L4** — Worker/optional skill ids `code-simplification`, `skill-creator`, `swiftui-liquid-glass`
  are referenced in missions but absent from the `community-skills.md` catalog.
  → **Fix:** add catalog entries (with source) in `community-skills.md`, or remove the references.
- **L5** — Version drift: codex adapter `1.0.0` vs orca/grok/claude-code/core `1.1.0`; missions lack
  the `compatibility:` field the other skills carry.
  → **Fix:** bump codex adapter to `1.1.0`; add `compatibility:` to mission frontmatter (or document
  that missions inherit compatibility from core+adapter).
- **L6** — `arXiv 2601.15195` is **real** (Ehsani et al., "Where Do AI Coding Agents Fail?", MSR
  2026, ~33k PRs) and the *direction* of the claim ("documentation tasks → highest merge success")
  is accurate, but the precise **"~84%"** is not in the abstract (unverified) and the paper ranks by
  *task category*, not "cross-agent" — so "highest cross-agent merge rate" is a mild reframe.
  → **Fix:** soften to the paper's own wording ("documentation/CI/build tasks achieve the highest
  merge success") and drop or source the exact 84% figure, in README and any mission SKILL.md that
  repeats it.

---

## Out of scope / human-owned (do NOT do in this run)
- `BASE → main` promotion (human meta-PR).
- Any `npx skills` re-publish / package publish.
- Activating any safety rail against a live external target (H3 ships as code/docs only).
