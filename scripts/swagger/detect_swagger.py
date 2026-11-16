#!/usr/bin/env python3
"""Detect direct springdoc dependencies in Spring Boot Maven modules."""
import argparse, json
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {"m": "http://maven.apache.org/POM/4.0.0"}
WEB = {"spring-boot-starter-web", "spring-boot-starter-webmvc", "spring-boot-starter-webflux"}

def val(node, name):
    x = node.find(f"m:{name}", NS)
    return x.text.strip() if x is not None and x.text else None

def deps(root):
    x = root.find("m:dependencies", NS)
    if x is None: return []
    return [{"groupId": val(d,"groupId"), "artifactId": val(d,"artifactId"),
             "version": val(d,"version")} for d in x.findall("m:dependency", NS)]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    pom = repo / "pom.xml"
    if not pom.is_file(): ap.error(f"pom.xml not found: {pom}")
    root = ET.parse(pom).getroot()
    mods = root.find("m:modules", NS)
    paths = [repo / m.text.strip() / "pom.xml" for m in mods.findall("m:module", NS) if m.text] if mods is not None else [pom]
    result = []
    for path in paths:
        if not path.is_file(): continue
        module = ET.parse(path).getroot()
        ds = deps(module)
        web = any(d["artifactId"] in WEB for d in ds)
        sd = [d for d in ds if d["groupId"] == "org.springdoc" or (d["artifactId"] or "").startswith("springdoc-openapi-")]
        result.append({
            "module": str(path.parent.relative_to(repo)) or ".",
            "artifactId": val(module, "artifactId"),
            "springWebModule": web,
            "springdocDependencies": sd,
            "swaggerDependencyDetected": bool(sd),
            "action": "already-present-review-runtime" if sd else ("candidate-for-install" if web else "not-a-detected-web-module")
        })
    report = {"repository": str(repo), "modules": result,
              "summary": {"modulesInspected": len(result),
                          "webModulesMissingSpringdoc": sum(1 for x in result if x["springWebModule"] and not x["swaggerDependencyDetected"])}}
    if a.json: print(json.dumps(report, indent=2))
    else:
        for x in result:
            print(f'{x["module"]}: web={x["springWebModule"]}, swagger={x["swaggerDependencyDetected"]}, action={x["action"]}')
        print("Summary:", report["summary"])
if __name__ == "__main__": main()
