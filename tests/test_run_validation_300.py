import copy
import dataclasses
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

from glk300_fixtures import read_index, sha256_file, write_json, write_valid_run, write_index


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "glk" / "scripts"
TEMPLATES = ROOT / "glk" / "templates"
RUN_PACKAGE_PATH = SCRIPTS / "run_package.py"
RUN_VALIDATION_PATH = SCRIPTS / "run_validation.py"
PROVENANCE_PATH = SCRIPTS / "provenance.py"
RUN_MODEL_PATH = SCRIPTS / "run_model.py"

TEMPLATE_TYPES = (
    "GLK_METHOD_LOCK",
    "PROVENANCE_ADAPTER_PROFILE",
    "ROLE_BINDING",
    "CELL_MANIFEST",
    "D0_RECEIPT",
    "D1_RECEIPT",
    "GO_CANDIDATE_CLOSURE",
    "SUPERVISOR_ADMISSION",
    "D2_RECEIPT",
    "GRAPH_EVENT",
    "MONITOR_CONTROL",
    "D3_RECEIPT",
    "OWNER_ACCEPTANCE",
)

ISSUER_BY_TYPE = {
    "D0_RECEIPT": "ROLE-WORKER-GO-001",
    "D1_RECEIPT": "ROLE-CHECKER-GO-001",
    "D2_RECEIPT": "ROLE-GO-VERIFIER-GO-001",
    "D3_RECEIPT": "ROLE-RUN-VERIFIER-RUN-001",
}

ROLE_BINDINGS = {
    "ROLE-RUN-001-SUPERVISOR": "RUN_SUPERVISOR",
    "ROLE-WORKER-GO-001": "WORKER",
    "ROLE-CHECKER-GO-001": "CHECKER",
    "ROLE-GO-VERIFIER-GO-001": "GO_VERIFIER",
    "ROLE-RUN-VERIFIER-RUN-001": "RUN_VERIFIER",
    "ROLE-OWNER-RUN-001": "OWNER",
}

ISSUABLE_BY_ROLE = {
    "RUN_SUPERVISOR": (
        "GRAPH_BASELINE",
        "CELL_MANIFEST",
        "SUPERVISOR_ADMISSION",
        "GRAPH_EVENT",
        "MONITOR_CONTROL",
        "RUN_PACKAGE_INDEX",
        "WORKER_CHECKER_WAKE_BINDING",
        "DEVICE_CAPACITY_PROFILE",
        "CUMULATIVE_ENGINEERING_LOAD",
        "CELL_WORK_ESTIMATE",
        "CELL_CAPACITY_GATE",
        "CELL_PLAN_AMENDMENT",
        "SUPERVISOR_PROGRESS_EVENT",
    ),
    "WORKER": (
        "D0_RECEIPT",
        "GO_CANDIDATE_CLOSURE",
        "WAKE_ATTEMPT",
        "PENDING_WAKE",
        "CELL_SCOPE_EXCEEDED",
    ),
    "CHECKER": ("D1_RECEIPT", "WAKE_ACK", "CHECKER_PROGRESS_EVENT"),
    "GO_VERIFIER": ("D2_RECEIPT",),
    "RUN_VERIFIER": ("D3_RECEIPT",),
    "OWNER": ("OWNER_ACCEPTANCE",),
}


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def load_module(path: Path, name: str, missing_message: str):
    if not path.is_file():
        pytest.fail(missing_message)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


def load_prerequisites():
    package = load_module(RUN_PACKAGE_PATH, "glk_run_package_validation_tests", "run package loader is missing")
    provenance = load_module(PROVENANCE_PATH, "glk_provenance_validation_tests", "provenance boundary is missing")
    sys.modules["provenance"] = provenance
    run_model = sys.modules.get("run_model")
    if run_model is None:
        run_model = load_module(RUN_MODEL_PATH, "run_model", "run model is missing")
        sys.modules["run_model"] = run_model
    return package, provenance, run_model


def load_validation():
    return load_module(
        RUN_VALIDATION_PATH,
        "glk_run_validation_300",
        "GLK 3.0 cross-artifact run validation engine is missing",
    )


def _template(artifact_type):
    return yaml.safe_load((TEMPLATES / f"{artifact_type}.yaml").read_text(encoding="utf-8"))


def _candidate_hash(candidate_id):
    return hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()


def _manifest_closure_sha256_300(manifest):
    payload = {
        "run_id": manifest["run_id"],
        "graph_id": manifest["graph_id"],
        "graph_version": manifest["graph_version"],
        "go_id": manifest["go_id"],
        "manifest_id": manifest["manifest_id"],
        "manifest_version": manifest["manifest_version"],
        "go_contract_sha256": manifest["go_contract_sha256"],
        "required_cells": sorted(manifest["required_cells"], key=lambda cell: cell["cell_id"]),
        "prior_manifest_sha256": manifest["prior_manifest_sha256"],
    }
    return _candidate_hash(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


def _go_candidate_sha256_300(manifest, selected_cells):
    payload = {
        "go_id": manifest["go_id"],
        "manifest_id": manifest["manifest_id"],
        "manifest_version": manifest["manifest_version"],
        "manifest_closure_sha256": manifest["closure_sha256"],
        "selected_cells": sorted(selected_cells, key=lambda item: item["cell_id"]),
    }
    return _candidate_hash(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


def _all_formal_paths(root):
    return tuple(
        sorted(
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".json", ".yaml", ".yml"}
            and path.relative_to(root).parts[0] not in {"indexes", "evidence"}
        )
    )


def _artifact_path(root, artifact_type, occurrence=0):
    matches = []
    for path in _all_formal_paths(root):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data.get("artifact_type") == artifact_type:
            matches.append(path)
    if occurrence >= len(matches):
        pytest.fail(f"missing fixture artifact {artifact_type}[{occurrence}]")
    return matches[occurrence]


def _artifact(root, artifact_type, occurrence=0):
    path = _artifact_path(root, artifact_type, occurrence)
    return path, yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_artifact(path, value):
    write_json(path, value)


def _reindex(fixture):
    index = read_index(fixture.index_path)
    referenced = set(index.get("evidence_refs", []))
    for path in _all_formal_paths(fixture.root):
        referenced.update(_evidence_references(yaml.safe_load(path.read_text(encoding="utf-8"))))
    for path in tuple(sorted((fixture.root / "evidence").rglob("*"))):
        if path.is_file() and path.relative_to(fixture.root).as_posix() not in referenced:
            path.unlink()
    formal_entries = []
    ledger_heads = {}
    for path in _all_formal_paths(fixture.root):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        digest = sha256_file(path)
        formal_entries.append(
            {
                "path": path.relative_to(fixture.root).as_posix(),
                "sha256": digest,
                "artifact_type": data["artifact_type"],
            }
        )
        ledger_heads[data["artifact_id"]] = digest
    evidence_paths = tuple(sorted(path for path in (fixture.root / "evidence").rglob("*") if path.is_file()))
    index["formal_artifacts"] = formal_entries
    index["evidence_objects"] = [
        {"path": path.relative_to(fixture.root).as_posix(), "sha256": sha256_file(path)}
        for path in evidence_paths
    ]
    index["ledger_heads"] = ledger_heads
    write_index(fixture.index_path, index)


def _preserved_envelope(original, template, *, candidate_id=None, issuer_binding_ref=None):
    value = copy.deepcopy(template)
    for field in (
        "artifact_id",
        "run_id",
        "graph_id",
        "graph_version",
        "evidence_refs",
        "provenance_ref",
        "issued_at",
    ):
        value[field] = original[field]
    value["candidate_id"] = candidate_id or original["candidate_id"]
    value["candidate_sha256"] = _candidate_hash(value["candidate_id"])
    if issuer_binding_ref is not None:
        value["issuer_binding_ref"] = issuer_binding_ref
    return value


def _add_evidence(root, relative, label):
    path = root / relative
    write_json(path, {"subject": label, "result": "PASS"})
    return relative


def _evidence_references(value):
    references = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if (key == "evidence_refs" or key.endswith("_evidence_refs")) and isinstance(item, list):
                references.update(ref for ref in item if isinstance(ref, str) and ref.startswith("evidence/"))
            references.update(_evidence_references(item))
    elif isinstance(value, list):
        for item in value:
            references.update(_evidence_references(item))
    return references


def _materialize_referenced_evidence(root):
    references = set()
    for path in _all_formal_paths(root):
        references.update(_evidence_references(yaml.safe_load(path.read_text(encoding="utf-8"))))
    for reference in sorted(references):
        path = root / reference
        if not path.exists():
            write_json(path, {"subject": reference, "result": "PASS"})


def _admission_for_target(root, target_path):
    target_ref = target_path.relative_to(root).as_posix()
    for path in _all_formal_paths(root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if value.get("artifact_type") == "SUPERVISOR_ADMISSION" and value.get("admitted_artifact_ref") == target_ref:
            return path, value
    return None


def _add_supervisor_admission(root, target_path, *, suffix, issued_at):
    target = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    admission_id = f"SUPERVISOR-ADMISSION-{suffix}"
    evidence_ref = _add_evidence(root, f"evidence/admissions/{admission_id}.json", admission_id)
    admission = copy.deepcopy(_template("SUPERVISOR_ADMISSION"))
    admission.update(
        {
            "artifact_id": admission_id,
            "candidate_id": target["candidate_id"],
            "candidate_sha256": target["candidate_sha256"],
            "issuer_binding_ref": "ROLE-RUN-001-SUPERVISOR",
            "execution_context_ref": "CONTEXT-RUN-001-SUPERVISOR",
            "evidence_refs": [evidence_ref],
            "provenance_ref": f"attestations/{admission_id}.json",
            "issued_at": issued_at,
            "admission_id": admission_id,
            "admitted_artifact_ref": target_path.relative_to(root).as_posix(),
            "admitted_artifact_sha256": sha256_file(target_path),
            "decision": "ADMITTED",
            "failure_codes": [],
        }
    )
    path = root / "admissions" / f"{admission_id}.json"
    write_json(path, admission)
    return path, admission


def _ensure_supervisor_admission(root, target_path, *, suffix=None, issued_at="2026-08-03T03:40:00Z"):
    existing = _admission_for_target(root, target_path)
    if existing is not None:
        return existing
    return _add_supervisor_admission(
        root,
        target_path,
        suffix=suffix or yaml.safe_load(target_path.read_text(encoding="utf-8"))["artifact_id"],
        issued_at=issued_at,
    )


def _sync_supervisor_admission(root, target_path):
    path, admission = _ensure_supervisor_admission(root, target_path)
    target = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    admission["candidate_id"] = target["candidate_id"]
    admission["candidate_sha256"] = target["candidate_sha256"]
    admission["admitted_artifact_sha256"] = sha256_file(target_path)
    admission["decision"] = "ADMITTED"
    admission["failure_codes"] = []
    write_json(path, admission)
    return path


def _add_role_binding(root, role_ref, role_type, ordinal):
    template = _template("ROLE_BINDING")
    artifact_id = f"ROLE-BINDING-{role_type}-{ordinal}-V1"
    evidence_ref = _add_evidence(root, f"evidence/roles/{artifact_id}.json", artifact_id)
    template.update(
        {
            "artifact_id": artifact_id,
            "candidate_id": role_ref,
            "candidate_sha256": _candidate_hash(role_ref),
            "issuer_binding_ref": "TRUSTED-RUNTIME-REGISTRATION-001",
            "execution_context_ref": f"CONTEXT-REGISTRATION-{ordinal}",
            "evidence_refs": [evidence_ref],
            "provenance_ref": f"attestations/{artifact_id}.json",
            "role_binding_id": role_ref,
            "role_type": role_type,
            "go_id": "GO-001" if role_type in {"WORKER", "CHECKER", "GO_VERIFIER"} else None,
            "instance_id": f"INSTANCE-{role_type}-{ordinal}",
            "conversation_ref": f"conversation/RUN-001/{role_type}/{ordinal}",
            "workspace_ref": f"workspace/RUN-001/{role_type}/{ordinal}",
            "evidence_root": f"evidence/roles/{role_type}/{ordinal}",
            "capability_profile_id": f"CAPABILITY-{role_type}",
        }
    )
    path = root / "bindings" / f"{artifact_id}.json"
    _write_artifact(path, template)


def _prepare_validation_fixture(tmp_path):
    fixture = write_valid_run(tmp_path, cells_per_go=1, go_count=1)

    for artifact_type in TEMPLATE_TYPES:
        path, original = _artifact(fixture.root, artifact_type)
        issuer = ISSUER_BY_TYPE.get(artifact_type)
        value = _preserved_envelope(original, _template(artifact_type), issuer_binding_ref=issuer)
        if artifact_type == "GLK_METHOD_LOCK":
            value.update(
                schema_version="3.0.0",
                candidate_id="METHOD-GLK-3.0.0",
                candidate_sha256=_candidate_hash("METHOD-GLK-3.0.0"),
                release_tag="v3.0.0",
                method_version="3.0.0",
                validator_version="3.0.0",
            )
        _write_artifact(path, value)

    supervisor_path, supervisor = _artifact(fixture.root, "ROLE_BINDING")
    supervisor.update(
        {
            "artifact_id": "ROLE-BINDING-RUN-001-SUPERVISOR-V1",
            "candidate_id": "ROLE-RUN-001-SUPERVISOR",
            "candidate_sha256": _candidate_hash("ROLE-RUN-001-SUPERVISOR"),
            "role_binding_id": "ROLE-RUN-001-SUPERVISOR",
            "capability_profile_id": "CAPABILITY-RUN_SUPERVISOR",
        }
    )
    _write_artifact(supervisor_path, supervisor)
    for ordinal, (role_ref, role_type) in enumerate(tuple(ROLE_BINDINGS.items())[1:], start=2):
        _add_role_binding(fixture.root, role_ref, role_type, ordinal)

    run_contract_evidence = _add_evidence(
        fixture.root, "evidence/contracts/RUN-CONTRACT-RUN-001-V1.json", "RUN-CONTRACT-RUN-001-V1"
    )
    run_contract = {
        "schema_version": "3.0.0",
        "artifact_type": "RUN_CONTRACT",
        "artifact_id": "RUN-CONTRACT-RUN-001-V1",
        "run_id": "RUN-001",
        "graph_id": "GRAPH-RUN-001",
        "graph_version": 1,
        "candidate_id": "CANDIDATE-RUN-001-V1",
        "candidate_sha256": _candidate_hash("CANDIDATE-RUN-001-V1"),
        "issuer_binding_ref": "ROLE-OWNER-RUN-001",
        "execution_context_ref": "CONTEXT-OWNER-RUN-001",
        "evidence_refs": [run_contract_evidence],
        "provenance_ref": "attestations/RUN-CONTRACT-RUN-001-V1.json",
        "issued_at": "2026-08-03T01:00:00Z",
        "run_supervisor_binding": {
            "role_binding_id": "ROLE-RUN-001-SUPERVISOR",
            "role_type": "RUN_SUPERVISOR",
            "run_id": "RUN-001",
        },
    }
    _write_artifact(fixture.root / "contracts" / "RUN-CONTRACT-RUN-001-V1.json", run_contract)

    manifest_path, manifest = _artifact(fixture.root, "CELL_MANIFEST")
    cell_id = "GO-001-CELL-001"
    cell_candidate = f"CANDIDATE-{cell_id}-V1"
    cell_candidate_sha = _candidate_hash(cell_candidate)
    manifest["go_id"] = "GO-001"
    manifest["required_cells"] = [
        {
            "cell_id": cell_id,
            "cell_contract_sha256": "c" * 64,
            "required": True,
        }
    ]
    manifest["closure_sha256"] = _manifest_closure_sha256_300(manifest)
    _write_artifact(manifest_path, manifest)

    d0_path, d0 = _artifact(fixture.root, "D0_RECEIPT")
    d0.update(
        {
            "candidate_id": cell_candidate,
            "candidate_sha256": cell_candidate_sha,
            "go_id": "GO-001",
            "cell_id": cell_id,
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "cell_contract_sha256": manifest["required_cells"][0]["cell_contract_sha256"],
            "dispatch_admission_refs": ["SUPERVISOR-ADMISSION-D2-V1"],
        }
    )
    _write_artifact(d0_path, d0)
    d0_digest = sha256_file(d0_path)

    d1_path, d1 = _artifact(fixture.root, "D1_RECEIPT")
    d1.update(
        {
            "candidate_id": cell_candidate,
            "candidate_sha256": cell_candidate_sha,
            "go_id": "GO-001",
            "cell_id": cell_id,
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "cell_contract_sha256": manifest["required_cells"][0]["cell_contract_sha256"],
            "d0_artifact_sha256": d0_digest,
        }
    )
    _write_artifact(d1_path, d1)
    d1_digest = sha256_file(d1_path)

    selected_cell = {
        "cell_id": cell_id,
        "candidate_id": cell_candidate,
        "candidate_sha256": cell_candidate_sha,
        "d0_artifact_sha256": d0_digest,
        "d1_artifact_sha256": d1_digest,
    }
    closure_path, closure = _artifact(fixture.root, "GO_CANDIDATE_CLOSURE")
    closure.update(
        {
            "candidate_id": "CANDIDATE-GO-001-G1",
            "candidate_sha256": _go_candidate_sha256_300(manifest, [selected_cell]),
            "go_id": "GO-001",
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "selected_cells": [selected_cell],
        }
    )
    _write_artifact(closure_path, closure)
    closure_digest = sha256_file(closure_path)

    d2_path, d2 = _artifact(fixture.root, "D2_RECEIPT")
    d2.update(
        {
            "candidate_id": closure["candidate_id"],
            "candidate_sha256": closure["candidate_sha256"],
            "go_id": "GO-001",
            "go_candidate_closure_sha256": closure_digest,
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "required_cell_tuples": [selected_cell],
        }
    )
    _write_artifact(d2_path, d2)
    d2_digest = sha256_file(d2_path)

    admission_path, admission = _artifact(fixture.root, "SUPERVISOR_ADMISSION")
    admission.update(
        {
            "candidate_id": d2["candidate_id"],
            "candidate_sha256": d2["candidate_sha256"],
            "admitted_artifact_ref": d2_path.relative_to(fixture.root).as_posix(),
            "admitted_artifact_sha256": d2_digest,
        }
    )
    _write_artifact(admission_path, admission)

    event_path, event = _artifact(fixture.root, "GRAPH_EVENT")
    event.update(
        {
            "trigger_artifact_ref": d2_path.relative_to(fixture.root).as_posix(),
            "trigger_artifact_sha256": d2_digest,
            "waiting_go_ids": [],
            "active_go_ids": ["GO-001"],
        }
    )
    _write_artifact(event_path, event)

    d3_path, d3 = _artifact(fixture.root, "D3_RECEIPT")
    d3["required_go_ids"] = ["GO-001"]
    d3["admitted_d2_artifact_sha256s"] = [d2_digest]
    _write_artifact(d3_path, d3)
    d3_digest = sha256_file(d3_path)

    owner_path, owner = _artifact(fixture.root, "OWNER_ACCEPTANCE")
    owner["admitted_d3_artifact_sha256"] = d3_digest
    _write_artifact(owner_path, owner)

    _add_supervisor_admission(
        fixture.root,
        d0_path,
        suffix="D0-GO-001-CELL-001-V1",
        issued_at="2026-08-03T03:40:00Z",
    )
    _add_supervisor_admission(
        fixture.root,
        d1_path,
        suffix="D1-GO-001-CELL-001-V1",
        issued_at="2026-08-03T03:41:00Z",
    )
    _add_supervisor_admission(
        fixture.root,
        closure_path,
        suffix="CLOSURE-GO-001-V1",
        issued_at="2026-08-03T03:42:00Z",
    )

    _materialize_referenced_evidence(fixture.root)
    _reindex(fixture)
    return fixture


def _refresh_lineage(fixture, *, keep_d1_reference=False):
    d0_path, d0 = _artifact(fixture.root, "D0_RECEIPT")
    d1_path, d1 = _artifact(fixture.root, "D1_RECEIPT")
    if not keep_d1_reference:
        d1["d0_artifact_sha256"] = sha256_file(d0_path)
        _write_artifact(d1_path, d1)
    selected = {
        "cell_id": d0["cell_id"],
        "candidate_id": d0["candidate_id"],
        "candidate_sha256": d0["candidate_sha256"],
        "d0_artifact_sha256": sha256_file(d0_path),
        "d1_artifact_sha256": sha256_file(d1_path),
    }
    closure_path, closure = _artifact(fixture.root, "GO_CANDIDATE_CLOSURE")
    closure["selected_cells"] = [selected]
    manifest = _artifact(fixture.root, "CELL_MANIFEST")[1]
    closure["candidate_sha256"] = _go_candidate_sha256_300(manifest, [selected])
    _write_artifact(closure_path, closure)
    d2_path, d2 = _artifact(fixture.root, "D2_RECEIPT")
    d2["candidate_id"] = closure["candidate_id"]
    d2["candidate_sha256"] = closure["candidate_sha256"]
    d2["go_candidate_closure_sha256"] = sha256_file(closure_path)
    d2["required_cell_tuples"] = [selected]
    _write_artifact(d2_path, d2)
    d2_digest = sha256_file(d2_path)
    _sync_supervisor_admission(fixture.root, d0_path)
    _sync_supervisor_admission(fixture.root, d1_path)
    _sync_supervisor_admission(fixture.root, closure_path)
    d2_admission = _admission_for_target(fixture.root, d2_path)
    if d2_admission is None:
        pytest.fail("fixture D2 admission is missing")
    admission_path, admission = d2_admission
    admission["admitted_artifact_sha256"] = d2_digest
    admission["candidate_id"] = d2["candidate_id"]
    admission["candidate_sha256"] = d2["candidate_sha256"]
    _write_artifact(admission_path, admission)
    event_path, event = _artifact(fixture.root, "GRAPH_EVENT")
    event["trigger_artifact_sha256"] = d2_digest
    _write_artifact(event_path, event)
    d3_path, d3 = _artifact(fixture.root, "D3_RECEIPT")
    d3["admitted_d2_artifact_sha256s"] = [d2_digest]
    _write_artifact(d3_path, d3)
    owner_path, owner = _artifact(fixture.root, "OWNER_ACCEPTANCE")
    owner["admitted_d3_artifact_sha256"] = sha256_file(d3_path)
    _write_artifact(owner_path, owner)
    _reindex(fixture)


def _mutate(
    fixture,
    artifact_type,
    mutate,
    occurrence=0,
    *,
    preserve_lineage=False,
    keep_d1_reference=False,
):
    path, value = _artifact(fixture.root, artifact_type, occurrence)
    mutate(value)
    _write_artifact(path, value)
    if preserve_lineage:
        _refresh_lineage(fixture, keep_d1_reference=keep_d1_reference)
    else:
        _reindex(fixture)
    return value["artifact_id"]


def _signed_request(provenance, request_type, **values):
    request = request_type(request_digest="0" * 64, **values)
    return dataclasses.replace(request, request_digest=provenance.request_digest_for(request))


class TrustedAdapterFixture:
    def __init__(self, provenance, run_model, *, role_overrides=None, collide_isolation=False):
        self.p = provenance
        self.rm = run_model
        self.role_overrides = role_overrides or {}
        self.collide_isolation = collide_isolation
        self.calls = []

    def _common(self, request):
        return {
            "adapter_contract_version": request.adapter_contract_version,
            "request_digest": request.request_digest,
            "binding_ref": request.binding_ref,
            "run_id": request.run_id,
            "scope": request.scope,
            "artifact_sha256": request.artifact_sha256,
            "status": "VERIFIED",
            "evidence_ref": f"attestations/{request.binding_ref}.json",
            "observed_at": "2026-08-03T04:00:00Z",
        }

    def resolve_binding(self, request):
        self.calls.append(("resolve_binding", request))
        role_type = self.role_overrides.get(request.binding_ref, ROLE_BINDINGS.get(request.binding_ref, request.expected_role))
        profile_role = role_type if role_type in ISSUABLE_BY_ROLE else "WORKER"
        profile = self.rm.RoleCapabilityProfile(
            profile_id=f"CAPABILITY-{profile_role}",
            role_type=profile_role,
            issuable_artifact_types=ISSUABLE_BY_ROLE[profile_role],
            held_issuance_artifact_types=(),
            invocable_issuance_artifact_types=(),
        )
        return self.p.BindingResult(
            **self._common(request),
            role_type=role_type,
            instance_id=f"INSTANCE-{request.binding_ref}",
            context_id=f"CONTEXT-{request.binding_ref}",
            workspace_id=f"WORKSPACE-{request.binding_ref}",
            evidence_root=f"evidence/roles/{request.binding_ref}",
            capability_profile=profile,
        )

    def verify_issuance(self, request):
        self.calls.append(("verify_issuance", request))
        return self.p.IssuanceResult(**self._common(request))

    def verify_isolation(self, request):
        self.calls.append(("verify_isolation", request))
        snapshots = []
        for ordinal, binding_ref in enumerate(request.binding_refs):
            suffix = "COLLISION" if self.collide_isolation else str(ordinal)
            snapshots.append(
                self.p.IsolationBindingSnapshot(
                    binding_ref=binding_ref,
                    conversation_ref=f"conversation/{suffix}",
                    context_ref=f"context/{suffix}",
                    workspace_ref=f"workspace/{suffix}",
                    runtime_state_ref=f"runtime-state/{suffix}",
                    evidence_root=f"evidence-root/{suffix}",
                    decision_input_ref=f"decision-input/{suffix}",
                )
            )
        return self.p.IsolationResult(
            **self._common(request),
            verified_dimensions=request.required_dimensions,
            binding_snapshots=tuple(snapshots),
        )

    def check_liveness(self, request):
        self.calls.append(("check_liveness", request))
        return self.p.LivenessResult(**self._common(request), deadline=request.deadline)


def _validate(tmp_path, mutation=None, *, adapter_options=None):
    fixture = _prepare_validation_fixture(tmp_path)
    artifact_ref = mutation(fixture) if mutation else None
    package_module, provenance, run_model = load_prerequisites()
    loaded = package_module.load_run_package(fixture.root)
    validation = load_validation()
    adapter = TrustedAdapterFixture(provenance, run_model, **(adapter_options or {}))
    report = validation.validate_loaded_run(loaded, adapter)
    return report, artifact_ref, adapter, loaded


def _issue_triples(report):
    return {(issue.code, issue.layer, issue.artifact_ref) for issue in report.issues}


@pytest.mark.parametrize(
    ("receipt_type", "expected_code"),
    [
        ("D0_RECEIPT", "R01_SUPERVISOR_D0_AUTHORITY"),
        ("D1_RECEIPT", "R02_SUPERVISOR_D1_AUTHORITY"),
        ("D2_RECEIPT", "R03_SUPERVISOR_D2_D3_AUTHORITY"),
        ("D3_RECEIPT", "R03_SUPERVISOR_D2_D3_AUTHORITY"),
    ],
)
def test_R01_R02_R03_supervisor_cannot_issue_technical_receipts(tmp_path, receipt_type, expected_code):
    def mutation(fixture):
        return _mutate(
            fixture,
            receipt_type,
            lambda value: value.__setitem__("issuer_binding_ref", "ROLE-RUN-001-SUPERVISOR"),
            preserve_lineage=True,
        )

    report, artifact_ref, adapter, _ = _validate(tmp_path, mutation)
    require((expected_code, 4, artifact_ref) in _issue_triples(report), "missing stable technical authority issue")
    require("RUN_AUTHORITY_HOLD" in report.holds, "technical authority violation must hold the Run")
    require(not any(name == "verify_issuance" and call.artifact_type == receipt_type for name, call in adapter.calls), "forbidden Supervisor path reached verify_issuance")


@pytest.mark.parametrize("artifact_type", ["D0_RECEIPT", "D1_RECEIPT", "SUPERVISOR_ADMISSION", "D2_RECEIPT", "D3_RECEIPT"])
def test_R04_empty_evidence_fails_at_schema_layer(tmp_path, artifact_type):
    def mutation(fixture):
        return _mutate(
            fixture,
            artifact_type,
            lambda value: value.__setitem__("evidence_refs", []),
            preserve_lineage=True,
        )

    report, artifact_ref, _, _ = _validate(tmp_path, mutation)
    require(("R04_EMPTY_EVIDENCE", 1, artifact_ref) in _issue_triples(report), "empty evidence did not fail at layer 1")


def test_R05_invented_receipt_digest_fails_lineage_after_integrity_passes(tmp_path):
    def mutation(fixture):
        return _mutate(
            fixture,
            "D1_RECEIPT",
            lambda value: value.__setitem__("d0_artifact_sha256", "9" * 64),
            preserve_lineage=True,
            keep_d1_reference=True,
        )

    report, artifact_ref, _, loaded = _validate(tmp_path, mutation)
    require(bool(loaded.index_head_sha256), "real package loader did not accept rebuilt index")
    require(("R05_UNRESOLVED_RECEIPT_LINEAGE", 5, artifact_ref) in _issue_triples(report), "invented receipt digest did not reach lineage layer")


def test_R06_arbitrary_verdict_is_rejected_by_schema_layer(tmp_path):
    def mutation(fixture):
        return _mutate(
            fixture,
            "D2_RECEIPT",
            lambda value: value.__setitem__("verdict", "SUPERVISOR_SAYS_PASS"),
            preserve_lineage=True,
        )

    report, artifact_ref, _, _ = _validate(tmp_path, mutation)
    require(("R06_VERDICT_INVALID", 1, artifact_ref) in _issue_triples(report), "arbitrary verdict was not rejected")


def test_R06_sentinel_issued_at_is_rejected_by_schema_layer(tmp_path):
    def mutation(fixture):
        return _mutate(
            fixture,
            "D0_RECEIPT",
            lambda value: value.__setitem__("issued_at", "1970-01-01T00:00:00Z"),
            preserve_lineage=True,
        )

    report, artifact_ref, _, _ = _validate(tmp_path, mutation)
    require(("R06_TIMESTAMP_INVALID", 1, artifact_ref) in _issue_triples(report), "sentinel timestamp was not rejected")


def test_R06_validator_closed_verdict_sets_exactly_match_schema_enums():
    validation = load_validation()
    schema = json.loads((ROOT / "glk" / "schemas" / "glk.schema.json").read_text(encoding="utf-8"))
    for artifact_type, (field, validator_values) in sorted(validation.VERDICT_FIELDS.items()):
        definition = validation.SCHEMA_DEF_BY_TYPE[artifact_type]
        schema_values = frozenset(schema["$defs"][definition]["properties"][field]["enum"])
        require_equal(validator_values, schema_values, f"{artifact_type}.{field} enum parity")


@pytest.mark.parametrize(
    "owner_verdict",
    [
        "LOOP_OWNER_ACCEPTED",
        "LOOP_PRODUCT_REWORK",
        "PRODUCT_DEFINITION_CHANGE",
        "NEW_FEATURE_REQUEST",
    ],
)
def test_R06_all_schema_owner_verdicts_are_validator_legal(tmp_path, owner_verdict):
    def mutation(fixture):
        return _mutate(
            fixture,
            "OWNER_ACCEPTANCE",
            lambda value: value.__setitem__("owner_verdict", owner_verdict),
        )

    report, artifact_ref, _, _ = _validate(tmp_path, mutation)
    owner_issues = [issue for issue in report.issues if issue.artifact_ref == artifact_ref]
    require(not any(issue.code == "R06_VERDICT_INVALID" for issue in owner_issues), f"schema-legal Owner verdict rejected: {owner_verdict}")
    require_equal(owner_issues, [], f"schema-legal Owner verdict issues: {owner_verdict}")


def test_R06_schema_unknown_owner_rejection_is_not_validator_legal(tmp_path):
    validation = load_validation()
    _, validator_values = validation.VERDICT_FIELDS["OWNER_ACCEPTANCE"]
    require("LOOP_OWNER_REJECTED" not in validator_values, "schema-unknown Owner verdict is in validator closed set")

    def mutation(fixture):
        return _mutate(
            fixture,
            "OWNER_ACCEPTANCE",
            lambda value: value.__setitem__("owner_verdict", "LOOP_OWNER_REJECTED"),
        )

    report, artifact_ref, _, _ = _validate(tmp_path, mutation)
    owner_codes = {issue.code for issue in report.issues if issue.artifact_ref == artifact_ref}
    require(bool(owner_codes & {"R06_VERDICT_INVALID", "SCHEMA_INVALID"}), "schema-unknown Owner verdict was accepted")


def test_R07_run_contract_and_embedded_supervisor_run_id_must_match(tmp_path):
    def mutation(fixture):
        return _mutate(fixture, "RUN_CONTRACT", lambda value: value["run_supervisor_binding"].__setitem__("run_id", "RUN-OTHER"))

    report, artifact_ref, _, _ = _validate(tmp_path, mutation)
    require(("R07_RUN_BINDING_SCOPE_MISMATCH", 3, artifact_ref) in _issue_triples(report), "Run/Supervisor scope mismatch was not rejected")


def test_R09_free_role_string_from_adapter_is_rejected(tmp_path):
    report, artifact_ref, _, _ = _validate(
        tmp_path,
        lambda fixture: _artifact(fixture.root, "D0_RECEIPT")[1]["artifact_id"],
        adapter_options={"role_overrides": {"ROLE-WORKER-GO-001": "WORKERISH"}},
    )
    require(("R09_UNTRUSTED_ROLE_STRING", 4, artifact_ref) in _issue_triples(report), "free role string was trusted")


def test_R10_checker_and_worker_context_workspace_collision_is_rejected(tmp_path):
    report, artifact_ref, _, _ = _validate(
        tmp_path,
        lambda fixture: _artifact(fixture.root, "D1_RECEIPT")[1]["artifact_id"],
        adapter_options={"collide_isolation": True},
    )
    require(("R10_ISOLATION_NOT_PROVEN", 4, artifact_ref) in _issue_triples(report), "false Worker/Checker isolation was trusted")


def test_valid_real_package_returns_frozen_derived_pass_report_without_mutation(tmp_path):
    fixture = _prepare_validation_fixture(tmp_path)
    before = tuple((path, path.read_bytes()) for path in sorted(fixture.root.rglob("*")) if path.is_file())
    package_module, provenance, run_model = load_prerequisites()
    loaded = package_module.load_run_package(fixture.root)
    validation = load_validation()
    report = validation.validate_loaded_run(loaded, TrustedAdapterFixture(provenance, run_model))
    after = tuple((path, path.read_bytes()) for path in sorted(fixture.root.rglob("*")) if path.is_file())
    require_equal(report.status, "PASS", "valid report status")
    require_equal(report.issues, (), "valid report issues")
    require_equal(before, after, "validator disk mutation")
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.status = "FAIL"


def test_first_structural_failure_blocks_dependent_checks_but_collects_unrelated_issues_stably(tmp_path):
    def mutation(fixture):
        d0_ref = _mutate(
            fixture,
            "D0_RECEIPT",
            lambda value: (value.__setitem__("evidence_refs", []), value.__setitem__("issuer_binding_ref", "ROLE-RUN-001-SUPERVISOR")),
            preserve_lineage=True,
        )
        _mutate(fixture, "RUN_CONTRACT", lambda value: value["run_supervisor_binding"].__setitem__("run_id", "RUN-OTHER"))
        return d0_ref

    report, d0_ref, _, _ = _validate(tmp_path, mutation)
    d0_issues = [issue for issue in report.issues if issue.artifact_ref == d0_ref]
    require_equal([(issue.code, issue.layer) for issue in d0_issues], [("R04_EMPTY_EVIDENCE", 1)], "D0 first-failure gating")
    require(any(issue.code == "R07_RUN_BINDING_SCOPE_MISMATCH" for issue in report.issues), "unrelated artifact issue was not collected")
    require_equal(tuple(report.issues), tuple(sorted(report.issues, key=lambda issue: (issue.layer, issue.artifact_ref, issue.code))), "stable issue order")
