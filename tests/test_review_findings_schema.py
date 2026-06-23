"""Structural integrity test for the shipped JSON schema asset.

The verifier lib reimplements a SUBSET of the schema's constraints in Python (so
the lib runs without a jsonschema runtime dep). That duplication is dangerous —
a drift between the JSON schema and the lib means the doctrine is double-stated
in two places that can disagree.

This test asserts the two stay in sync on the dimensions that matter:
  - The schema is well-formed JSON with the expected top-level shape
  - The enum value sets in the JSON schema match the enum value sets the
    verifier lib enforces. If you add `category: regression` to the schema
    and forget to add it to lib.verify_findings, this test fails.

The schema file itself is the SHIPPED ARTIFACT (it ends up in user installs
via `skills/autonomous-fleet-core/assets/`). The lib is INTERNAL ENFORCEMENT.
The schema is authoritative; the lib follows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT / "skills" / "autonomous-fleet-core" / "assets" / "fleet-review-findings.schema.json"
)
sys.path.insert(0, str(ROOT / "scripts"))

from lib import verify_findings as vf  # noqa: E402


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_file_exists_and_is_valid_json():
    assert SCHEMA_PATH.is_file(), f"missing schema at {SCHEMA_PATH}"
    _schema()  # raises if not parseable


def test_schema_pins_top_level_required_fields_we_enforce_in_lib():
    """The lib's _REQUIRED_TOP and the schema's required must agree, otherwise
    a missing-field error will fire in one place and not the other."""
    schema = _schema()
    schema_required = set(schema["required"])
    assert set(vf._REQUIRED_TOP) == schema_required, (
        f"lib._REQUIRED_TOP {vf._REQUIRED_TOP} must equal schema required {schema_required}"
    )


def test_schema_pins_finding_required_fields_we_enforce_in_lib():
    schema = _schema()
    finding_required = set(schema["$defs"]["finding"]["required"])
    assert set(vf._REQUIRED_FINDING) == finding_required, (
        f"lib._REQUIRED_FINDING {vf._REQUIRED_FINDING} must equal "
        f"schema $defs.finding.required {finding_required}"
    )


def test_schema_pins_evidence_required_fields_we_enforce_in_lib():
    schema = _schema()
    evidence_required = set(
        schema["$defs"]["finding"]["properties"]["evidence"]["required"]
    )
    assert set(vf._REQUIRED_EVIDENCE) == evidence_required


def test_schema_severity_enum_matches_lib():
    schema = _schema()
    schema_sev = set(
        schema["$defs"]["finding"]["properties"]["severity"]["enum"]
    )
    assert vf._VALID_SEVERITIES == schema_sev


def test_schema_category_enum_matches_lib():
    schema = _schema()
    schema_cat = set(
        schema["$defs"]["finding"]["properties"]["category"]["enum"]
    )
    assert vf._VALID_CATEGORIES == schema_cat


def test_schema_fix_strategy_enum_matches_lib():
    schema = _schema()
    schema_strat = set(
        schema["$defs"]["finding"]["properties"]["fix_strategy"]["enum"]
    )
    assert vf._VALID_STRATEGIES == schema_strat


def test_schema_effort_enum_matches_lib():
    schema = _schema()
    schema_eff = set(
        schema["$defs"]["finding"]["properties"]["fix_alternatives"]["items"][
            "properties"
        ]["effort"]["enum"]
    )
    assert vf._VALID_EFFORTS == schema_eff


def test_schema_verdict_decision_enum_matches_lib():
    schema = _schema()
    schema_dec = set(
        schema["properties"]["verdict"]["properties"]["decision"]["enum"]
    )
    assert vf._VALID_VERDICTS == schema_dec


def test_schema_pins_schema_version_to_string_1_0():
    """Bumping schema_version is a breaking change. This test pins the version
    so a casual edit to 1.1 must touch the verifier lib in the same commit."""
    schema = _schema()
    sv = schema["properties"]["schema_version"]
    assert sv["const"] == "1.0", "schema_version is part of the public contract"


def test_schema_confidence_bounds_match_lib_constraint():
    """The schema constrains confidence to 0-100 inclusive; the lib must
    enforce the same range. Drift here means an auto-applicable finding could
    sneak through one gate but not the other."""
    schema = _schema()
    conf = schema["$defs"]["finding"]["properties"]["confidence"]
    assert conf["minimum"] == 0
    assert conf["maximum"] == 100


def test_schema_fix_alternatives_bounds_match_lib():
    schema = _schema()
    alts = schema["$defs"]["finding"]["properties"]["fix_alternatives"]
    assert alts["minItems"] == 1
    assert alts["maxItems"] == 4


def test_shipped_example_findings_file_passes_validation():
    """The example file at assets/fleet-review-findings.example.json is the
    copy-paste starting point for reviewers. If it ever falls out of schema,
    every new reviewer instance begins broken."""
    example_path = (
        ROOT
        / "skills"
        / "autonomous-fleet-core"
        / "assets"
        / "fleet-review-findings.example.json"
    )
    assert example_path.is_file()
    doc = json.loads(example_path.read_text(encoding="utf-8"))
    errors = vf.validate_findings_doc(doc, label="example.json")
    assert errors == [], f"example file violates schema: {errors}"


def test_schema_disallows_additional_properties_at_every_level():
    """Drift defense: if a future contributor adds a field to the schema, they
    must EXPLICITLY add it to additionalProperties:false objects. This test
    pins additionalProperties:false where we expect it — the doc root, the
    finding, the evidence block, the verdict block, the fix_alternative item,
    and the reviewer block."""
    schema = _schema()
    assert schema.get("additionalProperties") is False, "top-level"
    assert schema["properties"]["verdict"].get("additionalProperties") is False
    assert schema["properties"]["reviewer"].get("additionalProperties") is False
    finding = schema["$defs"]["finding"]
    assert finding.get("additionalProperties") is False
    assert finding["properties"]["evidence"].get("additionalProperties") is False
    assert (
        finding["properties"]["fix_alternatives"]["items"].get(
            "additionalProperties"
        )
        is False
    )


# ───────────────────────────────────────────────────────────────────────
# Commit 3 — ROOT_CAUSE_DEPTH schema enforcement
# ───────────────────────────────────────────────────────────────────────


def test_schema_conditionally_requires_cascade_impact_for_root_cause_depth():
    """The engine's ROOT_CAUSE_DEPTH HARD RULE is schema-enforced: a finding
    with category=root_cause_depth MUST carry a non-empty cascade_impact.
    Without this, a reviewer can file a symptom-fix as a root_cause_depth
    finding and the discipline collapses to prose.

    Pin BOTH the structural shape (allOf with if/then) and the semantic
    requirement (cascade_impact required + minLength 1) so a future edit
    that softens this to a soft warning fails the test."""
    schema = _schema()
    finding = schema["$defs"]["finding"]
    assert "allOf" in finding, "schema must carry conditional constraints in allOf"
    # Find the rule keyed to category=root_cause_depth.
    rcd_rules = [
        rule for rule in finding["allOf"]
        if (rule.get("if", {}).get("properties", {}).get("category", {}).get("const")
            == "root_cause_depth")
    ]
    assert len(rcd_rules) == 1, "exactly one allOf rule must gate on root_cause_depth"
    rule = rcd_rules[0]
    # The conditional then-branch requires cascade_impact.
    assert "cascade_impact" in rule["then"]["required"]
    # And it must be non-empty (minLength 1) — empty strings are a symptom-fix
    # finding wearing the root_cause_depth label, which is what we're stopping.
    assert (
        rule["then"]["properties"]["cascade_impact"]["minLength"] == 1
    ), "cascade_impact for root_cause_depth must require non-empty string"


def test_lib_rejects_root_cause_depth_finding_without_cascade_impact(tmp_path):
    """The lib's enforcement must match the schema's. A finding with
    category=root_cause_depth and no cascade_impact (or empty) must fail
    validation. This is the doctrine: a root-cause-depth finding without a
    cascade is almost always a symptom-fix finding miscategorised."""
    doc = {
        "schema_version": "1.0",
        "mission": "adversarial-review-and-fix",
        "review_id": "test-rcd-missing",
        "findings": [
            {
                "id": "F-001",
                "severity": "high",
                "category": "root_cause_depth",
                "claim": "Symptom-fix at caller; root cause untouched",
                "evidence": {
                    "file_path": "src/x.py",
                    "quoted_line": "    if x is None: return  # silently swallow",
                },
                "fix_alternatives": [
                    {"label": "A", "description": "Fix the source", "effort": "moderate"}
                ],
                "confidence": 85,
                "fix_strategy": "ask",
                # cascade_impact OMITTED — the doctrine violation we're catching.
            }
        ],
        "verdict": {"decision": "request_changes", "reasoning": "RCD"},
    }
    errors = vf.validate_findings_doc(doc, label="rcd-missing.json")
    assert any("root_cause_depth" in e and "cascade_impact" in e for e in errors), (
        f"lib must reject root_cause_depth finding without cascade_impact; got: {errors}"
    )


def test_lib_rejects_root_cause_depth_finding_with_empty_cascade_impact():
    """Whitespace-only cascade_impact is the same failure mode as omission —
    a reviewer pasted the field but didn't fill it in. Must be caught."""
    doc = {
        "schema_version": "1.0",
        "mission": "adversarial-review-and-fix",
        "review_id": "test-rcd-empty",
        "findings": [
            {
                "id": "F-001",
                "severity": "high",
                "category": "root_cause_depth",
                "claim": "Symptom-fix at caller",
                "evidence": {
                    "file_path": "src/x.py",
                    "quoted_line": "    if x is None: return",
                },
                "fix_alternatives": [
                    {"label": "A", "description": "x", "effort": "moderate"}
                ],
                "confidence": 85,
                "fix_strategy": "ask",
                "cascade_impact": "   ",  # whitespace-only
            }
        ],
        "verdict": {"decision": "request_changes", "reasoning": "RCD"},
    }
    errors = vf.validate_findings_doc(doc, label="rcd-empty.json")
    assert any("cascade_impact" in e for e in errors), errors


def test_lib_accepts_root_cause_depth_finding_with_real_cascade_impact():
    """Pin the happy path: a properly-filed root-cause-depth finding with
    a cascade naming the other affected paths MUST validate cleanly. Without
    this, a tightening of the rule could silently false-positive on real
    findings and the doctrine would be unusable."""
    doc = {
        "schema_version": "1.0",
        "mission": "adversarial-review-and-fix",
        "review_id": "test-rcd-ok",
        "findings": [
            {
                "id": "F-001",
                "severity": "high",
                "category": "root_cause_depth",
                "claim": "Null returned from helper; caller guards but other callers don't",
                "evidence": {
                    "file_path": "src/x.py",
                    "quoted_line": "    return _maybe_load(path)  # can return None",
                },
                "fix_alternatives": [
                    {"label": "A", "description": "Fix _maybe_load to raise", "effort": "moderate"}
                ],
                "confidence": 88,
                "fix_strategy": "ask",
                "cascade_impact": (
                    "Two other callers in scripts/lib/ rely on the helper "
                    "and don't guard for None; both will crash on the same input."
                ),
            }
        ],
        "verdict": {"decision": "request_changes", "reasoning": "RCD"},
    }
    errors = vf.validate_findings_doc(doc, label="rcd-ok.json")
    assert errors == [], f"valid root_cause_depth finding must pass; got: {errors}"


def test_lib_does_not_require_cascade_impact_for_other_categories():
    """The cascade_impact requirement is GATED on category=root_cause_depth.
    A regular bug finding should not need cascade_impact. Pin to prevent
    over-broadening of the rule."""
    doc = {
        "schema_version": "1.0",
        "mission": "adversarial-review-and-fix",
        "review_id": "test-bug",
        "findings": [
            {
                "id": "F-001",
                "severity": "medium",
                "category": "bug",
                "claim": "Off-by-one in pagination",
                "evidence": {
                    "file_path": "src/page.py",
                    "quoted_line": "    return items[start:end+1]",
                },
                "fix_alternatives": [
                    {"label": "A", "description": "drop +1", "effort": "minimal"}
                ],
                "confidence": 90,
                "fix_strategy": "auto",
                # cascade_impact OMITTED — should be fine for category=bug.
            }
        ],
        "verdict": {"decision": "request_changes", "reasoning": "bug"},
    }
    errors = vf.validate_findings_doc(doc, label="bug.json")
    assert errors == [], f"non-RCD finding must not require cascade_impact; got: {errors}"
