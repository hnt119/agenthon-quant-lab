"""Search the curated local archive; never execute or fetch historical experiments."""
from pathlib import Path
import json

from .records import bounded_read, strict_json

ARCHIVES = {"papers": "research/papers.json", "experiments": "experiments/experiments.json"}


def search_archive(root: Path, category: str, query: str = "", status: str | None = None) -> list[dict]:
    if category not in ARCHIVES:
        raise ValueError("Archive category must be papers or experiments")
    path = root / ARCHIVES[category]
    if not path.is_file():
        raise ValueError(f"Curated {category} archive is unavailable in this checkout: {ARCHIVES[category]}")
    document = strict_json(bounded_read(path, 8 * 1024 * 1024))
    records = document.get(category) if isinstance(document, dict) else None
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise ValueError(f"Archive must contain a {category} array of records")
    needle = query.casefold().strip()
    selected = []
    for record in records:
        if status is not None and str(record.get("adaptation_status" if category == "papers" else "status", "")).casefold() != status.casefold():
            continue
        if needle and needle not in json.dumps(record, ensure_ascii=False, sort_keys=True).casefold():
            continue
        selected.append(record)
    return selected
