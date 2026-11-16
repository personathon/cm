"""Analyze one Maven POM and its source tree. Static analysis only; no build or edits."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

NS = {"m": "http://maven.apache.org/POM/4.0.0"}
WEB_ARTIFACTS = {
    "spring-boot-starter-web": "webmvc",
    "spring-boot-starter-webmvc": "webmvc",
    "spring-boot-starter-webflux": "webflux",
}
REST_ANNOTATIONS = (
    "@RestController", "@Controller", "@RequestMapping", "@GetMapping",
    "@PostMapping", "@PutMapping", "@DeleteMapping", "@PatchMapping",
)
SWAGGER_MARKERS = (
    "springdoc-openapi", "io.swagger.v3", "OpenAPI", "GroupedOpenApi",
    "OpenApiResource", "SwaggerConfig",
)

def _find_text(root, path):
    el = root.find(path, NS)
    return (el.text or "").strip() if el is not None and el.text else None

def _properties(root):
    result = {}
    props = root.find("m:properties", NS)
    if props is not None:
        for child in list(props):
            tag = child.tag.split("}", 1)[-1]
            result[tag] = (child.text or "").strip()
    return result

def _dependencies(root):
    deps = []
    for dep in root.findall(".//m:dependencies/m:dependency", NS):
        group = _find_text(dep, "m:groupId")
        artifact = _find_text(dep, "m:artifactId")
        version = _find_text(dep, "m:version")
        if group and artifact:
            deps.append((group, artifact, version))
    return deps

def _resolve_simple(value, props):
    if not value:
        return None
    # Resolve simple ${property} references; leave unresolved expressions visible.
    for _ in range(10):
        match = re.search(r"\$\{([^}]+)\}", value)
        if not match:
            break
        replacement = props.get(match.group(1))
        if replacement is None:
            break
        value = value[:match.start()] + replacement + value[match.end():]
    return value

def _boot_version(root, props):
    parent_version = _find_text(root, "m:parent/m:version")
    parent_artifact = _find_text(root, "m:parent/m:artifactId")
    parent_group = _find_text(root, "m:parent/m:groupId")
    if parent_artifact == "spring-boot-starter-parent" and parent_group == "org.springframework.boot":
        return _resolve_simple(parent_version, props)
    for key in ("spring-boot.version", "spring-boot.version.number", "spring.boot.version"):
        if key in props:
            return _resolve_simple(props[key], props)
    for group, artifact, version in _dependencies(root):
        if group == "org.springframework.boot" and artifact.startswith("spring-boot-"):
            if version:
                return _resolve_simple(version, props)
    return None

def _java_version(root, props):
    for key in ("java.version", "maven.compiler.release", "maven.compiler.source", "jdk.version"):
        if key in props:
            return _resolve_simple(props[key], props)
    for path in ("m:build/m:plugins/m:plugin", "m:build/m:pluginManagement/m:plugins/m:plugin"):
        for plugin in root.findall(path, NS):
            if _find_text(plugin, "m:artifactId") == "maven-compiler-plugin":
                for conf in plugin.findall("m:configuration", NS):
                    for key in ("release", "source", "target"):
                        val = _find_text(conf, f"m:{key}")
                        if val:
                            return _resolve_simple(val, props)
    return None

def analyze_module(repo: Path, module: dict, include_tests: bool = False) -> dict:
    pom = module["pom"]
    try:
        root = ET.parse(pom).getroot()
    except (ET.ParseError, OSError) as exc:
        return _empty(module, f"Cannot parse POM: {exc}")

    props = _properties(root)
    deps = _dependencies(root)
    artifacts = {a for _, a, _ in deps}
    frameworks = sorted({framework for artifact, framework in WEB_ARTIFACTS.items() if artifact in artifacts})
    swagger = any(
        group == "org.springdoc" or artifact.startswith("springdoc-openapi-") or group.startswith("io.swagger")
        for group, artifact, _ in deps
    )

    source_roots = [module["path"] / "src" / "main" / "java"]
    if include_tests:
        source_roots.append(module["path"] / "src" / "test" / "java")

    controller_files = set()
    swagger_source_hits = set()
    for source_root in source_roots:
        if not source_root.exists():
            continue
        for java_file in source_root.rglob("*.java"):
            try:
                content = java_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(marker in content for marker in REST_ANNOTATIONS):
                controller_files.add(str(java_file.relative_to(repo)))
            if any(marker in content for marker in SWAGGER_MARKERS):
                swagger_source_hits.add(str(java_file.relative_to(repo)))

    boot = _boot_version(root, props)
    java = _java_version(root, props)
    return {
        "module": module["module"],
        "relative_path": module["relative_path"],
        "pom": str(pom.relative_to(repo)),
        "spring_boot_version": boot,
        "java_version": java,
        "web_frameworks": frameworks,
        "web_dependency_detected": bool(frameworks),
        "rest_controller_count": len(controller_files),
        "rest_controller_files": sorted(controller_files),
        "swagger_detected": bool(swagger or swagger_source_hits),
        "swagger_dependency_detected": swagger,
        "swagger_source_hits": sorted(swagger_source_hits),
        "api_candidate": bool(frameworks and controller_files),
        "notes": _notes(boot, java, frameworks, controller_files, swagger),
    }

def _notes(boot, java, frameworks, controllers, swagger):
    notes = []
    if not boot:
        notes.append("Spring Boot version not resolved from this POM; parent/effective POM may be required.")
    if not java:
        notes.append("Java version not resolved from this POM; it may be inherited from a parent.")
    if len(frameworks) > 1:
        notes.append("Both MVC and WebFlux dependencies detected; inspect runtime configuration before selecting Springdoc starter.")
    if frameworks and not controllers:
        notes.append("Web dependency found, but no REST/controller annotations detected in src/main/java.")
    if controllers and not frameworks:
        notes.append("Controller annotations found without a recognized direct Spring Boot web starter.")
    if swagger:
        notes.append("Swagger/Springdoc marker detected; validate configuration and endpoint rather than reinstalling.")
    return notes

def _empty(module, note):
    return {
        "module": module["module"], "relative_path": module["relative_path"],
        "pom": str(module["pom"]), "spring_boot_version": None, "java_version": None,
        "web_frameworks": [], "web_dependency_detected": False,
        "rest_controller_count": 0, "rest_controller_files": [],
        "swagger_detected": False, "swagger_dependency_detected": False,
        "swagger_source_hits": [], "api_candidate": False, "notes": [note],
    }
