"""Local setup diagnostics and private, inspectable run bundles (no network APIs)."""
from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

from .records import bounded_read, code_identity, digest, strict_json, verify_saved

MAX_BUNDLE_BYTES = 128 * 1024 * 1024
MAX_RECORD_BYTES = 64 * 1024 * 1024


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def skill_directory() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"


def install_skill(root: Path, skills_dir: Path | None = None) -> dict:
    """Create only a new link; an existing same-target symlink is idempotent."""
    target = (root / "skills/quant-research").resolve()
    if not (target / "SKILL.md").is_file():
        raise ValueError("The source checkout is missing skills/quant-research/SKILL.md")
    destination = (skills_dir if skills_dir is not None else skill_directory()) / "quant-research"
    if destination.is_symlink() and destination.resolve() == target:
        return {"status": "already_linked", "path": str(destination), "target": str(target)}
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Skill destination already exists and was preserved: {destination}. Use another --skills-dir or inspect it manually.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(target, target_is_directory=True)
    return {"status": "linked", "path": str(destination), "target": str(target)}


def setup_environment(root: Path, *, with_skill: bool = False, skills_dir: Path | None = None,
                      runner=None) -> dict:
    """Install free package dependencies into the checkout's own virtualenv."""
    if sys.version_info < (3, 12):
        raise ValueError("Python 3.12 or newer is required. Run setup with a supported Python interpreter.")
    root = root.resolve()
    if not all((root / name).is_file() for name in ("pyproject.toml", "requirements-verified.txt")):
        raise ValueError("Setup must run from a complete Agenthon Quant Lab source checkout")
    environment = root / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if environment.is_symlink():
        raise ValueError("Existing .venv is a symlink and was preserved; use a checkout-local environment")
    if environment.exists() and (not environment.is_dir() or not (environment / "pyvenv.cfg").is_file() or not python.is_file()):
        raise ValueError("Existing .venv is not a complete virtual environment and was preserved")
    invoke = runner or subprocess.run
    # Pip's --isolated ignores user configuration and PIP_* option variables,
    # while PIP_CONFIG_FILE=os.devnull also disables global/site config files.
    # Strip inherited redirects before spawning pip or its build subprocesses.
    # Python -I likewise ignores PYTHONPATH/PYTHONHOME and user site packages.
    child_env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PIP_")}
    child_env["PIP_CONFIG_FILE"] = os.devnull
    pip = [str(python), "-I", "-m", "pip", "--isolated", "--require-virtualenv", "--disable-pip-version-check"]
    commands = []
    if not environment.exists():
        commands.append([sys.executable, "-I", "-m", "venv", str(environment)])
    commands.extend([
        [*pip, "install", "-r", str(root / "requirements-verified.txt")],
        [*pip, "install", "-e", str(root), "--no-deps"],
    ])
    for command in commands:
        try:
            invoke(command, cwd=root, check=True, shell=False, env=child_env)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError(f"Setup stopped at {'pip install' if 'pip' in command else 'virtual environment creation'}. No system-Python fallback was attempted. Fix the reported installation error and rerun setup.") from exc
    result = {"status": "ready", "python": str(python), "dependencies": "requirements-verified.txt", "commands_completed": len(commands)}
    if with_skill:
        result["skill"] = install_skill(root, skills_dir)
    return result


def doctor(root: Path | None = None, *, skills_dir: Path | None = None) -> dict:
    """Read local availability without importing finance engines or invoking endpoints."""
    root = (root or repository_root()).resolve()
    checks = []
    checks.append({"name": "python", "status": "passed" if sys.version_info >= (3, 12) else "failed",
                   "required": True, "details": f"{sys.version.split()[0]} at {sys.executable}; requires Python >=3.12"})
    versions = {}
    for package in ("scipy", "numpy", "pyarrow"):
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            version = None
        versions[package] = version
        compatible = version is not None
        if package == "scipy" and version:
            try:
                major, minor = (int(part) for part in version.split(".")[:2])
                compatible = (1, 11) <= (major, minor) < (2, 0)
            except ValueError:
                compatible = False
        required = package in {"scipy", "numpy"}
        detail = version or ("Optional; CSV works without PyArrow" if not required else "Not installed")
        if compatible:
            try:
                importlib.import_module("scipy.integrate" if package == "scipy" else package)
                detail += "; module import succeeded"
            except (ImportError, OSError, RuntimeError) as exc:
                compatible = False
                detail += f"; import failed: {type(exc).__name__}: {exc}"
        elif package == "scipy" and version:
            detail += "; requires >=1.11,<2"
        checks.append({"name": package, "status": "passed" if compatible else "failed" if required else "unavailable",
                       "required": required, "details": detail})
    source_ok = (root / "pyproject.toml").is_file() and (root / "src/agenthon_quant").is_dir()
    checks.append({"name": "source_checkout", "status": "passed" if source_ok else "failed", "required": True,
                   "details": str(root) if source_ok else "Use a source checkout for bundled examples, archive and reproduction"})
    for name in ("examples/options.json", "examples/trading.json", "examples/historical.json", "examples/data/bitstamp/btcusd-2025-q2.csv", "examples/data/synthetic_prices.csv"):
        path = root / name
        checks.append({"name": name, "status": "passed" if path.is_file() else "failed", "required": True,
                       "details": f"sha256:{digest(path.read_bytes())}" if path.is_file() else "Bundled file missing"})
    destination = (skills_dir if skills_dir is not None else skill_directory()) / "quant-research"
    expected = (root / "skills/quant-research").resolve()
    linked = destination.is_symlink() and destination.resolve() == expected
    checks.append({"name": "codex_skill", "status": "passed" if linked else "unavailable", "required": False,
                   "details": "Linked to this checkout" if linked else "Optional. Install with scripts/setup.py --install-skill; existing destinations are preserved"})
    return {"status": "ready" if all(c["status"] == "passed" for c in checks if c["required"]) else "needs_setup",
            "checks": checks, "versions": versions, "code": code_identity(),
            "next_step": "Use btc-study for the frozen BTC comparison or example options, trading or historical. Run python3 scripts/setup.py if required dependencies are missing. No model or broker connection is checked."}


def example_path(kind: str, root: Path | None = None) -> Path:
    if kind not in {"options", "trading", "historical"}:
        raise ValueError("Supported examples are options, trading and historical")
    path = (root or repository_root()) / "examples" / f"{kind}.json"
    if not path.is_file():
        raise ValueError("Bundled example missing; use a complete source checkout")
    return path


def _regular_inside(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts or "\\" in relative:
        raise ValueError(f"Bundle path must be a safe relative path: {relative}")
    path = root
    for part in pure.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Bundle refuses symlink input: {relative}")
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError(f"Bundle input is missing or outside the run directory: {relative}")
    return path


def bundle_run(run_dir: Path, out: Path) -> dict:
    """Package only known run artifacts and verified input snapshots; private by default."""
    if run_dir.is_symlink():
        raise ValueError("Bundle refuses a symlink run directory")
    root = run_dir.resolve()
    if out.resolve().is_relative_to(root):
        raise ValueError("Bundle output must be outside the saved run directory, which remains unchanged")
    if out.exists() or out.is_symlink():
        raise ValueError(f"Bundle output already exists and was preserved: {out}")
    # Reject links before verify_saved follows any snapshot paths.
    raw = bounded_read(_regular_inside(root, "run.json"), MAX_RECORD_BYTES)
    initial = strict_json(raw)
    _regular_inside(root, "spec.json")
    if not isinstance(initial, dict) or not isinstance(initial.get("input_provenance"), list):
        raise ValueError("Run record has no input provenance list")
    snapshots = {}
    for item in initial["input_provenance"]:
        name = item["snapshot"]
        if not isinstance(name, str) or not name.startswith("inputs/"):
            raise ValueError("Only recorded inputs/ snapshots can enter a bundle")
        _regular_inside(root, name)
        if name in snapshots:
            raise ValueError("Duplicate input snapshot in run record")
        snapshots[name] = item["sha256"]
    record = verify_saved(root)
    if record != initial:
        raise ValueError("Run record changed during bundle verification; retry with stable files")
    names = {"run.json", "spec.json", "report.md", *snapshots}
    artifacts = {}
    if record.get("workflow") == "historical" and record["status"] == "passed":
        from .historical_report import CURVE_FILES
        artifacts = record.get("output_artifacts_sha256")
        expected_names = {"report.md", *CURVE_FILES}
        if record["specification"].get("spectral_diagnostic") is True:
            expected_names.add("spectral.json")
        if not isinstance(artifacts, dict) or set(artifacts) != expected_names:
            raise ValueError("Historical run has an incomplete report or curve inventory")
        names.update(artifacts)
    if record["status"] == "passed":
        names.add("validated-results.json")
    elif (root / "validated-results.json").exists():
        raise ValueError("A failed run unexpectedly contains validated results; inspect it before bundling")
    payload = {}
    total = 0
    for name in sorted(names):
        data = bounded_read(_regular_inside(root, name), MAX_RECORD_BYTES)
        total += len(data)
        if total > MAX_BUNDLE_BYTES:
            raise ValueError("Bundle exceeds the 128 MiB content limit")
        if name == "run.json" and data != raw:
            raise ValueError("Run record changed during bundling")
        expected = snapshots.get(name) if name in snapshots else record.get("effective_specification_sha256") if name == "spec.json" else None
        if name in artifacts and digest(data) != artifacts[name]:
            raise ValueError(f"Bundle content hash mismatch: {name}")
        if expected is not None and digest(data) != expected:
            raise ValueError(f"Bundle content hash mismatch: {name}")
        if name == "validated-results.json" and strict_json(data) != record["analysis"]["results"]:
            raise ValueError("Validated results do not match the saved run record")
        payload[name] = data
    manifest = {"schema_version": 1, "intended_visibility": "private", "contains_input_data": bool(snapshots),
                "notice": "Includes input snapshots and local provenance, potentially user-private data. Review redistribution rights before sharing; no upload was performed.",
                "validation_scope": "Saved input and effective-specification hashes; output consistency and per-file content hashes. Calculations were not rerun.",
                "run_status": record["status"], "source_fingerprint_sha256": record["code"]["source_fingerprint_sha256"],
                "files": {name: {"bytes": len(data), "sha256": digest(data)} for name, data in payload.items()}}
    payload["bundle-manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle, zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                item = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                item.external_attr = 0o600 << 16
                archive.writestr(item, data)
    except BaseException:
        out.unlink(missing_ok=True)
        raise
    return {"status": "bundled", "path": str(out.resolve()), "sha256": digest(out.read_bytes()),
            "files": len(payload), "intended_visibility": "private", "notice": manifest["notice"]}
