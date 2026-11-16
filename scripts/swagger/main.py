#!/usr/bin/env python3
"""Stage 1: dynamically discover Spring Boot API modules. Read-only."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from discovery.maven_discovery import discover_modules
from discovery.module_analyzer import analyze_module
from reporting.report_generator import write_reports


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover Spring Boot modules and Swagger readiness without modifying the repository."
    )
    parser.add_argument("--repo", required=True, help="Path to the consumer Maven repository")
    parser.add_argument("--output", help="Optional output directory (default: <repo>/.swagger-discovery)")
    parser.add_argument("--include-tests", action="store_true", help="Also scan test source roots for API annotations")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        parser.error(f"Repository directory does not exist: {repo}")
    if not (repo / "pom.xml").is_file():
        parser.error(f"No root pom.xml found under: {repo}")

    modules = discover_modules(repo)
    results = [analyze_module(repo, module, include_tests=args.include_tests) for module in modules]

    output_dir = Path(args.output).expanduser().resolve() if args.output else repo / ".swagger-discovery"
    write_reports(repo, results, output_dir)

    summary = {
        "modules_discovered": len(results),
        "spring_boot_modules": sum(bool(x["spring_boot_version"]) for x in results),
        "web_modules": sum(bool(x["web_frameworks"]) for x in results),
        "api_candidate_modules": sum(x["api_candidate"] for x in results),
        "swagger_configured_modules": sum(x["swagger_detected"] for x in results),
        "report_directory": str(output_dir),
    }
    print(json.dumps(summary, indent=2))
    print("\nModule details:")
    for item in results:
        frameworks = ",".join(item["web_frameworks"]) or "none"
        print(
            f'- {item["module"]}: boot={item["spring_boot_version"] or "unknown"}, '
            f'java={item["java_version"] or "unknown"}, web={frameworks}, '
            f'rest_controllers={item["rest_controller_count"]}, '
            f'swagger={item["swagger_detected"]}, api_candidate={item["api_candidate"]}'
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
