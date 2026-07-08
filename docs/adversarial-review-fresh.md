# Adversarial Architecture Review (fresh) — autonomous-fleet

| Field | Value |
|-------|-------|
| **run_id** | `20260708T184204Z-adversarial-review-and-fix-c6c486` |
| **BASE** | `cursor/adversarial-review-base-256a` @ `e9e541b` |
| **Scope** | Entire app (scripts/, skills substrate, CI/action, campaign orchestration) |
| **Grounding** | CODE only — prior review docs ignored |
| **PHASE** | REVIEW (pending skeptic freeze) |

---

## Ranking (dependency-ordered)

1. **FOUNDATION** — SEC-001 (`install-community.sh` eval injection)
2. **FOUNDATION** — SEC-002 (`run-id` path escape in reviewer sandbox)
3. **FOUNDATION** — SEC-003 (Linux bwrap reviewer network not unshared)
4. VERIFY-01 / SEC-005 (fleet-verify missing reviewer-sandbox + sha-pin layers)
5. ARCH-001 / VAL-006 (campaign exec-time archived-mission hole)
6. ARCHIVE-01 / ARCHIVE-02 (created_utc doctrine unenforced + stamped late)
7. Remaining medium/low findings in waves below

---

## Root-cause CLUSTERS

| Cluster | Tag | touches | CLOSES |
|---------|-----|---------|--------|
| C-INJECT | FOUNDATION | `scripts/install-community.sh` | SEC-001, SEC-006 |
| C-SANDBOX | FOUNDATION | `scripts/run-sandboxed.sh` | SEC-002, SEC-003, SANDBOX-02 |
| C-VERIFY-PARITY | FOUNDATION | `scripts/lib/fleet_verify.py`, `action.yml` | VERIFY-01, SEC-005 |
| C-CAMPAIGN-GATE | FOUNDATION | `scripts/run-campaign.sh` | ARCH-001, VAL-006, CAMPAIGN-01 |
| C-ARCHIVE-TIME | INDEPENDENT | `scripts/lib/fleet_run.py` | ARCHIVE-01, ARCHIVE-02 |
| C-NAMESPACE-DRIFT | INDEPENDENT | `scripts/lib/namespace.py`, `scripts/validate_*.py` | NAMESPACE-01, COLLECT-01 |
| C-LEDGER-RELOC | INDEPENDENT | `scripts/lib/mission_promotion.py`, `scripts/lib/mission_registry.py` | PROMO-002, READY-004 |
| C-HEADLESS-AUTH | INDEPENDENT | `scripts/run-mission-headless.sh`, `scripts/lib/adapter_preflight.py` | HEADLESS-01, HEADLESS-02, HEADLESS-03, PREFLIGHT-01 |
| C-DOC-DRIFT | INDEPENDENT | `SECURITY.md` | SEC-004 |
| C-LINT-GAPS | INDEPENDENT | `scripts/lib/skill_lint.py`, `scripts/registry_lint.py` | LINT-005, SEC-007, REG-003 |
| C-RECOVERY | INDEPENDENT | `scripts/lib/recovery_scan.py`, `scripts/stop_verify.py`, `scripts/lib/verify_findings.py` | RECOVERY-01, STOP-01, STOP-02, VERIFY-FINDINGS-01 |

---

## Findings

### SEC-001 — `install-community.sh` eval injection (P0 / critical)

| Field | Value |
|-------|-------|
| **severity** | P0 / critical |
| **category** | security |
| **problem** | `--execute` builds shell strings from unvalidated `--host` and `GSTACK_*` env overrides, then runs them through `eval`, enabling arbitrary command injection. |
| **evidence** | `scripts/install-community.sh:160` `eval "$cmd"`; `:91` interpolates `${GSTACK_REPO}` / `${GSTACK_CLONE_DIR}`; `:92` interpolates `${HOST}`. |
| **FIX** | Remove `eval`. Execute via argv arrays; allowlist `--host` to `cursor\|claude\|grok\|codex`; reject shell metacharacters in `GSTACK_*`. |
| **in-tree primitive** | List-form `subprocess` / bash argv arrays (same posture as `verify_sha_pin.py`). |
| **acceptance** | `HOST='; touch /tmp/pwned #' --execute` exits non-zero and does not create `/tmp/pwned`; legitimate gstack install still works. |
| **tag** | CODE |
| **lane** | A |

### SEC-002 — Reviewer `--run-id` path escape (P0 / critical)

| Field | Value |
|-------|-------|
| **severity** | P0 / critical |
| **category** | security |
| **problem** | `--run-id` / `FLEET_RUN_ID` is concatenated into `.fleet/runs/$run_id` without `RUN_ID_PATTERN` validation, so `../` escapes the runs directory and the bwrap writable bind targets an attacker-chosen path. |
| **evidence** | `scripts/run-sandboxed.sh:128` `run_id="$2"`; `:953` `reviewer_run_dir="$repo_root/.fleet/runs/$run_id"`. Contrast `scripts/lib/fleet_run.py` `RUN_ID_PATTERN`. |
| **FIX** | Reject `run_id` unless it matches `RUN_ID_PATTERN` (or at minimum reject `/`, `..`); assert resolved path is under `.fleet/runs/`. |
| **in-tree primitive** | `fleet_run.RUN_ID_PATTERN` / `parse_run_id()`. |
| **acceptance** | `--role reviewer --run-id '../../tmp/evil' -- echo ok` refuses before exec; valid RUN_ID still works. |
| **tag** | CODE |
| **lane** | A |

### SEC-003 — Linux bwrap reviewer keeps host network (P0 / high)

| Field | Value |
|-------|-------|
| **severity** | P0 / high |
| **category** | security |
| **problem** | Comments claim “Network is DROPPED” but the Linux `bwrap` path never passes `--unshare-net`, so a reviewer child retains host network (exfiltration path). |
| **evidence** | `scripts/run-sandboxed.sh:818` network-dropped comment; `:872` `exec "${cap_drop[@]}" bwrap \` with no `--unshare-net` through `:884`. |
| **FIX** | Add `--unshare-net` to the bwrap argv in `_exec_reviewer_sandbox`. |
| **in-tree primitive** | Existing narrowed-mount reviewer block; extend `tests/test_reviewer_sandbox.py`. |
| **acceptance** | Reviewer child cannot open outbound TCP under `--role reviewer` on Linux; tests assert `unshare-net` present. |
| **tag** | CODE+OPS |
| **lane** | A |

### SANDBOX-02 — Fallback reviewer sandbox is detect-only (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | security |
| **problem** | When neither `sandbox-exec` nor `bwrap` exists, reviewer role falls back to post-exec hash comparison that detects but does not prevent mutations. |
| **evidence** | `scripts/run-sandboxed.sh:887` fallback start; `:896` `cmp` after child already ran. |
| **FIX** | Fail closed for `--role reviewer` without a real sandbox binary unless `FLEET_SECURITY_OVERRIDE_ACK=1`. |
| **in-tree primitive** | `verify_reviewer_sandbox.py` kill-switch / ack pattern. |
| **acceptance** | Fallback-only hosts refuse reviewer exec by default; forced-fallback tests still cover detection. |
| **tag** | CODE+OPS |
| **lane** | A |

### VERIFY-01 — fleet-verify omits reviewer-sandbox layer (P1 / high)

| Field | Value |
|-------|-------|
| **severity** | P1 / high |
| **category** | architecture |
| **problem** | Published `fleet-verify` / `action.yml` omits the reviewer-sandbox manifest layer that `validate-all.sh` enforces. |
| **evidence** | `scripts/lib/fleet_verify.py:307-314` layer list has no reviewer-sandbox check; `scripts/validate-all.sh` runs `verify_reviewer_sandbox.py`. |
| **FIX** | Add `_check_reviewer_sandbox(run_dir)` calling `verify_reviewer_sandbox_manifest()`. |
| **in-tree primitive** | `scripts/lib/reviewer_sandbox.py`. |
| **acceptance** | `fleet-verify` FAIL on reviewer-attributed `kind: diff`; PASS on clean fixture. |
| **tag** | CODE |
| **lane** | A |

### SEC-005 — fleet-verify omits sha-pin layer (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | security |
| **problem** | Same parity gap: `fleet_verify.verify_layers()` never calls sha-pin, so the composite action is weaker than repo CI. |
| **evidence** | `scripts/lib/fleet_verify.py:307-314`; `scripts/validate-all.sh` sha-pin loop; `action.yml:28` only runs `fleet_verify.py`. |
| **FIX** | Add sha-pin layer via `lib.verify_sha_pin`. |
| **in-tree primitive** | `scripts/lib/verify_sha_pin.py`. |
| **acceptance** | Action fails when fixture pin is stale; passes when pin matches HEAD. |
| **tag** | CODE+OPS |
| **lane** | A |

### ARCH-001 — Campaign exec gate misses archived missions (P0 / high)

| Field | Value |
|-------|-------|
| **severity** | P0 / high |
| **category** | architecture |
| **problem** | Exec-time loader gates only `docs/exploratory/missions/<slug>/`, not `archive/` or `archived:true` registry rows. Hand-written `--campaign` YAML can invoke parked missions (e.g. `legacy-rebuild`) while author-time lint rejects them. |
| **evidence** | `scripts/run-campaign.sh:193-196` exploratory path probe only; `validate_mission` at `:226` accepts any `MISSION_DOCS` key including archived. |
| **FIX** | Reject `MISSIONS[mission]["archived"]`; treat `archive/<slug>/SKILL.md` as archived. |
| **in-tree primitive** | `fleet_registry.MISSIONS` + `registry_lint` archived check. |
| **acceptance** | Dry-run referencing `legacy-rebuild` exits non-zero before headless. |
| **tag** | CODE |
| **lane** | A |

### VAL-006 — `validate_mission` accepts archived registry rows (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | architecture |
| **problem** | Companion to ARCH-001: `mission in MISSION_DOCS` is too broad. |
| **evidence** | `scripts/run-campaign.sh:226`. |
| **FIX** | Allow only shipped ∪ exploratory-with-opt-in; deny archived unless new opt-in. |
| **acceptance** | Same as ARCH-001; shipped presets unchanged. |
| **tag** | CODE |
| **lane** | A |

### CAMPAIGN-01 — Blocked-halt swallows parse failures (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | bug |
| **problem** | Blocked-campaign halt still uses `|| true` on `parse_readiness`, allowing silent skip of the blocked gate on subprocess error. |
| **evidence** | `scripts/run-campaign.sh:424` ends with `|| true)`. |
| **FIX** | Remove `|| true`; fail campaign on parse error. |
| **acceptance** | Injected parse failure exits non-zero; `test_blocked_node_halts_campaign` still passes. |
| **tag** | CODE |
| **lane** | A |

### ARCHIVE-01 — `created_utc` ordering never enforced (P1 / high)

| Field | Value |
|-------|-------|
| **severity** | P1 / high |
| **category** | bug |
| **problem** | Manifest validator checks `created_utc` format only; never enforces that it precedes every file `mtime_utc`. |
| **evidence** | `scripts/lib/fleet_run.py:713` format-only check. |
| **FIX** | Add `_validate_created_precedes_files` in `validate_manifest_payload`. |
| **acceptance** | Manifest with `created_utc` later than any file mtime fails validation. |
| **tag** | CODE |
| **lane** | A |

### ARCHIVE-02 — `write_manifest` stamps `created_utc` at finalize (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | architecture |
| **problem** | Headless archive writer materializes artifacts then calls `write_manifest` with `_utc_now()`, so `created_utc` is finalize time. |
| **evidence** | `scripts/lib/fleet_run.py:625`. |
| **FIX** | Capture run-start at allocation; pass `created_utc=run_start` into `write_manifest`. |
| **acceptance** | Every `files[].mtime_utc >= created_utc` for headless archives. |
| **tag** | CODE |
| **lane** | A |

### NAMESPACE-01 — Namespace regex looser than `RUN_ID_PATTERN` (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | bug |
| **problem** | `namespace._RUN_ID_RE` accepts 1-char mission slugs that `fleet_run.RUN_ID_PATTERN` rejects. |
| **evidence** | `scripts/lib/namespace.py:15`. |
| **FIX** | Pin to `fleet_run.RUN_ID_PATTERN`. |
| **acceptance** | Drift test pins regexes equal; invalid short slugs rejected. |
| **tag** | CODE |
| **lane** | A |

### COLLECT-01 — Archive discovery filters disagree (P2 / medium)

| Field | Value |
|-------|-------|
| **severity** | P2 / medium |
| **category** | architecture |
| **problem** | `validate_run_archive` requires `RUN_ID_PATTERN` basenames; `validate_namespacing` accepts any dir with `manifest.json`. |
| **evidence** | `scripts/validate_run_archive.py:42` vs `scripts/validate_namespacing.py:21`. |
| **FIX** | Shared `collect_run_archives()` on `RUN_ID_PATTERN`. |
| **acceptance** | Both CLIs return the same directory set for a mixed `.fleet/runs/` tree. |
| **tag** | CODE |
| **lane** | A |

### PROMO-002 — Promotion ignores `FLEET_LEDGER_DIR` (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | bug |
| **problem** | `_canonical_registry_doc` hardcodes `docs/`, breaking promotion on docs-site repos using `.fleet/docs`. |
| **evidence** | `scripts/lib/mission_promotion.py:77`. |
| **FIX** | Use `ledger_dir()` from `mission_registry`. |
| **acceptance** | `assess_promotion()` finds docs under relocated ledger. |
| **tag** | CODE |
| **lane** | A |

### READY-004 — Readiness discovery precedence diverges (P2 / medium)

| Field | Value |
|-------|-------|
| **severity** | P2 / medium |
| **category** | architecture |
| **problem** | Campaign routing prefers newest mtime; promotion prefers canonical unkeyed file — same repo can disagree. |
| **evidence** | `mission_registry.resolve_readiness_file` vs `mission_promotion._promotion_readiness_path`. |
| **FIX** | Shared resolver: canonical-with-valid-outcome first, else newest keyed. |
| **acceptance** | Campaign edge eval and promotion agree on fixture with both docs. |
| **tag** | CODE |
| **lane** | A |

### RECOVERY-01 — Resume counter ignores table ledgers (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | bug |
| **problem** | `increment_resume_count` only rewrites pipe rows; table-format tasks silently no-op. |
| **evidence** | `scripts/lib/recovery_scan.py:377`. |
| **FIX** | Extend writer for markdown-table rows. |
| **acceptance** | Table ledger RESUME_COUNT increments; budget exhaustion escalates. |
| **tag** | CODE |
| **lane** | A |

### HEADLESS-01 — Auth probe fail-open (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | security |
| **problem** | Unsupported auth probe subcommand returns 0 and proceeds. |
| **evidence** | `scripts/run-mission-headless.sh:273-274`. |
| **FIX** | Fail closed (exit 3) unless `--skip-auth-check`. |
| **acceptance** | Missing probe refuses by default; skip flag still bypasses. |
| **tag** | CODE |
| **lane** | A |

### HEADLESS-02 — Grok has no auth probe / 5400s sink (P2 / medium)

| Field | Value |
|-------|-------|
| **severity** | P2 / medium |
| **category** | performance |
| **problem** | Grok auth-check returns 0 immediately; hung/unauth runs burn full default timeout. |
| **evidence** | `scripts/run-mission-headless.sh:261`. |
| **FIX** | Short grok smoke probe or lower default timeout for grok. |
| **acceptance** | Unauthenticated grok fails in <120s. |
| **tag** | CODE+OPS |
| **lane** | A |

### HEADLESS-03 — Archive emit failure non-fatal (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | ops |
| **problem** | Real headless archive emission failure is non-fatal; runtime may exit 0 with no audit trail. |
| **evidence** | `scripts/run-mission-headless.sh:227-228`. |
| **FIX** | Make emit failure fatal for real runs. |
| **acceptance** | Emit failure → non-zero headless exit. |
| **tag** | CODE+OPS |
| **lane** | A |

### PREFLIGHT-01 — Adapter auth check has no timeout (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | ops |
| **problem** | `adapter_preflight.check()` runs auth commands with no timeout. |
| **evidence** | `scripts/lib/adapter_preflight.py:127`. |
| **FIX** | Add `timeout=30` to `subprocess.run`. |
| **acceptance** | Hung check fails within 30s. |
| **tag** | CODE |
| **lane** | A |

### SEC-004 — SECURITY.md classifier drift (P2 / medium)

| Field | Value |
|-------|-------|
| **severity** | P2 / medium |
| **category** | other |
| **problem** | Doc claims `curl\|bash`, `find / -delete`, `dd of=/dev/sda`, `chmod -R 000 /` classify as ALLOW; classifier now DENY/ASK. |
| **evidence** | `SECURITY.md:109` vs `run-sandboxed.sh` DENY/ASK rules. |
| **FIX** | Rewrite residual-risk section to match classifier + tests. |
| **acceptance** | No ALLOW example that tests prove DENY/ASK. |
| **tag** | CODE |
| **lane** | A |

### SEC-003-CI — Floating GitHub Action tags (P1 / medium)

| Field | Value |
|-------|-------|
| **severity** | P1 / medium |
| **category** | security |
| **problem** | CI and published action use `@v4`/`@v5` tags, not immutable SHAs. |
| **evidence** | `action.yml:15` `actions/setup-python@v5`; `.github/workflows/ci.yml:16` `actions/checkout@v4`. |
| **FIX** | Pin every `uses:` to full commit SHAs. |
| **acceptance** | No `@vN` tags remain; CI green. |
| **tag** | CODE+OPS |
| **lane** | B (supply-chain pin choice / Dependabot workflow — draft both pin strategy vs vendor-local) |

### SEC-006 — Community installer uses `skills@latest` (P2 / medium)

| Field | Value |
|-------|-------|
| **severity** | P2 / medium |
| **category** | security |
| **problem** | `mattpocock` bundle uses `npx skills@latest` while fleet skills pin `skills@1.5.12`. |
| **evidence** | `scripts/install-community.sh:126`. |
| **FIX** | Pin to same `SKILLS_CLI` constant as `install-skills.sh`. |
| **acceptance** | Dry-run shows pinned version. |
| **tag** | CODE |
| **lane** | A |

### SEC-007 — Registry-lint kill-switch not fail-closed (P2 / medium)

| Field | Value |
|-------|-------|
| **severity** | P2 / medium |
| **category** | security |
| **problem** | `FLEET_DISABLE_REGISTRY_LINT` alone exits 0, dropping supply-chain pin enforcement. |
| **evidence** | `scripts/registry_lint.py:12`. |
| **FIX** | Require `FLEET_SECURITY_OVERRIDE_ACK` (match sha-pin). |
| **acceptance** | Disable without ack fails closed in CI. |
| **tag** | CODE+OPS |
| **lane** | A |

### REG-003 — Exploratory SKILLs missing registry rows (P2 / medium)

| Field | Value |
|-------|-------|
| **severity** | P2 / medium |
| **category** | architecture |
| **problem** | `scaffold-align`, `contract-first-build`, `agents-layer` exist on disk but not in `MISSIONS`. |
| **evidence** | On-disk dirs under `docs/exploratory/missions/`; grep of `fleet_registry.py` returns no keys. |
| **FIX** | Add registry rows OR remove SKILL trees; lint exploratory-on-disk ⊆ registry. |
| **acceptance** | `validate-all` includes exploratory ⊆ registry check. |
| **tag** | CODE |
| **lane** | A |

### LINT-005 — Mission lint skips name==dir (P2 / low)

| Field | Value |
|-------|-------|
| **severity** | P2 / low |
| **category** | architecture |
| **problem** | `lint_mission` does not enforce `frontmatter.name == directory` (adapters do). |
| **evidence** | `scripts/lib/skill_lint.py:170-177`. |
| **FIX** | Share `_assert_name_matches_dir` with mission lint. |
| **acceptance** | Synthetic mismatch fails lint. |
| **tag** | CODE |
| **lane** | A |

### STOP-01 — Stop-verify fail-open on bad repo (P2 / medium)

| Field | Value |
|-------|-------|
| **severity** | P2 / medium |
| **category** | security |
| **problem** | Missing `--repo` ALLOWs session termination, silently disabling evidence gate. |
| **evidence** | `scripts/stop_verify.py:209`. |
| **FIX** | Opt-in strict BLOCK via `FLEET_STOP_VERIFY_STRICT=1`. |
| **acceptance** | Strict mode blocks; default unchanged. |
| **tag** | CODE+OPS |
| **lane** | A |

### STOP-02 — Stdin timeout unused (P3 / low)

| Field | Value |
|-------|-------|
| **severity** | P3 / low |
| **category** | bug |
| **problem** | `_read_hook_input(timeout_sec=2.0)` calls blocking `sys.stdin.read()` with no timeout. |
| **evidence** | `scripts/stop_verify.py:64` (signature advertises timeout). |
| **FIX** | Apply `select` deadline or remove dead parameter. |
| **acceptance** | Blocked stdin returns within timeout. |
| **tag** | CODE |
| **lane** | A |

### VERIFY-FINDINGS-01 — Findings loader uncapped (P2 / medium)

| Field | Value |
|-------|-------|
| **severity** | P2 / medium |
| **category** | security |
| **problem** | `load_findings_doc` slurps entire file; source verification caps at 8 MB. |
| **evidence** | `scripts/lib/verify_findings.py:65`. |
| **FIX** | Cap read (~1–8 MB) mirroring `MAX_SOURCE_BYTES`. |
| **acceptance** | Oversized findings doc returns structured error, no OOM. |
| **tag** | CODE |
| **lane** | A |

### CAMP-007 — Dry-run metric pre-seed is global (P3 / low)

| Field | Value |
|-------|-------|
| **severity** | P3 / low |
| **category** | bug |
| **problem** | Dry-run seeds all mission metrics into one flat dict; `--probe-fail` injects `findings_open=1` globally. |
| **evidence** | `scripts/run-campaign.sh` dry_run_next_node block (~253–271). |
| **FIX** | Seed only current node's mission metrics. |
| **acceptance** | `--probe-fail` on repo-health does not inject audit-only metrics. |
| **tag** | CODE |
| **lane** | A |

---

## Hot-file collision map

| File | Findings | Max parallel |
|------|----------|--------------|
| `scripts/install-community.sh` | SEC-001, SEC-006 | 1 |
| `scripts/run-sandboxed.sh` | SEC-002, SEC-003, SANDBOX-02 | 1 |
| `scripts/lib/fleet_verify.py` | VERIFY-01, SEC-005 | 1 |
| `scripts/run-campaign.sh` | ARCH-001, VAL-006, CAMPAIGN-01, CAMP-007 | 1 |
| `scripts/lib/fleet_run.py` | ARCHIVE-01, ARCHIVE-02 | 1 |
| `scripts/run-mission-headless.sh` | HEADLESS-01, HEADLESS-02, HEADLESS-03 | 1 |
| `scripts/lib/mission_promotion.py` | PROMO-002, READY-004 | 1 |
| `scripts/lib/namespace.py` + validate CLIs | NAMESPACE-01, COLLECT-01 | 1 |
| `scripts/lib/recovery_scan.py` | RECOVERY-01 | 1 |
| `scripts/stop_verify.py` | STOP-01, STOP-02 | 1 |
| `SECURITY.md` | SEC-004 | 1 |
| `action.yml` + `.github/workflows/*` | SEC-003-CI | 1 (Lane B) |

---

## Validated strengths (do-not-touch)

1. **Blast-radius classifier** — structural token parsing, pipe backstop, argv preservation; extensive `test_sandbox_guard.py` / `test_adversarial_fixes.py`.
2. **Credential scrub** — `env -i` allowlist + credential-shaped var drop before sandboxed child.
3. **YOLO / external-repo RCE gate** — mechanical acknowledgement in headless + campaign.
4. **SHA-pin argv hardening** — branch regex + `rev-parse --end-of-options`.
5. **Security-knob fail-closed** for sha-pin / reviewer-sandbox (require ack).
6. **Findings path containment** — `relative_to(repo_root)` before read.
7. **Lock steal CAS** — tombstone rename + byte-identity verify.
8. **Independent-review integrity** — rejects byte-identical findings across producers.
9. **Trace-before-ledger** + secret/path hygiene at emit.
10. **Campaign loop guards** — revisit budget, step cap, exploratory opt-in (shipped path).
11. **Version hygiene** — VERSION / pyproject / plugin / README badge aligned at 0.3.0.
12. **Bwrap mount narrowing** — ro system + ro repo + rw run-dir only (network gap is SEC-003, not mount).

---

## Schema-verified counterpart

`.fleet/runs/20260708T184204Z-adversarial-review-and-fix-c6c486/p0-review-findings.json`

## Skeptic freeze (P0-SKEPTIC)

**PHASE=REVIEW_FROZEN** after code-grounded stress of every finding.

### CONFIRMED (21) — Phase 1 spec

| ID | Lane | Notes |
|----|------|-------|
| SEC-001 | A | eval injection — critical |
| SEC-002 | A | run-id path escape |
| SEC-003 | A | bwrap missing --unshare-net |
| SEC-004 | B | Actions SHA-pin — draft-both / human-gate |
| ARCH-001 | A | fleet-verify missing layers |
| ARCH-002 | A | campaign archived-mission hole |
| BUG-001 | A | created_utc ordering unenforced |
| SEC-005 | B | fallback sandbox — narrowed low/ask |
| SEC-007 | A | SECURITY.md drift |
| SEC-008 | A | skills@latest pin |
| SEC-009 | B | registry-lint kill-switch — narrowed ask |
| BUG-002 | A | campaign \|\| true swallow |
| BUG-003 | A | namespace regex drift |
| BUG-004 | A | resume count table rows |
| ARCH-003 | A | promotion ledger_dir |
| ARCH-004 | B | exploratory registry gap — narrowed ask |
| OPS-001 | A | real-run archive emit fatal (narrowed) |
| OPS-002 | A | preflight timeout |
| ARCH-005 | B | archive collect mismatch — narrowed ask |
| SEC-010 | B | stop-verify fail-open — opt-in strict |
| SEC-011 | A | findings doc byte cap |

### REFUTED / DO-NOT-FIX (1)

| ID | Reason |
|----|--------|
| SEC-006 | Intentional version-tolerant auth probe; bounded by timeout. Fail-closed would break validated compatibility. |

### Clusters (confirmed)

1. **FOUNDATION C-SHELL** — SEC-001, SEC-002, SEC-003, SEC-005, SEC-007, SEC-008 — install-community + run-sandboxed + SECURITY.md
2. **FOUNDATION C-VERIFY** — SEC-004, ARCH-001, BUG-001, BUG-003, ARCH-005, SEC-009, SEC-010, SEC-011 — fleet-verify/action/archive/stop-verify
3. **FOUNDATION C-CAMPAIGN** — ARCH-002, ARCH-003, ARCH-004, BUG-002 — campaign/registry/promotion
4. **INDEPENDENT C-OPS** — OPS-001, OPS-002, BUG-004 — headless/preflight/recovery

Refuted findings are never fixed.
