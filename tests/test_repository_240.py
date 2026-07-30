from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
NORMATIVE = [
    ROOT / "SPEC.md",
    ROOT / "SKILL.md",
    ROOT / "glk" / "SKILL.md",
    ROOT / "glk" / "references" / "canonical-dictionary.md",
    ROOT / "glk" / "references" / "scheduling.md",
    ROOT / "glk" / "references" / "state-machine.md",
    ROOT / "glk" / "references" / "causal-impact.md",
]


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_version_is_240_everywhere():
    assert text(ROOT / "VERSION").strip() == "2.4.0"
    for path in [
        ROOT / "SPEC.md",
        ROOT / "SKILL.md",
        ROOT / "README.md",
        ROOT / "glk" / "examples" / "appointment-run.yaml",
    ]:
        assert "2.4.0" in text(path)


def test_six_roles_are_canonical_and_legacy_roles_are_not_normative():
    spec = text(ROOT / "SPEC.md")
    roles = [
        "Run Supervisor",
        "Worker",
        "Checker",
        "GO Verifier",
        "Run Verifier",
        "Owner",
    ]
    for role in roles:
        assert role in spec
    for legacy_role in ["Grapher", "Planner", "Router"]:
        assert legacy_role not in spec


def test_every_run_requires_a_fresh_supervisor_instance():
    spec = text(ROOT / "SPEC.md")
    assert "fresh Run Supervisor instance" in spec
    assert "must not reuse" in spec
    assert "run_supervisor_binding" in text(ROOT / "glk" / "templates" / "RUN_CONTRACT.yaml")


def test_normative_model_has_no_ready_state_or_queue():
    for path in NORMATIVE:
        assert "READY" not in text(path), path


def test_graph_activates_a_maximal_safe_set_instead_of_serializing():
    spec = text(ROOT / "SPEC.md")
    assert "maximal safe ACTIVE_GO set" in spec
    assert "arbitrary serialization" in spec
    assert "fake dependency" in spec


def test_dag_d0_d3_and_owner_acceptance_boundaries_remain():
    spec = text(ROOT / "SPEC.md")
    assert "acyclic" in spec
    assert all(marker in spec for marker in ["D0", "D1", "D2", "D3"])
    assert "GO Verifier" in spec and "Run Verifier" in spec
    assert "LOOP_OWNER_ACCEPTED" in spec
    assert "centralized vulnerability closure" in spec


def test_causal_source_and_symptom_are_incident_annotations_not_go_types():
    spec = text(ROOT / "SPEC.md")
    assert "CAUSAL_SOURCE" in spec
    assert "DOWNSTREAM_SYMPTOM" in spec
    assert "incident annotations" in spec
    assert "any position in the DAG" in spec
    assert "new GO type" in spec


def test_edges_bind_actual_consumption_for_reverse_causal_slicing():
    spec = text(ROOT / "SPEC.md")
    assert "source_claim_or_output_refs" in spec
    assert "target_input_or_assumption_refs" in spec
    assert "consumption_evidence_refs" in spec
    assert "reverse causal slice" in spec
    assert "actual consumption" in spec
    assert "unbound incoming dependency" in spec
    assert "call graph" in spec and "data-flow graph" in spec


def test_only_confirmed_trace_can_drive_minimal_invalidation():
    spec = text(ROOT / "SPEC.md")
    assert "SUSPECTED" in spec and "CONFIRMED" in spec
    assert all(
        marker in spec
        for marker in ["UNAFFECTED", "REVERIFY", "REWORK", "QUARANTINE"]
    )
    assert "current-validity" in spec
    assert "append-only" in spec
    assert "full-graph replay" in spec


def test_repaired_source_reuses_waiting_active_and_maximal_parallelism():
    combined = text(ROOT / "SPEC.md") + text(
        ROOT / "glk" / "references" / "causal-impact.md"
    )
    assert "WAITING_GO" in combined and "ACTIVE_GO" in combined
    assert "maximum-cardinality" in combined
    assert "same recalculation" in combined
    assert "READY" not in combined


def test_240_example_edges_use_complete_consumption_contracts():
    example = yaml.safe_load(
        text(ROOT / "glk" / "examples" / "appointment-run.yaml")
    )
    required = {
        "source",
        "target",
        "justification",
        "source_claim_or_output_refs",
        "target_input_or_assumption_refs",
        "consumption_evidence_refs",
    }
    assert example["graph"]["edges"]
    assert all(set(edge) == required for edge in example["graph"]["edges"])
