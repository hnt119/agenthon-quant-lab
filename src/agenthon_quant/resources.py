"""Locate canonical resources in a development tree or an unpacked pip installation."""
from importlib.resources import files
from pathlib import Path
import subprocess


def checkout_root() -> Path | None:
    package = Path(__file__).resolve().parent
    root = package.parent.parent
    if package.parent.name == "src" and (root / "pyproject.toml").is_file():
        return root
    return None


def resource_root() -> Path:
    root = checkout_root()
    if root is not None:
        return root
    # pip installs wheels on disk. Existing CSV, gzip and CLI input readers use Paths.
    return Path(files("agenthon_quant").joinpath("_bundled"))


def checkout_commit() -> str | None:
    root = checkout_root()
    if root is not None and (root / ".git").exists():
        try:
            return subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            pass
    return None
