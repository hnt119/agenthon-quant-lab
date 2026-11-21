"""Show a saved Quant Lab diagnostic in a sibling copy of the offline Edge Lab dashboard."""
import argparse
from html import escape
from pathlib import Path

from agenthon_quant.records import bounded_read, digest, strict_json


def render(dashboard: Path, run: Path, output: Path) -> None:
    if output.resolve().parent != dashboard.resolve().parent:
        raise ValueError("Choose a new HTML file beside the dashboard to preserve its relative links")
    record = strict_json(bounded_read(run / "run.json", 64 * 1024 * 1024))
    if (record["workflow"] != "historical" or record["status"] != "passed"
            or record["specification"].get("spectral_diagnostic") is not True):
        raise ValueError("Choose a passed historical run with spectral_diagnostic enabled")
    payload = bounded_read(run / "spectral.json", 64 * 1024 * 1024)
    if digest(payload) != record["output_artifacts_sha256"]["spectral.json"]:
        raise ValueError("Spectral artifact hash differs from the run record")
    spectral = strict_json(payload)
    latest = spectral["observations"][-1]
    def value(key):
        return escape(str(latest[key])) if latest[key] is not None else "Unavailable"

    panel = (
        '<details><summary>Quant Lab · Historical spectral diagnostic</summary>'
        f'<p>{escape(spectral["source"])}</p><p>At the close on {value("date")} · {value("status")}</p>'
        f'<p>Normalized entropy: {value("spectral_entropy")} · Dominant period: '
        f'{value("dominant_period_observations")} trading observations</p>'
        f'<p>{spectral["window_returns"]:d} completed returns · {escape(spectral["return_basis"])}</p></details>'
    )
    write_panel(dashboard, output, panel)


def write_panel(dashboard: Path, output: Path, panel: str) -> None:
    """Insert a saved-result panel into a new sibling of an offline Edge Lab page."""
    if output.resolve().parent != dashboard.resolve().parent:
        raise ValueError("Choose a new HTML file beside the dashboard to preserve its relative links")
    html = dashboard.read_text(encoding="utf-8")
    if 'id="dashboard-data"' not in html or html.count("<footer>") != 1:
        raise ValueError("Expected the Edge Lab offline dashboard with its report footer")
    with output.open("x", encoding="utf-8") as handle:
        handle.write(html.replace("<footer>", panel + "\n  <footer>", 1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dashboard", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        render(args.dashboard, args.run, args.out)
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        parser.exit(2, f"edge_lab_spectral: {exc}\n")
