<!-- title: The Guide | description: Structured walk through every concept, mission, and reference in autonomous-fleet | sidebar_order: 0 -->

# autonomous-fleet: The Guide

**On this page:** [How to read this guide](#how-to-read-this-guide) ·
[Get started](#-get-started) · [Concepts](#-concepts) · [How-to](#-how-to) ·
[Reference](#-reference)

The `README.md` pitches the framework. This is the book. It walks a developer from a first
green PR all the way to writing a custom runtime adapter, with every concept, mission, and
schema documented against the code on `main`. If you only have ten minutes, read the
[Quickstart](01-quickstart.md). If you want to understand the thing, read tier by tier.

## How to read this guide

Twenty chapters, four tiers. The tiers are an order, not a menu: each builds on the last.

```
 Tier 1  GET STARTED   ── read in order, ~30 min ──►  a green PR in your own repo
   │
 Tier 2  CONCEPTS      ── read for the "why", ~90 min ──►  explain it to a colleague
   │
 Tier 3  HOW-TO        ── consult per-chapter when you need to do a thing
   │
 Tier 4  REFERENCE     ── look-up material, never sequential
```

- New here? Read Tier 1 top to bottom. By the end of chapter 3 you have run `doc-sync`
  end-to-end and seen the run-archive it produced.
- Want the model in your head? Tier 2. Chapter 04 is the mental model; 06 and 07 are the
  dense ones (the engine, then the 4-layer substrate).
- Need to do one specific thing? Jump straight into Tier 3. Each how-to chapter stands alone
  and links back to the concepts it assumes.
- Looking up a field, a flag, or a term? Tier 4. The [Glossary](20-glossary.md) defines every
  framework-specific word and links to the chapter that explains it.

Two honest limitations are surfaced where they live, not hidden:

> The trace stream emits exactly one event in production today, `T-FINAL`, written by
> `scripts/lib/fleet_run.py` (before the manifest, per the engine doctrine). The schema covers
> its 11-value trace primitive enum; per-transition emission is rolling out. See [Trace schema](16-trace-schema.md).

> Headless campaign mode (`run-campaign.sh`) is not yet validated end-to-end. The interactive
> path (your agent's chat, `/goal`) is the supported flow today. See
> [Safety and secrets](12-safety-and-secrets.md).

## 🚀 Get started

- [Quickstart](01-quickstart.md), your first PR in 10 minutes
- [Installation](02-installation.md), full setup across all 4 runtimes
- [Your first mission](03-your-first-mission.md), running doc-sync end-to-end

## 🧠 Concepts

- [Mental model](04-mental-model.md), what a "run" actually is
- [Missions vs campaigns](05-missions-vs-campaigns.md), when to chain
- [The engine](06-the-engine.md), primitives, ledger, frozen DAG
- [The substrate](07-the-substrate.md), 4-layer verification
- [Roles and blindness](08-roles-and-blindness.md), why review is structural

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

---

[📖 Guide Index](README.md) · [Next: Quickstart →](01-quickstart.md)
