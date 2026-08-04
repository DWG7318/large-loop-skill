import copy
import dataclasses
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

import test_conformance_300 as cf
import test_run_closure_300 as rc
import test_run_validation_300 as rv
from glk300_fixtures import sha256_file, write_json


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "glk" / "scripts"
RUN_CONTROL_PATH = SCRIPTS / "run_control.py"
DEADLINE = "2026-08-03T02:00:00Z"
BEFORE_DEADLINE = "2026-08-03T01:59:00Z"
AFTER_DEADLINE = "2026-08-03T02:01:00Z"


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def load_control():
    if not RUN_CONTROL_PATH.is_file():
        pytest.fail("GLK 3.0 Run control engine is missing")
    rv.load_prerequisites()
    spec = importlib.util.spec_from_file_location(
        "glk_run_control_300_tests", RUN_CONTROL_PATH
    )
    if spec is None or spec.loader is None:
        pytest.fail("cannot load GLK 3.0 Run control engine")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


def _package(case):
    package_module, _, _ = rv.load_prerequisites()
    return package_module.load_run_package(case.root)


def _binding_slug(binding_ref):
    return binding_ref.removeprefix("ROLE-").replace("_", "-")


def _add_liveness_attestations(case, control, *, status="LIVE"):
    initial = _package(case)
    attestation_refs = []
    for binding in sorted(
        initial.artifacts_by_type["ROLE_BINDING"],
        key=lambda item: item["role_binding_id"],
    ):
        request = control.build_liveness_request(initial, binding, DEADLINE)
        slug = _binding_slug(binding["role_binding_id"])
        artifact_id = f"LIVENESS-{slug}-V1"
        evidence_ref = rv._add_evidence(
            case.root,
            f"evidence/liveness/{slug}-v1.json",
            artifact_id,
        )
        attestation = {
            "schema_version": "3.0.0",
            "artifact_type": "LIVENESS_ATTESTATION",
            "artifact_id": artifact_id,
            "run_id": binding["run_id"],
            "graph_id": binding["graph_id"],
            "graph_version": binding["graph_version"],
            "candidate_id": artifact_id,
            "candidate_sha256": hashlib.sha256(artifact_id.encode("utf-8")).hexdigest(),
            "issuer_binding_ref": "TRUSTED-EXTERNAL-ADAPTER-001",
            "execution_context_ref": "CONTEXT-TRUSTED-ENVIRONMENT-001",
            "evidence_refs": [evidence_ref],
            "provenance_ref": f"external-attestation/{artifact_id}",
            "issued_at": "2026-08-03T01:30:00Z",
            "operation": "check_liveness",
            "adapter_profile_id": initial.artifacts_by_type[
                "PROVENANCE_ADAPTER_PROFILE"
            ][0]["profile_id"],
            "binding_ref": binding["role_binding_id"],
            "request_digest": request.request_digest,
            "subject_artifact_sha256": request.artifact_sha256,
            "status": status,
            "observation_deadline": DEADLINE,
            "observed_at": "2026-08-03T01:30:00Z",
        }
        relative = f"attestations/{artifact_id}.json"
        write_json(case.root / relative, attestation)
        attestation_refs.append(relative)
    monitor_path, monitor = cf._record(case.root, "MONITOR_CONTROL")
    monitor["observation_deadline"] = DEADLINE
    monitor["liveness_attestation_refs"] = attestation_refs
    write_json(monitor_path, monitor)
    return cf.rebuild_conformance_indexes(case)


def _control_case(tmp_path, *, status="LIVE"):
    control = load_control()
    case = cf.build_conformance_case(tmp_path)
    case = _add_liveness_attestations(case, control, status=status)
    validation, report, loaded = rc._validate(case)
    require_equal(report.status, "PASS", "control fixture validation")
    return control, case, validation, report, loaded


class IndexedLivenessAdapter:
    def __init__(self, control, package, *, mode="ATTESTED"):
        self.control = control
        self.mode = mode
        self.calls = []
        self.attestations = {
            value["binding_ref"]: value
            for value in package.artifacts_by_type["LIVENESS_ATTESTATION"]
        }

    def resolve_binding(self, request):
        raise RuntimeError("not used by liveness evaluation")

    def verify_issuance(self, request):
        raise RuntimeError("not used by liveness evaluation")

    def verify_isolation(self, request):
        raise RuntimeError("not used by liveness evaluation")

    def check_liveness(self, request):
        self.calls.append(request)
        if self.mode == "READ_FAILURE":
            raise RuntimeError("role read failed")
        attestation = self.attestations[request.binding_ref]
        status = "HEALTHY" if self.mode == "HEALTHY" else attestation["status"]
        evidence_ref = (
            "does/not/exist.json"
            if self.mode == "UNINDEXED"
            else attestation["evidence_refs"][0]
        )
        return self.control.LivenessResult(
            adapter_contract_version=request.adapter_contract_version,
            request_digest=request.request_digest,
            binding_ref=request.binding_ref,
            run_id=request.run_id,
            scope=request.scope,
            artifact_sha256=request.artifact_sha256,
            status=status,
            evidence_ref=evidence_ref,
            observed_at=attestation["observed_at"],
            deadline=request.deadline,
        )


@pytest.mark.parametrize("mode", ["READ_FAILURE", "HEALTHY"])
def test_R22_all_role_reads_fail_closed_and_never_infer_healthy(tmp_path, mode):
    control, _, _, _, loaded = _control_case(tmp_path)
    adapter = IndexedLivenessAdapter(control, loaded, mode=mode)
    projection = control.evaluate_liveness(
        loaded,
        adapter,
        observation_deadline=DEADLINE,
        as_of=BEFORE_DEADLINE,
    )
    require_equal(projection.overall_state, "UNKNOWN", f"{mode} overall state")
    require_equal(
        {state for _, state in projection.role_states},
        {"UNKNOWN"},
        f"{mode} role states",
    )
    emitted_states = (projection.overall_state,) + tuple(
        state for _, state in projection.role_states
    )
    require("HEALTHY" not in emitted_states, "health was inferred")
    require_equal(len(adapter.calls), 6, f"{mode} adapter call count")


def test_R22_timeout_advances_unknown_to_role_unreachable(tmp_path):
    control, _, _, _, loaded = _control_case(tmp_path)
    adapter = IndexedLivenessAdapter(control, loaded, mode="READ_FAILURE")
    before = control.evaluate_liveness(
        loaded,
        adapter,
        observation_deadline=DEADLINE,
        as_of=BEFORE_DEADLINE,
    )
    after = control.evaluate_liveness(
        loaded,
        adapter,
        observation_deadline=DEADLINE,
        as_of=AFTER_DEADLINE,
    )
    require_equal(before.overall_state, "UNKNOWN", "pre-timeout state")
    require_equal(after.overall_state, "ROLE_UNREACHABLE", "post-timeout state")
    require_equal(
        after.blocked_or_unreachable_role_bindings,
        tuple(ref for ref, _ in after.role_states),
        "unreachable bindings",
    )


def test_R22_requires_indexed_request_bound_check_liveness_attestation(tmp_path):
    control, _, _, _, loaded = _control_case(tmp_path)
    adapter = IndexedLivenessAdapter(control, loaded, mode="UNINDEXED")
    projection = control.evaluate_liveness(
        loaded,
        adapter,
        observation_deadline=DEADLINE,
        as_of=BEFORE_DEADLINE,
    )
    require_equal(projection.overall_state, "UNKNOWN", "unindexed liveness state")
    require(
        "LIVENESS_ATTESTATION_UNINDEXED_OR_UNBOUND"
        in {issue.code for issue in projection.issues},
        "unindexed adapter evidence was accepted",
    )


def test_R22_indexed_exact_liveness_attestations_produce_all_live(tmp_path):
    control, _, _, _, loaded = _control_case(tmp_path)
    adapter = IndexedLivenessAdapter(control, loaded)
    projection = control.evaluate_liveness(
        loaded,
        adapter,
        observation_deadline=DEADLINE,
        as_of=BEFORE_DEADLINE,
    )
    require_equal(projection.overall_state, "ALL_LIVE", "attested liveness")
    require_equal(projection.issues, (), "attested liveness issues")
    require_equal(
        projection.blocked_or_unreachable_role_bindings,
        (),
        "attested blocked bindings",
    )


def test_R22_indexed_live_attestation_expires_at_observation_deadline(tmp_path):
    control, _, _, _, loaded = _control_case(tmp_path)
    projection = control.evaluate_liveness(
        loaded,
        IndexedLivenessAdapter(control, loaded),
        observation_deadline=DEADLINE,
        as_of=AFTER_DEADLINE,
    )
    require_equal(projection.overall_state, "ROLE_UNREACHABLE", "expired LIVE state")
    require_equal(
        {state for _, state in projection.role_states},
        {"ROLE_UNREACHABLE"},
        "expired role states",
    )


def test_R22_attestation_observed_after_bound_deadline_is_invalid(tmp_path):
    control, case, _, _, _ = _control_case(tmp_path)
    for path in rv._all_formal_paths(case.root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if value.get("artifact_type") == "LIVENESS_ATTESTATION":
            value["observed_at"] = "2026-08-03T02:01:00Z"
            write_json(path, value)
    _, loaded = _reload_control_case(case)
    projection = control.evaluate_liveness(
        loaded,
        IndexedLivenessAdapter(control, loaded),
        observation_deadline=DEADLINE,
        as_of=BEFORE_DEADLINE,
    )
    require_equal(projection.overall_state, "UNKNOWN", "future attestation state")
    require(
        "LIVENESS_ATTESTATION_TIME_INVALID"
        in {issue.code for issue in projection.issues},
        "post-deadline attestation was accepted",
    )


def _monitor_records(case):
    records = []
    for path in rv._all_formal_paths(case.root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if value.get("artifact_type") == "MONITOR_CONTROL":
            records.append((path, value))
    return tuple(sorted(records))


def _append_monitor(case, *, label, version, prior_digest, **overrides):
    _, base = _monitor_records(case)[0]
    monitor = copy.deepcopy(base)
    artifact_id = f"MONITOR-CONTROL-RUN-001-{label}"
    monitor.update(
        {
            "artifact_id": artifact_id,
            "candidate_id": artifact_id,
            "candidate_sha256": hashlib.sha256(artifact_id.encode("utf-8")).hexdigest(),
            "issued_at": f"2026-08-03T01:{30 + version:02d}:00Z",
            "monitor_version": version,
            "prior_monitor_sha256": prior_digest,
            "evidence_refs": [
                rv._add_evidence(
                    case.root,
                    f"evidence/monitor/{artifact_id}.json",
                    artifact_id,
                )
            ],
            **overrides,
        }
    )
    path = case.root / "controls" / f"{artifact_id}.json"
    write_json(path, monitor)
    return path


def _reload_control_case(case):
    case = cf.rebuild_conformance_indexes(case)
    return case, _package(case)


@pytest.mark.parametrize("mutation", ["WRONG_DEADLINE", "UNRELATED_BINDING"])
def test_R23_monitor_binds_exact_current_liveness_attestation_set(tmp_path, mutation):
    control, case, _, _, _ = _control_case(tmp_path)
    attestation_path = next(
        path
        for path in rv._all_formal_paths(case.root)
        if yaml.safe_load(path.read_text(encoding="utf-8")).get("artifact_type")
        == "LIVENESS_ATTESTATION"
    )
    attestation = yaml.safe_load(attestation_path.read_text(encoding="utf-8"))
    if mutation == "WRONG_DEADLINE":
        attestation["observation_deadline"] = "2026-08-03T03:00:00Z"
    else:
        attestation["binding_ref"] = "ROLE-UNRELATED-RUN-999"
    write_json(attestation_path, attestation)
    _, loaded = _reload_control_case(case)
    projection = control.advance_monitor_control(
        loaded,
        existing_patrol_conversation_ref="task/RUN-001/PATROL",
        existing_patrol_heartbeat_ref="heartbeat/RUN-001/PATROL",
        existing_callback_target="callback/RUN-001/PATROL",
    )
    require_equal(projection.status, "MONITOR_HELD", f"{mutation} monitor state")
    require(
        "MONITOR_LIVENESS_ATTESTATION_UNBOUND"
        in {issue.code for issue in projection.issues},
        f"{mutation} liveness binding was accepted",
    )


def test_R23_monitor_control_has_one_append_only_head_and_reuses_existing_task(tmp_path):
    control, case, _, _, _ = _control_case(tmp_path)
    first_path, _ = _monitor_records(case)[0]
    second_path = _append_monitor(
        case,
        label="V2",
        version=2,
        prior_digest=sha256_file(first_path),
    )
    _, loaded = _reload_control_case(case)
    projection = control.advance_monitor_control(
        loaded,
        existing_patrol_conversation_ref="task/RUN-001/PATROL",
        existing_patrol_heartbeat_ref="heartbeat/RUN-001/PATROL",
        existing_callback_target="callback/RUN-001/PATROL",
    )
    require_equal(projection.status, "MONITOR_ACTIVE", "valid monitor chain")
    require_equal(projection.head_sha256, sha256_file(second_path), "monitor head")
    emitted = dataclasses.asdict(projection)
    for forbidden in ("created_task_ref", "schedule", "cron_expression"):
        require(forbidden not in emitted, f"monitor projection exposed {forbidden}")


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("DUPLICATE", "MONITOR_DUPLICATE_KEY"),
        ("FORK", "MONITOR_FORKED_HEAD"),
        ("SECOND_TASK", "MONITOR_SECOND_VISIBLE_TASK"),
        ("CRON", "MONITOR_CRON_FORBIDDEN"),
        ("CRON_ALIAS", "MONITOR_CRON_FORBIDDEN"),
    ],
)
def test_R23_monitor_control_rejects_duplicate_fork_task_and_cron(
    tmp_path, mutation, expected_code
):
    control, case, _, _, _ = _control_case(tmp_path)
    first_path, first = _monitor_records(case)[0]
    first_digest = sha256_file(first_path)
    if mutation == "DUPLICATE":
        _append_monitor(case, label="DUPLICATE-V1", version=1, prior_digest=None)
    elif mutation == "FORK":
        _append_monitor(case, label="FORK-A-V2", version=2, prior_digest=first_digest)
        _append_monitor(case, label="FORK-B-V2", version=2, prior_digest=first_digest)
    elif mutation == "SECOND_TASK":
        _append_monitor(
            case,
            label="SECOND-TASK-V2",
            version=2,
            prior_digest=first_digest,
            patrol_conversation_ref="task/RUN-001/SECOND-PATROL",
        )
    elif mutation == "CRON":
        first["cron_expression"] = "* * * * *"
        write_json(first_path, first)
    elif mutation == "CRON_ALIAS":
        first["cron_job"] = "create-another-monitor"
        write_json(first_path, first)
    _, loaded = _reload_control_case(case)
    projection = control.advance_monitor_control(
        loaded,
        existing_patrol_conversation_ref="task/RUN-001/PATROL",
        existing_patrol_heartbeat_ref="heartbeat/RUN-001/PATROL",
        existing_callback_target="callback/RUN-001/PATROL",
    )
    require_equal(projection.status, "MONITOR_HELD", f"{mutation} monitor state")
    require(expected_code in {issue.code for issue in projection.issues}, expected_code)
    require("RUN_MONITOR_HOLD" in projection.holds, f"{mutation} monitor hold")


def test_technical_authority_violation_immediately_produces_run_hold(tmp_path):
    control = load_control()

    def mutation(fixture):
        return rv._mutate(
            fixture,
            "D0_RECEIPT",
            lambda value: value.__setitem__(
                "issuer_binding_ref", "ROLE-RUN-001-SUPERVISOR"
            ),
            preserve_lineage=True,
        )

    report, _, _, _ = rv._validate(tmp_path, mutation)
    projection = control.derive_control_holds(report.holds, ())
    require("RUN_AUTHORITY_HOLD" in report.holds, "validator omitted authority hold")
    require("RUN_AUTHORITY_HOLD" in projection.current_holds, "control dropped authority hold")
    require_equal(projection.may_continue, False, "authority hold continuation")


def test_two_consecutive_architecture_high_findings_stop_same_path(tmp_path):
    control = load_control()
    same_path = (
        control.ArchitectureFinding(
            path="admission/D2",
            severity="HIGH",
            sequence=1,
            evidence_ref="evidence/architecture/high-1.json",
        ),
        control.ArchitectureFinding(
            path="admission/D2",
            severity="HIGH",
            sequence=2,
            evidence_ref="evidence/architecture/high-2.json",
        ),
    )
    projection = control.derive_control_holds((), same_path)
    require("RUN_ARCHITECTURE_HOLD" in projection.current_holds, "architecture hold missing")
    require_equal(projection.architecture_path, "admission/D2", "held architecture path")
    require_equal(projection.may_continue, False, "architecture hold continuation")
    different_path = dataclasses.replace(same_path[1], path="graph/event")
    not_held = control.derive_control_holds((), (same_path[0], different_path))
    require("RUN_ARCHITECTURE_HOLD" not in not_held.current_holds, "different paths held")


def test_architecture_high_streak_is_evaluated_per_path(tmp_path):
    control = load_control()
    findings = (
        control.ArchitectureFinding("admission/A", "HIGH", 1, "evidence/A-1.json"),
        control.ArchitectureFinding("admission/B", "HIGH", 1, "evidence/B-1.json"),
        control.ArchitectureFinding("admission/A", "HIGH", 2, "evidence/A-2.json"),
    )
    projection = control.derive_control_holds((), findings)
    require("RUN_ARCHITECTURE_HOLD" in projection.current_holds, "path A streak missed")
    require_equal(projection.architecture_path, "admission/A", "interleaved held path")


@pytest.mark.parametrize(
    "decision",
    ["FROZEN_AMENDMENT_REVALIDATION", "SEAL_AND_START_NEW_RUN"],
)
def test_architecture_recovery_only_records_bounded_owner_routes(tmp_path, decision):
    control = load_control()
    findings = (
        control.ArchitectureFinding("graph/event", "HIGH", 4, "evidence/high-4.json"),
        control.ArchitectureFinding("graph/event", "HIGH", 5, "evidence/high-5.json"),
    )
    recovery = control.ArchitectureRecovery(
        decision=decision,
        external_recovery_ref=f"owner-gateway/{decision}",
        callback_target="callback/RUN-001/SUPERVISOR",
    )
    projection = control.derive_control_holds((), findings, recovery=recovery)
    require_equal(projection.recovery_decision, decision, "recovery decision")
    require("RUN_ARCHITECTURE_HOLD" in projection.current_holds, "derived report cleared hold")
    require_equal(projection.may_continue, False, "recovery bypassed formal revalidation")
    require("runtime" not in json.dumps(dataclasses.asdict(projection)).lower(), "Runtime leaked")
    with pytest.raises(control.RunControlError) as captured:
        control.derive_control_holds(
            (),
            findings,
            recovery=dataclasses.replace(recovery, decision="AUTO_CLEAR"),
        )
    require_equal(captured.value.code, "ARCHITECTURE_RECOVERY_INVALID", "invalid recovery")


def test_progress_emits_exact_dual_go_and_cell_closure_counts_and_ids(tmp_path):
    control, _, _, report, loaded = _control_case(tmp_path)
    liveness = control.evaluate_liveness(
        loaded,
        IndexedLivenessAdapter(control, loaded),
        observation_deadline=DEADLINE,
        as_of=BEFORE_DEADLINE,
    )
    holds = control.derive_control_holds(report.holds, ())
    progress = control.derive_progress(loaded, report, liveness, holds)
    require_equal(tuple(progress.as_dict()), control.PROGRESS_FIELDS, "progress fields")
    require_equal(progress.required_go_count, 2, "required GO count")
    require_equal(progress.d2_verified_required_go_count, 2, "verified GO count")
    require_equal(progress.required_cell_count, 4, "required CELL count")
    require_equal(progress.d1_accepted_required_cell_count, 4, "accepted CELL count")
    require_equal(progress.required_go_ids, ("GO-001", "GO-002"), "required GO IDs")
    require_equal(
        progress.d2_verified_required_go_ids,
        ("GO-001", "GO-002"),
        "verified GO IDs",
    )
    expected_cells = (
        ("GO-001", "GO-001-CELL-001"),
        ("GO-001", "GO-001-CELL-002"),
        ("GO-001", "GO-001-CELL-003"),
        ("GO-002", "GO-002-CELL-001"),
    )
    require_equal(progress.required_cell_ids, expected_cells, "required CELL IDs")
    require_equal(progress.d1_accepted_required_cell_ids, expected_cells, "accepted CELL IDs")
    require_equal(progress.blocked_or_unreachable_role_bindings, (), "blocked roles")
    require_equal(report.graph_topology.required_go_ids, progress.required_go_ids, "topology handoff")
