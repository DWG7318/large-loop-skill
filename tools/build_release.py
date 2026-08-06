#!/usr/bin/env python3
import argparse
import json
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
from repository import release_files, write_hash_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    write_hash_manifest(root, output)

    prefix = "GLK-3.1.0"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in release_files(root, output):
            relative = path.relative_to(root).as_posix()
            archive.write(path, f"{prefix}/{relative}")

    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise SystemExit(f"FAIL: ZIP integrity failed at {bad}")
        names = archive.namelist()
        forbidden = [".git/", ".codex/", "__pycache__/", ".pytest_cache/"]
        if any(marker in name for name in names for marker in forbidden):
            raise SystemExit("FAIL: release ZIP contains cache or repository metadata")

    manifest = json.loads((root / "FILE_HASHES.json").read_text(encoding="utf-8"))
    print(
        f"PASS: built {output} with {len(manifest['files']) + 1} integrity-checked files"
    )


if __name__ == "__main__":
    main()
