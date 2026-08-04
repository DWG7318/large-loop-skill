import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest
import yaml

import glk300_fixtures as fixtures
import test_run_validation_300 as rv


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "glk" / "scripts"
TEMPLATES = ROOT / "glk" / "templates"
NEW_TYPES = (
    "WORKER_CHECKER_WAKE_BINDING",
    "DEVICE_CAPACITY_PROFILE",
    "CUMULATIVE_ENGINEERING_LOAD",
    "CELL_WORK_ESTIMATE",
    "CELL_CAPACITY_GATE",
)


def require(condition, message):
    if not condition:
        pytest.fail(message)


@pytest.fixture
def modules():
    sys.path.insert(0, str(SCRIPTS))
    for name in ("run_package", "run_validation"):
        sys.modules.pop(name, None)
    try:
        yield importlib.import_module("run_package"), importlib.import_module("run_validation")
    finally:
        sys.path.remove(str(SCRIPTS))


def _template(name):
    return yaml.safe_load((TEMPLATES / f"{name}.yaml").read_text(encoding="utf-8"))


def _write_artifact(root, value):
    path = root / "controls" / f"{value['artifact_id']}.json"
    fixtures.write_json(path, value)
    evidence_refs = set()

    def collect(current, key=None):
        if isinstance(current, dict):
            for child_key, child in current.items():
                collect(child, child_key)
        elif isinstance(current, (list, tuple)):
            if key == "evidence_refs" or (isinstance(key, str) and key.endswith("_evidence_refs")):
                evidence_refs.update(
                    item
                    for item in current
                    if isinstance(item, str) and item.startswith("evidence/")
                )
            for child in current:
                collect(child, key)

    collect(value)
    for evidence_ref in evidence_refs:
        fixtures.write_json(root / evidence_ref, {"artifact_id": value["artifact_id"], "observed": True})
    return path


def _all_formal(root):
    return tuple(
        sorted(
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".json", ".yaml", ".yml"}
            and path.relative_to(root).parts[0] not in {"indexes", "evidence", "simulation"}
        )
    )


def _reindex(case):
    formal = _all_formal(case.root)
    document = fixtures._index_document(
        case.root,
        formal,
        tuple(sorted(path for path in (case.root / "evidence").rglob("*") if path.is_file())),
        version=1,
        prior_index_sha256=None,
        suffix="v1",
    )
    fixtures.write_index(case.index_path, document)


def _operational_case(tmp_path):
    case = rv._prepare_validation_fixture(tmp_path)
    root = case.root

    method_lock_path = _artifact_path(root, "GLK_METHOD_LOCK")
    historical_lock = yaml.safe_load(method_lock_path.read_text(encoding="utf-8"))
    for evidence_ref in historical_lock.get("evidence_refs", ()):
        evidence = root / evidence_ref
        if evidence.is_file():
            evidence.unlink()
    current_lock = _template("GLK_METHOD_LOCK")
    fixtures.write_json(method_lock_path, current_lock)
    for evidence_ref in current_lock["evidence_refs"]:
        fixtures.write_json(
            root / evidence_ref,
            {"artifact_id": current_lock["artifact_id"], "observed": True},
        )

    old_monitor = next(
        path
        for path in _all_formal(root)
        if yaml.safe_load(path.read_text(encoding="utf-8")).get("artifact_type") == "MONITOR_CONTROL"
    )
    old_monitor_value = yaml.safe_load(old_monitor.read_text(encoding="utf-8"))
    for evidence_ref in old_monitor_value.get("evidence_refs", ()):
        (root / evidence_ref).unlink()
    monitor = _template("MONITOR_CONTROL")
    old_monitor.unlink()
    _write_artifact(root, monitor)

    d0_path = _artifact_path(root, "D0_RECEIPT")
    d0 = yaml.safe_load(d0_path.read_text(encoding="utf-8"))
    d1_path = _artifact_path(root, "D1_RECEIPT")
    d1 = yaml.safe_load(d1_path.read_text(encoding="utf-8"))
    manifest_path = _artifact_path(root, "CELL_MANIFEST")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    closure_path = _artifact_path(root, "GO_CANDIDATE_CLOSURE")
    d2_path = _artifact_path(root, "D2_RECEIPT")
    graph_event_path = _artifact_path(root, "GRAPH_EVENT")
    d3_path = _artifact_path(root, "D3_RECEIPT")
    owner_path = _artifact_path(root, "OWNER_ACCEPTANCE")

    values = {name: _template(name) for name in NEW_TYPES}
    estimate = values["CELL_WORK_ESTIMATE"]
    estimate.update(go_id=d0["go_id"], cell_id=d0["cell_id"])
    binding = values["WORKER_CHECKER_WAKE_BINDING"]
    binding.update(
        go_id=d0["go_id"],
        cell_id=d0["cell_id"],
        required_cell_count=len(manifest["required_cells"]),
        manifest_id=manifest["manifest_id"],
        manifest_version=manifest["manifest_version"],
        delivery_candidate_id=d0["candidate_id"],
        delivery_candidate_sha256=d0["candidate_sha256"],
    )
    paths = {name: _write_artifact(root, value) for name, value in values.items()}
    gate_digest = fixtures.sha256_file(paths["CELL_CAPACITY_GATE"])
    binding["capacity_gate_sha256"] = gate_digest
    fixtures.write_json(paths["WORKER_CHECKER_WAKE_BINDING"], binding)

    attempts = []
    wake_message = (
        f"GO {d0['go_id']} CELL 1/{len(manifest['required_cells'])} 已交付，请检查"
    )
    wake_message_sha256 = hashlib.sha256(wake_message.encode("utf-8")).hexdigest()
    for level in (1, 2, 3):
        attempt = _template("WAKE_ATTEMPT")
        attempt["artifact_id"] = f"WAKE-ATTEMPT-GO-001-CELL-001-R1-L{level}"
        attempt["candidate_id"] = attempt["artifact_id"]
        attempt.update(go_id=d0["go_id"], cell_id=d0["cell_id"])
        attempt["level"] = level
        attempt["message"] = wake_message
        attempt["message_sha256"] = wake_message_sha256
        attempt["outcome"] = "FAILED"
        attempt["error_codes"] = ["WAKE_ACK_TIMEOUT"]
        attempt["evidence_refs"] = [f"evidence/wake/attempt-l{level}.json"]
        attempts.append(_write_artifact(root, attempt))
    pending = _template("PENDING_WAKE")
    pending.update(go_id=d0["go_id"], cell_id=d0["cell_id"])
    pending["message_sha256"] = wake_message_sha256
    pending["attempt_refs"] = [path.relative_to(root).as_posix() for path in attempts]
    _write_artifact(root, pending)

    _add_progress_events(
        case,
        manifest_path=manifest_path,
        manifest=manifest,
        d0=d0,
        d1_path=d1_path,
        d1=d1,
        closure_path=closure_path,
        d2_path=d2_path,
        graph_event_path=graph_event_path,
        d3_path=d3_path,
        owner_path=owner_path,
    )

    if hasattr(case, "index_path"):
        _reindex(case)
    return case


def _add_progress_events(
    case,
    *,
    manifest_path,
    manifest,
    d0,
    d1_path,
    d1,
    closure_path,
    d2_path,
    graph_event_path,
    d3_path,
    owner_path,
):
    root = case.root
    required_count = len(manifest["required_cells"])
    common_checker = dict(
        go_id=d0["go_id"],
        cell_id=d0["cell_id"],
        round_id="ROUND-01",
        cell_ordinal=1,
        required_cell_count=required_count,
        manifest_id=manifest["manifest_id"],
        manifest_version=manifest["manifest_version"],
        plan_id="CELL-PLAN-GO-001",
        plan_version=1,
        accepted_cell_count=required_count,
    )
    checker = _template("CHECKER_PROGRESS_EVENT")
    checker.update(
        **common_checker,
        trigger_artifact_ref=d1_path.relative_to(root).as_posix(),
        trigger_artifact_sha256=fixtures.sha256_file(d1_path),
        d1_verdict=d1["verdict"],
        state="D1_ACCEPTED",
        progress_sequence=2,
        message=f"{d0['go_id']} CELL验收 {required_count}/{required_count}，GO候选待形成",
    )
    _write_artifact(root, checker)

    milestone = copy.deepcopy(checker)
    milestone.update(
        artifact_id="CHECKER-PROGRESS-GO-001-CANDIDATE-V1",
        candidate_id="CHECKER-PROGRESS-GO-001-CANDIDATE-V1",
        event_id="CHECKER-PROGRESS-GO-001-CANDIDATE-V1",
        event_kind="GO_CANDIDATE_MILESTONE",
        trigger_artifact_ref=closure_path.relative_to(root).as_posix(),
        trigger_artifact_sha256=fixtures.sha256_file(closure_path),
        d1_verdict="NONE",
        state="GO_CANDIDATE_READY",
        progress_sequence=3,
        message=f"GO 1/1；本GO CELL {required_count}/{required_count}已验收；当前状态=GO_CANDIDATE_READY",
        evidence_refs=["evidence/progress/checker-go-001-candidate.json"],
    )
    _write_artifact(root, milestone)

    supervisor_template = _template("SUPERVISOR_PROGRESS_EVENT")
    manifest_version_row = [
        {
            "go_id": d0["go_id"],
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "plan_id": "CELL-PLAN-GO-001",
            "plan_version": 1,
        }
    ]
    specs = (
        ("REQUIRED_SET_CHANGED", manifest_path, "DELIVERED", 1, 0, 0),
        ("D2_STATE_CHANGED", d2_path, "D2_VERIFIED", 4, 1, required_count),
        ("GRAPH_STATE_CHANGED", graph_event_path, "D2_VERIFIED", 5, 1, required_count),
        ("RUN_STATE_CHANGED", d3_path, "RUN_VERIFIED", 6, 1, required_count),
        ("OWNER_STATE_CHANGED", owner_path, "OWNER_ACCEPTED", 7, 1, required_count),
    )
    for event_kind, trigger_path, state, sequence, verified_go_count, accepted_count in specs:
        value = copy.deepcopy(supervisor_template)
        suffix = event_kind.replace("_STATE_CHANGED", "").replace("_SET_CHANGED", "")
        value.update(
            artifact_id=f"SUPERVISOR-PROGRESS-RUN-001-{suffix}-V1",
            candidate_id=f"SUPERVISOR-PROGRESS-RUN-001-{suffix}-V1",
            event_id=f"SUPERVISOR-PROGRESS-RUN-001-{suffix}-V1",
            event_kind=event_kind,
            trigger_artifact_ref=trigger_path.relative_to(root).as_posix(),
            trigger_artifact_sha256=fixtures.sha256_file(trigger_path),
            required_go_count=1,
            d2_verified_required_go_count=verified_go_count,
            required_cell_count=required_count,
            d1_accepted_required_cell_count=accepted_count,
            active_go_ids=[] if state in {"RUN_VERIFIED", "OWNER_ACCEPTED"} else [d0["go_id"]],
            cell_manifest_versions=manifest_version_row,
            state=state,
            progress_sequence=sequence,
            evidence_refs=[f"evidence/progress/supervisor-{suffix.lower()}.json"],
            message=(
                f"Run=RUN-001 CELL(D1)={accepted_count}/{required_count} "
                f"GO(D2)={verified_go_count}/1 "
                f"ACTIVE={'-' if state in {'RUN_VERIFIED', 'OWNER_ACCEPTED'} else d0['go_id']} "
                f"WAITING=0 HOLDS=- Graph=v1 Capacity=v1 Load=v1 状态={state}"
            ),
        )
        _write_artifact(root, value)


def _remove_types(case, *artifact_types):
    remove = set(artifact_types)
    removed_evidence = set()
    def collect_evidence(current, key=None):
        if isinstance(current, dict):
            for child_key, child in current.items():
                collect_evidence(child, child_key)
        elif isinstance(current, (list, tuple)):
            if key == "evidence_refs" or (isinstance(key, str) and key.endswith("_evidence_refs")):
                removed_evidence.update(
                    item
                    for item in current
                    if isinstance(item, str) and item.startswith("evidence/")
                )
            for child in current:
                collect_evidence(child, key)
    for path in _all_formal(case.root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if value.get("artifact_type") in remove:
            collect_evidence(value)
            path.unlink()
    for relative in removed_evidence:
        evidence = case.root / relative
        if evidence.is_file():
            evidence.unlink()
    _reindex(case)


def _adapter():
    provenance = importlib.import_module("provenance")
    run_model = importlib.import_module("run_model")
    return rv.TrustedAdapterFixture(provenance, run_model)


def _artifact_path(root, artifact_type, occurrence=0):
    matches = []
    for path in _all_formal(root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if value.get("artifact_type") == artifact_type:
            matches.append(path)
    return matches[occurrence]


def _mutate(case, artifact_type, mutate, occurrence=0):
    path = _artifact_path(case.root, artifact_type, occurrence)
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(value)
    fixtures.write_json(path, value)
    _reindex(case)


def _unique_control(template_name, suffix, **changes):
    value = _template(template_name)
    value.update(
        artifact_id=f"{template_name}-{suffix}",
        candidate_id=f"{template_name}-{suffix}",
        evidence_refs=[f"evidence/controls/{template_name.lower()}-{suffix.lower()}.json"],
        **changes,
    )
    if "event_id" in value:
        value["event_id"] = value["artifact_id"]
    return value


def _upgrade_existing_case_to_310(case, *, replace_method_lock=True):
    """Test-only builder for a complete current 3.1 operational closure."""
    root = case.root
    if replace_method_lock:
        path = _artifact_path(root, "GLK_METHOD_LOCK")
        old = yaml.safe_load(path.read_text(encoding="utf-8"))
        for ref in old.get("evidence_refs", ()):
            if (root / ref).is_file():
                (root / ref).unlink()
        current = _template("GLK_METHOD_LOCK")
        fixtures.write_json(path, current)
        for ref in current["evidence_refs"]:
            fixtures.write_json(root / ref, {"artifact_id": current["artifact_id"], "observed": True})

    monitor_path = _artifact_path(root, "MONITOR_CONTROL")
    old_monitor = yaml.safe_load(monitor_path.read_text(encoding="utf-8"))
    monitor_path.unlink()
    for ref in old_monitor.get("evidence_refs", ()):
        if (root / ref).is_file():
            (root / ref).unlink()
    _write_artifact(root, _template("MONITOR_CONTROL"))

    profile = _template("DEVICE_CAPACITY_PROFILE")
    load = _template("CUMULATIVE_ENGINEERING_LOAD")
    _write_artifact(root, profile)
    _write_artifact(root, load)

    manifests = tuple(
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in _all_formal(root)
        if yaml.safe_load(path.read_text(encoding="utf-8")).get("artifact_type") == "CELL_MANIFEST"
    )
    manifest_by_identity = {
        (value.get("manifest_id"), value.get("manifest_version")): value
        for value in manifests
    }
    d0_paths = tuple(
        path for path in _all_formal(root)
        if yaml.safe_load(path.read_text(encoding="utf-8")).get("artifact_type") == "D0_RECEIPT"
    )
    d1_paths = tuple(
        path for path in _all_formal(root)
        if yaml.safe_load(path.read_text(encoding="utf-8")).get("artifact_type") == "D1_RECEIPT"
    )
    d1_by_candidate = {}
    for path in d1_paths:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        d1_by_candidate[(value.get("go_id"), value.get("cell_id"), value.get("candidate_id"))] = (path, value)

    binding_by_d0_digest = {}
    plan_by_manifest = {}
    for ordinal, d0_path in enumerate(sorted(d0_paths), start=1):
        d0 = yaml.safe_load(d0_path.read_text(encoding="utf-8"))
        manifest = manifest_by_identity[(d0["manifest_id"], d0["manifest_version"])]
        required_ids = tuple(
            item["cell_id"] for item in manifest["required_cells"] if item.get("required")
        )
        cell_ordinal = required_ids.index(d0["cell_id"]) + 1
        suffix = f"{d0['go_id']}-{d0['cell_id']}-V{d0['manifest_version']}"
        plan_id = f"CELL-PLAN-{d0['go_id']}"
        plan_version = d0["manifest_version"]
        plan_by_manifest[(d0["manifest_id"], d0["manifest_version"])] = (plan_id, plan_version)
        estimate = _unique_control(
            "CELL_WORK_ESTIMATE",
            suffix,
            estimate_id=f"CELL-WORK-ESTIMATE-{suffix}",
            go_id=d0["go_id"],
            cell_id=d0["cell_id"],
            plan_id=plan_id,
            plan_version=plan_version,
        )
        estimate_path = _write_artifact(root, estimate)
        gate = _unique_control(
            "CELL_CAPACITY_GATE",
            suffix,
            gate_id=f"CELL-CAPACITY-GATE-{suffix}",
            estimate_id=estimate["estimate_id"],
            plan_version=plan_version,
            profile_id=profile["profile_id"],
            profile_version=profile["profile_version"],
            load_id=load["load_id"],
            load_version=load["load_version"],
            result="PASS",
            dispatch_authorized=True,
        )
        gate_path = _write_artifact(root, gate)
        d1_path, d1 = d1_by_candidate[(d0["go_id"], d0["cell_id"], d0["candidate_id"])]
        wake_id = f"WAKE-BINDING-{suffix}"
        binding = _unique_control(
            "WORKER_CHECKER_WAKE_BINDING",
            suffix,
            wake_binding_id=wake_id,
            go_id=d0["go_id"],
            cell_id=d0["cell_id"],
            round_id="ROUND-01",
            cell_ordinal=cell_ordinal,
            required_cell_count=len(required_ids),
            manifest_id=d0["manifest_id"],
            manifest_version=d0["manifest_version"],
            plan_id=plan_id,
            plan_version=plan_version,
            worker_binding_ref=d0["issuer_binding_ref"],
            worker_thread_id=f"THREAD-{d0['issuer_binding_ref']}",
            checker_binding_ref=d1["issuer_binding_ref"],
            checker_thread_id=f"THREAD-{d1['issuer_binding_ref']}",
            capacity_gate_sha256=fixtures.sha256_file(gate_path),
            delivery_candidate_id=d0["candidate_id"],
            delivery_candidate_sha256=d0["candidate_sha256"],
        )
        _write_artifact(root, binding)
        binding_by_d0_digest[fixtures.sha256_file(d0_path)] = binding
        message = f"GO {d0['go_id']} CELL {cell_ordinal}/{len(required_ids)} 已交付，请检查"
        message_sha = hashlib.sha256(message.encode("utf-8")).hexdigest()
        attempt_paths = []
        for level in (1, 2, 3):
            attempt = _unique_control(
                "WAKE_ATTEMPT",
                f"{suffix}-L{level}",
                wake_binding_id=wake_id,
                go_id=d0["go_id"],
                cell_id=d0["cell_id"],
                round_id="ROUND-01",
                level=level,
                message=message,
                message_sha256=message_sha,
                timeout_seconds=120,
                outcome="FAILED",
                error_codes=["WAKE_ACK_TIMEOUT"],
            )
            attempt_paths.append(_write_artifact(root, attempt))
        pending = _unique_control(
            "PENDING_WAKE",
            suffix,
            wake_binding_id=wake_id,
            pending_key=f"PENDING-WAKE/{suffix}",
            heartbeat_key=f"GLK-WAKE/{suffix}",
            go_id=d0["go_id"],
            cell_id=d0["cell_id"],
            round_id="ROUND-01",
            worker_binding_ref=d0["issuer_binding_ref"],
            checker_binding_ref=d1["issuer_binding_ref"],
            message_sha256=message_sha,
            attempt_refs=[path.relative_to(root).as_posix() for path in attempt_paths],
        )
        _write_artifact(root, pending)

    sequence = 1
    required_go_ids = tuple(
        yaml.safe_load(_artifact_path(root, "D3_RECEIPT").read_text(encoding="utf-8")).get("required_go_ids", ())
    )
    required_cell_count = sum(
        sum(1 for item in manifest.get("required_cells", ()) if item.get("required"))
        for manifest in manifests
    )
    manifest_rows = []
    for manifest in sorted(manifests, key=lambda value: (value.get("go_id"), value.get("manifest_version"))):
        plan_id, plan_version = plan_by_manifest[(manifest["manifest_id"], manifest["manifest_version"])]
        manifest_rows.append(
            {"go_id": manifest["go_id"], "manifest_id": manifest["manifest_id"], "manifest_version": manifest["manifest_version"], "plan_id": plan_id, "plan_version": plan_version}
        )
        path = _artifact_path(root, "CELL_MANIFEST", tuple(manifests).index(manifest))
        event = _unique_control(
            "SUPERVISOR_PROGRESS_EVENT",
            f"MANIFEST-{manifest['go_id']}-V{manifest['manifest_version']}",
            event_kind="REQUIRED_SET_CHANGED",
            trigger_artifact_ref=path.relative_to(root).as_posix(),
            trigger_artifact_sha256=fixtures.sha256_file(path),
            required_go_count=len(required_go_ids),
            d2_verified_required_go_count=0,
            required_cell_count=required_cell_count,
            d1_accepted_required_cell_count=0,
            cell_manifest_versions=[],
            state="DELIVERED",
            progress_sequence=sequence,
            message=f"Run=RUN-001 CELL(D1)=0/{required_cell_count} GO(D2)=0/{len(required_go_ids)} ACTIVE=- WAITING=0 HOLDS=- Graph=v1 Capacity=v1 Load=v1 状态=DELIVERED",
        )
        event["cell_manifest_versions"] = list(manifest_rows)
        _write_artifact(root, event)
        sequence += 1

    accepted_by_go = {}
    for d1_path in sorted(d1_paths):
        d1 = yaml.safe_load(d1_path.read_text(encoding="utf-8"))
        manifest = manifest_by_identity[(d1["manifest_id"], d1["manifest_version"])]
        required_ids = tuple(item["cell_id"] for item in manifest["required_cells"] if item.get("required"))
        accepted = accepted_by_go.setdefault(d1["go_id"], set())
        if d1.get("verdict") == "D1_PASS":
            accepted.add(d1["cell_id"])
        plan_id, plan_version = plan_by_manifest[(d1["manifest_id"], d1["manifest_version"])]
        binding = binding_by_d0_digest[d1["d0_artifact_sha256"]]
        state = "D1_ACCEPTED" if d1.get("verdict") == "D1_PASS" else "DELIVERED"
        message = (
            f"{d1['go_id']} CELL验收 {len(accepted)}/{len(required_ids)}，"
            + ("GO候选待形成" if len(accepted) == len(required_ids) else "下一CELL待交付")
        )
        event = _unique_control(
            "CHECKER_PROGRESS_EVENT",
            f"D1-{d1['go_id']}-{d1['cell_id']}",
            event_kind="D1_DECISION",
            go_id=d1["go_id"],
            cell_id=d1["cell_id"],
            round_id=binding["round_id"],
            cell_ordinal=required_ids.index(d1["cell_id"]) + 1,
            required_cell_count=len(required_ids),
            manifest_id=d1["manifest_id"],
            manifest_version=d1["manifest_version"],
            plan_id=plan_id,
            plan_version=plan_version,
            trigger_artifact_ref=d1_path.relative_to(root).as_posix(),
            trigger_artifact_sha256=fixtures.sha256_file(d1_path),
            d1_verdict=d1["verdict"],
            accepted_cell_count=len(accepted),
            state=state,
            progress_sequence=sequence,
            message=message,
        )
        event["issuer_binding_ref"] = d1["issuer_binding_ref"]
        _write_artifact(root, event)
        sequence += 1

    closure_paths = tuple(
        path for path in _all_formal(root)
        if yaml.safe_load(path.read_text(encoding="utf-8")).get("artifact_type") == "GO_CANDIDATE_CLOSURE"
    )
    for closure_path in sorted(closure_paths):
        closure = yaml.safe_load(closure_path.read_text(encoding="utf-8"))
        manifest = manifest_by_identity[(closure["manifest_id"], closure["manifest_version"])]
        required_ids = tuple(item["cell_id"] for item in manifest["required_cells"] if item.get("required"))
        plan_id, plan_version = plan_by_manifest[(closure["manifest_id"], closure["manifest_version"])]
        last_cell = required_ids[-1]
        d1 = next(value for _, value in d1_by_candidate.values() if value.get("go_id") == closure["go_id"] and value.get("cell_id") == last_cell)
        event = _unique_control(
            "CHECKER_PROGRESS_EVENT",
            f"MILESTONE-{closure['go_id']}",
            event_kind="GO_CANDIDATE_MILESTONE",
            go_id=closure["go_id"],
            cell_id=last_cell,
            round_id="ROUND-01",
            cell_ordinal=len(required_ids),
            required_cell_count=len(required_ids),
            manifest_id=closure["manifest_id"],
            manifest_version=closure["manifest_version"],
            plan_id=plan_id,
            plan_version=plan_version,
            trigger_artifact_ref=closure_path.relative_to(root).as_posix(),
            trigger_artifact_sha256=fixtures.sha256_file(closure_path),
            d1_verdict="NONE",
            accepted_cell_count=len(required_ids),
            state="GO_CANDIDATE_READY",
            progress_sequence=sequence,
            message=f"GO {required_go_ids.index(closure['go_id']) + 1}/{len(required_go_ids)}；本GO CELL {len(required_ids)}/{len(required_ids)}已验收；当前状态=GO_CANDIDATE_READY",
        )
        event["issuer_binding_ref"] = d1["issuer_binding_ref"]
        _write_artifact(root, event)
        sequence += 1

    accepted_total = sum(len(value) for value in accepted_by_go.values())
    trigger_specs = []
    for path in _all_formal(root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        artifact_type = value.get("artifact_type")
        if artifact_type == "D2_RECEIPT":
            trigger_specs.append(("D2_STATE_CHANGED", path, value, "D2_VERIFIED" if value.get("verdict") == "D2_PASS" else "GO_CANDIDATE_READY"))
        elif artifact_type == "GRAPH_EVENT":
            trigger_specs.append(("GRAPH_STATE_CHANGED", path, value, "D2_VERIFIED"))
        elif artifact_type == "D3_RECEIPT":
            trigger_specs.append(("RUN_STATE_CHANGED", path, value, "RUN_VERIFIED" if value.get("verdict") == "D3_PASS" else "D2_VERIFIED"))
        elif artifact_type == "OWNER_ACCEPTANCE":
            trigger_specs.append(("OWNER_STATE_CHANGED", path, value, "OWNER_ACCEPTED" if value.get("owner_verdict") == "LOOP_OWNER_ACCEPTED" else "RUN_VERIFIED"))
    kind_order = {"D2_STATE_CHANGED": 0, "GRAPH_STATE_CHANGED": 1, "RUN_STATE_CHANGED": 2, "OWNER_STATE_CHANGED": 3}
    verified_go_ids = set()
    for event_kind, path, trigger, state in sorted(trigger_specs, key=lambda item: (kind_order[item[0]], item[1].as_posix())):
        if event_kind == "D2_STATE_CHANGED" and trigger.get("verdict") == "D2_PASS":
            verified_go_ids.add(trigger.get("go_id"))
        event = _unique_control(
            "SUPERVISOR_PROGRESS_EVENT",
            f"{event_kind}-{trigger['artifact_id']}",
            event_kind=event_kind,
            trigger_artifact_ref=path.relative_to(root).as_posix(),
            trigger_artifact_sha256=fixtures.sha256_file(path),
            required_go_count=len(required_go_ids),
            d2_verified_required_go_count=len(verified_go_ids),
            required_cell_count=required_cell_count,
            d1_accepted_required_cell_count=accepted_total,
            active_go_ids=[] if state in {"RUN_VERIFIED", "OWNER_ACCEPTED"} else list(required_go_ids),
            cell_manifest_versions=manifest_rows,
            state=state,
            progress_sequence=sequence,
            message=f"Run=RUN-001 CELL(D1)={accepted_total}/{required_cell_count} GO(D2)={len(verified_go_ids)}/{len(required_go_ids)} ACTIVE=- WAITING=0 HOLDS=- Graph=v1 Capacity=v1 Load=v1 状态={state}",
        )
        _write_artifact(root, event)
        sequence += 1
    if hasattr(case, "index_path"):
        _reindex(case)
    return case


def _append_operational_index(case):
    root = case.root
    indexes = tuple(sorted((root / "indexes").glob("*.yaml")))
    current_path = max(
        indexes,
        key=lambda path: fixtures.read_index(path).get("index_version", 0),
    )
    current = fixtures.read_index(current_path)
    version = current["index_version"] + 1
    new_path = root / "indexes" / f"RUN_PACKAGE_INDEX-v{version}.yaml"
    document = fixtures._index_document(
        root,
        _all_formal(root),
        tuple(sorted(path for path in (root / "evidence").rglob("*") if path.is_file())),
        version=version,
        prior_index_sha256=fixtures.sha256_file(current_path),
        suffix=f"v{version}",
    )
    fixtures.write_index(new_path, document)
    return new_path


def _codes(report):
    return {issue.code for issue in report.issues}


def test_real_indexed_operational_package_passes(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    package = package_module.load_run_package(case.root)
    report = validation.validate_operational_controls(package)
    assert report.status == "PASS"
    assert report.issues == ()
    assert report.projection_kind == "DERIVED_NON_AUTHORITATIVE"


def test_current_310_real_package_passes_all_eleven_layers(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    report = validation.validate_loaded_run(
        package_module.load_run_package(case.root), _adapter()
    )
    require(report.status == "PASS", "current 3.1 package must pass")
    require(len(report.layers) == 11, "current 3.1 package must execute layer 11")
    require(report.layers[-1].layer == 11, "last validation layer must be 11")
    require(report.layers[-1].status == "PASS", "layer 11 must pass")


def test_REDO_current_310_method_lock_requires_layer_11_even_when_controls_absent(
    modules, tmp_path
):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    _remove_types(
        case,
        "WORKER_CHECKER_WAKE_BINDING",
        "WAKE_ATTEMPT",
        "WAKE_ACK",
        "PENDING_WAKE",
        "DEVICE_CAPACITY_PROFILE",
        "CUMULATIVE_ENGINEERING_LOAD",
        "CELL_WORK_ESTIMATE",
        "CELL_CAPACITY_GATE",
        "CHECKER_PROGRESS_EVENT",
        "SUPERVISOR_PROGRESS_EVENT",
    )
    package = package_module.load_run_package(case.root)

    report = validation.validate_loaded_run(package, _adapter())

    require(len(report.layers) == 11, "current 3.1 lock must not bypass layer 11")
    require(any(
        issue.layer == 11 and issue.code == "OPERATIONAL_CONTROL_REQUIRED"
        for issue in report.issues
    ), "missing current controls must fail closed")


def test_REDO_historical_300_method_lock_is_explicitly_not_applicable(modules, tmp_path):
    package_module, validation = modules
    case = rv._prepare_validation_fixture(tmp_path)
    _mutate(
        case,
        "GLK_METHOD_LOCK",
        lambda value: value.update(
            schema_version="3.0.0",
            candidate_id="METHOD-GLK-3.0.0",
            release_tag="v3.0.0",
            method_version="3.0.0",
            validator_version="3.0.0",
        ),
    )
    _remove_types(case, "MONITOR_CONTROL")
    package = package_module.load_run_package(case.root)

    report = validation.validate_operational_controls(package)

    require(report.status == "NOT_APPLICABLE", "historical 3.0 package must be explicit legacy")
    require(report.applicable is False, "historical report must be inapplicable")


def test_REDO_current_310_cannot_delete_entire_worker_wake_closure(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    _remove_types(
        case,
        "WORKER_CHECKER_WAKE_BINDING",
        "WAKE_ATTEMPT",
        "WAKE_ACK",
        "PENDING_WAKE",
    )
    report = validation.validate_operational_controls(
        package_module.load_run_package(case.root)
    )
    require(report.status == "FAIL", "missing wake closure must fail")
    require("WORKER_WAKE_CLOSURE_REQUIRED" in _codes(report), "missing wake closure code required")


def test_REDO_completed_d0_d1_cannot_delete_capacity_gate_and_wake_scope(
    modules, tmp_path
):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    _remove_types(
        case,
        "CELL_CAPACITY_GATE",
        "WORKER_CHECKER_WAKE_BINDING",
        "WAKE_ATTEMPT",
        "WAKE_ACK",
        "PENDING_WAKE",
    )
    report = validation.validate_operational_controls(
        package_module.load_run_package(case.root)
    )
    require(report.status == "FAIL", "missing capacity gate must fail")
    require("CELL_CAPACITY_GATE_REQUIRED" in _codes(report), "missing capacity gate code required")


def test_REDO_current_310_requires_exact_layered_progress_coverage(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    _remove_types(case, "CHECKER_PROGRESS_EVENT", "SUPERVISOR_PROGRESS_EVENT")
    report = validation.validate_operational_controls(
        package_module.load_run_package(case.root)
    )
    require(report.status == "FAIL", "missing layered progress must fail")
    require("PROGRESS_COVERAGE_REQUIRED" in _codes(report), "progress coverage code required")


def test_REDO_duplicate_or_wrong_trigger_progress_is_rejected(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    source = _artifact_path(case.root, "CHECKER_PROGRESS_EVENT")
    duplicate = yaml.safe_load(source.read_text(encoding="utf-8"))
    duplicate.update(
        artifact_id="CHECKER-PROGRESS-DUPLICATE",
        candidate_id="CHECKER-PROGRESS-DUPLICATE",
        event_id="CHECKER-PROGRESS-DUPLICATE",
        evidence_refs=["evidence/progress/checker-duplicate.json"],
    )
    _write_artifact(case.root, duplicate)
    _mutate(
        case,
        "SUPERVISOR_PROGRESS_EVENT",
        lambda value: value.update(trigger_artifact_sha256="f" * 64),
    )
    report = validation.validate_operational_controls(
        package_module.load_run_package(case.root)
    )
    require(report.status == "FAIL", "duplicate/wrong progress must fail")
    require(
        {"PROGRESS_DUPLICATE", "PROGRESS_TRIGGER_INVALID"} <= _codes(report),
        "duplicate and wrong-trigger codes required",
    )


@pytest.mark.parametrize(
    "mutation,expected_code",
    [
        (lambda value: value.update(round_id="ROUND-99"), "WORKER_WAKE_CLOSURE_INVALID"),
        (lambda value: value.update(manifest_version=99), "WAKE_BINDING_SCOPE_MISMATCH"),
    ],
)
def test_current_310_wake_scope_round_and_version_are_exact(
    modules, tmp_path, mutation, expected_code
):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    _mutate(case, "WORKER_CHECKER_WAKE_BINDING", mutation)
    report = validation.validate_operational_controls(
        package_module.load_run_package(case.root)
    )
    require(expected_code in _codes(report), f"expected fail-closed code {expected_code}")


def test_current_310_successful_wake_requires_exact_ack_and_stops_escalation(
    modules, tmp_path
):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    binding = yaml.safe_load(
        _artifact_path(case.root, "WORKER_CHECKER_WAKE_BINDING").read_text(encoding="utf-8")
    )
    _remove_types(case, "WAKE_ATTEMPT", "PENDING_WAKE")
    message = (
        f"GO {binding['go_id']} CELL {binding['cell_ordinal']}/"
        f"{binding['required_cell_count']} 已交付，请检查"
    )
    message_sha = hashlib.sha256(message.encode("utf-8")).hexdigest()
    attempt = _template("WAKE_ATTEMPT")
    attempt.update(
        wake_binding_id=binding["wake_binding_id"],
        go_id=binding["go_id"],
        cell_id=binding["cell_id"],
        round_id=binding["round_id"],
        level=1,
        message=message,
        message_sha256=message_sha,
        timeout_seconds=120,
        outcome="ACKNOWLEDGED",
        error_codes=[],
    )
    _write_artifact(case.root, attempt)
    ack = _template("WAKE_ACK")
    ack.update(
        wake_binding_id=binding["wake_binding_id"],
        go_id=binding["go_id"],
        cell_id=binding["cell_id"],
        round_id=binding["round_id"],
        checker_binding_ref=binding["checker_binding_ref"],
        checker_thread_id=binding["checker_thread_id"],
        checker_host_id=binding["checker_host_id"],
    )
    _write_artifact(case.root, ack)
    _reindex(case)
    report = validation.validate_operational_controls(
        package_module.load_run_package(case.root)
    )
    require(report.status == "PASS", "exact acknowledged wake must pass and stop escalation")


@pytest.mark.parametrize(
    "artifact_type,mutation,expected_code",
    [
        (
            "SUPERVISOR_PROGRESS_EVENT",
            lambda value: value.update(progress_sequence=99),
            "PROGRESS_ORDER_INVALID",
        ),
        (
            "CHECKER_PROGRESS_EVENT",
            lambda value: value.update(manifest_version=99),
            "PROGRESS_SCOPE_INVALID",
        ),
    ],
)
def test_current_310_progress_order_and_version_fail_closed(
    modules, tmp_path, artifact_type, mutation, expected_code
):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    _mutate(case, artifact_type, mutation, occurrence=1)
    report = validation.validate_operational_controls(
        package_module.load_run_package(case.root)
    )
    require(expected_code in _codes(report), f"expected progress failure {expected_code}")


def test_nonpass_gate_can_never_have_dispatch_or_wake_binding(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    _mutate(
        case,
        "CELL_CAPACITY_GATE",
        lambda value: value.update(result="SPLIT_REQUIRED", dispatch_authorized=False),
    )
    package = package_module.load_run_package(case.root)
    assert "CELL_CAPACITY_NOT_PASS" in _codes(validation.validate_operational_controls(package))


def test_duplicate_patrol_conversation_or_heartbeat_fails(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    first_path = _artifact_path(case.root, "MONITOR_CONTROL")
    duplicate = yaml.safe_load(first_path.read_text(encoding="utf-8"))
    duplicate["artifact_id"] = "MONITOR-CONTROL-RUN-001-DUPLICATE"
    duplicate["candidate_id"] = duplicate["artifact_id"]
    _write_artifact(case.root, duplicate)
    _reindex(case)
    package = package_module.load_run_package(case.root)
    assert "PATROL_DUPLICATE" in _codes(validation.validate_operational_controls(package))


def test_pending_wake_requires_exact_three_levels_and_same_message(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    _mutate(case, "WAKE_ATTEMPT", lambda value: value.update(message_sha256="e" * 64), occurrence=1)
    package = package_module.load_run_package(case.root)
    assert "PENDING_WAKE_ATTEMPTS_INVALID" in _codes(
        validation.validate_operational_controls(package)
    )


@pytest.mark.parametrize("successor_count", [3, 6, 7, 8])
def test_post_dispatch_three_plus_requires_severe_and_remaining_recheck(
    modules, tmp_path, successor_count
):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    amendment = _template("CELL_PLAN_AMENDMENT")
    amendment["dispatch_timing"] = "POST_DISPATCH"
    amendment["successor_cell_ids"] = [f"CELL-001-{index}" for index in range(successor_count)]
    amendment["defect_codes"] = ["POST_DISPATCH_CELL_SPLIT"]
    amendment["reevaluate_undispatched_cell_ids"] = []
    _write_artifact(case.root, amendment)
    _reindex(case)
    package = package_module.load_run_package(case.root)
    assert "CELL_OVERSIZE_SEVERE_MISSING" in _codes(
        validation.validate_operational_controls(package)
    )


def test_scope_exceeded_is_not_a_product_failure_or_self_split(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    scope = _template("CELL_SCOPE_EXCEEDED")
    _write_artifact(case.root, scope)
    _reindex(case)
    package = package_module.load_run_package(case.root)
    report = validation.validate_operational_controls(package)
    assert "CELL_SELF_SPLIT_FORBIDDEN" not in _codes(report)
    assert report.status == "PASS"
