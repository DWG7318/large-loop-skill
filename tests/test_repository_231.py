from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NORMATIVE = [
    ROOT / "SPEC.md",
    ROOT / "SKILL.md",
    ROOT / "glk" / "SKILL.md",
    ROOT / "glk" / "references" / "canonical-dictionary.md",
    ROOT / "glk" / "references" / "scheduling.md",
    ROOT / "glk" / "references" / "state-machine.md",
]


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_version_is_231_everywhere():
    assert text(ROOT / "VERSION").strip() == "2.3.1"
    for path in [ROOT / "SPEC.md", ROOT / "SKILL.md", ROOT / "README.md"]:
        assert "2.3.1" in text(path)


def test_six_roles_are_canonical_and_legacy_roles_are_not_normative():
    spec = text(ROOT / "SPEC.md")
    roles = [
        "Run Supervisor",
        "Worker",
        "Checker",
        "GO Verifier",
        "Run Verifier",
        "Owner",
    ]
    for role in roles:
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
        assert "READY" not in text(path), path


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
