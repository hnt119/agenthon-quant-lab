#!/usr/bin/env python3
"""Locate the maintained engine; this helper never duplicates calculations."""
from pathlib import Path
import os
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[3]
    python = root / ".venv/bin/python"
    if not python.is_file():
        raise SystemExit(f"Set up the project environment first; see {root / 'README.md'}")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    return subprocess.call([str(python), "-m", "agenthon_quant", *sys.argv[1:]], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
