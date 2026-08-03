import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

import test_conformance_300 as cf
import test_run_closure_300 as rc
import test_run_validation_300 as rv
from glk300_fixtures import read_index, sha256_file, write_index, write_json


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_PATH = ROOT / "glk" / "scripts" / "preflight.py"
FORMAL_ROOTS = {
    "contracts", "bindings", "graph", "manifests", "closures", "receipts",
    "admissions", "indexes", "events", "controls", "acceptance", "handoffs",
    "attestations",
}
REQUIRED_OPERATIONS = (
    "resolve_binding",
    "verify_issuance",
    "verify_isolation",
    "check_liveness",
)
REQUIRED_CAPABILITIES = {
    "RUN_SUPERVISOR": ("GRAPH_EVENT", "SUPERVISOR_ADMISSION", "PREFLIGHT_ADMISSION"),
    "WORKER": ("D0_RECEIPT", "GO_CANDIDATE_CLOSURE"),
    "CHECKER": ("D1_RECEIPT",),
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


def load_preflight():
    if not PREFLIGHT_PATH.is_file():
        pytest.fail("GLK 3.0 preflight/simulation engine is missing")
    spec = importlib.util.spec_from_file_location("glk_preflight_300_tests", PREFLIGHT_PATH)
    if spec is None or spec.loader is None:
        pytest.fail("cannot load GLK preflight module")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(PREFLIGHT_PATH.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(PREFLIGHT_PATH.parent))
    return module


def _formal_snapshot(root):
    return tuple(
        (path.relative_to(root).as_posix(), path.read_bytes())
        for formal_root in sorted(FORMAL_ROOTS)
        for path in sorted((root / formal_root).rglob("*"))
        if path.is_file()
    )


def _method_lock(loaded):
    return dict(loaded.artifacts_by_type["GLK_METHOD_LOCK"][0])


class ReadinessAdapter(rv.TrustedAdapterFixture):
    def __init__(self, provenance, run_model, loaded, *, fault=None):
        super().__init__(provenance, run_model)
        self.fault = fault
        self.bindings = {
            binding["role_binding_id"]: binding
            for binding in loaded.artifacts_by_type["ROLE_BINDING"]
        }

    def _common(self, request):
        binding = self.bindings.get(request.binding_ref)
        if binding is None:
            binding = next(iter(self.bindings.values()))
        evidence_ref = binding["evidence_refs"][0]
        if self.fault == "FAKE_EVIDENCE":
            evidence_ref = "does/not/exist.json"
        return {
            "adapter_contract_version": request.adapter_contract_version,
            "request_digest": request.request_digest,
            "binding_ref": request.binding_ref,
            "run_id": request.run_id,
            "scope": request.scope,
            "artifact_sha256": request.artifact_sha256,
            "status": "VERIFIED",
            "evidence_ref": evidence_ref,
            "observed_at": "2026-08-03T04:00:00Z",
        }

    def resolve_binding(self, request):
        self.calls.append(("resolve_binding", request))
        binding = self.bindings[request.binding_ref]
        issuable = tuple(rv.ISSUABLE_BY_ROLE[binding["role_type"]])
        if binding["role_type"] == "RUN_SUPERVISOR":
            issuable += ("PREFLIGHT_ADMISSION", "SECURITY_HANDOFF")
            if self.fault == "SUPERVISOR_TECHNICAL":
                issuable += ("D0_RECEIPT",)
        elif self.fault == "CAPABILITY" and binding["role_type"] == "WORKER":
            issuable = ()
        profile = self.rm.RoleCapabilityProfile(
            profile_id=binding["capability_profile_id"],
            role_type=binding["role_type"],
            issuable_artifact_types=issuable,
            held_issuance_artifact_types=(),
            invocable_issuance_artifact_types=(),
        )
        context_id = binding["execution_context_ref"]
        if self.fault == "BINDING_MISMATCH" and binding["role_type"] == "WORKER":
            context_id = "context/not-the-formal-worker"
        return self.p.BindingResult(
            **self._common(request),
            role_type=binding["role_type"],
            instance_id=binding["instance_id"],
            context_id=context_id,
            workspace_id=binding["workspace_ref"],
            evidence_root=binding["evidence_root"],
            capability_profile=profile,
        )

    def verify_isolation(self, request):
        self.calls.append(("verify_isolation", request))
        snapshots = []
        for ordinal, binding_ref in enumerate(request.binding_refs):
            binding = self.bindings[binding_ref]
            snapshots.append(
                self.p.IsolationBindingSnapshot(
                    binding_ref=binding_ref,
                    conversation_ref=binding["conversation_ref"],
                    context_ref=binding["execution_context_ref"],
                    workspace_ref=binding["workspace_ref"],
                    runtime_state_ref=f"runtime-state/{ordinal}",
                    evidence_root=binding["evidence_root"],
                    decision_input_ref=f"decision-input/{ordinal}",
                )
            )
        dimensions = request.required_dimensions
        if self.fault == "MISSING_DIMENSION":
            dimensions = tuple(item for item in dimensions if item != "runtime_state")
        elif self.fault == "WORKSPACE_OVERLAP":
            snapshots[-1] = dataclasses.replace(
                snapshots[-1], workspace_ref=snapshots[0].workspace_ref
            )
        elif self.fault == "EXTRA_BINDING":
            snapshots.append(
                self.p.IsolationBindingSnapshot(
                    binding_ref="ROLE-UNBOUND",
                    conversation_ref="conversation/unbound",
                    context_ref="context/unbound",
                    workspace_ref="workspace/unbound",
                    runtime_state_ref="runtime-state/unbound",
                    evidence_root="evidence/unbound",
                    decision_input_ref="decision-input/unbound",
                )
            )
        elif self.fault == "DUPLICATE_BINDING":
            snapshots.append(snapshots[0])
        return self.p.IsolationResult(
            **self._common(request),
            verified_dimensions=dimensions,
            binding_snapshots=tuple(snapshots),
        )

    def check_liveness(self, request):
        self.calls.append(("check_liveness", request))
        common = self._common(request)
        common["status"] = "LIVE"
        if self.fault == "LIVENESS" and request.binding_ref.endswith("WORKER-GO-001"):
            common["status"] = "UNKNOWN"
        return self.p.LivenessResult(**common, deadline=request.deadline)


def _readiness_adapter(module, loaded, *, fault=None):
    return ReadinessAdapter(module, module, loaded, fault=fault)


def _scenario():
    return {
        "fork": {
            "source_go_id": "SIM-GO-ROOT",
            "successor_go_ids": ["SIM-GO-A", "SIM-GO-B"],
            "conflict_pairs": [],
        },
        "liveness": {
            "binding_ref": "ROLE-WORKER-GO-001",
            "status": "UNREACHABLE",
            "evidence_ref": "simulation/liveness/worker-unreachable.json",
        },
        "architecture": {
            "hold": "RUN_ARCHITECTURE_HOLD",
            "recovery_decision": "FROZEN_AMENDMENT_REVALIDATION",
            "evidence_ref": "simulation/architecture/recovery.json",
        },
    }


def _valid_inputs(tmp_path):
    case = cf.build_conformance_case(tmp_path)
    _, validation_report, loaded = rc._validate(case)
    module = load_preflight()
    simulation = module.simulate_run(
        loaded,
        validation_report,
        case.root / "simulation",
        _scenario(),
    )
    return module, case, loaded, validation_report, simulation, _readiness_adapter(module, loaded)


def test_simulation_rehearses_full_gates_and_never_mutates_formal_ledger(tmp_path):
    case = cf.build_conformance_case(tmp_path)
    _, validation_report, loaded = rc._validate(case)
    module = load_preflight()
    before = _formal_snapshot(case.root)
    simulation = module.simulate_run(
        loaded,
        validation_report,
        case.root / "simulation",
        _scenario(),
    )
    after = _formal_snapshot(case.root)
    require_equal(simulation.status, "SIMULATION_PASS", "simulation status")
    require_equal(before, after, "formal ledger mutation")
    require_equal(simulation.marker, "SIMULATION_ONLY", "simulation marker")
    require_equal(simulation.current_evidence_eligible, False, "formal evidence eligibility")
    require_equal(simulation.fork_active_go_ids, ("SIM-GO-A", "SIM-GO-B"), "max-safe fork activation")
    require_equal(simulation.liveness_status, "UNREACHABLE", "liveness failure")
    require_equal(simulation.health_inferred, False, "health inference")
    require_equal(simulation.architecture_hold_observed, True, "architecture hold")
    require_equal(simulation.recovery_decision, "FROZEN_AMENDMENT_REVALIDATION", "recovery decision")
    require_equal(simulation.formal_hold_cleared, False, "formal hold mutation")
    steps = tuple((step.kind, step.subject_type) for step in simulation.steps)
    for technical_type in ("D0_RECEIPT", "D1_RECEIPT", "D2_RECEIPT", "D3_RECEIPT"):
        positions = [index for index, step in enumerate(steps) if step == ("TECHNICAL_RECEIPT", technical_type)]
        require(positions, f"simulation omitted {technical_type}")
        for position in positions:
            require_equal(steps[position + 1][0], "SUPERVISOR_ADMISSION", f"{technical_type} admission order")
    require(any(kind == "GRAPH_EVENT" for kind, _ in steps), "simulation omitted graph event")
    require(any(kind == "OWNER_GATE" for kind, _ in steps), "simulation omitted Owner gate")
    report_path = case.root / "simulation" / "SIMULATION_REPORT.json"
    written = json.loads(report_path.read_text(encoding="utf-8"))
    require_equal(written["marker"], "SIMULATION_ONLY", "written simulation marker")
    require("artifact_type" not in written, "simulation report became a formal artifact")
    package_module, _, _ = rv.load_prerequisites()
    reloaded = package_module.load_run_package(case.root)
    require_equal(reloaded.index_head_sha256, loaded.index_head_sha256, "simulation changed package head")
    head = read_index(case.head_path)
    head["formal_artifacts"].append(
        {
            "path": "simulation/SIMULATION_REPORT.json",
            "sha256": sha256_file(report_path),
            "artifact_type": "SIMULATION_REPORT",
        }
    )
    write_index(case.head_path, head)
    with pytest.raises(package_module.PackageError) as captured:
        package_module.load_run_package(case.root)
    require(
        captured.value.code in {"UNKNOWN_FORMAL_TYPE", "UNKNOWN_FORMAL_ROOT"},
        "simulation output entered current formal evidence",
    )


def test_preflight_pass_is_adapter_verified_derived_and_cannot_advance_run(tmp_path):
    module, case, loaded, validation_report, simulation, adapter = _valid_inputs(tmp_path)
    report = module.derive_preflight_report(
        loaded,
        validation_report,
        adapter,
        _method_lock(loaded),
        simulation,
        current_holds=(),
        observation_deadline="2026-08-03T23:59:59Z",
    )
    require_equal(report.status, "PREFLIGHT_PASS", "preflight status")
    require_equal(report.failure_codes, (), "preflight failures")
    require_equal(report.required_role_types, tuple(REQUIRED_CAPABILITIES), "six-role readiness")
    require_equal(report.readiness_receipt_count, 6, "readiness receipt count")
    require_equal(len(report.readiness_observation_digest), 64, "readiness observation digest")
    require_equal(report.projection_kind, "DERIVED_NON_AUTHORITATIVE", "preflight authority")
    require_equal(report.can_advance_run, False, "preflight state authority")
    call_names = tuple(name for name, _ in adapter.calls)
    require_equal(call_names.count("resolve_binding"), 6, "binding verification count")
    require_equal(call_names.count("check_liveness"), 6, "liveness verification count")
    require_equal(call_names.count("verify_isolation"), 1, "isolation verification count")
    require_equal(call_names.count("verify_issuance"), 0, "preflight issuance calls")
    serialized = json.dumps(dataclasses.asdict(report), sort_keys=True)
    for forbidden in ("artifact_type", "issuer_binding_ref", "decision", "verdict"):
        require(f'"{forbidden}"' not in serialized, f"derived preflight exposed {forbidden}")
    require(not any((case.root / "admissions").glob("*PREFLIGHT*")), "preflight issued its own admission")


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("CAPABILITY", "READINESS_CAPABILITY_MISSING"),
        ("BINDING_MISMATCH", "READINESS_BINDING_INVALID"),
        ("LIVENESS", "READINESS_LIVENESS_INVALID"),
        ("METHOD_LOCK", "METHOD_LOCK_INCOMPLETE"),
        ("METHOD_LOCK_MISMATCH", "METHOD_LOCK_MISMATCH"),
        ("SUPERVISOR_TECHNICAL", "SUPERVISOR_TECHNICAL_CAPABILITY_FORBIDDEN"),
        ("HOLD", "PREFLIGHT_ACTIVE_HOLD"),
        ("VALIDATION", "RUN_PACKAGE_VALIDATION_REQUIRED"),
        ("SIMULATION", "SIMULATION_REQUIRED"),
    ],
)
def test_preflight_fails_closed_for_every_readiness_gate(tmp_path, mutation, expected_code):
    module, _, loaded, validation_report, simulation, _ = _valid_inputs(tmp_path)
    adapter = _readiness_adapter(
        module,
        loaded,
        fault=mutation if mutation in {
            "CAPABILITY", "BINDING_MISMATCH", "LIVENESS", "SUPERVISOR_TECHNICAL"
        } else None,
    )
    expected_lock = _method_lock(loaded)
    holds = ()
    if mutation == "METHOD_LOCK":
        expected_lock.pop("validator_sha256")
    elif mutation == "METHOD_LOCK_MISMATCH":
        expected_lock["validator_sha256"] = "9" * 64
    elif mutation == "HOLD":
        holds = ("RUN_AUTHORITY_HOLD",)
    elif mutation == "VALIDATION":
        validation_report = dataclasses.replace(validation_report, status="FAIL")
    elif mutation == "SIMULATION":
        simulation = None
    report = module.derive_preflight_report(
        loaded,
        validation_report,
        adapter,
        expected_lock,
        simulation,
        current_holds=holds,
        observation_deadline="2026-08-03T23:59:59Z",
    )
    require_equal(report.status, "PREFLIGHT_FAIL", f"{mutation} preflight status")
    require(expected_code in report.failure_codes, f"{mutation} missing {expected_code}")
    require_equal(report.can_advance_run, False, f"{mutation} state authority")


def test_preflight_requires_the_formal_adapter_profile(tmp_path):
    case = cf.build_conformance_case(tmp_path)
    profile_path, profile = cf._record(case.root, "PROVENANCE_ADAPTER_PROFILE")
    profile["allowed_operations"].remove("check_liveness")
    write_json(profile_path, profile)
    case = cf.rebuild_conformance_indexes(case)
    _, validation_report, loaded = rc._validate(case)
    module = load_preflight()
    simulation = module.simulate_run(loaded, validation_report, case.root / "simulation", _scenario())
    report = module.derive_preflight_report(
        loaded,
        validation_report,
        _readiness_adapter(module, loaded),
        _method_lock(loaded),
        simulation,
        current_holds=(),
        observation_deadline="2026-08-03T23:59:59Z",
    )
    require("ADAPTER_PROFILE_INVALID" in report.failure_codes, "incomplete adapter profile was accepted")


def test_preflight_rejects_incomplete_package_role_registry(tmp_path):
    case = cf.build_conformance_case(tmp_path)
    owner_binding = next(
        path
        for path in rv._all_formal_paths(case.root)
        if (value := yaml.safe_load(path.read_text(encoding="utf-8"))).get("artifact_type") == "ROLE_BINDING"
        and value.get("role_type") == "OWNER"
    )
    owner_binding.unlink()
    case = cf.rebuild_conformance_indexes(case)
    _, validation_report, loaded = rc._validate(case)
    module = load_preflight()
    simulation = module.simulate_run(loaded, validation_report, case.root / "simulation", _scenario())
    report = module.derive_preflight_report(
        loaded,
        validation_report,
        _readiness_adapter(module, loaded),
        _method_lock(loaded),
        simulation,
        current_holds=(),
        observation_deadline="2026-08-03T23:59:59Z",
    )
    require("ROLE_BINDING_INCOMPLETE" in report.failure_codes, "missing Owner binding was accepted")


@pytest.mark.parametrize(
    ("fault", "expected_code"),
    [
        ("FAKE_EVIDENCE", "READINESS_EVIDENCE_UNINDEXED"),
        ("MISSING_DIMENSION", "READINESS_ISOLATION_DIMENSION_MISSING"),
        ("WORKSPACE_OVERLAP", "READINESS_WORKSPACE_NOT_SEPARATED"),
        ("EXTRA_BINDING", "READINESS_OBSERVATION_UNBOUND"),
        ("DUPLICATE_BINDING", "READINESS_OBSERVATION_UNBOUND"),
    ],
)
def test_preflight_rejects_untrusted_readiness_observations(tmp_path, fault, expected_code):
    module, _, loaded, validation_report, simulation, _ = _valid_inputs(tmp_path)
    report = module.derive_preflight_report(
        loaded,
        validation_report,
        _readiness_adapter(module, loaded, fault=fault),
        _method_lock(loaded),
        simulation,
        current_holds=(),
        observation_deadline="2026-08-03T23:59:59Z",
    )
    require_equal(report.status, "PREFLIGHT_FAIL", f"{fault} preflight status")
    require(expected_code in report.failure_codes, f"{fault} missing {expected_code}")


def test_preflight_rejects_self_reported_readiness_without_trusted_adapter(tmp_path):
    module, _, loaded, validation_report, simulation, _ = _valid_inputs(tmp_path)
    forged = {
        binding["role_binding_id"]: {
            "capabilities": REQUIRED_CAPABILITIES[binding["role_type"]],
            "supervisor_technical_capabilities": (),
            "evidence_ref": binding["evidence_refs"][0],
        }
        for binding in loaded.artifacts_by_type["ROLE_BINDING"]
    }
    report = module.derive_preflight_report(
        loaded,
        validation_report,
        forged,
        _method_lock(loaded),
        simulation,
        current_holds=(),
        observation_deadline="2026-08-03T23:59:59Z",
    )
    require_equal(report.status, "PREFLIGHT_FAIL", "self-reported readiness")
    require("READINESS_ADAPTER_INVALID" in report.failure_codes, "self-report was trusted")


def test_simulation_liveness_failure_never_becomes_healthy_and_recovery_is_not_formal(tmp_path):
    case = cf.build_conformance_case(tmp_path)
    _, validation_report, loaded = rc._validate(case)
    module = load_preflight()
    scenario = _scenario()
    scenario["liveness"]["status"] = "LIVE"
    scenario["architecture"]["recovery_decision"] = "AUTO_CLEAR"
    report = module.simulate_run(loaded, validation_report, case.root / "simulation", scenario)
    require_equal(report.status, "SIMULATION_FAIL", "invalid recovery simulation")
    require("LIVENESS_FAILURE_NOT_REHEARSED" in report.failure_codes, "LIVE was treated as failure rehearsal")
    require("ARCHITECTURE_RECOVERY_INVALID" in report.failure_codes, "automatic hold clear was accepted")
    serialized = json.dumps(dataclasses.asdict(report), sort_keys=True)
    require('"HEALTHY"' not in serialized, "liveness failure inferred HEALTHY")
    require_equal(report.formal_hold_cleared, False, "formal architecture hold")


def test_simulation_rejects_an_out_of_package_root_without_writing(tmp_path):
    case = cf.build_conformance_case(tmp_path)
    _, validation_report, loaded = rc._validate(case)
    module = load_preflight()
    outside = tmp_path / "outside-simulation"
    report = module.simulate_run(loaded, validation_report, outside, _scenario())
    require_equal(report.status, "SIMULATION_FAIL", "outside-root simulation")
    require("SIMULATION_ROOT_INVALID" in report.failure_codes, "outside root was accepted")
    require_equal(outside.exists(), False, "outside-root simulation write")
