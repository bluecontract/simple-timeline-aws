"""Reproduce the pinned MyOS-compatible runtime from blue-packages Git history.

The working tree and its current branch are intentionally irrelevant. Updating
vendor/selection.json is an explicit protocol upgrade, not a routine rebuild.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT.parent / "blue-packages")
    args = parser.parse_args()
    out = ROOT / "vendor"
    selection = json.loads((out / "selection.json").read_text())
    paths = ["blue-language", "blue-bex", "blue-contracts", "blue-coordination",
             "verification/reference/blue-contracts"]
    archive = subprocess.check_output([
        "git", "-C", str(args.source), "archive", selection["sourceRevision"], *paths])
    with tempfile.TemporaryDirectory(prefix="timeline-vendor-") as temporary:
        source = Path(temporary) / "source"
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(source, filter="data")
        staged = Path(temporary) / "vendor"
        staged.mkdir()
        subprocess.run([sys.executable, "-B", str(source / "blue-contracts/tools/release.py"),
                        "runtime-copy", str(staged / "runtime")], check=True)
        # Verify the published Contracts/BEX implementation bindings, including
        # source overrides applied by the pinned runtime-copy command.
        for name in ("blue-bex", "blue-contracts"):
            bindings = json.loads((source / name / "docs/sources.json").read_text())
            for relative, digest in bindings["modules"].items():
                if sha(staged / "runtime" / relative.removeprefix("src/")) != digest.removeprefix("sha256:"):
                    raise ValueError("Runtime source mismatch: " + relative)
        for pin in selection["packages"].values():
            relative = Path(pin["path"]).relative_to("packages")
            if sha(source / relative) != pin["sha256"]:
                raise ValueError("Package archive mismatch: " + str(relative))
            name = relative.parts[0]
            copies = ["dist/package.bluepkg"]
            if name == "blue-contracts":
                copies += ["tools"]
            if name == "blue-coordination":
                copies += ["types", "spec", "tools", "blue-package.yaml", "blue-package.lock.json"]
            for item in copies:
                src, dest = source / name / item, staged / "packages" / name / item
                dest.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    shutil.copyfile(src, dest)
        # Runtime-only adapter: mount exact archives instead of invoking the
        # historical publisher. No protocol definitions or execution rules change.
        for name in ("reference.py", "examples.py"):
            path = staged / "packages/blue-coordination/tools" / name
            text = path.read_text()
            if text.count("import package as publisher") != 1:
                raise ValueError("Unexpected publisher adapter: " + name)
            path.write_text(text.replace("import package as publisher",
                                        "from app import protocol_packages as publisher"))
        shutil.copyfile(out / "selection.json", staged / "selection.json")
        manifest = {p.relative_to(staged).as_posix(): sha(p)
                    for p in sorted(staged.rglob("*"))
                    if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        for name in ("runtime", "packages", "tools"):
            shutil.rmtree(out / name)
            shutil.copytree(staged / name, out / name)
        shutil.copyfile(staged / "manifest.json", out / "manifest.json")
        print("Vendored", len(manifest), "verified files from", selection["sourceRevision"])


if __name__ == "__main__":
    main()
