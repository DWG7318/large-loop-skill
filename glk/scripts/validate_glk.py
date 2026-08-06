#!/usr/bin/env python3
import runpy
from pathlib import Path


runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "tools" / "validate_glk.py"),
    run_name="__main__",
)
