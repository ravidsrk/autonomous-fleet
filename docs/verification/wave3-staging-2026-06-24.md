# Wave 3 staging verification — 2026-06-24

Lane-0 record (VERIFY-AT-SCALE-IS-OPS): a human-initiated clean-room verification of the
Wave 3 mechanisms on published main, standing in for CI while GitHub Actions is billing-locked
(PRs #50 and #51 merged with `--admin` on green local gates; this record closes the
merged-but-unverified gap).

## Environment

- Fresh `git clone` of `origin/main` at `6028ccd` (Wave 3 code #50 + the docs sync #51).
- Fresh virtualenv, Python 3.14.6, deps from `requirements.txt` (pytest 8.3.4, coverage 7.14.3, PyYAML 6.0.2).
- Working tree clean (staging == exactly published main, not a dev checkout).

## Gate suite (CI-equivalent)

| Gate                          | Result                         |
| ----------------------------- | ------------------------------ |
| `validate-all.sh`             | All checks passed              |
| pytest                        | 918 passed                     |
| coverage (`--fail-under=100`) | 100% (3589 statements)         |
| mutation gate                 | 50 mutations: 50 caught, 0 survived, 0 stale |

## Live mechanism scenarios (real subprocesses, not unit tests)

| Scenario                                                              | Result |
| -------------------------------------------------------------------- | ------ |
| SHA-pin: HEAD == reviewed SHA -> no violation                        | PASS   |
| SHA-pin: branch HEAD moved -> REVIEWED flagged OUTDATED, names both shas | PASS   |
| Recovery scan: SCM-merged + ledger-not-merged -> partial / ESCALATE  | PASS   |
| Resume cap: RESUME_COUNT == 3 -> ESCALATE_TO_DECISIONS (not continue) | PASS   |
| Namespacing: per-run suffix applied, distinct run_ids -> distinct branches | PASS   |
| Trace lineage: COMMIT.parent_event resolves to the real SPAWN_WORKER id | PASS   |
| Reviewer sandbox: write to a tracked file under `--role reviewer` -> "Operation not permitted", file unchanged | PASS   |

7 / 7 scenarios pass. The reviewer sandbox was verified with the real macOS sandbox-exec
boundary, not the post-exec fallback: the OS denied the write.

## Verdict

Wave 3 is verified on staging. Main at `6028ccd` is sound: the gate suite reproduces green
on a clean clone + clean venv, and every Wave 3 mechanism behaves correctly end-to-end.

## Outstanding

The GitHub Actions billing lock is still active (account-level, unrelated to the code). This
record substitutes for the skipped CI; clearing the billing lock will let CI validate the
history on the next push.
