# gstack → autonomous-fleet mission research

**Date:** 2026-06-27  
**Source:** shallow clone of [garrytan/gstack](https://github.com/garrytan/gstack) to scratch  
(`find … -maxdepth 2 -name SKILL.md` → **54** top-level skills; full inventory in scratch `gstack-deepdive.log`)

## Executive summary

gstack is a **Claude Code skill suite** built around three pillars: (1) a persistent
headless browser daemon (`$B` / `browse`) for sub-second QA and dogfooding, (2) a
**virtual specialist team** invoked as slash skills (`/office-hours`, `/plan-ceo-review`,
`/qa`, `/cso`, `/ship`, …), and (3) **prose chaining** — skills explicitly call the next
skill in sequence rather than a file-based coordinator ledger.

autonomous-fleet is the inverse emphasis: **tool-agnostic engine**, **worktree-isolated
roles** (`@codex` build, fresh `@claude` review), **frozen ledgers** on disk, and
**fleet-outcome** as the ship contract. The high-value translation is not porting gstack
SKILL bodies verbatim, but **distilling gstack's specialist flows into fleet missions**
with frozen artifacts, EVID-grade repros, and promotion gates.

This pass implements **all six** candidate missions as exploratory skills under
`docs/exploratory/missions/`.

## gstack architecture (observed)

| Layer | What gstack does | Fleet analogue |
|-------|------------------|----------------|
| **Slash skills** | 54+ `SKILL.md` dirs; tmpl-generated; preamble bash probes session/branch | Mission `SKILL.md` + adapter primitives |
| **Virtual team** | CEO / design / eng / DX plan reviews; autoplan chains them with auto-decisions | `ROLE PIPELINE` + frozen spec before build |
| **Browser** | Bun-compiled daemon, `$B snapshot`, persistent cookies, ~100ms commands | Optional `browse` / Playwright worker; EVID screenshots in ledger |
| **Plan mode** | `office-hours` → design doc; `spec` five phases; `autoplan` runs full review gauntlet | `product-framing` mission freezes `docs/product-spec.md` |
| **Safety** | `careful`, `freeze`, `guard`, `cso` (daily vs comprehensive, confidence gates) | `security-cso-audit` + skeptic lane |
| **Ship loop** | `qa` / `qa-only` + `review` + `ship` + `health` scorecard | `browser-qa-fix` with QA-INDEX + health delta |
| **Chaining** | `benefits-from: [office-hours]` in frontmatter; skills say "use before X" | `fleet-program` campaigns; Deferred missions table |

Key docs read: `ARCHITECTURE.md` (daemon browser, security model), `ETHOS.md`,
`BROWSER.md`, `AGENTS.md`, root `SKILL.md` router.

Representative skills deep-read: `office-hours`, `autoplan`, `qa`, `qa-only`, `browse`,
`cso`, `plan-ceo-review`, `plan-eng-review`, `plan-design-review`, `design-review`,
`investigate`, `document-generate`, `document-release`, `health`, `benchmark`,
`design-html`, `ship`, `review`, `spec`, `devex-review`, `plan-devex-review`,
`land-and-deploy`, `canary`, `retro`, `learn`.

## gstack vs fleet contrast

| Dimension | gstack | autonomous-fleet |
|-----------|--------|-------------------|
| Orchestration | Single Claude session + slash skills | Coordinator + adapter + worktrees |
| Truth | Session prose + `~/.gstack/` sidecars | Repo `docs/*-progress.md` + frozen INDEX |
| Review | Interactive AskUserQuestion gates | Build-blind cross-vendor reviewer |
| Browser | Native `$B` daemon (required for QA skills) | Optional community `browse` / Playwright |
| Promotion | Skill install via `npx skills add` | Exploratory → shipped triple (progress + readiness + archive) |

## Candidate missions (6)

### 1. `product-framing` ✅ **implemented**

| gstack source | Fleet mapping |
|---------------|---------------|
| `office-hours`, `autoplan`, `plan-ceo-review`, `plan-eng-review`, `plan-design-review`, `spec` | @claude: forcing questions + review gauntlet → **frozen** `docs/product-spec.md` + `docs/framing-index.md` |

**Why meaningful:** Existing missions assume a scoped goal (`doc-sync`, `test-coverage`,
`adversarial-review-and-fix`). gstack's pre-code pipeline (YC office hours → multi-lens
plan review) has no fleet equivalent; `take-product-to-completion` is Tier 3 and
post-stall, not pre-build framing.

### 2. `browser-qa-fix` ✅ **implemented**

| gstack source | Fleet mapping |
|---------------|---------------|
| `qa`, `qa-only`, `browse`, `design-review` (sampling) | @grok: browser-driven repro + fix; @claude: QA plan, blind review; ledger `docs/qa-progress.md` + frozen `docs/qa-index.md` with EVID paths |

**Why meaningful:** `adversarial-review-and-fix` is code-grounded, not user-journey grounded.
gstack `/qa` produces health scores and screenshot evidence from real browser steps — a
gap for web products before ship.

### 3. `security-cso-audit` ✅ **implemented**

| gstack source | Fleet mapping |
|---------------|---------------|
| `cso`, `investigate`, `careful` | @claude: CSO audit + skeptic; @codex: remediate; frozen `docs/security-findings.md` + CLOSE-INDEX |

**Why meaningful:** `adversarial-review-and-fix` covers general architecture; gstack `/cso`
adds infrastructure-first passes (secrets archaeology, CI/CD, LLM/skill supply chain, OWASP,
STRIDE, daily vs comprehensive confidence gates) as a dedicated mission shape.

### 4. `devex-audit` ✅ **implemented**

| gstack source | Fleet mapping |
|---------------|---------------|
| `devex-review`, `plan-devex-review`, `document-generate` | @claude: live DX walkthrough + scorecard → frozen `docs/devex-scorecard.md` + `docs/devex-gaps-index.md` |

**Why meaningful:** gstack `/devex-review` and `/plan-devex-review` time real onboarding
flows and score friction; fleet `doc-sync` fixes drift but does not produce a ranked DX
scorecard with evidence screenshots and doc-generation gaps before a release push.

### 5. `release-document` ✅ **implemented**

| gstack source | Fleet mapping |
|---------------|---------------|
| `document-release`, `ship`, `land-and-deploy`, `canary` | @claude: post-ship doc sweep + deploy checklist → frozen `docs/release-doc-checklist.md` + `docs/release-doc-readiness.md` |

**Why meaningful:** gstack `/document-release` closes the loop after `/ship` — changelog,
user-facing docs, deploy verification, canary notes. Fleet missions stop at merge; this
mission captures the documentation tail as a frozen checklist with fleet-outcome.

### 6. `incident-investigate` ✅ **implemented**

| gstack source | Fleet mapping |
|---------------|---------------|
| `investigate`, `retro`, `learn` | @claude: root-cause analysis; @codex: regression test; frozen `docs/incident-rca.md` + `docs/incident-close-index.md` |

**Why meaningful:** gstack `/investigate` plus `/retro` and `/learn` turn production
incidents into durable RCA docs and regression tests. `bug-batch` fixes listed bugs but
does not mandate RCA structure or learnings persistence.

## Implementation decision

Ship **all six** as exploratory missions under `docs/exploratory/missions/`. They cover
gstack's specialist clusters (pre-build framing, browser QA, security CSO, developer
experience, post-ship documentation, incident RCA) without overlapping the three shipped
missions. Promotion to `skills/` requires the standard triple: progress doc, readiness
doc with fleet-outcome, and external run archive.

## Evidence pointer

Scratch deep-dive log: `{SCRATCH}/gstack-deepdive.log` (54 skills, root docs, key SKILL excerpts).