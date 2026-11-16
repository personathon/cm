# Central Swagger scripts

Place this folder at `personathon/cm/scripts/swagger/`.

## Requirements
- Python 3.9+
- A checked-out consumer Maven repository

## Detect existing Swagger dependencies
```bash
python scripts/swagger/detect_swagger.py --repo /path/to/consumer-repo
python scripts/swagger/detect_swagger.py --repo /path/to/consumer-repo --json
```

## Plan dependency installation (dry run by default)
```bash
python scripts/swagger/install_swagger.py --repo /path/to/consumer-repo --springdoc-version 3.0.3
```

Apply only after checking Spring Boot/springdoc compatibility:
```bash
python scripts/swagger/install_swagger.py --repo /path/to/consumer-repo --module spring-petclinic-customers-service --springdoc-version 3.0.3 --apply
```

The installer adds `springdoc-openapi-starter-webmvc-ui` to detected Spring MVC
modules only. It does not automatically handle WebFlux starter selection,
Spring Boot version discovery, profiles, Maven properties, or all inherited
dependency-management arrangements. The version is deliberately supplied by
the caller instead of being guessed. A `.swagger.bak` copy is created before
each POM is modified. Review `git diff` and build before committing.

## Validate a running service's OpenAPI JSON
```bash
python scripts/swagger/validate_openapi.py --url http://localhost:8081/v3/api-docs
```

This checks HTTP retrieval, JSON parsing, OpenAPI 3.x version, paths and
operation count. It is not a full OpenAPI schema validator and does not
currently parse YAML.

## Suggested first test
Against the local `spring-petclinic-microservices` clone:
```bash
python /path/to/cm/scripts/swagger/detect_swagger.py --repo .
python /path/to/cm/scripts/swagger/install_swagger.py --repo . --module spring-petclinic-customers-service --springdoc-version 3.0.3
```
Review dry-run output first. Confirm the version is compatible with the
consumer's Spring Boot version before using `--apply`.
