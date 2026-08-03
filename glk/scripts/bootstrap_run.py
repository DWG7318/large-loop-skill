#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


SCAFFOLD_DIRECTORIES = (
    "contracts",
    "bindings",
    "graph",
    "manifests",
    "closures",
    "receipts",
    "admissions",
    "indexes",
    "events",
    "controls",
    "acceptance",
    "handoffs",
    "attestations",
    "evidence",
    "candidates",
    "amendments",
    "draft",
    "simulation",
)


def bootstrap_scaffold(target):
    root = Path(target)
    root.mkdir(parents=True, exist_ok=True)
    for dirname in SCAFFOLD_DIRECTORIES:
        (root / dirname).mkdir(parents=True, exist_ok=True)
    scaffold = {
        "document_kind": "GLK_RUN_SCAFFOLD",
        "scaffold_version": "3.0.0",
        "state": "DRAFT_SCAFFOLD",
        "formal_execution_eligible": False,
        "run_id": "UNRESOLVED",
        "graph_id": "UNRESOLVED",
        "method_lock": "UNRESOLVED",
        "adapter_profile": "UNRESOLVED",
        "role_bindings": "UNRESOLVED",
        "package_index": "UNRESOLVED",
    }
    draft_path = root / "draft" / "DRAFT_SCAFFOLD.json"
    draft_path.write_text(
        json.dumps(scaffold, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "scope": "RUN_SCAFFOLD",
        "status": "DRAFT_SCAFFOLD",
        "formal_execution_eligible": False,
        "draft_ref": draft_path.relative_to(root).as_posix(),
        "target": root.resolve().as_posix(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create an incomplete GLK 3.0 Run scaffold")
    parser.add_argument("target")
    args = parser.parse_args(argv)
    output = bootstrap_scaffold(args.target)
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
