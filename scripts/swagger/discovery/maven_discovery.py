"""Discover Maven modules recursively, including modules not listed at the root."""
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {"m": "http://maven.apache.org/POM/4.0.0"}

def _text(node, path):
    found = node.find(path, NS)
    return (found.text or "").strip() if found is not None and found.text else None

def discover_modules(repo: Path) -> list[dict]:
    found = {}
    for pom in repo.rglob("pom.xml"):
        # Avoid generated/build folders and the report output.
        if any(part in {".git", "target", ".swagger-discovery"} for part in pom.parts):
            continue
        try:
            root = ET.parse(pom).getroot()
        except (ET.ParseError, OSError):
            continue
        rel = pom.parent.relative_to(repo).as_posix()
        name = _text(root, "m:artifactId") or (repo.name if rel == "." else pom.parent.name)
        found[str(pom.parent.resolve())] = {
            "path": pom.parent.resolve(),
            "pom": pom.resolve(),
            "module": name,
            "relative_path": "." if rel == "." else rel,
        }
    # Root POM first, then modules in stable path order.
    return sorted(found.values(), key=lambda x: (x["relative_path"] != ".", x["relative_path"]))
