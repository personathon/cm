"""Write machine-readable and human-readable discovery reports."""
from pathlib import Path
import json
from datetime import datetime, timezone

def write_reports(repo: Path, results: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": str(repo),
        "stage": "discovery-only",
        "read_only": True,
        "modules": results,
    }
    (output_dir / "discovery-report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    lines = [
        "# Swagger discovery report", "",
        f"- Repository: `{repo}`",
        "- Mode: read-only discovery (no POM changes, builds or service starts)", "",
        "| Module | Spring Boot | Java | Web framework | REST controllers | Swagger detected | API candidate |",
        "|---|---:|---:|---|---:|---|---|",
    ]
    for x in results:
        lines.append(
            f"| `{x['module']}` | {x['spring_boot_version'] or 'unknown'} | "
            f"{x['java_version'] or 'unknown'} | "
            f"{', '.join(x['web_frameworks']) or 'none'} | "
            f"{x['rest_controller_count']} | {x['swagger_detected']} | {x['api_candidate']} |"
        )
    lines += ["", "## Module notes", ""]
    for x in results:
        lines.append(f"### {x['module']}")
        if x["rest_controller_files"]:
            lines.append("- Controller candidates: " + ", ".join(f"`{p}`" for p in x["rest_controller_files"]))
        if x["swagger_source_hits"]:
            lines.append("- Swagger source markers: " + ", ".join(f"`{p}`" for p in x["swagger_source_hits"]))
        if x["notes"]:
            lines.extend(f"- {note}" for note in x["notes"])
        else:
            lines.append("- No additional notes.")
        lines.append("")
    (output_dir / "discovery-report.md").write_text("\n".join(lines), encoding="utf-8")
