# Research notes (test-coverage dogfood, 2026-06-21)

Per engine-workers.md RESEARCH DISCIPLINE: log every external fact the build relies on with a source +
verified flag. This is a test-coverage mission over the repo's OWN python CLIs, so the expected
behaviors derive from in-repo code, not external sources. The discipline fires minimally here, which
is the honest case: when there is no stale-prone external fact, the gate is satisfied by recording
that the behavior was read from the code, not assumed.

| unknown | source | finding | status |
|---------|--------|---------|--------|
| what eval-campaign-edge.py should do | repo `scripts/eval-campaign-edge.py` + lib.fleet_outcome.eval_edge | --expr evaluates one edge; --campaign+--current-node picks next node from fleet-outcome metrics | verified (from code) |
| what mission_registry should return | repo `scripts/lib/mission_registry.py` | readiness_path/progress_path map known missions; fall back to docs/<m>-*.md for unknown | verified (from code) |
| what validate_fleet_outcome.py CLI should do | repo `scripts/validate_fleet_outcome.py` | exit 0 + OK on a valid readiness doc, exit 1 + FAIL on an invalid one | verified (from code) |
| pytest subprocess + capsys patterns are current | local pytest 8.3.4 (requirements.txt) | standard subprocess.run / monkeypatch.argv patterns valid | verified (installed version) |

unverified_assumptions: 0 (every behavior under test was read from the code, no external assumption).
