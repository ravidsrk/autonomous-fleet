<!-- title: Roles and blindness | description: Why review in autonomous-fleet is structural, not instructed: the builder/reviewer/integrator topology, build-blindness, cross-vendor diversity, and the single-vendor trade-off. | sidebar_order: 8 -->

# Roles and blindness

**On this page:** [Three roles, three terminals](#three-roles-three-terminals) ·
[Build-blindness is structural](#build-blindness-is-structural) ·
[Anti-anchoring: the blind fix](#anti-anchoring-the-blind-fix) ·
[The Aula run](#the-aula-run) ·
[Single-vendor mode](#single-vendor-mode) ·
[The design-mission exception](#the-design-mission-exception) ·
[What's enforced vs what's a default](#whats-enforced-vs-whats-a-default)

If you have read [The engine](06-the-engine.md) and [The substrate](07-the-substrate.md), you
know the framework spends a lot of effort making sure a piece of work is actually correct before it
merges. This chapter answers the question underneath all of that machinery: why does the framework
keep insisting on separate roles, separate terminals, and (when it can) separate model vendors?

The short answer: the most reliable way to catch a mistake is to have it graded by something that
never saw how it was made. Not "a careful reviewer." A reviewer that is _structurally incapable_ of
inheriting the builder's blind spots, because it was never in the room. The rest of this chapter is
about how the fleet builds that structural blindness out of three roles, three terminals, and a
filesystem that proves the discipline happened in the right order.

This is a concepts chapter. It explains _why_ the topology looks the way it does. The exact commands
each runtime uses to spawn these roles live in the adapter `SKILL.md` files (the Orca mapping is in
`skills/autonomous-fleet-adapter-orca/SKILL.md`); the verification layers that back the discipline
are in [The substrate](07-the-substrate.md).

## Three roles, three terminals

Every fleet run decomposes into a pipeline of three roles. The default pipeline in the engine is
`BUILD → open PR → REVIEW → FIX → SHIP`, and three roles carry it:

```
  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
  │   BUILDER   │      │  REVIEWER   │      │ INTEGRATOR  │
  │             │      │             │      │             │
  │ implements  │ PR   │ fresh,      │ PASS │ conflict-   │
  │ the task    ├─────►│ build-blind ├─────►│ aware merge │
  │ unit, adds  │ diff │ grade only  │      │ into BASE,  │
  │ the test,   │ as   │ vs the      │      │ delete the  │
  │ opens a PR  │ TEXT │ acceptance  │ FAIL │ branch,     │
  │             │      │ contract    │  │   │ clean the   │
  └─────────────┘      └──────┬──────┘  │   │ checkout    │
                              │         │   └─────────────┘
                              └─────────┘
                          fix round on the
                          SAME branch, re-review
```

The roles are not three hats one agent wears in sequence. They are three separate worker sessions,
in three separate terminals, with deliberately different information:

- The **builder** implements one task unit on a branch off BASE. It commits in small increments,
  adds the regression-catching test the mission calls for, runs build plus lint plus the affected
  tests green, then opens a PR. The builder owns the full construction conversation: every
  exploration, every dead end, every "actually this approach is cleaner" pivot.

- The **reviewer** is the load-bearing role. The engine describes it as `REVIEW (reviewer — FRESH,
BUILD-BLIND, never saw the build conversation)`. It reads the PR diff and grades it _only_ against
  the unit's acceptance criteria. Read and verdict only, no edits. It is handed the diff plus the
  acceptance contract as text, and nothing else: not the build worktree, not the builder's session,
  not the construction reasoning.

- The **integrator** ships. On a PASS it confirms the branch HEAD still matches the SHA the reviewer
  graded (the SHA-pin), checks for conflicts against BASE, does a conflict-aware merge with a merge
  commit (commits preserved, never squashed), deletes the branch, and cleans the checkout.

On Orca, the default handle assignment makes the vendor split concrete:
`@codex builds, a fresh build-blind @claude reviews, @claude integrates` (from the Orca adapter
`SKILL.md` frontmatter). The builder is one vendor, the reviewer a different one. That cross-vendor
split is the topic of the next two sections.

### Why separate terminals, not separate prompts

You could imagine a cheaper design: one agent, one terminal, and a prompt that says "now switch
roles and review your own work critically." The fleet does not do this, on purpose.

A reviewer in the same session has already seen the build. It has the construction reasoning in its
context window. When it then "reviews," it is not grading the diff, it is rationalising the artifact
it just helped produce. The engine is blunt about this in the placement rules: a review-fix cycle is
`DEPENDENT` work that runs in `the SAME checkout, a FRESH worker session`. On Orca, `dependent` maps
to `the ACTIVE worktree, a FRESH terminal`. Fresh terminal, fresh session: the reviewer starts with
an empty context window and is fed only the diff and the contract.

This is the "fresh terminal" rule. It is not a politeness convention. It is the mechanism that makes
the next claim true.

## Build-blindness is structural

Here is the thesis of the whole chapter, stated the way the engine states it:

> build-blindness is structural, not just instructed

You cannot get build-blindness from a prompt. A prompt that says "pretend you didn't see the build"
is asking a model to un-know something it knows, which is exactly the kind of instruction models are
bad at honoring under pressure. The fleet does not ask. It arranges the world so the reviewer
_never had_ the build context to begin with.

Three structural facts produce build-blindness:

1. **Separate session.** The reviewer runs in a fresh worker session (a fresh terminal on Orca),
   so its context window never contained the build conversation.

2. **Text-only handoff.** The engine requires you to `hand the reviewer the diff + the acceptance
contract as TEXT ONLY, never the build worktree or the builder's session`. The reviewer cannot
   `git log` the builder's reasoning or read scratch files, because it does not have the worktree.
   It has a diff and a contract, as strings.

3. **Different vendor when available.** When more than one worker vendor is configured, the engine
   says the reviewer `SHOULD be a DIFFERENT vendor than the builder (a Codex build reviewed by
Claude, etc.) so a vendor's blind spot is not its own grader`.

That third point is the cross-vendor blind-spot diversity argument, and it is worth slowing down on.

### Cross-vendor blind-spot diversity

Every model family has systematic blind spots: classes of mistake it tends to make and, crucially,
classes of mistake it tends not to _notice_. If the same vendor builds and reviews, the review is
blind to exactly the failures the builder was prone to, because they share a blind spot. A
vendor's blind spot becomes its own grader.

Putting a different vendor in the reviewer seat breaks that correlation. A Codex build reviewed by
Claude is graded by a model whose failure modes do not line up with the builder's. The two do not
share the same blind spots, so a mistake invisible to the builder's vendor has a real chance of
being visible to the reviewer's.

```
   SAME-VENDOR REVIEW                 CROSS-VENDOR REVIEW
   (build + review by one family)     (build by A, review by B)

   builder blind spots ████░░░░       builder (A) blind spots ████░░░░
   reviewer blind spots ████░░░░       reviewer (B) blind spots ░░░░██░░
                        ▲                                       ▲   ▲
                        same gap                          A's gap   B catches it
                        survives review                   covered by B
```

This is the structural reason the framework is so insistent about multi-vendor agents. It is not
brand preference and it is not hedging. It is that a reviewer who shares the builder's blind spots
is, for the failures that matter most, not really reviewing.

The default handles encode this. On Orca: `@codex` builds, a different-vendor `@claude` reviews. The
adapter could run same-vendor (and in single-vendor mode it does, see below), but the recommended
default is always cross-vendor when the host has more than one vendor available.

## Anti-anchoring: the blind fix

A fresh, cross-vendor, build-blind reviewer is necessary. The engine argues it is _not sufficient_,
and adds a second discipline on top. This is the part that surprises people, so read it carefully.

Even with zero build context, a reviewer handed a patch and asked "is this correct?" anchors on
whatever it sees. The engine's ANTI-ANCHORING block puts it this way: the reviewer rationalises the
existing fix, because `rationalising an artifact is cognitively cheaper than independently
re-deriving the correct one`. The mere act of reading the candidate diff first biases the verdict
toward "looks fine." The empirical observation the engine cites (from SWE-Review) is that reviewers
given the same patch in two orders, patch-first versus root-cause-first, `produce systematically
different decisions on the same case`.

The countermeasure is mechanical, and it is one of the more distinctive things the fleet does:

> BEFORE the reviewer opens the candidate diff, it writes its INDEPENDENT proposed fix to
> `.fleet/runs/<run_id>/reviewer-blind-fix-<finding-id>.md`.

The blind-fix file names three things:

- The **point of creation** (`file:function:line`), in the same call-stack-depth language the engine
  uses for root-cause analysis.
- The **shape of the change** the reviewer would make, as a paragraph (no code required).
- The reviewer's **pre-commit confidence** (0 to 100).

Only _then_ does the reviewer open the candidate patch. Now the review is a comparison: candidate
versus the reviewer's own pre-committed fix. A candidate that agrees with the blind fix at the same
call-stack depth gets weight. A candidate that patches a _different_ (shallower) depth than the blind
fix trips the root-cause-depth rule, the finding that catches a symptom fix dressed up as a real one.

Why this works: you cannot rationalise a patch you have not read yet. By forcing the reviewer to
commit its own answer in writing _before_ it ever sees the candidate, the anchor is gone. The
reviewer has its own opinion on the record, and the candidate has to earn agreement with it.

### The filesystem proves the order

This is where roles and blindness connect back to [The substrate](07-the-substrate.md). The
discipline above is only real if the order it demands actually happened, and the fleet makes that
auditable on disk. The engine:

> A review run whose blind-fix file is missing or is mtime-AFTER the candidate-findings file is
> structurally suspect — the protocol requires blind-fix BEFORE patch read, and the filesystem must
> reflect that order.

The run-archive validator enforces exactly this as one of its mtime-ordering invariants:

```
  blind_fix.mtime   <   findings.mtime     (Layer 3: blind fix written BEFORE the diff was read)
  findings.mtime    <   verify_summary.mtime
  readiness.mtime   =   latest in archive
```

So "the reviewer was build-blind and committed its fix first" is not a claim you have to trust. It
is a property the archive validator checks. A blind-fix file with an mtime after the findings file
fails validation even when every checksum matches, `because these orderings ARE the disciplines`.
The role topology in this chapter is the _intent_; the manifest and its mtime invariants are the
_proof_ that the intent was honored. See [Run-archive anatomy](15-run-archive.md) for the manifest
fields and [The substrate](07-the-substrate.md) for how the four layers compose.

## The Aula run

The roles exist because of mistakes the framework's predecessors actually made. The clearest origin
story is the one the engine cites for its anti-inflation discipline, the Aula run.

The problem the Aula run exposed has a name in the engine: **inflation**. An autonomous run that
previously claimed completion will, on a re-run, believe its own prior green checkmarks and skip the
work as "already done", even when the work was never actually finished. The engine quotes the lesson
directly from the run's prompts:

> anti-inflation has to be structural; an autonomous run will otherwise believe its own green
> checkmarks

(Source: Stage-9 prompt 24, the Aula "Completion-for-Real" run, recorded in the engine's INFLATION
POST-MORTEM block.)

Notice the shape of that lesson. It is the _same_ shape as build-blindness. In both cases the failure
is an agent trusting its own prior state: the builder trusting its own construction reasoning when it
reviews, the re-run trusting its own prior "DONE" when it re-plans. And in both cases the fix is the
same: do not ask the agent to be skeptical of itself (it will not be), arrange the world so the prior
state is not available to trust.

What changed because of Aula: a re-run now begins with an INFLATION POST-MORTEM _before_ it bootstraps.
It re-reads the prior readiness and `fleet-outcome` docs, identifies every claim that was
green-CI-but-not-real-result-state (a feature that built but did not work end to end, a "passing"
suite that masked a missing flow, a "DONE" that survived only because a unit test stubbed the failing
dependency), and lists those items as the _first_ entries in the new close-index with the prior PR
number noted alongside the re-confirmed OPEN state. The run is structurally forbidden from skipping
them on faith.

The throughline from Aula to this chapter: trust of self is the enemy. Build-blindness keeps the
reviewer from trusting the builder's reasoning. The blind-fix keeps the reviewer from trusting the
candidate patch. The inflation post-mortem keeps the re-run from trusting its own prior checkmarks.
Same disease, same structural cure, applied at three different seams.

## Single-vendor mode

Not everyone has four agent CLIs authenticated on one host. If you only have one vendor, the fleet
still runs, and it is honest with you about what you give up.

The engine's instruction for this case is explicit:

> Single-vendor host: say so in DECISIONS.md and use a fresh same-vendor reviewer.

So in single-vendor mode:

```
  ┌──────────────────────────── single-vendor mode ────────────────────────────┐
  │                                                                             │
  │   builder (vendor A)  ──PR diff as TEXT──►  reviewer (vendor A, FRESH)      │
  │                                                                             │
  │   STILL ENFORCED:                          LOST:                            │
  │   - fresh session (no build context)       - cross-vendor blind-spot        │
  │   - text-only handoff (diff + contract)      diversity (builder and         │
  │   - blind-fix before patch read              reviewer share a blind spot)   │
  │   - mtime-ordering archive proof                                            │
  │   - SHA-pinned, conflict-aware ship                                         │
  │                                                                             │
  └─────────────────────────────────────────────────────────────────────────────┘
```

Read the trade-off honestly. What you keep is most of the discipline: the reviewer is still a fresh
session with no build context, the handoff is still text-only, the blind-fix-before-patch protocol
still runs, the archive still proves the order on disk, and the ship is still SHA-pinned and
conflict-aware. The structural build-blindness from separate sessions is intact.

What you lose is one specific thing: cross-vendor blind-spot diversity. A same-vendor reviewer does
not share the builder's _session_, but it does share the builder's _vendor blind spots_. For the
class of mistakes a model family systematically fails to notice, a same-vendor reviewer is weaker
than a cross-vendor one, because the builder's blind spot is, partly, its own grader again.

That is a real reduction in catch-rate for vendor-correlated failures, not a cosmetic one. It is
also better than no fresh review at all, which is why single-vendor mode is supported rather than
forbidden. The rule is just that you have to _say so_ in `DECISIONS.md`: the run records that it ran
single-vendor, so anyone auditing the archive later knows the cross-vendor layer was not in play.

If you can get a second vendor authenticated, do it. See [Installation](02-installation.md) for the
per-runtime auth setup. The framework will use the cross-vendor default the moment a second vendor
is available.

## The design-mission exception

There is one place the default builder/reviewer vendor split deliberately changes: design work.

Most missions default to `@codex` building and `@claude` reviewing on Orca. But design missions are
different. From the Orca adapter `SKILL.md`:

> `grok` builds design missions

and in the frontmatter:

> (@grok builds design missions)

The two missions this applies to are `design-integration` and `landing-page-convergence`. The engine
classes both as Tier 2 work in its risk tiers:

> design-integration, landing-page-convergence (no direct category in the study — treat as Tier 2).

Why a different builder for design. The choice of `@grok` as the builder for these missions is a
mission-level role-pipeline override, not a change to the topology. The roles are still
builder / reviewer / integrator. The blindness disciplines are unchanged: the reviewer is still
fresh, still build-blind, still gets the diff as text, still writes a blind fix first. What changes
is _which vendor sits in the builder seat_ for that mission, because the mission's role pipeline says
so. The engine is explicit that the mission's role pipeline overrides the adapter defaults: the Orca
`SKILL.md` describes its handle assignment as "overridable by the mission's role pipeline."

The takeaway: the design-mission exception is not a hole in the discipline. It is the role pipeline
doing exactly what it is designed to do, swapping the builder vendor per mission, while every
blindness guarantee in this chapter stays in force.

## What's enforced vs what's a default

It is worth being precise about which parts of this chapter are hard guarantees and which are
recommended defaults, because the difference matters when you are debugging a run or reading an
archive.

```
  ┌────────────────────────────────────────┬──────────────────────────────────┐
  │ DISCIPLINE                              │ ENFORCED HOW                      │
  ├────────────────────────────────────────┼──────────────────────────────────┤
  │ Fresh, build-blind reviewer session     │ Structural: separate session/     │
  │                                         │ terminal, text-only handoff       │
  │ Blind-fix written BEFORE the diff read   │ Filesystem: mtime ordering        │
  │                                         │ checked by the archive validator  │
  │ blind_fix.mtime < findings.mtime        │ Archive validator (hard fail)     │
  │ Reviewer = DIFFERENT vendor             │ Default (SHOULD), when >1 vendor  │
  │ Same-vendor fallback                    │ Allowed, must be noted in         │
  │                                         │ DECISIONS.md                      │
  │ @codex build / @claude review (Orca)    │ Adapter default, overridable by   │
  │                                         │ the mission role pipeline         │
  │ @grok builds design missions            │ Mission role-pipeline override    │
  └────────────────────────────────────────┴──────────────────────────────────┘
```

The fresh-session and blind-fix-order disciplines are not negotiable: the first is built into how
workers are placed, the second is checked on disk by the run-archive validator and a missing or
out-of-order blind-fix file fails validation. The cross-vendor reviewer is a strong default (`SHOULD`,
not `MUST`) precisely so single-vendor hosts can still run, but a same-vendor run has to declare
itself in `DECISIONS.md`. And the specific handle-to-vendor mapping is an adapter default that any
mission's role pipeline can override, which is exactly the mechanism the design-mission exception
uses.

If you remember one thing from this chapter, make it this: the framework does not ask agents to be
honest reviewers of their own work, because that is not a property you can request. It arranges
separate sessions, text-only handoffs, a write-your-answer-first protocol, and a filesystem that
proves the order, so that build-blindness is something the run _has_, not something it _promises_.

### Where to go next

- [The engine](06-the-engine.md): the primitives that spawn and place these roles, and the
  signal-reconciliation discipline that decides when a review-fix cycle is really done.
- [The substrate](07-the-substrate.md): the four verification layers that back these roles,
  including the blind-fix mechanical guard (Layer 3) that enforces the mtime ordering.
- [Run-archive anatomy](15-run-archive.md): the `reviewer-blind-fix-*.md` file, the findings file,
  and the manifest fields that make the order auditable.
- [Installation](02-installation.md): getting a second vendor authenticated so you get cross-vendor
  review by default.

---

← [Previous: The substrate](07-the-substrate.md) ·
[Guide Index](README.md) ·
[Next: Mission catalog](09-mission-catalog.md) →
