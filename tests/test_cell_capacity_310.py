import importlib
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "glk" / "scripts"


@pytest.fixture
def modules():
    sys.path.insert(0, str(SCRIPTS))
    for name in ("cell_capacity", "graph_model"):
        sys.modules.pop(name, None)
    try:
        yield importlib.import_module("cell_capacity"), importlib.import_module("graph_model")
    finally:
        sys.path.remove(str(SCRIPTS))


def _vector(m, **changes):
    values = dict(
        cpu_slots=8,
        ram_mb=16384,
        gpu_count=0,
        vram_mb=0,
        disk_mb=100000,
        io_mb_s=300,
        processes=16,
        ports=(8000, 8001),
        parallel_commands=4,
        duration_seconds=7200,
        context_tokens=200000,
        evidence_mb=2000,
        external_service_slots=2,
    )
    values.update(changes)
    return m.CapacityVector(**values)


def _profile(m, **changes):
    values = dict(
        profile_id="DEVICE-RUN-310",
        profile_version=1,
        observed_at="2026-08-04T00:00:00Z",
        fresh_until="2026-08-04T12:00:00Z",
        capacity=_vector(m),
        gpu_applicability="NOT_APPLICABLE",
        network_applicability="AVAILABLE",
        command_durations=(
            ("FOCUSED_TEST", 60),
            ("FULL_REGRESSION", 1800),
            ("VALIDATE", 120),
            ("HASH_PACKAGE", 120),
        ),
        evidence_refs=("evidence/device-profile.json",),
        units_explicit=True,
        provenance_verified=True,
        prior_profile_sha256=None,
    )
    values.update(changes)
    return m.DeviceCapacityProfile(**values)


def _load(m, **changes):
    values = dict(
        load_id="LOAD-RUN-310",
        load_version=1,
        profile_id="DEVICE-RUN-310",
        profile_version=1,
        graph_version=1,
        accepted_baseline_ref="BASELINE-1",
        regression_case_count=100,
        regression_duration_seconds=600,
        file_count=100,
        dependency_count=20,
        evidence_size_mb=100,
        context_recovery_seconds=120,
        active_reservations=_vector(
            m,
            cpu_slots=0,
            ram_mb=0,
            disk_mb=0,
            io_mb_s=0,
            processes=0,
            ports=(),
            parallel_commands=0,
            duration_seconds=0,
            context_tokens=0,
            evidence_mb=0,
            external_service_slots=0,
        ),
        evidence_refs=("evidence/load-v1.json",),
        prior_load_sha256=None,
    )
    values.update(changes)
    return m.CumulativeEngineeringLoad(**values)


def _estimate(m, **changes):
    values = dict(
        estimate_id="EST-CELL-01-V1",
        go_id="GO-01",
        cell_id="CELL-01",
        plan_id="PLAN-GO-01",
        plan_version=1,
        go_outcome_ref="GO-01-OUTCOME",
        acceptance_refs=("AC-01",),
        implementation_scope_refs=("src/change.py",),
        input_dependency_refs=("BASELINE-1",),
        expected_artifact_refs=("src/change.py", "tests/test_change.py"),
        build_test_matrix=("FOCUSED_TEST",),
        checker_reproduction_refs=("CHECK-01",),
        regression_refs=("REG-FOCUSED",),
        evidence_hash_cleanup_refs=("HASH", "CLEAN"),
        context_refs=("CONTEXT-01",),
        external_tool_refs=(),
        rollback_retry_count=1,
        cumulative_coupling_score=10,
        cost=_vector(
            m,
            cpu_slots=2,
            ram_mb=2048,
            disk_mb=1000,
            io_mb_s=50,
            processes=2,
            ports=(),
            parallel_commands=1,
            duration_seconds=600,
            context_tokens=20000,
            evidence_mb=100,
            external_service_slots=0,
        ),
        includes_full_regression=False,
        dispatched=False,
        evidence_refs=("evidence/estimate-cell-01.json",),
    )
    values.update(changes)
    return m.CellWorkEstimate(**values)


def _gate(m, profile=None, load=None, estimate=None):
    return m.evaluate_cell_capacity(
        profile or _profile(m),
        load or _load(m),
        estimate or _estimate(m),
        as_of="2026-08-04T01:00:00Z",
    )


def test_capacity_contracts_are_immutable(modules):
    m, _ = modules
    profile = _profile(m)
    with pytest.raises(FrozenInstanceError):
        profile.profile_version = 2


def test_early_surface_small_cell_passes_but_late_regression_growth_splits(modules):
    m, _ = modules
    estimate = _estimate(m, includes_full_regression=True)
    early = _gate(m, estimate=estimate)
    late = _gate(
        m,
        load=_load(
            m,
            load_version=2,
            regression_case_count=5000,
            regression_duration_seconds=6900,
            evidence_size_mb=1800,
            context_recovery_seconds=1800,
        ),
        estimate=estimate,
    )
    assert early.result == "PASS"
    assert late.result == "SPLIT_REQUIRED"
    assert "TOTAL_ENGINEERING_DURATION" in late.reasons


@pytest.mark.parametrize(
    "profile",
    [
        lambda m: _profile(m, capacity=_vector(m, ram_mb=1024)),
        lambda m: _profile(m, capacity=_vector(m, disk_mb=500)),
        lambda m: _profile(m, capacity=_vector(m, parallel_commands=0)),
    ],
)
def test_low_ram_disk_or_concurrency_rejects_heavy_cell(modules, profile):
    m, _ = modules
    assert _gate(m, profile=profile(m)).result in {"SPLIT_REQUIRED", "CAPACITY_BLOCKED"}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda m: _profile(m, units_explicit=False),
        lambda m: _profile(m, provenance_verified=False),
        lambda m: _profile(m, fresh_until="2026-08-04T00:30:00Z"),
        lambda m: _profile(m, gpu_applicability="UNKNOWN"),
        lambda m: _profile(m, evidence_refs=()),
    ],
)
def test_unknown_stale_unitless_or_unbound_capacity_fails_closed(modules, mutation):
    m, _ = modules
    gate = _gate(m, profile=mutation(m))
    assert gate.result == "CAPACITY_BLOCKED"


def test_gate_must_pass_before_dispatch(modules):
    m, _ = modules
    blocked = _gate(m, profile=_profile(m, units_explicit=False))
    with pytest.raises(m.CapacityContractError, match="CELL_CAPACITY_NOT_PASS"):
        m.authorize_dispatch(_estimate(m), blocked)
    assert m.authorize_dispatch(_estimate(m), _gate(m)).dispatch_authorized is True


def test_predispatch_split_preserves_one_go_outcome_and_acceptance(modules):
    m, _ = modules
    parent = _estimate(m)
    children = tuple(
        replace(
            parent,
            estimate_id=f"EST-CELL-01-{suffix}",
            cell_id=f"CELL-01-{suffix}",
            plan_version=2,
            cost=replace(parent.cost, duration_seconds=200),
        )
        for suffix in ("A", "B", "C")
    )
    amendment = m.split_before_dispatch(parent, children, new_manifest_version=2)
    assert amendment.go_id == parent.go_id
    assert amendment.go_outcome_ref == parent.go_outcome_ref
    assert amendment.acceptance_refs == parent.acceptance_refs
    assert amendment.successor_cell_ids == ("CELL-01-A", "CELL-01-B", "CELL-01-C")
    assert all(_gate(m, estimate=child).result == "PASS" for child in children)


def test_predispatch_split_cannot_change_go_or_acceptance(modules):
    m, _ = modules
    parent = _estimate(m)
    wrong = replace(parent, estimate_id="EST-WRONG", cell_id="CELL-WRONG", go_id="GO-02")
    with pytest.raises(m.CapacityContractError, match="CELL_SPLIT_OUTCOME_CHANGED"):
        m.split_before_dispatch(parent, (wrong, replace(wrong, cell_id="CELL-WRONG-2")), new_manifest_version=2)


def test_worker_cannot_self_split_and_may_only_signal_scope_exceeded(modules):
    m, _ = modules
    with pytest.raises(m.CapacityContractError, match="CELL_SELF_SPLIT_FORBIDDEN"):
        m.record_scope_exceeded(
            actor_role="WORKER",
            estimate=_estimate(m),
            checkpoint_refs=("checkpoint/usable.json",),
            evidence_refs=("evidence/actual-peak.json",),
            proposed_successor_cell_ids=("CELL-A", "CELL-B"),
        )
    signal = m.record_scope_exceeded(
        actor_role="WORKER",
        estimate=_estimate(m),
        checkpoint_refs=("checkpoint/usable.json",),
        evidence_refs=("evidence/actual-peak.json",),
    )
    assert signal.signal == "CELL_SCOPE_EXCEEDED"
    assert signal.authorized_action == "RETURN_TO_ORIGINAL_CHECKER_AND_PLANNING_AUTHORITY"


@pytest.mark.parametrize("successors", [3, 6, 7, 8])
def test_post_dispatch_three_or_more_is_severe_and_reevaluates_remaining(modules, successors):
    m, _ = modules
    defect = m.record_post_dispatch_split(
        replace(_estimate(m), dispatched=True),
        successor_count=successors,
        undispatched_cell_ids=("CELL-02", "CELL-03"),
    )
    assert defect.codes == ("POST_DISPATCH_CELL_SPLIT", "CELL_OVERSIZE_SEVERE")
    assert defect.reevaluate_cell_ids == ("CELL-02", "CELL-03")


def test_actual_peak_feedback_tightens_following_budget(modules):
    m, _ = modules
    original = _load(m)
    updated = m.update_cumulative_load(
        original,
        observed_regression_seconds=4000,
        observed_memory_peak_mb=12000,
        evidence_ref="evidence/late-boundary.json",
    )
    assert updated.load_version == 2
    assert updated.regression_duration_seconds == 4000
    assert updated.observed_memory_peak_mb == 12000
    assert _gate(m, load=updated).result == "SPLIT_REQUIRED"


def test_small_diff_with_full_regression_keeps_full_regression_cost(modules):
    m, _ = modules
    estimate = _estimate(
        m,
        expected_artifact_refs=("one-line.txt",),
        includes_full_regression=True,
        build_test_matrix=("FULL_REGRESSION",),
    )
    gate = _gate(m, load=_load(m, regression_duration_seconds=7000), estimate=estimate)
    assert gate.result == "SPLIT_REQUIRED"


def test_resource_capacity_limits_logically_independent_go_activation(modules):
    m, graph_model = modules
    gos = (
        graph_model.Go("A", resource_claims={"cpu_slots": 2, "ram_mb": 3000}),
        graph_model.Go("B", resource_claims={"cpu_slots": 2, "ram_mb": 3000}),
        graph_model.Go("C", resource_claims={"cpu_slots": 1, "ram_mb": 1000}),
    )
    graph = graph_model.GoGraph(gos, resource_capacity={"cpu_slots": 3, "ram_mb": 5000})
    assert graph.active() == ["A", "C"]
    assert graph.waiting() == ["B"]
    assert graph.predecessors("B") == set()
    assert graph.waiting_reasons("B")[0].kind == "RESOURCE"


def test_sufficient_capacity_preserves_maximal_parallel_activation(modules):
    _, graph_model = modules
    gos = (
        graph_model.Go("A", resource_claims={"cpu_slots": 2}),
        graph_model.Go("B", resource_claims={"cpu_slots": 2}),
        graph_model.Go("C", resource_claims={"cpu_slots": 1}),
    )
    graph = graph_model.GoGraph(gos, resource_capacity={"cpu_slots": 8})
    assert graph.active() == ["A", "B", "C"]
