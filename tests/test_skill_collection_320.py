from __future__ import annotations

import re

from skill_testkit import (
    EXPECTED_CHILDREN,
    EXPECTED_SKILLS,
    ROOT,
    SKILLS,
    assert_skill_shape,
    read_skill,
)


def test_version_is_320() -> None:
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "3.2.0"


def test_collection_has_one_main_and_three_children() -> None:
    actual = (
        tuple(sorted(path.name for path in SKILLS.iterdir() if path.is_dir()))
        if SKILLS.is_dir()
        else ()
    )
    assert actual == tuple(sorted(EXPECTED_SKILLS))
    for name in EXPECTED_SKILLS:
        assert_skill_shape(name)


def test_main_routes_to_three_children_and_latest_slk() -> None:
    text = read_skill("graph-loop-skill")
    for child in EXPECTED_CHILDREN:
        assert text.count(f"`${child}`") == 1, child
    assert "$small-loop-skill" in text
    assert "最新SLK" in text
    assert not (SKILLS / "glk-select-models").exists()
    assert "$slk-select-models" in "\n".join(read_skill(name) for name in EXPECTED_SKILLS)


def test_main_defines_one_run_as_a_supervisor_owned_go_dag() -> None:
    text = read_skill("graph-loop-skill")
    for marker in (
        "Graph逻辑",
        "Loop Engineering",
        "一个Graph就是一个Run",
        "每个节点是一个GO",
        "DAG",
        "多个起点",
        "ALL",
        "Fusion GO",
        "Supervisor",
        "GLK-GRAPH.md",
        "GLK-ROSTER.md",
        "GLK-RUN-<RUN-ID>.md",
    ):
        assert marker in text
    assert "Checker和Worker只按SLK" in text
    assert "普通GO" in text and "D2" in text


def test_graph_design_skill_checks_the_approved_topology() -> None:
    text = read_skill("glk-design-graph")
    for marker in (
        "GO001",
        "两个或以上",
        "零入度",
        "有向无环",
        "ALL",
        "普通GO",
        "可选",
        "空GO",
        "输出接口",
        "输入接口",
        "都能到达Fusion",
        "唯一Fusion GO",
        "D2 Repair GO",
        "$small-loop-skill",
        "$slk-select-models",
    ):
        assert marker in text
    assert "Owner查看逻辑图是建议" in text


def test_graph_assets_define_one_graph_roster_and_shared_run_record() -> None:
    graph = (SKILLS / "glk-design-graph" / "assets" / "GLK-GRAPH.template.md")
    roster = (SKILLS / "glk-design-graph" / "assets" / "GLK-ROSTER.template.md")
    run = (SKILLS / "glk-design-graph" / "assets" / "GLK-RUN.template.md")
    for path in (graph, roster, run):
        assert path.is_file(), path
    graph_text = graph.read_text(encoding="utf-8")
    for marker in (
        "GLK-GRAPH.md",
        "GO registry",
        "Direct predecessors",
        "Start prerequisite",
        "Output interface",
        "Fusion GO",
        "D2 Repair GO",
        "Static DAG check",
    ):
        assert marker in graph_text
    roster_text = roster.read_text(encoding="utf-8")
    assert "只有Supervisor创建和修改" in roster_text
    assert "所有成员可以读取" in roster_text
    run_text = run.read_text(encoding="utf-8")
    assert "Supervisor创建" in run_text
    assert "每个成员追加自己的事实" in run_text
    assert "每个GO单独方法记录" not in run_text


def test_run_graph_uses_visible_exclusive_slk_pairs_and_event_activation() -> None:
    text = read_skill("glk-run-graph")
    for marker in (
        "每个GO独占",
        "GO012-Checker",
        "GO012-Worker",
        "Supervisor ↔ 每个Checker",
        "每个Checker ↔ 自己的Worker",
        "所有起点GO",
        "全部直接前置GO",
        "立即启动",
        "完整交付",
        "原样重发",
        "未启动区域",
        "不复用GO编号",
        "其他路径继续",
    ):
        assert marker in text
    assert "Checker ↔ Checker" not in text
    assert "Supervisor不检查交付内容" in text
    assert "不使用`wait_threads`" in text


def test_close_run_gives_fusion_and_final_d2_distinct_ownership() -> None:
    text = read_skill("glk-close-run")
    for marker in (
        "Fusion是普通GO",
        "最后一个GO",
        "新的独立worktree",
        "Run基线",
        "直接前置GO候选",
        "代码重叠",
        "实现冲突",
        "接口适配",
        "不是机械Git merge",
        "最终D2",
        "最高能力模型",
        "D2 Repair GO",
        "同一最终D2",
        "原Checker和Worker",
        "归档",
    ):
        assert marker in text
    assert text.count("D2 Repair GO") >= 3


def test_active_skills_do_not_restore_the_old_glk_kernel() -> None:
    active = "\n".join(read_skill(name) for name in EXPECTED_SKILLS)
    for stale in (
        "Grapher",
        "Planner",
        "Router",
        "Verifier",
        "Patrol",
        "READY queue",
        "bounded cycle",
        "GO-[A-Z]",
    ):
        assert stale not in active
    assert not re.search(r"\bStage\b|\bLevel\b", active)


def test_child_skills_are_glk_only_and_do_not_copy_slk_roles() -> None:
    boundary = "本Skill是Graph Loop Skill（GLK）的子Skill，不可脱离当前GLK Run单独使用"
    for name in EXPECTED_CHILDREN:
        text = read_skill(name)
        assert boundary in text, name
    active = "\n".join(read_skill(name) for name in EXPECTED_SKILLS)
    assert "GLK Checker" not in active
    assert "GLK Worker" not in active
    assert not (SKILLS / "glk-check-cell").exists()
    assert not (SKILLS / "glk-execute-cell").exists()
