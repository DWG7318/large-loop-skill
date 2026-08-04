import importlib
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "glk" / "scripts"


@pytest.fixture
def progress():
    sys.path.insert(0, str(SCRIPTS))
    sys.modules.pop("progress_reporting", None)
    try:
        yield importlib.import_module("progress_reporting")
    finally:
        sys.path.remove(str(SCRIPTS))


def _required(m, *, cells=("CELL-01", "CELL-02"), version=1, plan_version=1):
    return m.RequiredCellSet(
        go_id="GO-01",
        manifest_id="MANIFEST-GO-01",
        manifest_version=version,
        plan_id="PLAN-GO-01",
        plan_version=plan_version,
        required_cell_ids=tuple(cells),
    )


def _d1(m, cell_id, *, verdict="D1_PASS", current=True, receipt="a", version=1):
    return m.D1ProgressFact(
        go_id="GO-01",
        cell_id=cell_id,
        manifest_id="MANIFEST-GO-01",
        manifest_version=version,
        verdict=verdict,
        receipt_digest=(receipt * 64)[:64],
        current_valid=current,
        admitted=True,
        round_id="ROUND-01",
    )


def test_worker_delivery_scope_is_delivered_not_accepted(progress):
    delivery = progress.WorkerDeliveryProgress(
        run_id="RUN-310",
        go_id="GO-03",
        cell_id="CELL-025",
        round_id="ROUND-02",
        cell_ordinal=25,
        required_cell_count=30,
        manifest_version=4,
        state="DELIVERED",
    )
    assert delivery.message == "GO GO-03 CELL 25/30 已交付，请检查"
    assert delivery.accepted_cell_count_delta == 0


def test_progress_objects_are_immutable(progress):
    required = _required(progress)
    with pytest.raises(FrozenInstanceError):
        required.manifest_version = 2


def test_d1_pass_increments_each_required_cell_exactly_once(progress):
    required = _required(progress)
    facts = (
        _d1(progress, "CELL-01", receipt="a"),
        _d1(progress, "CELL-01", receipt="b"),
        _d1(progress, "CELL-02", receipt="c"),
    )

    projection = progress.derive_checker_progress(required, facts, current_cell_id="CELL-02")

    assert projection.accepted_cell_count == 2
    assert projection.required_cell_count == 2
    assert projection.state == "D1_ACCEPTED"
    assert projection.message == "GO-01 CELL验收 2/2，GO候选待形成"


@pytest.mark.parametrize(
    "fact",
    [
        lambda m: _d1(m, "CELL-01", verdict="D1_FAIL"),
        lambda m: _d1(m, "CELL-01", verdict="D1_REWORK"),
        lambda m: _d1(m, "CELL-01", verdict="D1_BLOCKED"),
        lambda m: _d1(m, "CELL-01", current=False),
        lambda m: _d1(m, "CELL-01", version=0),
    ],
)
def test_noncurrent_or_nonpass_d1_does_not_increment(progress, fact):
    projection = progress.derive_checker_progress(
        _required(progress), (fact(progress),), current_cell_id="CELL-01"
    )
    assert projection.accepted_cell_count == 0


def test_rework_and_blocked_messages_retain_accepted_count(progress):
    required = _required(progress)
    accepted = _d1(progress, "CELL-01")
    rework = progress.derive_checker_progress(
        required,
        (accepted, _d1(progress, "CELL-02", verdict="D1_REWORK")),
        current_cell_id="CELL-02",
        rework_round="R03",
    )
    blocked = progress.derive_checker_progress(
        required,
        (accepted, _d1(progress, "CELL-02", verdict="D1_BLOCKED")),
        current_cell_id="CELL-02",
        blocker_ref="external/build-service",
    )
    assert rework.accepted_cell_count == blocked.accepted_cell_count == 1
    assert rework.message == "GO-01 CELL验收仍为 1/2，CELL-02进入R03返工"
    assert blocked.message == "GO-01 CELL验收仍为 1/2，CELL-02阻断=external/build-service"


def test_checker_ack_and_start_message_are_scope_bound(progress):
    delivery = progress.WorkerDeliveryProgress(
        run_id="RUN-310",
        go_id="GO-01",
        cell_id="CELL-02",
        round_id="ROUND-03",
        cell_ordinal=2,
        required_cell_count=2,
        manifest_version=1,
        state="DELIVERED",
    )
    ack, started = progress.checker_wake_messages(delivery)
    assert ack == "WAKE_ACK RUN=RUN-310 GO=GO-01 CELL=CELL-02 ROUND=ROUND-03"
    assert started == "收到GO-01 CELL 2/2，开始检查"


def test_go_boundary_milestone_requires_all_d1_and_current_closure(progress):
    required = _required(progress)
    one = (_d1(progress, "CELL-01"),)
    both = one + (_d1(progress, "CELL-02", receipt="b"),)

    assert progress.derive_go_boundary_milestone(
        required, one, closure_current=True, go_ordinal=1, required_go_count=3
    ) is None
    assert progress.derive_go_boundary_milestone(
        required, both, closure_current=False, go_ordinal=1, required_go_count=3
    ) is None
    milestone = progress.derive_go_boundary_milestone(
        required, both, closure_current=True, go_ordinal=1, required_go_count=3
    )
    assert milestone.state == "GO_CANDIDATE_READY"
    assert milestone.message == "GO 1/3；本GO CELL 2/2已验收；当前状态=GO_CANDIDATE_READY"
    assert milestone.d2_verified is False


def test_go_candidate_ready_is_not_d2_verified(progress):
    required = _required(progress)
    both = (_d1(progress, "CELL-01"), _d1(progress, "CELL-02", receipt="b"))
    candidate = progress.derive_go_boundary_milestone(
        required, both, closure_current=True, go_ordinal=1, required_go_count=1
    )
    verified = progress.derive_go_boundary_milestone(
        required,
        both,
        closure_current=True,
        d2_current_pass=True,
        go_ordinal=1,
        required_go_count=1,
    )
    assert candidate.state == "GO_CANDIDATE_READY"
    assert verified.state == "D2_VERIFIED"


def test_go_milestone_is_deduplicated_by_current_identity(progress):
    required = _required(progress)
    facts = (_d1(progress, "CELL-01"), _d1(progress, "CELL-02", receipt="b"))
    first = progress.derive_go_boundary_milestone(
        required, facts, closure_current=True, go_ordinal=1, required_go_count=1
    )
    second = progress.derive_go_boundary_milestone(
        required,
        facts,
        closure_current=True,
        go_ordinal=1,
        required_go_count=1,
        previously_emitted_identity=first.identity,
    )
    assert second is None


def test_supervisor_global_progress_uses_d1_and_d2_truth_without_percentage(progress):
    required = _required(progress)
    snapshot = progress.derive_supervisor_progress(
        run_id="RUN-310",
        graph_version=2,
        required_go_ids=("GO-01", "GO-02"),
        d2_verified_go_ids=("GO-01", "GO-01", "STALE"),
        required_cell_sets=(required,),
        d1_facts=(_d1(progress, "CELL-01"),),
        active_go_ids=("GO-02",),
        waiting_go_reasons=(("GO-01", ("DEPENDENCY_WAITING_GO:GO-00",)),),
        holds=("RUN_MONITOR_HOLD",),
        capacity_profile_version=3,
        cumulative_load_version=5,
        run_verified=False,
        owner_accepted=False,
    )
    assert snapshot.d1_accepted_required_cell_count == 1
    assert snapshot.required_cell_count == 2
    assert snapshot.d2_verified_required_go_count == 1
    assert snapshot.required_go_count == 2
    assert snapshot.run_state == "D2_VERIFIED"
    assert "%" not in snapshot.message
    assert "CELL(D1)=1/2" in snapshot.message
    assert "GO(D2)=1/2" in snapshot.message


def test_supervisor_emits_only_material_changes(progress):
    required = _required(progress)
    kwargs = dict(
        run_id="RUN-310",
        graph_version=1,
        required_go_ids=("GO-01",),
        d2_verified_go_ids=(),
        required_cell_sets=(required,),
        d1_facts=(),
        active_go_ids=("GO-01",),
        waiting_go_reasons=(),
        holds=(),
        capacity_profile_version=1,
        cumulative_load_version=1,
        run_verified=False,
        owner_accepted=False,
    )
    first = progress.derive_supervisor_progress(**kwargs)
    assert progress.derive_supervisor_progress(**kwargs, previous=first) is None
    assert progress.derive_supervisor_progress(**{**kwargs, "holds": ("RUN_MONITOR_HOLD",)}, previous=first)


def test_run_verified_and_owner_accepted_are_distinct(progress):
    base = dict(
        run_id="RUN-310",
        graph_version=1,
        required_go_ids=("GO-01",),
        d2_verified_go_ids=("GO-01",),
        required_cell_sets=(_required(progress),),
        d1_facts=(_d1(progress, "CELL-01"), _d1(progress, "CELL-02", receipt="b")),
        active_go_ids=(),
        waiting_go_reasons=(),
        holds=(),
        capacity_profile_version=1,
        cumulative_load_version=1,
    )
    assert progress.derive_supervisor_progress(**base, run_verified=True, owner_accepted=False).run_state == "RUN_VERIFIED"
    assert progress.derive_supervisor_progress(**base, run_verified=True, owner_accepted=True).run_state == "OWNER_ACCEPTED"


def test_manifest_and_plan_amendment_recompute_denominator_without_accepting_split(progress):
    old_required = _required(progress, cells=("CELL-01", "CELL-02"), version=1, plan_version=1)
    old = progress.derive_supervisor_progress(
        run_id="RUN-310",
        graph_version=1,
        required_go_ids=("GO-01",),
        d2_verified_go_ids=(),
        required_cell_sets=(old_required,),
        d1_facts=(_d1(progress, "CELL-01"),),
        active_go_ids=("GO-01",),
        waiting_go_reasons=(),
        holds=(),
        capacity_profile_version=1,
        cumulative_load_version=1,
        run_verified=False,
        owner_accepted=False,
    )
    new_required = _required(
        progress,
        cells=("CELL-01", "CELL-02A", "CELL-02B", "CELL-02C"),
        version=2,
        plan_version=2,
    )
    new = progress.derive_supervisor_progress(
        run_id="RUN-310",
        graph_version=1,
        required_go_ids=("GO-01",),
        d2_verified_go_ids=(),
        required_cell_sets=(new_required,),
        d1_facts=(_d1(progress, "CELL-01", version=2),),
        active_go_ids=("GO-01",),
        waiting_go_reasons=(),
        holds=(),
        capacity_profile_version=1,
        cumulative_load_version=2,
        run_verified=False,
        owner_accepted=False,
        previous=old,
    )
    assert old.required_cell_count == 2
    assert new.required_cell_count == 4
    assert new.d1_accepted_required_cell_count == 1
    assert old.required_cell_count == 2
    assert new.cell_plan_versions == (("GO-01", "PLAN-GO-01", 2),)


@pytest.mark.parametrize("emitter", ["GO_VERIFIER", "RUN_VERIFIER", "RUN_PATROL", "ROUTER", "GRAPHER"])
def test_other_roles_cannot_emit_continuous_progress(progress, emitter):
    with pytest.raises(progress.ProgressContractError, match="PROGRESS_EMITTER_FORBIDDEN"):
        progress.validate_progress_emitter(emitter, "CONTINUOUS_PROGRESS")
