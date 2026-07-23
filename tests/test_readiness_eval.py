from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "graph-loop-skill" / "scripts" / "run_glk_readiness_eval.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("glk_eval", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonical_answers_pass() -> None:
    module = load_runner()
    bank = module.load_json(ROOT / "graph-loop-skill" / "evals" / "glk-readiness-questions.json")
    key = module.load_json(ROOT / "graph-loop-skill" / "evals" / "glk-readiness-answer-key.json")
    order = module.emit_questions(bank, 7318)
    submitted = {
        "question_order": [q["id"] for q in order],
        "answers": [{"id": q["id"], "answer": key["answers"][q["id"]]} for q in order],
    }
    passed, results = module.grade(bank, key, submitted, [q["id"] for q in order])
    assert passed
    assert all(item["passed"] for item in results)


def test_one_wrong_answer_fails() -> None:
    module = load_runner()
    bank = module.load_json(ROOT / "graph-loop-skill" / "evals" / "glk-readiness-questions.json")
    key = module.load_json(ROOT / "graph-loop-skill" / "evals" / "glk-readiness-answer-key.json")
    order = module.emit_questions(bank, 7318)
    answers = [{"id": q["id"], "answer": key["answers"][q["id"]]} for q in order]
    answers[0]["answer"] = "错误答案"
    passed, results = module.grade(
        bank, key,
        {"question_order": [q["id"] for q in order], "answers": answers},
        [q["id"] for q in order],
    )
    assert not passed
    assert sum(item["passed"] for item in results) == 24


def test_wrong_seed_order_fails() -> None:
    module = load_runner()
    bank = module.load_json(ROOT / "graph-loop-skill" / "evals" / "glk-readiness-questions.json")
    key = module.load_json(ROOT / "graph-loop-skill" / "evals" / "glk-readiness-answer-key.json")
    expected = module.emit_questions(bank, 7318)
    wrong = module.emit_questions(bank, 7319)
    submitted = {
        "question_order": [q["id"] for q in wrong],
        "answers": [{"id": q["id"], "answer": key["answers"][q["id"]]} for q in wrong],
    }
    passed, results = module.grade(
        bank, key, submitted, [q["id"] for q in expected]
    )
    assert not passed
    assert results[0]["reason"] == "seed/order mismatch"
