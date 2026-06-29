# Attributions and third-party credits

`autonomous-fleet` is [MIT licensed](LICENSE) (Copyright 2026 ravidsrk). Parts of the
orchestration substrate adapt **mechanism designs** from other open-source projects. We
thank these authors and link to their licenses below.

When you redistribute or fork this repo, keep this file (and [`NOTICE`](NOTICE)) alongside
[`LICENSE`](LICENSE).

---

## Agent Orchestrator

| | |
|---|---|
| **Project** | [Agent Orchestrator](https://github.com/AgentWrapper/agent-orchestrator) |
| **Maintainer** | [AgentWrapper](https://github.com/AgentWrapper) (formerly [ComposioHQ](https://github.com/ComposioHQ)) |
| **Copyright** | Copyright 2026 Untrivial |
| **License** | [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| **Relationship** | Mechanism inspiration and port map — **not** a fork of the AO product |

Agent Orchestrator is a daemon-backed orchestration product (control plane, UI, PR loop).
`autonomous-fleet` adopts selected **mechanisms** as portable validators, engine doctrine,
and coordinator obligations. We do **not** ship AO source code, the Electron UI, or the AO
daemon in this repository.

### Mechanisms adapted from Agent Orchestrator

| AO concept (indicative source) | What autonomous-fleet ships |
|---|---|
| Lifecycle `sendOnce` nudge dedup (`lifecycle/reactions.go`) | `nudge-state.json`, `scripts/lib/nudge_dedup.py`, `scripts/verify_nudge_dedup.py` |
| Stacked PR session status (`service/session/status.go`) | `pr-snapshot.json`, `scripts/lib/stacked_pr_status.py`, `scripts/verify_stacked_pr.py` |
| Hook pipeline `no_signal` grace (`service/session/status.go`) | `activity_hooks` adapter requires, `scripts/lib/hook_signal.py`, `scripts/verify_hook_signal.py` |
| Review run supersede on HEAD move | `sha-pin.json` / `sha-pins/*.json` `superseded` field, `verify_sha_pin.py` |
| Three-signal reconciliation + anti-flap `evidence_hash` | `engine.md` § SIGNAL RECONCILIATION, trace emission discipline |
| SHA-pin at PASS (`code-review-manager.ts`) | `sha-pin.json`, `scripts/verify_sha_pin.py` |
| Recovery / resume patterns | `scripts/recovery_scan.py` (advisory), `CONTINUE_WORKER` primitive |
| Dashboard attention zones | `scripts/render-dashboard.py` zone mapping (language borrowed) |

**Canonical port map (maintained):**
[`skills/autonomous-fleet-core/references/ao-adoptions.md`](skills/autonomous-fleet-core/references/ao-adoptions.md)

**Research context:**
[`docs/orchestration-landscape.md`](docs/orchestration-landscape.md)

### License note

Apache 2.0 governs Agent Orchestrator. `autonomous-fleet`'s MIT-licensed code that
re-expresses these mechanisms was written as a **clean-room port** (Python validators +
skill doctrine), informed by AO's public design. If you combine or redistribute AO
**source code** with this project, comply with Apache 2.0 for that code separately.

---

## Other peers (research credits, not code ports)

The orchestration landscape survey also studied these projects when positioning
`autonomous-fleet`. They are credited for **ideas and comparison**, not as vendored
dependencies unless explicitly named elsewhere in this repo:

- [omnigent](https://github.com/omnigent-ai/omnigent) — blast-radius policy patterns
- [container-use](https://github.com/dagger/container-use) — isolation transport
- [vibe-kanban](https://github.com/BloopAI/vibe-kanban) — trace/dashboard contract alignment

See [`docs/orchestration-landscape.md`](docs/orchestration-landscape.md) for the full peer set.

---

## Adding attribution

If you port a mechanism from another OSS project, add a row to this file (and `NOTICE` when
the upstream license requires retained notices), link the upstream license, and document the
port map in `skills/autonomous-fleet-core/references/` or `docs/`.