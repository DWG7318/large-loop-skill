import hashlib
import json
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
    ROOT / "glk" / "references" / "artifact-authority.md",
    ROOT / "glk" / "references" / "run-package-validation.md",
    ROOT / "glk" / "references" / "readiness-and-liveness.md",
    ROOT / "glk" / "references" / "supply-chain.md",
    ROOT / "glk" / "references" / "worker-wake.md",
    ROOT / "glk" / "references" / "run-patrol.md",
    ROOT / "glk" / "references" / "layered-progress.md",
    ROOT / "glk" / "references" / "cell-capacity.md",
]

CANONICAL_REPOSITORY = "https://github.com/DWG7318/large-loop-skill"
SIX_ROLES = [
    "Run Supervisor",
    "Worker",
    "Checker",
    "GO Verifier",
    "Run Verifier",
    "Owner",
]


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_version_is_310_everywhere():
    assert text(ROOT / "VERSION").strip() == "3.1.0"
    for path in [
        ROOT / "SPEC.md",
        ROOT / "SKILL.md",
        ROOT / "glk" / "SKILL.md",
        ROOT / "README.md",
        ROOT / "README.zh-CN.md",
        ROOT / "CHANGELOG.md",
        ROOT / "MIGRATION.md",
        ROOT / "VALIDATION-REPORT.md",
        ROOT / "glk" / "examples" / "appointment-run.yaml",
        ROOT / "MANIFEST.json",
        ROOT / "agents" / "openai.yaml",
    ]:
        assert "3.1.0" in text(path), path


def test_canonical_repository_and_skill_entrypoints_are_locked():
    manifest = json.loads(text(ROOT / "MANIFEST.json"))
    assert manifest["canonical_repository"] == CANONICAL_REPOSITORY
    assert manifest["invocation"] == "graph-loop-skill"
    assert manifest["version"] == "3.1.0"
    assert manifest["roles"] == SIX_ROLES
    assert text(ROOT / "SKILL.md") == text(ROOT / "glk" / "SKILL.md")
    for path in [ROOT / "SPEC.md", ROOT / "SKILL.md", ROOT / "README.md"]:
        assert CANONICAL_REPOSITORY in text(path), path


def test_six_roles_are_canonical_and_legacy_roles_are_not_normative():
    spec = text(ROOT / "SPEC.md")
    for role in SIX_ROLES:
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
        assert "READY" not in text(path).replace("GO_CANDIDATE_READY", ""), path


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


def test_confirmed_trace_binds_current_source_explicit_symptoms_and_selected_edges():
    spec = text(ROOT / "SPEC.md")
    assert "current immutable" in spec
    assert "current D2 receipt" in spec
    assert "symptom set is explicit" in spec
    assert "explicitly selects each traversed edge" in spec
    assert "Alternative reachable edges" in spec
    assert "reachability" in spec and "insufficient" in spec


def test_amendment_uses_typed_seed_kinds_and_rejects_unrelated_refs():
    spec = text(ROOT / "SPEC.md")
    assert all(kind in spec for kind in ["CANDIDATE", "EVIDENCE", "CLAIM_OR_OUTPUT"])
    assert "Unrelated refs fail closed" in spec
    amendment = yaml.safe_load(
        text(ROOT / "glk" / "templates" / "GRAPH_AMENDMENT.yaml")
    )
    assert amendment["impact_seeds"] == [
        {"kind": "CANDIDATE", "ref": "candidates/GO-002/v1"}
    ]
    assert amendment["source_go"] == "GO-002"
    assert amendment["source_disposition"] == "REWORK"
    source_item = next(
        item
        for item in amendment["impact_slice"]
        if item["go_id"] == amendment["source_go"]
    )
    assert source_item["disposition"] == amendment["source_disposition"]
    assert source_item["invalidated_candidate_refs"]
    assert len(source_item["invalidated_receipt_refs"]) == 3


def test_seed_kind_sets_minimum_source_disposition_without_widening_descendants():
    spec = text(ROOT / "SPEC.md")
    assert "CANDIDATE" in spec and "REWORK" in spec and "QUARANTINE" in spec
    assert "`REVERIFY` is forbidden" in spec
    assert "strictest source disposition" in spec
    assert "D0/D1/D2" in spec
    assert "do not widen downstream impact" in spec


def test_repaired_source_reuses_waiting_active_and_maximal_parallelism():
    combined = text(ROOT / "SPEC.md") + text(
        ROOT / "glk" / "references" / "causal-impact.md"
    )
    assert "WAITING_GO" in combined and "ACTIVE_GO" in combined
    assert "maximum-cardinality" in combined
    assert "same recalculation" in combined
    assert "READY" not in combined.replace("GO_CANDIDATE_READY", "")


def test_310_example_edges_use_complete_consumption_contracts():
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


def test_repository_and_run_validators_have_distinct_declared_scopes():
    repository_validator = text(ROOT / "glk" / "scripts" / "validate_glk.py")
    run_cli = text(ROOT / "glk" / "scripts" / "validate_run.py")
    run_validator = text(ROOT / "glk" / "scripts" / "run_validation.py")
    assert 'VALIDATION_SCOPE = "REPOSITORY_DISTRIBUTION"' in repository_validator
    assert 'RUN_VALIDATION_SCOPE = "RUN_PACKAGE"' in run_validator
    assert "RUN_VALIDATION_SCOPE" in run_cli
    assert "validate_loaded_run" in run_cli
    assert "validate_loaded_run" not in repository_validator


def test_method_lock_binds_the_real_declared_run_validator_bundle():
    manifest = json.loads(text(ROOT / "MANIFEST.json"))
    bundle = manifest["run_validator_bundle"]
    assert bundle["paths"] == [
        "glk/scripts/run_validation.py",
        "glk/scripts/validate_run.py",
    ]
    entries = [
        {
            "path": relative,
            "sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
        }
        for relative in bundle["paths"]
    ]
    actual = hashlib.sha256(
        json.dumps(entries, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert bundle["sha256"] == actual
    lock = yaml.safe_load(text(ROOT / "glk" / "templates" / "GLK_METHOD_LOCK.yaml"))
    assert lock["validator_sha256"] == actual


def test_310_surface_documents_authority_runtime_and_migration_boundaries():
    combined = "\n".join(text(path) for path in NORMATIVE)
    for marker in [
        "2.4 formal-use freeze",
        "resolve_binding",
        "verify_issuance",
        "verify_isolation",
        "check_liveness",
        "ten validation layers",
        "REPOSITORY_DISTRIBUTION",
        "RUN_PACKAGE",
        "derived non-authoritative",
        "required GO/D2",
        "required CELL/D1",
        "RUN_AUTHORITY_HOLD",
        "RUN_ARCHITECTURE_HOLD",
        "LCagent",
        "LCCoding",
        "Worker-only",
        "WAKE_ACK",
        "PENDING_WAKE",
        "gpt-5.6-luna",
        "UNAUTHORIZED_THREAD_PIN",
        "PIN_PROVENANCE_UNKNOWN",
        "CELL_CAPACITY_GATE",
        "SPLIT_REQUIRED",
        "CELL_OVERSIZE_SEVERE",
        "DELIVERED",
        "GO_CANDIDATE_READY",
    ]:
        assert marker in combined, marker
    assert "unproven 2.4" in combined and "current evidence" in combined


def test_glk_contains_no_runtime_or_credential_subsystem_implementation():
    forbidden_files = {
        "broker.py",
        "checkpoint.py",
        "credential_store.py",
        "replay.py",
        "runtime.py",
        "session_manager.py",
    }
    present = {
        path.name.lower()
        for path in (ROOT / "glk" / "scripts").glob("*.py")
    }
    assert forbidden_files.isdisjoint(present)


def test_310_has_worker_wake_patrol_progress_contract_and_capacity_surface():
    for relative in [
        "glk/scripts/graph_kernel.py",
        "glk/scripts/worker_wake.py",
        "glk/scripts/run_patrol.py",
        "glk/scripts/cell_capacity.py",
        "glk/references/worker-wake.md",
        "glk/references/run-patrol.md",
        "glk/references/layered-progress.md",
        "glk/references/cell-capacity.md",
    ]:
        assert (ROOT / relative).is_file(), relative


def test_superseded_construction_packets_are_history_only():
    superseded = (
        "docs/superpowers/plans/2026-07-29-glk-2.3.1.md",
        "docs/superpowers/plans/2026-07-30-glk-2.4.0.md",
        "docs/superpowers/plans/2026-08-03-glk-3.0.0-authority-and-run-validation-implementation.md",
        "docs/superpowers/specs/2026-08-03-glk-3.0.0-authority-and-run-validation-design.md",
        "docs/superpowers/plans/2026-08-04-glk-3.1.0-worker-wake-patrol-and-progress-implementation.md",
        "docs/superpowers/specs/2026-08-04-glk-3.1.0-worker-wake-patrol-and-progress-design.md",
    )
    present = tuple(relative for relative in superseded if (ROOT / relative).exists())
    assert present == (), f"superseded construction packets remain current: {present}"


def test_patrol_is_not_a_seventh_authority_role():
    manifest = json.loads(text(ROOT / "MANIFEST.json"))
    assert manifest["roles"] == SIX_ROLES
    combined = text(ROOT / "SPEC.md") + text(ROOT / "SKILL.md")
    assert "patrol is not a seventh" in combined
    assert "gpt-5.6-luna" in combined and "xhigh" in combined


def test_pin_is_owner_only_and_never_automatic():
    combined = text(ROOT / "SPEC.md") + text(ROOT / "glk" / "references" / "run-patrol.md")
    for marker in [
        "set_thread_pinned", "Owner", "UNAUTHORIZED_THREAD_PIN",
        "PIN_PROVENANCE_UNKNOWN", "must not unpin",
    ]:
        assert marker in combined


def test_capacity_and_progress_amendments_recompute_denominators():
    combined = text(ROOT / "SPEC.md") + text(ROOT / "glk" / "references" / "cell-capacity.md") + text(ROOT / "glk" / "references" / "layered-progress.md")
    assert "DEVICE_CAPACITY_PROFILE" in combined
    assert "CUMULATIVE_ENGINEERING_LOAD" in combined
    assert "CELL_CAPACITY_GATE" in combined
    assert "POST_DISPATCH_CELL_SPLIT" in combined
    assert "CELL_OVERSIZE_SEVERE" in combined
    assert "recompute" in combined and "denominator" in combined
