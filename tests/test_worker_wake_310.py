import importlib
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "glk" / "scripts"


@pytest.fixture
def modules():
    sys.path.insert(0, str(SCRIPTS))
    for name in ("worker_wake", "run_model"):
        sys.modules.pop(name, None)
    try:
        yield importlib.import_module("worker_wake"), importlib.import_module("run_model")
    finally:
        sys.path.remove(str(SCRIPTS))


class FakeClock:
    def __init__(self):
        self.seconds = 0.0

    def monotonic(self):
        return self.seconds

    def utc_now(self):
        return datetime.fromtimestamp(self.seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    def advance(self, seconds):
        self.seconds += seconds


class FakeGateway:
    def __init__(self, clock, *, acknowledgements=(), snapshots=(), registry=()):
        self.clock = clock
        self.acknowledgements = list(acknowledgements)
        self.snapshots = list(snapshots)
        self.registry = tuple(registry)
        self.calls = []

    def send_message(self, *, thread_id, host_id, message):
        self.calls.append(("send", thread_id, host_id, message))

    def wait_for_ack(self, *, wake_identity, checker_binding_id, timeout_seconds):
        self.calls.append(("wait", wake_identity, checker_binding_id, timeout_seconds))
        self.clock.advance(timeout_seconds)
        return self.acknowledgements.pop(0) if self.acknowledgements else None

    def read_thread(self, *, thread_id, host_id):
        self.calls.append(("read", thread_id, host_id))
        return self.snapshots.pop(0) if self.snapshots else None

    def list_threads(self, *, host_id):
        self.calls.append(("list", host_id))
        return self.registry

    def unarchive_thread(self, *, thread_id, host_id):
        self.calls.append(("unarchive", thread_id, host_id))


def _profile(run_model, operations=None, role_type="WORKER"):
    return run_model.RoleCapabilityProfile(
        profile_id="CAP-WORKER-1",
        role_type=role_type,
        issuable_artifact_types=("D0_RECEIPT",) if role_type == "WORKER" else (),
        held_issuance_artifact_types=(),
        invocable_issuance_artifact_types=(),
        operational_capabilities=tuple(operations or ()),
    )


def _binding(m, *, ordinal=25, required=30):
    return m.FrozenWakeBinding(
        contract_version="3.1.0",
        run_id="RUN-310",
        go_id="GO-03",
        cell_id="CELL-025",
        round_id="ROUND-02",
        cell_ordinal=ordinal,
        required_cell_count=required,
        cell_manifest_id="MANIFEST-GO-03",
        cell_manifest_version=4,
        worker_binding_id="ROLE-WORKER-03",
        worker_thread_id="THREAD-WORKER-03",
        worker_host_id="HOST-A",
        checker_binding_id="ROLE-CHECKER-03",
        checker_thread_id="THREAD-CHECKER-03",
        checker_host_id="HOST-A",
        capability_profile_digest="a" * 64,
        frozen_at="2026-08-04T00:00:00Z",
    )


def _ack(m, binding, **changes):
    values = dict(
        run_id=binding.run_id,
        go_id=binding.go_id,
        cell_id=binding.cell_id,
        round_id=binding.round_id,
        checker_binding_id=binding.checker_binding_id,
        checker_thread_id=binding.checker_thread_id,
        checker_host_id=binding.checker_host_id,
        acknowledged_at="2026-08-04T00:00:01Z",
    )
    values.update(changes)
    return m.WakeAck(**values)


def _snapshot(m, binding, *, archived=False, host_id=None, running=False, role_binding_id=None):
    return m.ThreadSnapshot(
        thread_id=binding.checker_thread_id,
        host_id=host_id or binding.checker_host_id,
        role_binding_id=role_binding_id or binding.checker_binding_id,
        archived=archived,
        running=running,
        observed_at="2026-08-04T00:02:00Z",
    )


def _required(m):
    return m.REQUIRED_WORKER_WAKE_CAPABILITIES


def test_scoped_delivery_and_failure_messages_preserve_position(modules):
    m, _ = modules
    binding = _binding(m)

    assert m.format_worker_message(binding, "DELIVERED") == "GO GO-03 CELL 25/30 已交付，请检查"
    assert m.format_worker_message(binding, "BLOCKED") == "GO GO-03 CELL 25/30 BLOCKED，请检查"
    assert m.format_worker_message(binding, "EXECUTION_FAILURE") == "GO GO-03 CELL 25/30 EXECUTION_FAILURE，请检查"
    assert m.format_worker_message(replace(binding, round_id="ROUND-03"), "DELIVERED").startswith(
        "GO GO-03 CELL 25/30"
    )


def test_contracts_are_immutable(modules):
    m, _ = modules
    binding = _binding(m)
    with pytest.raises(FrozenInstanceError):
        binding.cell_ordinal = 26


def test_level_one_matching_ack_stops_without_recovery(modules):
    m, run_model = modules
    binding = _binding(m)
    clock = FakeClock()
    gateway = FakeGateway(clock, acknowledgements=[_ack(m, binding)])

    result = m.attempt_levels_one_two(
        binding=binding,
        worker_profile=_profile(run_model, _required(m)),
        gateway=gateway,
        clock=clock,
    )

    assert result.status == "ACKNOWLEDGED"
    assert result.success_level == 1
    assert [call[0] for call in gateway.calls] == ["send", "wait"]
    assert gateway.calls[0][3] == "GO GO-03 CELL 25/30 已交付，请检查"
    assert gateway.calls[1][3] == 120


def test_level_one_failure_then_level_two_same_checker_succeeds(modules):
    m, run_model = modules
    binding = _binding(m)
    clock = FakeClock()
    gateway = FakeGateway(
        clock,
        acknowledgements=[None, _ack(m, binding)],
        snapshots=[_snapshot(m, binding)],
        registry=[_snapshot(m, binding)],
    )

    result = m.attempt_levels_one_two(
        binding=binding,
        worker_profile=_profile(run_model, _required(m)),
        gateway=gateway,
        clock=clock,
    )

    assert result.status == "ACKNOWLEDGED"
    assert result.success_level == 2
    assert [call[0] for call in gateway.calls] == ["send", "wait", "read", "list", "send", "wait"]
    assert all(call[3] <= 120 for call in gateway.calls if call[0] == "wait")


def test_level_two_unarchives_only_the_frozen_checker(modules):
    m, run_model = modules
    binding = _binding(m)
    clock = FakeClock()
    frozen = _snapshot(m, binding, archived=True)
    gateway = FakeGateway(clock, acknowledgements=[None, _ack(m, binding)], snapshots=[frozen], registry=[frozen])

    result = m.attempt_levels_one_two(
        binding=binding,
        worker_profile=_profile(run_model, _required(m)),
        gateway=gateway,
        clock=clock,
    )

    assert result.success_level == 2
    assert ("unarchive", binding.checker_thread_id, binding.checker_host_id) in gateway.calls


@pytest.mark.parametrize(
    "snapshot,registry,error",
    [
        (None, (), "WAKE_THREAD_NOT_FOUND"),
        ("wrong_host", (), "WAKE_BINDING_MISMATCH"),
        ("wrong_role", (), "WAKE_BINDING_MISMATCH"),
    ],
)
def test_level_two_missing_or_mismatched_checker_never_guesses_or_creates(modules, snapshot, registry, error):
    m, run_model = modules
    binding = _binding(m)
    if snapshot == "wrong_host":
        snapshot = _snapshot(m, binding, host_id="HOST-B")
    elif snapshot == "wrong_role":
        snapshot = _snapshot(m, binding, role_binding_id="ROLE-CHECKER-OTHER")
    clock = FakeClock()
    gateway = FakeGateway(clock, acknowledgements=[None], snapshots=[snapshot] if snapshot else [], registry=registry)

    result = m.attempt_levels_one_two(
        binding=binding,
        worker_profile=_profile(run_model, _required(m)),
        gateway=gateway,
        clock=clock,
    )

    assert result.status == "ESCALATE_LEVEL_3"
    assert error in result.error_codes
    assert not any(call[0] in {"create", "guess"} for call in gateway.calls)
    assert sum(call[0] == "send" for call in gateway.calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"run_id": "RUN-WRONG"},
        {"go_id": "GO-WRONG"},
        {"cell_id": "CELL-WRONG"},
        {"round_id": "ROUND-WRONG"},
        {"checker_binding_id": "ROLE-CHECKER-WRONG"},
        {"checker_host_id": "HOST-B"},
    ],
)
def test_wrong_ack_scope_never_stops_escalation(modules, change):
    m, run_model = modules
    binding = _binding(m)
    snapshot = _snapshot(m, binding)
    gateway = FakeGateway(
        FakeClock(),
        acknowledgements=[_ack(m, binding, **change), None],
        snapshots=[snapshot],
        registry=[snapshot],
    )

    result = m.attempt_levels_one_two(
        binding=binding,
        worker_profile=_profile(run_model, _required(m)),
        gateway=gateway,
        clock=gateway.clock,
    )

    assert result.status == "ESCALATE_LEVEL_3"
    assert "WAKE_ACK_SCOPE_MISMATCH" in result.error_codes


def test_non_worker_is_rejected_before_gateway_call(modules):
    m, run_model = modules
    gateway = FakeGateway(FakeClock())

    with pytest.raises(m.WakeContractError, match="WAKE_ROLE_FORBIDDEN"):
        m.attempt_levels_one_two(
            binding=_binding(m),
            worker_profile=_profile(run_model, _required(m), role_type="CHECKER"),
            gateway=gateway,
            clock=gateway.clock,
        )

    assert gateway.calls == []


def test_missing_each_required_capability_fails_before_gateway_call(modules):
    m, run_model = modules
    for missing in _required(m):
        gateway = FakeGateway(FakeClock())
        operations = tuple(value for value in _required(m) if value != missing)
        with pytest.raises(m.WakeContractError, match="WAKE_CAPABILITY_MISSING"):
            m.attempt_levels_one_two(
                binding=_binding(m),
                worker_profile=_profile(run_model, operations),
                gateway=gateway,
                clock=gateway.clock,
            )
        assert gateway.calls == []
