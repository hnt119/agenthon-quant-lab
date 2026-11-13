#!/usr/bin/env python3
"""Locate the maintained engine; this helper never duplicates calculations."""
from pathlib import Path
import os
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[3]
    python = root / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    if not python.is_file():
        raise SystemExit(f"Set up this source checkout first: python3 {root / 'scripts/setup.py'}. See {root / 'docs/user-guide.md'}")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    return subprocess.call([str(python), "-m", "agenthon_quant", *sys.argv[1:]], env=env, shell=False)


if __name__ == "__main__":
    raise SystemExit(main())
