#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def emit_questions(bank: dict[str, Any], seed: int) -> list[dict[str, str]]:
    questions = list(bank["questions"])
    random.Random(seed).shuffle(questions)
    return questions


def grade(
    bank: dict[str, Any],
    key: dict[str, Any],
    submission: dict[str, Any],
    expected_order: list[str] | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    expected_ids = {q["id"] for q in bank["questions"]}
    order = submission.get("question_order")
    submitted = submission.get("answers")
    if not isinstance(order, list) or not isinstance(submitted, list):
        return False, [{"passed": False, "reason": "missing ordered answers"}]
    if len(order) != len(bank["questions"]) or len(submitted) != len(bank["questions"]):
        return False, [{"passed": False, "reason": "answer count mismatch"}]
    if set(order) != expected_ids or [a.get("id") for a in submitted] != order:
        return False, [{"passed": False, "reason": "identity/order mismatch"}]
    if expected_order is not None and order != expected_order:
        return False, [{"passed": False, "reason": "seed/order mismatch"}]

    results: list[dict[str, Any]] = []
    for item in submitted:
        qid = item["id"]
        expected = str(key["answers"][qid]).strip()
        actual = str(item.get("answer", "")).strip()
        results.append({"id": qid, "passed": actual == expected})
    return all(r["passed"] for r in results), results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--submission", type=Path)
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()

    base = Path(__file__).resolve().parents[1]
    bank = load_json(base / "evals" / "glk-readiness-questions.json")
    key = load_json(base / "evals" / "glk-readiness-answer-key.json")
    ordered = emit_questions(bank, args.seed)

    if args.emit:
        print(json.dumps({"question_order": [q["id"] for q in ordered], "questions": ordered},
                         ensure_ascii=False, indent=2))
        return 0

    if args.submission is None:
        parser.error("--submission is required unless --emit is used")

    submission = load_json(args.submission)
    passed, results = grade(
        bank, key, submission, [q["id"] for q in ordered]
    )
    print(json.dumps({
        "result": "GLK_READINESS_EVAL_PASS" if passed else "GLK_READINESS_EVAL_FAIL",
        "score": f"{sum(r.get('passed', False) for r in results)}/{len(bank['questions'])}",
        "results": results,
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
