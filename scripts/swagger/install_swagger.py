#!/usr/bin/env python3
"""Plan or add springdoc Swagger UI dependency to selected Maven web modules."""
import argparse, shutil
from pathlib import Path
import xml.etree.ElementTree as ET

URI = "http://maven.apache.org/POM/4.0.0"
NS = {"m": URI}
ET.register_namespace("", URI)
WEB = {"spring-boot-starter-web", "spring-boot-starter-webmvc", "spring-boot-starter-webflux"}

def q(name): return f"{{{URI}}}{name}"
def val(node, name):
    x = node.find(f"m:{name}", NS)
    return x.text.strip() if x is not None and x.text else None
def direct_deps(root):
    x = root.find("m:dependencies", NS)
    return x, ([] if x is None else x.findall("m:dependency", NS))
def has_springdoc(root):
    for path in ("m:dependencies", "m:dependencyManagement/m:dependencies"):
        parent = root.find(path, NS)
        if parent is not None:
            for d in parent.findall("m:dependency", NS):
                if val(d,"groupId") == "org.springdoc" or (val(d,"artifactId") or "").startswith("springdoc-openapi-"):
                    return True
    return False
def is_web(root):
    _, ds = direct_deps(root)
    return any(val(d,"artifactId") in WEB for d in ds)
def modules(root):
    x = root.find("m:modules", NS)
    return [m.text.strip() for m in x.findall("m:module", NS) if m.text] if x is not None else ["."]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--springdoc-version", required=True, help="Choose a version compatible with the project's Spring Boot version")
    ap.add_argument("--module", action="append", help="Module directory; repeat for multiple modules")
    ap.add_argument("--apply", action="store_true", help="Write changes; default is dry-run")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    rootpom = repo / "pom.xml"
    if not rootpom.is_file(): ap.error(f"pom.xml not found: {rootpom}")
    root = ET.parse(rootpom).getroot()
    targets = a.module or modules(root)
    print(f'{"APPLY" if a.apply else "DRY RUN"}; springdoc version={a.springdoc_version}')
    for mod in targets:
        pom = rootpom if mod == "." else repo / mod / "pom.xml"
        if not pom.is_file():
            print(f"{mod}: SKIP (pom.xml not found)")
            continue
        tree = ET.parse(pom); node = tree.getroot()
        if has_springdoc(node):
            print(f"{mod}: already has springdoc; unchanged")
            continue
        if not is_web(node):
            print(f"{mod}: not detected as Spring web module; unchanged")
            continue
        parent, _ = direct_deps(node)
        if parent is None: parent = ET.SubElement(node, q("dependencies"))
        dep = ET.SubElement(parent, q("dependency"))
        ET.SubElement(dep, q("groupId")).text = "org.springdoc"
        # This starter is for Spring MVC. Review WebFlux modules separately.
        ET.SubElement(dep, q("artifactId")).text = "springdoc-openapi-starter-webmvc-ui"
        ET.SubElement(dep, q("version")).text = a.springdoc_version
        if a.apply:
            backup = pom.with_suffix(pom.suffix + ".swagger.bak")
            if not backup.exists(): shutil.copy2(pom, backup)
            tree.write(pom, encoding="UTF-8", xml_declaration=True)
            print(f"{mod}: UPDATED (backup: {backup.name})")
        else:
            print(f"{mod}: WOULD UPDATE")
    if not a.apply: print("No files changed. Review the plan, then repeat with --apply.")
    else: print("Review git diff and run Maven build before committing.")
if __name__ == "__main__": main()
