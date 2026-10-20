"""Mount the immutable publications selected for this provider.

Use archive records directly: the package authoring tool belongs to an older
build toolchain and must not re-publish definitions at application startup.
"""
from pathlib import Path
import hashlib
import json
import zipfile

from blue_language import Language
from blue_repository import Repository

VENDOR = Path(__file__).resolve().parents[1] / "vendor"
ROOT = VENDOR / "packages/blue-coordination"


def context():
    selection = json.loads((VENDOR / "selection.json").read_text())
    language = Language(core_contracts=False)
    aliases = {}
    rules = None
    for namespace, pin in selection["packages"].items():
        path = VENDOR / pin["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
            raise ValueError("PACKAGE_ARCHIVE_MISMATCH:" + namespace)
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("package.json"))
            records = json.loads(archive.read("package-records.json"))
        if manifest["packageBlueId"] != pin["blueId"]:
            raise ValueError("PACKAGE_ID_MISMATCH:" + namespace)
        exports = {namespace + "/" + row["name"]: row["blueId"]
                   for row in manifest["exports"]}
        language.enable_repository(Repository.from_payload(
            "provider:" + namespace, exports, records))
        if namespace == "Coordination":
            aliases = exports
            rules = manifest["semanticSpecifications"][manifest["protocol"]]["rules"]["blueId"]
    if rules is None:
        raise ValueError("MISSING_COORDINATION_PACKAGE")
    return language, aliases, rules
