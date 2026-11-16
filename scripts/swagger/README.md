# Dynamic Swagger Discovery Engine — Stage 1

This stage scans a consumer Maven repository and produces a discovery report. It is deliberately **read-only**: it does not edit POM files, download dependencies, build projects, start applications, or call external services.

## Requirements
- Python 3.9+
- No third-party Python packages

## Run from the central `cm` repository

```bash
python scripts/swagger/main.py \
  --repo /path/to/consumer-repository
```

Optional:
```bash
python scripts/swagger/main.py \
  --repo /path/to/consumer-repository \
  --output /path/to/report-folder
```

To include test source roots in annotation scanning:
```bash
python scripts/swagger/main.py \
  --repo /path/to/consumer-repository \
  --include-tests
```

## Output
The default output directory is `<consumer-repo>/.swagger-discovery/`:
- `discovery-report.json` — machine-readable output for later automation stages
- `discovery-report.md` — readable summary

## What it detects
- Every `pom.xml` found recursively (root and nested modules)
- Module artifact IDs and POM paths
- Spring Boot version when visible in the module POM
- Java version when visible in module properties/compiler plugin
- Direct Spring Boot WebMVC/WebFlux starter dependencies
- REST/controller annotation candidates in `src/main/java`
- Springdoc / Swagger dependency and source-code markers

## Important limitations of Stage 1
This is a static first-pass discovery engine, not a complete Maven model resolver:
- It does not yet calculate inherited dependencies/properties from parent POMs or imported BOMs.
- It does not execute `mvn help:effective-pom`.
- It does not resolve dependency versions from Maven Central.
- It does not prove a detected controller is reachable or that a module is a deployable API service.
- Annotation scanning is heuristic; it can miss Kotlin, XML configuration, composed annotations, generated sources, and non-Java APIs.
- A module with both WebMVC and WebFlux is flagged for review; no starter is selected automatically.

Those gaps are intentional for Stage 1. The next stage will add effective-POM resolution and compatibility-aware Springdoc selection before any POM modifications.

## Safety
Review the reports before proceeding. No `--apply` option exists in this stage because this stage never changes the consumer repository.
