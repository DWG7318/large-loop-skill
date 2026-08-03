import dataclasses
import importlib.util
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "glk" / "schemas" / "glk.schema.json"
TEMPLATE_DIR = ROOT / "glk" / "templates"
MODEL_PATH = ROOT / "glk" / "scripts" / "artifact_model.py"

REQUIRED_ENVELOPE = {
    "schema_version",
    "artifact_type",
    "artifact_id",
    "run_id",
    "graph_id",
    "graph_version",
    "candidate_id",
    "candidate_sha256",
    "issuer_binding_ref",
    "execution_context_ref",
    "evidence_refs",
    "provenance_ref",
    "issued_at",
}

EXPECTED_AUTHORITIES = {
    "RUN_CONTRACT": "LCCODING_OWNER_GATEWAY",
    "GLK_METHOD_LOCK": "LCCODING_OWNER_GATEWAY",
    "PROVENANCE_ADAPTER_PROFILE": "TRUSTED_EXECUTION_ENVIRONMENT",
    "ROLE_BINDING": "TRUSTED_RUNTIME_REGISTRATION",
    "GRAPH_BASELINE": "RUN_SUPERVISOR",
    "CELL_MANIFEST": "RUN_SUPERVISOR",
    "CELL_MANIFEST_AMENDMENT": "RUN_SUPERVISOR",
    "GO_CANDIDATE_CLOSURE": "WORKER",
    "D0_RECEIPT": "WORKER",
    "D1_RECEIPT": "CHECKER",
    "SUPERVISOR_ADMISSION": "RUN_SUPERVISOR",
    "PREFLIGHT_ADMISSION": "RUN_SUPERVISOR",
    "RUN_PACKAGE_INDEX": "RUN_SUPERVISOR",
    "D2_RECEIPT": "GO_VERIFIER",
    "GRAPH_EVENT": "RUN_SUPERVISOR",
    "MONITOR_CONTROL": "RUN_SUPERVISOR",
    "D3_RECEIPT": "RUN_VERIFIER",
    "OWNER_ACCEPTANCE": "OWNER",
    "SECURITY_HANDOFF": "RUN_SUPERVISOR",
    "PROVENANCE_ATTESTATION": "TRUSTED_EXTERNAL_ADAPTER",
    "LIVENESS_ATTESTATION": "TRUSTED_EXTERNAL_ADAPTER",
}

SUPERVISOR_ARTIFACTS = {
    "GRAPH_BASELINE",
    "CELL_MANIFEST",
    "CELL_MANIFEST_AMENDMENT",
    "SUPERVISOR_ADMISSION",
    "PREFLIGHT_ADMISSION",
    "RUN_PACKAGE_INDEX",
    "GRAPH_EVENT",
    "MONITOR_CONTROL",
    "SECURITY_HANDOFF",
}

TEMPLATES = {
    "GLK_METHOD_LOCK.yaml": "glk_method_lock",
    "PROVENANCE_ADAPTER_PROFILE.yaml": "provenance_adapter_profile",
    "ROLE_BINDING.yaml": "role_binding_300",
    "CELL_MANIFEST.yaml": "cell_manifest",
    "CELL_MANIFEST_AMENDMENT.yaml": "cell_manifest_amendment",
    "D0_RECEIPT.yaml": "d0_receipt",
    "D1_RECEIPT.yaml": "d1_receipt",
    "GO_CANDIDATE_CLOSURE.yaml": "go_candidate_closure",
    "SUPERVISOR_ADMISSION.yaml": "supervisor_admission",
    "PREFLIGHT_ADMISSION.yaml": "preflight_admission",
    "RUN_PACKAGE_INDEX.yaml": "run_package_index",
    "D2_RECEIPT.yaml": "d2_receipt",
    "GRAPH_EVENT.yaml": "graph_event",
    "MONITOR_CONTROL.yaml": "monitor_control",
    "D3_RECEIPT.yaml": "d3_receipt",
    "OWNER_ACCEPTANCE.yaml": "owner_acceptance_300",
    "SECURITY_HANDOFF.yaml": "security_handoff_300",
}

CLOSED_OUTCOMES = {
    "D0_RECEIPT.yaml": "outcome",
    "D1_RECEIPT.yaml": "verdict",
    "SUPERVISOR_ADMISSION.yaml": "decision",
    "PREFLIGHT_ADMISSION.yaml": "decision",
    "D2_RECEIPT.yaml": "verdict",
    "GRAPH_EVENT.yaml": "event_type",
    "MONITOR_CONTROL.yaml": "monitor_state",
    "D3_RECEIPT.yaml": "verdict",
    "OWNER_ACCEPTANCE.yaml": "owner_verdict",
    "SECURITY_HANDOFF.yaml": "status",
}

NON_EMPTY_EVIDENCE = {
    "D0_RECEIPT.yaml",
    "D1_RECEIPT.yaml",
    "SUPERVISOR_ADMISSION.yaml",
    "PREFLIGHT_ADMISSION.yaml",
    "D2_RECEIPT.yaml",
    "D3_RECEIPT.yaml",
}


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def load_model():
    if not MODEL_PATH.is_file():
        pytest.fail("GLK 3.0 artifact model is missing")
    spec = importlib.util.spec_from_file_location("glk_artifact_model", MODEL_PATH)
    if spec is None or spec.loader is None:
        pytest.fail("cannot load GLK 3.0 artifact model")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_template(filename):
    path = TEMPLATE_DIR / filename
    if not path.is_file():
        pytest.fail(f"missing GLK 3.0 template: {filename}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate_definition(schema, definition, instance):
    if definition not in schema["$defs"]:
        pytest.fail(f"missing GLK 3.0 schema definition: {definition}")
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"#/$defs/{definition}",
        "$defs": schema["$defs"],
    }
    Draft202012Validator(wrapper).validate(instance)


def test_formal_registry_has_exact_unique_authorities_and_six_roles():
    model = load_model()
    require_equal(set(model.FORMAL_TYPES), set(EXPECTED_AUTHORITIES), "formal types")
    require_equal(
        {name: authority.sole_issuer for name, authority in model.FORMAL_TYPES.items()},
        EXPECTED_AUTHORITIES,
        "sole issuers",
    )
    require_equal(
        set(model.ROLE_TYPES),
        {"RUN_SUPERVISOR", "WORKER", "CHECKER", "GO_VERIFIER", "RUN_VERIFIER", "OWNER"},
        "role types",
    )
    require_equal(
        set(model.authorized_artifact_types("RUN_SUPERVISOR")),
        SUPERVISOR_ARTIFACTS,
        "Supervisor artifact authority",
    )
    require(
        {"D0_RECEIPT", "D1_RECEIPT", "D2_RECEIPT", "D3_RECEIPT"}.isdisjoint(
            model.authorized_artifact_types("RUN_SUPERVISOR")
        ),
        "Run Supervisor must have no D0-D3 issuance authority",
    )


@pytest.mark.parametrize(
    "artifact_type",
    [
        "CELL_RECEIPT",
        "GO_RECEIPT",
        "RUN_RECEIPT",
        "VALIDATION_REPORT",
        "PREFLIGHT_REPORT",
        "SIMULATION_REPORT",
        "PROGRESS_PROJECTION",
    ],
)
def test_legacy_mixed_and_derived_objects_are_not_formal(artifact_type):
    model = load_model()
    require(not model.is_formal_type(artifact_type), f"{artifact_type} became formal")
    with pytest.raises(model.UnknownArtifactType):
        model.artifact_authority(artifact_type)


def test_artifact_models_are_immutable_and_hash_canonical_bytes():
    model = load_model()
    envelope = model.ArtifactEnvelope(
        schema_version="3.0.0",
        artifact_type="D0_RECEIPT",
        artifact_id="D0-CELL-001-V1",
        run_id="RUN-001",
        graph_id="GRAPH-RUN-001",
        graph_version=1,
        candidate_id="CANDIDATE-CELL-001-V1",
        candidate_sha256="a" * 64,
        issuer_binding_ref="ROLE-WORKER-GO-001",
        execution_context_ref="CONTEXT-WORKER-GO-001",
        evidence_refs=("evidence/CELL-001/d0.json",),
        provenance_ref="attestations/D0-CELL-001-V1.json",
        issued_at="2026-08-03T01:00:00Z",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        envelope.run_id = "RUN-FORGED"
    first = model.canonical_sha256({"b": 2, "a": 1})
    second = model.canonical_sha256({"a": 1, "b": 2})
    require_equal(first, second, "canonical digest")
    require_equal(len(first), 64, "canonical digest length")


def test_all_task1_templates_have_a_valid_300_envelope_and_schema():
    schema = load_schema()
    for filename, definition in TEMPLATES.items():
        instance = load_template(filename)
        require_equal(instance["schema_version"], "3.0.0", f"{filename} version")
        require_equal(
            set(instance) & REQUIRED_ENVELOPE,
            REQUIRED_ENVELOPE,
            f"{filename} common envelope",
        )
        validate_definition(schema, definition, instance)


@pytest.mark.parametrize("filename,field", CLOSED_OUTCOMES.items())
def test_technical_and_control_outcomes_are_closed_enums(filename, field):
    schema = load_schema()
    instance = load_template(filename)
    instance[field] = "SUPERVISOR-SAYS-PASS"
    with pytest.raises(ValidationError):
        validate_definition(schema, TEMPLATES[filename], instance)


@pytest.mark.parametrize("filename", sorted(NON_EMPTY_EVIDENCE))
def test_r04_technical_and_admission_evidence_cannot_be_empty(filename):
    schema = load_schema()
    instance = load_template(filename)
    instance["evidence_refs"] = []
    with pytest.raises(ValidationError):
        validate_definition(schema, TEMPLATES[filename], instance)


@pytest.mark.parametrize("filename", TEMPLATES)
@pytest.mark.parametrize("invalid_time", ["not-a-time", "1970-01-01T00:00:00Z"])
def test_r06_formal_timestamps_reject_invalid_and_sentinel_values(filename, invalid_time):
    schema = load_schema()
    instance = load_template(filename)
    instance["issued_at"] = invalid_time
    with pytest.raises(ValidationError):
        validate_definition(schema, TEMPLATES[filename], instance)
