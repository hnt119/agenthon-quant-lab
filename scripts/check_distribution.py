"""Compare both built wheels and the sdist to the reviewed source and data allowlist."""
import argparse
from email.parser import BytesParser
from pathlib import Path
import tarfile
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(wheel, sdist, rebuilt):
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = config["project"]
    setup = config["tool"]["setuptools"]
    resources = setup["package-data"]["agenthon_quant._bundled"]
    version = project["version"]
    base = f"agenthon_quant_lab-{version}"
    require(wheel.name == rebuilt.name == base + "-py3-none-any.whl", "Unexpected wheel filename")
    require(sdist.name == base + ".tar.gz", "Unexpected sdist filename")
    sources = [p.relative_to(ROOT).as_posix() for pkg in setup["packages"] if pkg != "agenthon_quant._bundled"
               for p in (ROOT / "src" / pkg).glob("*.py")]
    dist_info = base + ".dist-info/"
    payload = {p.removeprefix("src/"): p for p in sources}
    payload.update({"agenthon_quant/_bundled/" + p: p for p in resources})
    payload.update({dist_info + "licenses/" + p: p for p in project["license-files"]})
    generated = {dist_info + p for p in ("METADATA", "WHEEL", "RECORD", "entry_points.txt", "top_level.txt")}
    with zipfile.ZipFile(wheel) as a, zipfile.ZipFile(rebuilt) as b:
        for archive in (a, b):
            names = archive.namelist()
            require(len(names) == len(set(names)) and set(names) == payload.keys() | generated,
                    "Unexpected, duplicate or missing wheel members")
            for name, original in payload.items():
                require(archive.read(name) == (ROOT / original).read_bytes(), f"Wheel payload differs: {name}")
        for name in a.namelist():
            require(a.read(name) == b.read(name), f"Rebuilt wheel differs: {name}")
        metadata = a.read(dist_info + "METADATA")
        require(b"quant-lab = agenthon_quant.cli:main" in a.read(dist_info + "entry_points.txt"), "Missing entry point")
    info = BytesParser().parsebytes(metadata)
    require(info["Name"] == project["name"] and info["Version"] == version, "Incorrect core metadata")
    require(info["License-Expression"] == project["license"] and
            set(info.get_all("License-File")) == set(project["license-files"]), "Incorrect license metadata")
    require(info.get_payload(decode=True).decode("utf-8").strip() == (ROOT / project["readme"]).read_text().strip(), "Description differs")
    tracked = set(sources + resources + project["license-files"] + ["MANIFEST.in", "README.md", "PYPI.md"])
    egg = "src/agenthon_quant_lab.egg-info/"
    extras = {"setup.cfg", "PKG-INFO"} | {egg + n for n in
             ("PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt", "requires.txt", "top_level.txt")}
    with tarfile.open(sdist) as archive:
        seen = set()
        for member in archive:
            if member.isdir():
                continue
            require(member.isfile() and member.name.startswith(base + "/"), "Unexpected source archive member")
            name = member.name[len(base) + 1:]
            require(name not in seen and name in tracked | extras, f"Unlisted source file: {name}")
            seen.add(name)
            if name in tracked:
                require(archive.extractfile(member).read() == (ROOT / name).read_bytes(), f"Source file differs: {name}")
            elif name == "PKG-INFO":
                require(archive.extractfile(member).read() == metadata, "Source and wheel metadata differ")
        require(seen == tracked | extras, "Missing source archive members")
    print(f"Passed: {len(resources)} canonical resources, both licenses, {len(sources)} Python files, "
          f"all {len(payload) + len(generated)} wheel members and {len(seen)} sdist files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("wheel", "sdist", "rebuilt"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    check(args.wheel, args.sdist, args.rebuilt)
