# DECISIONS — close-gaps run (2026-06-21)

- BASE ravidsrk/close-gaps branched off ravidsrk/gap-analysis-doc (not bare main) because REVIEW_DOC
  (docs/gap-analysis-genesis-prompts.md) is committed there, not yet on main. BASE = main + that one
  doc commit. BASE->main promotion is human-owned (out of scope).
- Builder = codex via `codex exec` (NOT `codex --full-auto` — rejected by codex 0.141; this is the
  E1 finding fixed in PR #27/#orca-adapter). Reviewer = coordinator reviewing the diff cross-vendor.
- Adapter: git worktrees + codex exec (the engine's sanctioned fallback when not driving Orca's RPC
  worktree/terminal loop) for control + quality on framework-core edits; WT_CLEAN = `git worktree
  remove`. Orca runtime is up but the leaner fallback is used per the version-tolerant adapter rule.
- Frozen scope: only REVIEW_DOC's PARTIAL/MISSING + 4 verified-directly gaps. New ideas -> DEFERRED.
