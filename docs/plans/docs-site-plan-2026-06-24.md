# Plan — User-facing docs site for `autonomous-fleet`

Author: planning session with Mogra agent, 2026-06-24.

Status: **PROPOSAL** — to be reviewed, amended, and accepted before implementation.

Amended 2026-06-24: refreshed against `main` after PR #41. The four e2553ac audit
findings are FIXED (not open); §7 rewritten, mutation count 29→32, docs count
~45→~33, `self.md` reference corrected. The campaign count (3 active presets) was
verified correct and left unchanged.

This plan covers **what to write**, **how it's organised**, **how users navigate
it**, and **what's deferred**. Implementation is broken into three independently
shippable batches; each batch is its own PR with its own readiness doc.

---

# 1. Why this exists

## 1.1 Problem statement

A new user landing on `github.com/ravidsrk/autonomous-fleet` today gets:

- **`README.md` (439 lines)** — strong landing-page-style intro, install steps,
  mission overview, architecture sketch. Optimised for scanning, not reading.
- **`AGENTS.md` (113 lines)** — repo conventions for AI agents. Not user docs.
- **`CONTRIBUTING.md` (~90 lines)** — distillation discipline. Contributor docs.
- **12 × `skills/*/README.md`** — every one is the **same 33-line stub**
  ("see SKILL.md"). Zero user-facing value.
- **`docs/` (~33 markdown files)** — almost entirely internal artefacts:
  `*-readiness.md`, `*-progress.md`, audits, plans, research notes. Useful as
  evidence trail; opaque to a new user.
- **`docs/external-dogfood/vibe-kanban-integration.md`** — the lone outward
  integration doc; its scope was corrected in PR #41 to describe the trace
  CONTRACT plus a rollout-in-progress (in production only one `T-FINAL` event is
  wired today).

After the README pitch, the user falls off a cliff. There is no "the book" — no
concepts page, no run-archive walkthrough, no troubleshooting, no glossary, no
extending guide, no CLI reference. The `SKILL.md` files are agent-facing
prompts; they are not user documentation.

## 1.2 Goal of this plan

Ship a **proper docs site** that a developer evaluating or adopting
`autonomous-fleet` can read end-to-end and walk away knowing:

1. What the framework is and isn't
2. How to install it on their own repo
3. How to run their first mission
4. How the engine, substrate, and ledger work conceptually
5. What every shipped mission does, what it expects, what it produces
6. How to extend it (new mission, new adapter)
7. Where to look when something goes wrong
8. Every schema, every CLI flag, every term — as reference

## 1.3 Non-goals

- ❌ **No rewrite of `README.md`.** It works for the landing-page job.
- ❌ **No changes to `SKILL.md` files.** They are agent prompts, different
  audience, not human docs.
- ❌ **No changes to `docs/exploratory/`, `docs/external-dogfood/`, or the
  internal `*-readiness.md` / `*-progress.md` files.** Those are evidence
  trail and must stay where they are.
- ❌ **No marketing copy in the guide.** The guide is for people who already
  clicked through and want depth.
- ❌ **No interactive playground / runnable demos.** Future scope.
- ❌ **No translation / i18n.** Future scope.

---

# 2. The navigation question — answered

## 2.1 Options considered

| Option | Cost | Pros | Cons | Verdict |
|---|---|---|---|---|
| **A. Pure markdown in `docs/guide/`** | $0, zero infra | Renders on GitHub, IDE preview, terminal, agent context. No build. Same PR as code. | No full-text search. GitHub markdown rendering is "fine, not great". | 🟢 Recommended start |
| **B. GitHub Pages + Jekyll/MkDocs** | ~1 day setup | Free hosting on `ravidsrk.github.io/autonomous-fleet`. Real sidebar nav. | Adds a build pipeline. Jekyll is fading. | 🟡 Skip |
| **C. Astro Starlight on Cloudflare Pages** | ~2 hours setup | Modern OSS-docs standard (Bun, Drizzle, Hono, Biome). Looks gorgeous. Search, dark mode, multi-version. Custom domain. | Adds a build pipeline, new repo subdir, deployment surface. | 🟢 Recommended Stage 2 |
| **D. GitHub Wiki** | $0 | Native to GitHub. | Separate repo. No PR review. Out of fashion. | 🔴 Don't |

## 2.2 The decision — Option A now, Starlight-ready

**Stage 1 — Pure markdown in `docs/guide/` (this plan):**

- Docs *exist* on day one — no build pipeline blocking the writing
- Lives in the same PR as the code it documents → CI gates docs against code
- Renders correctly in any context: GitHub web, IDE preview, `cat` in a
  terminal, an AI agent reading it as context
- Reversible — every modern docs framework (Starlight, VitePress, Mintlify,
  Docusaurus) reads markdown, so migration is a config file, not a rewrite

**Stage 2 — Flip on Starlight when traffic justifies it:**

- Triggered by: "we have N readers / week and need search" or "the framework
  is getting picked up externally and a real URL matters"
- Estimated 2-hour flip: `npm create astro@latest -- --template starlight`,
  point its `srcDir` at `docs/guide/`, deploy to Cloudflare Pages, custom
  domain at `autonomous-fleet.dev`
- **Pre-condition:** Stage 1 chapters are written with frontmatter Starlight
  expects (`title`, `description`, `sidebar_order`) as harmless top-of-file
  comments, and use only portable markdown (no GitHub-only `[!NOTE]`
  callouts in body text — plain blockquotes that render everywhere)

This plan covers **Stage 1 only**. Stage 2 is a follow-up plan after Stage 1
ships and we have signal on whether the docs are being read.

## 2.3 Navigation mechanics in Stage 1

Four navigation surfaces, all pure markdown:

**Surface 1 — Index page `docs/guide/README.md`** (the book's homepage):

```markdown
# autonomous-fleet — The Guide

## 🚀 Get started
- [Quickstart](01-quickstart.md) — your first PR in 10 minutes
- [Installation](02-installation.md) — full setup across all 4 runtimes
- [Your first mission](03-your-first-mission.md) — running doc-sync end-to-end

## 🧠 Concepts
- [Mental model](04-mental-model.md) — what a "run" actually is
- [Missions vs campaigns](05-missions-vs-campaigns.md) — when to chain
- [The engine](06-the-engine.md) — primitives, ledger, frozen DAG
- [The substrate](07-the-substrate.md) — 4-layer verification
- [Roles and blindness](08-roles-and-blindness.md) — why review is structural

## 🛠️ How-to
- [Mission catalog](09-mission-catalog.md)
- [Campaigns](10-campaigns.md)
- [Strict mode](11-strict-mode.md)
- [Safety and secrets](12-safety-and-secrets.md)
- [Extending](13-extending.md)
- [Troubleshooting](14-troubleshooting.md)

## 📚 Reference
- [Run-archive anatomy](15-run-archive.md)
- [Trace schema (v1)](16-trace-schema.md)
- [fleet-outcome schema](17-fleet-outcome-schema.md)
- [CLI reference](18-cli-reference.md)
- [FAQ](19-faq.md)
- [Glossary](20-glossary.md)
```

**Surface 2 — Footer nav on every chapter:**

```markdown
---
← [Previous: The Engine](06-the-engine.md) ·
[📖 Guide Index](README.md) ·
[Next: Roles and Blindness →](08-roles-and-blindness.md)
```

**Surface 3 — "On this page" anchor list at the top of each chapter** (GitHub
auto-renders heading anchors):

```markdown
**On this page:** [Concept](#concept) · [Example](#example) · [Edge cases](#edge-cases)
```

**Surface 4 — Cross-references throughout** (e.g. the engine chapter links to
the trace-schema reference, mission-catalog links to run-archive anatomy, etc.)

**Surface 5 — Entry from `README.md`** — add a prominent

```markdown
> 📖 **New here?** Read the [Guide](docs/guide/README.md) — a structured walk
> through every concept, mission, and reference.
```

block right under the install section.

---

# 3. The chapters — full table of contents with scope

20 chapters across 4 tiers. Each entry below specifies **target length**,
**audience signal** (who reads this and why), **scope boundary** (what's in,
what's out), and **dependencies** (what the reader needs to have read first).

## 3.1 Tier 1 — Get Started

> Read in order, ~30 min total. Goal: a new user has a green PR in their own
> repo by the end of chapter 3.

### Chapter 01 — Quickstart

- **Length:** ~200 lines
- **Audience:** First-time visitor, evaluating in 10 minutes
- **In scope:** 5-step install + first mission + see the PR. Single runtime
  (Claude Code, the most-supported). No campaign, no concepts.
- **Out of scope:** Multi-runtime, headless mode, strict mode, internals
- **Depends on:** Nothing
- **Anchors:**
  1. Prerequisites (Node, git, gh, one supported agent)
  2. Install (the one `npx skills add` command)
  3. Configure (`/setup-autonomous-fleet`)
  4. Run (`fix our README`)
  5. What just happened (PR link + a paragraph)
  6. Next: read the [Mental model](04-mental-model.md) chapter

### Chapter 02 — Installation

- **Length:** ~400 lines
- **Audience:** Someone past quickstart, picking the right runtime for real
- **In scope:** Install across **all four runtimes** (Claude Code, Codex, Grok,
  Orca); auth requirements for each; headless CLI auth for campaigns;
  optional `container-use` for sandboxed worker placement; `.gitignore`
  expectations; verifying install
- **Out of scope:** Setup wizard internals (covered in [Extending](13-extending.md))
- **Depends on:** Quickstart
- **Anchors:**
  1. Prerequisite matrix (Node, git, gh, per-runtime CLI)
  2. Install (all skills vs targeted install vs `--skill '*'`)
  3. Per-runtime setup — Claude Code (longest, most-supported), Codex, Grok,
     Orca
  4. Optional: `container-use` for sandboxed workers
  5. Headless mode auth (only if you'll use `run-campaign.sh`)
  6. Verifying install (running `/setup-autonomous-fleet`, expected output)
  7. Where things live (`.agents/skills/` is gitignored; `skills-lock.json`
     is committed)

### Chapter 03 — Your first mission

- **Length:** ~500 lines
- **Audience:** Reader who wants to *understand what a run feels like* before
  trusting it on a real repo
- **In scope:** Walk through `doc-sync` end-to-end on a tiny example repo,
  with annotated output of what the agent is doing at each step, what files
  appear in `.fleet/runs/<id>/`, and what the PR looks like
- **Out of scope:** Internals of how the engine routes work (chapter 06)
- **Depends on:** Quickstart, Installation
- **Anchors:**
  1. The example repo (a 30-file dummy repo with deliberately-stale docs)
  2. The kickoff — `/doc-sync update the docs to match the code`
  3. The plan file — what gets written, what to look for, when to abort
  4. The workers spawn — terminal output, what's happening
  5. The PRs appear — the GitHub view, the readiness doc
  6. The run-archive — `.fleet/runs/<id>/`, every file with one-line purpose
  7. What "done" means — `fleet-outcome.yaml`, what fields to check

## 3.2 Tier 2 — Concepts

> Read when you want to understand *why*. ~90 min total. Goal: a reader
> finishing tier 2 can explain the framework to a colleague.

### Chapter 04 — Mental model

- **Length:** ~400 lines
- **Audience:** Reader who's done the quickstart and asks "wait, what is this
  actually doing?"
- **In scope:** What a "run" is. What "the ledger" is. Why workers are spawned
  in separate terminals. Why the reviewer is build-blind. Why everything is
  one PR per unit instead of one PR per run.
- **Out of scope:** Implementation details — those are chapter 06
- **Depends on:** Chapter 03
- **Anchors:**
  1. A run is a frozen plan + a worker fleet + an audit trail
  2. The ledger is a directory of files, not a database
  3. Workers are processes, not threads — terminal separation is the
     blind-spot defence
  4. PRs are the unit of work — never one giant blob
  5. The framework is the protocol; the agents are interchangeable
  6. Cross-references to chapters 05–08

### Chapter 05 — Missions vs campaigns

- **Length:** ~350 lines
- **Audience:** Reader deciding whether to invoke one mission or chain
  several
- **In scope:** What a mission is (the unit). What a campaign is (a DAG of
  missions with verification gates between nodes). When to use each. The
  three shipped campaigns (`repo-health`, `ship-with-proof`, `quality-gate`)
  and what they're for. How conditional gates work.
- **Out of scope:** Writing a custom campaign — that's chapter 10
- **Depends on:** Chapter 04
- **Anchors:**
  1. Mission = one discrete engineering job
  2. Campaign = a DAG of missions with hard gates
  3. The shipped campaigns and the problem each solves
  4. When you should chain vs run sequentially vs not chain at all
  5. The "one mission per repo at a time" rule (and why)
  6. Where conditional gates live (`fleet-outcome` from the previous node)

### Chapter 06 — The engine

- **Length:** ~600 lines (the densest chapter)
- **Audience:** Reader who wants to know how the sausage is made
- **In scope:** The 11 primitives (DISPATCH, SPAWN_WORKER, INSPECT, SYNC,
  WAIT, MERGE, FREEZE, GOAL_BLOCKED, COMMIT, ABORT, T-FINAL). The frozen DAG.
  The file-based ledger. The coordinator/adapter split. Signal reconciliation.
  Anti-flap. Evidence-hash. The plan/DAG validation gate. Why nothing is
  auto-emitted (vs explicitly called). Why "trace first, ledger second" is
  the doctrine, now enforced at the reference integration in `write_manifest`
  (emit precedes the manifest write, PR #41).
- **Out of scope:** The substrate (4-layer verification) — that's chapter 07
- **Depends on:** Chapter 04
- **Anchors:**
  1. Primitives — what each one does, what an adapter must implement
  2. The ledger directory layout
  3. Coordinator vs adapter — who decides, who acts
  4. Signal reconciliation — why a single poll isn't a decision
  5. Anti-flap — why the same primitive can't fire twice in succession
  6. Evidence-hash — how the run-archive proves the file was unmodified
  7. Plan/DAG validation — what the pre-flight check rejects
  8. Cross-reference to the [Trace schema](16-trace-schema.md) for the
     event ledger format

### Chapter 07 — The substrate (4-layer verification)

- **Length:** ~550 lines
- **Audience:** Reader who wants to know how the framework catches bad work
- **In scope:** The four layers (1: schema-enforced findings, 2: stop-verify
  hook, 3: blind-fix mechanical guard, 4: mutation gate). What each catches.
  How they compose. The kill switches. Where the mutation manifest lives
  and what each mutation pins. Why mutation testing matters more than line
  coverage.
- **Out of scope:** Strict-mode opt-in details — that's chapter 11
- **Depends on:** Chapter 06
- **Anchors:**
  1. Layer 1 — findings schema (`fleet-review-findings.schema.json`)
  2. Layer 2 — stop-verify hook (Claude Code adapter)
  3. Layer 3 — blind-fix mechanical guard (mtime ordering via manifest)
  4. Layer 4 — mutation gate (`tests/mutations.yaml`, 32 mutations today)
  5. How layers compose (a finding caught at L1 never reaches L2; L3 only
     fires after L2 passes; L4 catches regressions across all three)
  6. Kill switches (`substrate-disable-knobs.md` reference)
  7. Why mutation testing > coverage

### Chapter 08 — Roles and blindness

- **Length:** ~400 lines
- **Audience:** Reader who wonders why the framework is so insistent about
  multi-vendor agents
- **In scope:** The builder/reviewer/integrator role topology. The Aula run
  origin story (Stage-9 finding). The "fresh terminal" rule. Cross-vendor
  blind-spot diversity. Single-vendor mode and its honest trade-off. The
  design-mission exception (`@grok` for `design-integration` and
  `landing-page-convergence`).
- **Out of scope:** Implementation — covered in adapter SKILL.md files
- **Depends on:** Chapter 06
- **Anchors:**
  1. Three roles, three terminals, three (usually) model families
  2. Build-blindness is structural, not instructed
  3. The Aula run — what happened, what changed
  4. Single-vendor mode — what you lose, what's still enforced
  5. The design-mission exception

## 3.3 Tier 3 — How-to guides

> Read when you need to do a specific thing. ~120 min if read end-to-end;
> usually consulted by chapter.

### Chapter 09 — Mission catalog

- **Length:** ~700 lines (the longest chapter, one section per mission)
- **Audience:** Reader picking the right mission for a job
- **In scope:** Every shipped mission (`doc-sync`, `test-coverage`,
  `adversarial-review-and-fix`) with **the same template** for each: what
  it does, when to use it, input contract, output contract, typical PRs it
  produces, edge cases, failure modes, example invocations. Then a short
  section per exploratory mission explaining what it would do if shipped
  and what's missing for promotion.
- **Out of scope:** How to add a new mission — that's chapter 13
- **Depends on:** Chapter 05
- **Anchors:** One per mission, plus the exploratory roster at the end

### Chapter 10 — Campaigns

- **Length:** ~500 lines
- **Audience:** Reader chaining missions for repeated repo-health passes
- **In scope:** The three shipped presets in depth. Writing a custom campaign
  YAML (the schema, the gates, the conditional branches). `--dry-run` output.
  The headless mode caveat (the auth requirement, the validation status).
  How to read `composition-e2e-audit.md` to understand what the campaign
  actually exercises.
- **Out of scope:** Adding a new preset to the repo — that's a contributor
  task, lives in CONTRIBUTING.md
- **Depends on:** Chapters 05, 09
- **Anchors:**
  1. The three presets — every flag, every gate
  2. Custom campaign YAML — schema with annotated example
  3. Dry-run mode and how to read the plan
  4. Headless mode auth + the current "not fully validated" caveat
  5. Cross-reference to `composition-e2e-audit.md`

### Chapter 11 — Strict mode

- **Length:** ~300 lines
- **Audience:** Operator who wants disk-level enforcement, not just prompt-
  level discipline
- **In scope:** What strict mode enforces (today: Claude Code only — exit
  non-zero if `unverified_assumptions > 0` at run end). How to opt in.
  How to opt back out. What it changes in the adapter's hook config. What
  it does NOT enforce yet.
- **Out of scope:** Adding strict mode to a new adapter — that's chapter 13
- **Depends on:** Chapter 07
- **Anchors:** Verbatim what's in
  `skills/autonomous-fleet-core/references/strict-mode.md`, plus a "how to
  test you actually enabled it" recipe.

### Chapter 12 — Safety and secrets

- **Length:** ~450 lines
- **Audience:** Anyone running this on a repo they care about
- **In scope:** The threat model. What `run-sandboxed.sh` does (env scrubbing,
  blast-radius limits). The `--yolo` flag and when to NEVER use it.
  `container-use` worker placement. Secret hygiene rules from `engine.md`.
  What the framework does NOT defend against. How to report a vulnerability.
- **Out of scope:** Sandbox internals (covered in `run-sandboxed.sh` source
  comments)
- **Depends on:** Chapters 02, 06
- **Anchors:**
  1. Threat model (what we defend against, what we don't)
  2. The sandbox wrapper — what it scrubs, what it caps
  3. `--yolo` mode — what it disables, when to use, when to NEVER use
  4. `container-use` worker placement — isolated containers per worker
  5. Secret hygiene rules
  6. Reporting a vulnerability → `SECURITY.md`

### Chapter 13 — Extending

- **Length:** ~600 lines
- **Audience:** Someone adding a mission or a runtime adapter
- **In scope:** Adding a new mission (the template skill, the SKILL.md
  contract, the promotion criteria). Adding a new adapter (the template
  adapter, primitive-by-primitive mapping). Adding a new campaign preset.
  Adding a new mutation to the gate. How to keep your skill agentskills.io-
  compliant.
- **Out of scope:** Modifying the engine itself (contributor scope)
- **Depends on:** Chapters 06, 07, 09
- **Anchors:**
  1. Adding a mission (start from `autonomous-fleet-adapter-template`'s
     mission scaffold)
  2. Adding an adapter (the template adapter, primitive table)
  3. Adding a campaign preset
  4. Adding a mutation manifest entry
  5. Promotion criteria (the three-artifact rule from
     `docs/exploratory/missions/README.md`)

### Chapter 14 — Troubleshooting

- **Length:** ~500 lines
- **Audience:** Reader whose run just failed
- **In scope:** A bestiary of known failure modes with the **exact** error
  signature and the **exact** fix. Categories: install/auth, runtime spawn,
  ledger corruption, lock contention, verification failure, PR-open failure,
  archive validation, mutation gate, CI gate. Each entry has a "what you
  see" + "what's wrong" + "how to fix" + "how to prevent" structure.
- **Out of scope:** Engineering bugs (file a GitHub issue)
- **Depends on:** Chapter 03
- **Anchors:** One per failure mode, ~20–30 modes

## 3.4 Tier 4 — Reference

> Look-up material, not for sequential reading.

### Chapter 15 — Run-archive anatomy

- **Length:** ~400 lines
- **Audience:** Reader inspecting a `.fleet/runs/<id>/` directory
- **In scope:** Every file in the archive. The manifest schema. The
  `fleet-outcome.yaml` schema. The findings file. The blind-fix files.
  The verify-summary. The fix-attestation. The trace JSONL. The
  `stop-verify-decisions.log`. The integrity gates (mtime ordering,
  sha256 verification).
- **Out of scope:** How the archive is *produced* — that's chapter 06
- **Depends on:** Chapter 03
- **Anchors:** One per file kind, plus the manifest schema field-by-field

### Chapter 16 — Trace schema (v1)

- **Length:** ~350 lines
- **Audience:** Someone integrating a dashboard (vibe-kanban, Agent View,
  custom)
- **In scope:** The full schema (`fleet-trace.schema.json`). Every field,
  every constraint. The 11 primitives with what each one means. The 6
  roles. The 5 statuses. The `details` free-form contract. The "no secrets
  / no host-absolute paths" rule, now enforced by `validate_event` + `emit()`
  (PR #41). What's emitted today (`T-FINAL` only) vs the roadmap. The `$id`
  versioning policy.
- **Out of scope:** Building a dashboard renderer
- **Depends on:** Chapter 06
- **Anchors:**
  1. Schema reference (field-by-field)
  2. Primitive reference (one section per primitive)
  3. Role + status enums
  4. `details` contract + the redaction rule (validator-enforced, PR #41)
  5. What's auto-emitted today vs aspirational
  6. Versioning + `$id` policy
  7. Consumer guide — how to read the stream
  8. Cross-reference to `docs/external-dogfood/vibe-kanban-integration.md`
     **with the explicit note that the integration doc currently
     overpromises** and what it actually covers today

### Chapter 17 — fleet-outcome schema

- **Length:** ~300 lines
- **Audience:** Operator validating a run completed correctly; campaign
  author writing a conditional gate
- **In scope:** The full `fleet-outcome.yaml` schema. Every field. What each
  field means. What values are valid. What downstream campaigns check.
- **Depends on:** Chapter 15
- **Anchors:** Field-by-field reference

### Chapter 18 — CLI reference

- **Length:** ~500 lines
- **Audience:** Operator scripting against the framework
- **In scope:** Every script in `scripts/` with every flag.
  - `run-campaign.sh` — every flag
  - `run-mission-headless.sh` — every flag
  - `run-sandboxed.sh` — every flag
  - `validate-all.sh` and each sub-validator
  - `mutation-check.sh`
  - `install-skills.sh`
  - Library entrypoints that are actually meant to be CLI-invoked
    (`verify_findings.py`, `verify_blind_fix.py`, `validate_run_archive.py`,
    `emit_trace.py`, `analyze_seat.py`, `stop_verify.py`)
- **Depends on:** None (reference)
- **Anchors:** One per script, alphabetical

### Chapter 19 — FAQ

- **Length:** ~300 lines
- **Audience:** Reader skimming for an answer to a specific question
- **In scope:** ~30 questions across: installation, choosing a mission,
  campaigns, safety, the agent-itself ("does it support GPT-5?"), cost,
  commercial use, comparison to other frameworks.
- **Depends on:** None

### Chapter 20 — Glossary

- **Length:** ~250 lines
- **Audience:** Reader who hits an unfamiliar term anywhere in the docs
- **In scope:** Every framework-specific term with a one-paragraph definition
  and a "see [chapter]" link. Terms to cover:
  - primitive, ledger, frozen DAG, run-archive, manifest, blind-fix,
    attestation, findings, verify-summary, fix-attestation, seat, EVID,
    evidence-hash, signal reconciliation, anti-flap, stop-verify hook,
    mutation gate, kill switch, strict mode, single-vendor mode,
    build-blindness, role topology, builder, reviewer, integrator,
    fleet-outcome, fleet-program, campaign preset, headless mode,
    container-use, sandbox wrapper, blast radius, `--yolo`, T-FINAL,
    schema-drift test, mtime ordering, runtime adapter, agentskills.io,
    promotion criteria, exploratory mission, three-artifact rule
- **Depends on:** None

---

# 4. Top-level files to add

## 4.1 `CHANGELOG.md` (new)

- **Why:** No release history exists. Users can't tell what shipped when.
- **Source:** Seed from `git log --oneline --no-merges` walked back to the
  first tagged-ish point, then categorise by PR title.
- **Format:** Keep-a-Changelog style. `## [Unreleased]`, then dated sections.
- **Maintenance:** Add a one-line CONTRIBUTING.md rule that every PR
  description starts with a CHANGELOG line.

## 4.2 `SECURITY.md` (new)

- **Why:** Standard OSS hygiene; required for serious adoption.
- **Content:**
  1. Supported versions
  2. Threat model (cribbed from `scripts/run-campaign.sh` header comments)
  3. What the framework defends against (env scrubbing, blast radius,
     `container-use` isolation)
  4. What it does NOT defend against (a malicious `--yolo` operator,
     compromised upstream agent CLI, supply-chain attacks on `npm` packages)
  5. Reporting a vulnerability — private email + 90-day disclosure
  6. Track record (empty for now, populated as findings come in)

## 4.3 `docs/guide/README.md` (new — the book's index)

- The grouped TOC shown in §2.3 Surface 1 above
- Includes a "How to read this guide" preamble (~50 lines) explaining the
  tier structure and recommended order

## 4.4 `README.md` patch (one block)

Add this block right under the install section:

```markdown
> 📖 **Going deeper?** The [Guide](docs/guide/README.md) walks through every
> concept, mission, and reference — from your first PR to writing a custom
> adapter.
```

That's the only change to `README.md`.

---

# 5. Skill READMEs — what to replace the stubs with

All 12 `skills/*/README.md` files are currently identical 33-line stubs. We
replace each with a real per-skill user doc using **the same template**:

```markdown
# <skill-name>

<banner image>

> One-paragraph description (current short description from SKILL.md
> frontmatter, lightly edited for human reading)

🟦 / 🟧 / 🟩 **Tier N · <role>** — <one-line role description>

## When to use it

3–5 bullets. Specific situations. Not marketing.

## What it produces

The artifacts a successful run creates. Concrete file paths, concrete PR
shapes.

## What it expects from your repo

Preconditions. e.g. "doc-sync assumes you have a `README.md`" or
"test-coverage requires a discoverable test runner (`pytest`, `jest`,
`go test`)".

## Common failure modes

3–5 bullets, each pointing to the troubleshooting chapter.

## Quick install

(The current install snippet — keep as-is)

## Learn more

- [Guide chapter X](../../docs/guide/NN-chapter.md) — the depth on this skill
- [SKILL.md](./SKILL.md) — the agent-facing spec
```

**Per-skill specifics:**

| Skill | Tier | Primary use case | Chapter link |
|---|---|---|---|
| `autonomous-fleet` | 1 · Umbrella | Routes vague requests to the right mission | Guide 09 |
| `autonomous-fleet-core` | 1 · Engine | Loaded automatically by missions | Guide 06 |
| `setup-autonomous-fleet` | 1 · Setup | First-run configuration | Guide 02 |
| `fleet-program` | 1 · Campaigns | Chaining missions with gates | Guide 10 |
| `doc-sync` | 3 · Mission | Stale docs after a refactor | Guide 09 §doc-sync |
| `test-coverage` | 3 · Mission | Raising coverage on a module | Guide 09 §test-coverage |
| `adversarial-review-and-fix` | 3 · Mission | Red-team + patch | Guide 09 §adversarial |
| `autonomous-fleet-adapter-claude-code` | 2 · Adapter | Claude Code runtime | Guide 02, 13 |
| `autonomous-fleet-adapter-codex` | 2 · Adapter | Codex runtime | Guide 02, 13 |
| `autonomous-fleet-adapter-grok` | 2 · Adapter | Grok runtime | Guide 02, 13 |
| `autonomous-fleet-adapter-orca` | 2 · Adapter | Orca runtime | Guide 02, 13 |
| `autonomous-fleet-adapter-template` | 2 · Adapter | Template for adding a new runtime | Guide 13 |

---

# 6. Voice, tone, and style

**Reference points** — what we're imitating:

- **Astro docs** (https://docs.astro.build) — friendly, opinionated, dense
  per-chapter, clear "you should / you shouldn't" guidance
- **Prefect docs** — depth on concepts, clear primitive hierarchy
- **Stripe docs** — minimal prose around code, examples-first for reference

**What we're not doing:**

- ❌ AWS-docs-style ("This document describes the configuration of …") — too
  bureaucratic
- ❌ Marketing-deck-style ("Unlock the power of …") — already covered by
  README
- ❌ Auto-generated-from-source style (typedoc-style) — too dry, too thin

**Style rules** (lifted from AGENTS.md so the guide feels native to the repo):

- ASCII boxes for diagrams (matches engine.md). No mermaid (renders
  inconsistently across markdown readers).
- ASCII tables, not HTML.
- No GitHub-only `[!NOTE]` / `[!WARNING]` callouts in body text. Use plain
  blockquotes (`>`) so the docs render in any markdown context.
- Code samples are always copy-pasteable and complete (no `…` ellipses in
  the middle of a snippet unless explicitly marked `# (other config…)`).
- Every claim has provenance: "the engine emits T-FINAL before the manifest
  write (see the [Trace schema](16-trace-schema.md) reference)".
- No em-dashes in body text. (Repo convention from `AGENTS.md` / `CONTRIBUTING.md`.)
- 100-character soft wrap.

---

# 7. Honest documentation — current limitations we surface

This is the part most docs sites get wrong. We document what is actually true
today alongside what works, with provenance. The guide is not a sales pitch.

PROVENANCE NOTE (read first). The e2553ac post-merge audit raised four issues:
trace ordering inversion, prose-only `details` redaction, a coverage-hack test,
and a lock second-liveness mutation gap. ALL FOUR were FIXED in PR #41 (merged to
`main`). They are NOT known issues any more. The engine and substrate chapters
may cite them as worked examples of the review discipline (the framework found
and closed its own bugs), but the guide must not list them as open. The
known-issues list MUST be re-derived against current `main` at authoring time,
not copied from a superseded audit — copying a stale audit is its own dishonesty.

What REMAINS genuinely limited today (re-derived against `main`, MUST appear):

1. Chapter 16 (Trace schema) — "What's emitted today" section.
   Exactly one trace event is wired in production code today: `T-FINAL` from
   `fleet_run.write_manifest` (now correctly emitted BEFORE the manifest write,
   per the doctrine). The schema covers 11 primitives; the stream is
   intentionally sparse while per-transition emission rolls out — the
   coordinator and adapters emit the rest per the engine TRACE EMISSION doctrine.
   The vibe-kanban integration doc was corrected in PR #41 to describe the
   contract plus a rollout-in-progress, not a shipped full stream.

2. Chapter 12 (Safety and secrets) — "Headless mode caveat" subsection.
   The campaign scripts (`run-campaign.sh`) drive each runtime's CLI in headless
   mode, which requires that CLI to be authenticated on the host and is not yet
   fully validated end-to-end. The interactive path (chat / `/goal`) is the
   supported flow today.

Each entry states the current state, why it is limited, and a link to a tracking
issue WHERE ONE EXISTS — never invent a GitHub issue for already-fixed work.

This is doctrine. Documentation that hides current limitations is worse than no
documentation; documentation that invents stale limitations from a superseded
audit is just as dishonest.

---

# 8. Implementation batches

Three independently-shippable PRs. Each PR has its own readiness doc in
`docs/`.

## 8.1 Batch 1 — Foundation (PR #1)

**Files (8 new, 1 patched):**

- `docs/guide/README.md` (the index)
- `docs/guide/01-quickstart.md`
- `docs/guide/02-installation.md`
- `docs/guide/03-your-first-mission.md`
- `docs/guide/04-mental-model.md`
- `CHANGELOG.md` (seeded from git log)
- `SECURITY.md`
- `docs/docs-site-batch-1-readiness.md`
- `README.md` (add the one Guide link block)

**Estimated size:** ~2500 lines of new docs.

**Validation gates:**

- `validate-all.sh` passes
- All internal markdown links resolve (`lychee` or a one-shot
  `scripts/validate_doc_links.py` we add as part of this batch)
- Every chapter has the required structure (frontmatter comment +
  "On this page" + footer nav) — pinned by a new validator
- The README patch doesn't break any of the existing badges

**Why first:**

- Highest-leverage for new users (someone landing on the repo today)
- Standalone — tier 2/3/4 chapters can reference back to it but it
  doesn't reference forward to them
- Establishes the voice/tone/style; we course-correct after this batch
  before writing 6000 more lines

**Course-correction checkpoint:** After Batch 1 merges, **pause** and review
the voice with the operator. Only proceed to Batch 2 once the tone is
locked.

## 8.2 Batch 2 — Concepts + how-to (PR #2)

**Files (10 new):**

- `docs/guide/05-missions-vs-campaigns.md`
- `docs/guide/06-the-engine.md`
- `docs/guide/07-the-substrate.md`
- `docs/guide/08-roles-and-blindness.md`
- `docs/guide/09-mission-catalog.md`
- `docs/guide/10-campaigns.md`
- `docs/guide/11-strict-mode.md`
- `docs/guide/12-safety-and-secrets.md`
- `docs/guide/13-extending.md`
- `docs/guide/14-troubleshooting.md`
- `docs/docs-site-batch-2-readiness.md`

**Estimated size:** ~4500 lines.

**Validation gates:** Same as Batch 1 plus:

- Every primitive named in chapter 06 must exist in `emit_trace.py`'s
  `PRIMITIVES` tuple (pinned by a new test)
- Every mission named in chapter 09 must exist as a `skills/<name>/` dir
- Every campaign preset named in chapter 10 must exist in
  `scripts/campaigns/`
- Every CLI flag named in chapter 13 must exist in the script's argparse

These pin-tests catch doc drift the same way the schema-drift test catches
schema drift. Doctrine: **docs that describe code MUST be enforceable.**

## 8.3 Batch 3 — Reference + skill READMEs (PR #3)

**Files (6 new + 12 rewritten):**

- `docs/guide/15-run-archive.md`
- `docs/guide/16-trace-schema.md`
- `docs/guide/17-fleet-outcome-schema.md`
- `docs/guide/18-cli-reference.md`
- `docs/guide/19-faq.md`
- `docs/guide/20-glossary.md`
- 12 × `skills/*/README.md` (full rewrites per §5 template)
- `docs/docs-site-batch-3-readiness.md`

**Estimated size:** ~3500 lines.

**Validation gates:** Same as Batch 2 plus:

- Every field in chapter 17 must exist in the `fleet-outcome.yaml` schema
  (pinned)
- Every primitive/role/status in chapter 16 must match the schema enum
  (pinned by extending the existing schema-drift test)
- Every glossary term must appear in at least one chapter (pinned)
- Every chapter must link to at least one glossary term (encourages
  cross-linking)

## 8.4 Batch dependencies

```
Batch 1 ─┐
         ├─► Batch 2 ─┐
         │            ├─► Batch 3
         │            │
         └────────────┘
```

Batch 2 depends on Batch 1's voice + structure. Batch 3 depends on the
references-out from Batch 2 (the concept chapters cite the schema chapters).

---

# 9. Effort + scheduling

This is a **plan**, not an estimate. But the operator asked about scope, so:

| Batch | New files | Rewritten files | Approx lines | Validators added |
|---|---|---|---|---|
| 1 | 7 (4 chapters + index + CHANGELOG + SECURITY) | 1 (README patch) | ~2500 | 1 (link validator) |
| 2 | 11 (10 chapters + readiness) | 0 | ~4500 | 3 (primitive-pin, mission-pin, preset-pin) |
| 3 | 7 (6 chapters + readiness) | 12 (skill READMEs) | ~3500 | 2 (schema-drift extension, glossary-coverage) |
| **Total** | **25 new** | **13 rewritten** | **~10,500 lines** | **6 new validators** |

The operator decides cadence. Recommended: ship Batch 1 first, **pause for
voice review**, then commit to 2 and 3.

---

# 10. Stage 2 (deferred to a follow-up plan)

After Stage 1 ships and we have signal that the docs are being read,
revisit:

**Stage 2.A — Starlight site on Cloudflare Pages**

- ~2-hour setup if the chapters were authored per §2.2 (frontmatter present,
  portable markdown)
- New repo subdir `docs-site/` with `astro.config.mjs`, `package.json`,
  `tsconfig.json`
- Cloudflare Pages project pointed at `docs-site/` build output
- Custom domain at `autonomous-fleet.dev` (registrar TBD)
- GitHub Action that rebuilds on every push to `main`
- Adds: sidebar nav, full-text search, dark mode, anchor-link icons,
  responsive layout
- Cost: $0 hosting, ~$15/yr for the domain if we want a custom one

**Stage 2.B — Versioned docs**

- Only worth doing once we ship breaking changes regularly
- Starlight has first-class multi-version support

**Stage 2.C — Interactive playground**

- A tiny in-browser sandbox where someone can click through a simulated
  run and see what each artefact looks like, without installing anything
- Materially harder; only worth it if external adoption justifies it

**None of Stage 2 is in scope for this plan.** Stage 2 gets its own plan
when its trigger conditions are met.

---

# 11. Open questions for the operator

Before implementation begins, the operator should answer:

1. **Audience confirmation.** Is the primary audience *developers using
   `autonomous-fleet` on their own repo* (assumed), or *contributors to the
   framework itself*, or *both with clear separation*? This plan assumes the
   first.

2. **Voice confirmation.** This plan assumes **Astro-style** ("friendly,
   opinionated, dense per-chapter"). Alternatives: Prefect-style
   ("conceptual depth, formal reference"), Stripe-style ("examples-first,
   minimal prose"). Pick one before Batch 1 starts.

3. **Honest-documentation confirmation.** §7 says known issues from the
   e2553ac audit will be documented in-guide, not hidden. Confirm this is
   acceptable for an OSS project where some readers will be evaluating it
   for adoption.

4. **CHANGELOG seeding cutoff.** How far back should we walk the git log?
   First commit (the framework's origin) or first tagged release (none
   exists today) or "the past 60 days"?

5. **Cadence.** Ship Batch 1 as a proof-of-shape and pause for review, or
   commit to all three batches up-front?

6. **Stage 2 trigger.** What signal makes us flip on the Starlight site —
   adoption metric (stars / forks / external dogfood mentions), inbound
   request from a user, or a calendar date?

---

# 12. What this plan does NOT cover

To keep the scope honest:

- **No new code.** This plan is docs-only. No engine changes, no schema
  changes, no new validators (except the doc-validation ones in §8).
- **No fixes to the known issues from the audit.** Those are tracked
  separately. The guide documents them; it doesn't fix them.
- **No translation, no i18n, no a11y audit, no SEO** — Stage 2.
- **No screencast, no demo video, no marketing assets** — out of scope.
- **No `agentskills.io` marketplace listing rewrite.** Covered by
  `docs/marketplace-submission/`.
- **No external blog post / launch announcement** — out of scope; operator's
  call when the docs are stable.

---

# 13. Acceptance criteria for this plan

This plan is accepted when:

- [ ] Operator confirms audience (§11.1)
- [ ] Operator confirms voice (§11.2)
- [ ] Operator confirms honest-documentation policy (§11.3)
- [ ] Operator confirms CHANGELOG cutoff (§11.4)
- [ ] Operator picks cadence (§11.5)
- [ ] Operator notes Stage 2 trigger (§11.6, can be deferred)

Once accepted, this file is moved out of `docs/plans/` into
`docs/docs-site-readiness.md` and tracked through the three batches the
same way every other multi-PR initiative in this repo is tracked.

---

# 14. Provenance

This plan was written after:

- Walking `docs/` (45 files), `skills/` (12 × README + SKILL pairs), and
  `README.md`/`AGENTS.md`/`CONTRIBUTING.md` (2026-06-24)
- Reviewing the e2553ac post-merge audit findings (3 sub-agent deep audits
  on lock safety, mtime fix, trace schema-drift)
- Cross-checking the existing `docs/plans/way-ahead-2026-06-23.md` for
  format and tone
- Verifying the doctrine of `engine.md` (TRACE EMISSION block, lines
  406–432) against the implementation in `scripts/lib/fleet_run.py`

No code was changed in the production of this plan.
