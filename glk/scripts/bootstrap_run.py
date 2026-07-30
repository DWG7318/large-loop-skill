#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


TEMPLATES = {
    "RUN_CONTRACT.yaml": "run_contract",
    "ROLE_BINDING.yaml": "role_binding",
    "GO.yaml": "go",
    "GRAPH_BASELINE.yaml": "graph_baseline",
    "CELL_RECEIPT.yaml": "cell_receipt",
    "GO_RECEIPT.yaml": "go_receipt",
    "RUN_RECEIPT.yaml": "run_receipt",
    "GO_CAUSAL_TRACE.yaml": "go_causal_trace",
    "GRAPH_AMENDMENT.yaml": "graph_amendment",
    "FORMAL_RESOLUTION.yaml": "formal_resolution",
    "OWNER_ACCEPTANCE.yaml": "owner_acceptance",
    "SECURITY_HANDOFF.yaml": "security_handoff",
}


def validator_for(schema, definition):
    return Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"#/$defs/{definition}",
            "$defs": schema["$defs"],
        }
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parents[1]
    template_root = skill_root / "templates"
    schema = json.loads(
        (skill_root / "schemas" / "glk.schema.json").read_text(encoding="utf-8")
    )
    target = Path(args.target)
    contracts = target / "contracts"
    contracts.mkdir(parents=True, exist_ok=True)
    for dirname in ["candidates", "evidence", "receipts", "amendments"]:
        (target / dirname).mkdir(parents=True, exist_ok=True)

    for filename, definition in TEMPLATES.items():
        source = template_root / filename
        destination = contracts / filename
        shutil.copy2(source, destination)
        instance = yaml.safe_load(destination.read_text(encoding="utf-8"))
        validator_for(schema, definition).validate(instance)

    print(f"PASS: bootstrapped and validated GLK 2.4.0 Run workspace at {target}")


if __name__ == "__main__":
    main()
