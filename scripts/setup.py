#!/usr/bin/env python3
"""Create a checkout-local environment; optionally link the maintained Codex skill."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-skill", action="store_true", help="Link quant-research while preserving existing destinations")
    parser.add_argument("--skills-dir", type=Path, help="Override the destination skills directory")
    args = parser.parse_args(argv)
    if args.skills_dir is not None and not args.install_skill:
        parser.error("--skills-dir requires --install-skill")
    if sys.version_info < (3, 12):
        parser.exit(2, "Setup requires Python 3.12 or newer. Rerun with a supported interpreter.\n")
    from agenthon_quant.onboarding import setup_environment
    try:
        result = setup_environment(ROOT, with_skill=args.install_skill, skills_dir=args.skills_dir)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Setup failed: {exc}\n")
    print(json.dumps(result, indent=2))
    print("Next: .venv/bin/python -m agenthon_quant doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
