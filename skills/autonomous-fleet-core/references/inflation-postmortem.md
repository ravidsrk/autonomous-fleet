# Inflation Postmortem

<!-- demoted from engine.md (issue #84) -->
═══════════════════════════════════════════════════════════
INFLATION POST-MORTEM: break the "we already shipped that" trap on re-runs.
═══════════════════════════════════════════════════════════
When a prior run claimed completion but the RESULT-STATE TERMINATION GATE later proved incomplete
(green CI but the real end-to-end flow aborted, untested security leaks, half-built screens reached
via the live app), the next run starts with a brief INFLATION POST-MORTEM before BOOTSTRAP. Re-read
the prior readiness / fleet-outcome doc; identify every claim that was green-CI-but-not-real-result-
state (a feature that built but did not work end to end, a "passing" suite that masked a missing
flow, a "DONE" that survived only because the unit test stubbed the failing dependency); list those
items as the FIRST entries in the new CLOSE-INDEX with the prior PR# noted alongside the
re-confirmed OPEN state. This is structural anti-inflation: an autonomous run will otherwise believe
its own prior green checkmarks and skip them as "already done." Source: Stage-9 prompt 24 (Aula
Completion-for-Real — the anti-inflation run; prompts.md L3013 and L3061 — "anti-inflation has to
be structural; an autonomous run will otherwise believe its own green checkmarks").
