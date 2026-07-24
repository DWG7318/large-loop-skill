from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_contract() -> dict:
    return json.loads(
        (ROOT / "graph-loop-skill" / "contracts" / "glk-control-kernel.json").read_text(
            encoding="utf-8"
        )
    )


def test_version_and_identity() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert version == "2.0.0"
    skill = (ROOT / "graph-loop-skill" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Graph Loop Skill (GLK)" in skill
    assert "Current specification version: `2.0.0`." in skill
    assert "Current version: **2.0.0**" in readme


def test_authority_separation() -> None:
    c = load_contract()
    assert c["role_types"] == [
        "SUPERVISOR", "GRAPHER", "PLANNER", "WORKER",
        "CHECKER", "ROUTER", "VERIFICATION"
    ]
    a = c["authority"]
    assert a["graph_structure_and_route"] == ["GRAPHER"]
    assert a["cell_plan"] == ["PLANNER"]
    assert a["product_write"] == ["WORKER_WITH_ACTIVE_LEASE"]
    assert a["cell_validation"] == ["CHECKER"]
    assert a["cell_route"] == ["ROUTER"]
    assert a["go_verdict"] == ["VERIFICATION"]
    assert a["final_project_acceptance"] == ["SUPERVISOR"]


def test_calabash_and_graph_model() -> None:
    c = load_contract()
    gate = c["calabash_gate"]
    assert gate["required"] is True
    assert gate["minimum_layers"] == ["GRANDPA", "PRODUCT_ARCHITECTURE", "ONTOLOGY"]
    assert gate["go_trace_required"] is True
    assert gate["edge_trace_required"] is True

    g = c["graph_model"]
    assert g["grapher"] is True
    assert g["chain_model"] is False
    assert g["node_type"] == "GO"
    assert g["cell_as_cross_go_node"] is False
    assert g["partial_unlock"] is True
    assert g["conditional_routing"] is True
    assert g["cycles"] == "BOUNDED_ONLY"


def test_cell_loop_and_worker_set() -> None:
    c = load_contract()
    loop = c["cell_loop"]
    assert loop["ordered_roles"] == ["PLANNER", "WORKER", "CHECKER", "ROUTER"]
    assert loop["scope"] == "CELL"
    assert loop["router_can_choose_go"] is False
    assert loop["planner_can_choose_go"] is False

    workers = c["worker_set"]
    assert workers["multiple_eligible_workers_per_cell"] is True
    assert workers["maximum_active_workers_per_cell"] == 1
    assert workers["concurrent_product_writes"] is False
    assert workers["planner_recommends_worker"] is True
    assert workers["planner_selects_worker"] is True
    assert workers["planner_grants_lease"] is True
    assert workers["router_grants_lease"] is False
    assert workers["old_lease_revoked_before_new"] is True
    assert workers["immutable_handoff_required"] is True
    assert workers["fresh_workspace_on_switch"] is True

    skill = (ROOT / "graph-loop-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert "ROUTER_AUTHORIZED" not in skill
    assert "WORKER_LEASE_GRANTED" in skill
    assert "READY_WAITING_GO" in skill


def test_verification_and_go_boundary() -> None:
    c = load_contract()
    v = c["verification_policy"]
    assert v["fresh_per_go_candidate"] is True
    assert v["prebound_before_first_cell"] is True
    assert v["direct_handoff"] is True
    assert v["supervisor_relay"] is False
    assert v["product_writes"] is False

    x = c["cross_go_rule"]
    assert x["cell_to_cell_dependency_allowed"] is False
    assert x["required_source_state"] == "GO_VERIFIED"
    assert x["named_frozen_output_required"] is True


def test_autonomy_and_detection() -> None:
    c = load_contract()
    a = c["autonomy"]
    assert a["project_autonomy_envelope_required"] is True
    assert a["routine_owner_authorization_required"] is False
    assert a["worker_switch_owner_approval_required"] is False
    assert a["graph_route_owner_approval_required"] is False
    assert c["detection_tiers"] == [
        "CELL_ALWAYS", "CELL_TRIGGERED", "GO_BOUNDARY",
        "GRAPH_EDGE", "PROJECT_FINAL"
    ]


def test_line_budgets() -> None:
    governed = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "MIGRATION-LLK-TO-GLK.md",
        ROOT / "graph-loop-skill" / "SKILL.md",
        *sorted((ROOT / "graph-loop-skill" / "references").glob("*.md")),
    ]
    for path in governed:
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 1000, path


def test_eval_count_and_ids() -> None:
    bank = json.loads(
        (ROOT / "graph-loop-skill" / "evals" / "glk-readiness-questions.json").read_text(
            encoding="utf-8"
        )
    )
    key = json.loads(
        (ROOT / "graph-loop-skill" / "evals" / "glk-readiness-answer-key.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(bank["questions"]) == 25
    assert len(key["answers"]) == 25
    assert {q["id"] for q in bank["questions"]} == set(key["answers"])


def test_readiness_worker_switch_authority() -> None:
    key = json.loads(
        (ROOT / "graph-loop-skill" / "evals" / "glk-readiness-answer-key.json").read_text(encoding="utf-8")
    )
    answer = key["answers"]["Q12"]
    assert "Planner从冻结Worker Set选择" in answer
    assert "Planner" in answer and "授予新lease" in answer
    assert "Router授新lease" not in answer
