import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "glk" / "scripts" / "run_model.py"


def load_model():
    if not MODEL_PATH.exists():
        pytest.fail("GLK 2.4.0 Run model does not exist")
    spec = importlib.util.spec_from_file_location("glk_run_model", MODEL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def binding(m, run_id, suffix):
    return m.RoleBinding(
        role_binding_id=f"ROLE-{suffix}",
        role_type="RUN_SUPERVISOR",
        run_id=run_id,
        instance_id=f"INSTANCE-{suffix}",
        context_id=f"CONTEXT-{suffix}",
        workspace_id=f"WORKSPACE-{suffix}",
        evidence_root=f"evidence/{suffix}",
    )


def test_each_run_accepts_one_fresh_supervisor_binding():
    m = load_model()
    registry = m.RunSupervisorRegistry()
    first = binding(m, "RUN-001", "ONE")
    second = binding(m, "RUN-002", "TWO")
    registry.bind(first)
    registry.bind(second)
    assert registry.binding_for("RUN-001") == first
    assert registry.binding_for("RUN-002") == second


@pytest.mark.parametrize(
    "field",
    [
        "role_binding_id",
        "instance_id",
        "context_id",
        "workspace_id",
        "evidence_root",
    ],
)
def test_supervisor_identity_or_environment_cannot_be_reused_across_runs(field):
    m = load_model()
    registry = m.RunSupervisorRegistry()
    first = binding(m, "RUN-001", "ONE")
    registry.bind(first)
    values = binding(m, "RUN-002", "TWO").__dict__
    values[field] = getattr(first, field)
    with pytest.raises(m.RunBindingError, match="fresh"):
        registry.bind(m.RoleBinding(**values))


def test_binding_must_be_run_supervisor_and_match_its_run():
    m = load_model()
    registry = m.RunSupervisorRegistry()
    wrong_role = binding(m, "RUN-001", "ONE")
    wrong_role = m.RoleBinding(**{**wrong_role.__dict__, "role_type": "WORKER"})
    with pytest.raises(m.RunBindingError, match="RUN_SUPERVISOR"):
        registry.bind(wrong_role)
