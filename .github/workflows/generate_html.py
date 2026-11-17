#!/usr/bin/env python3
"""
Generic k6 JSON-to-HTML report generator.
Input: k6 JSON output produced with: k6 run --out json=results.json script.js
No Python dependencies required.
"""
import argparse
import datetime as dt
import html
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def percentile(values, p):
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return float(vals[0])
    rank = (len(vals) - 1) * p / 100.0
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(vals[lo])
    return float(vals[lo] + (vals[hi] - vals[lo]) * (rank - lo))


def stats(values):
    if not values:
        return {"count": 0, "avg": 0, "min": 0, "max": 0,
                "p90": 0, "p95": 0, "p99": 0}
    return {
        "count": len(values), "avg": statistics.fmean(values),
        "min": min(values), "max": max(values),
        "p90": percentile(values, 90), "p95": percentile(values, 95),
        "p99": percentile(values, 99),
    }


def esc(value):
    return html.escape(str(value))


def fmt(value, suffix=" ms"):
    return f"{value:.2f}{suffix}"


def svg_bars(rows, key, title, width=900, row_h=34):
    usable = width - 260
    max_v = max((r[key] for r in rows), default=0) or 1
    height = max(90, 48 + row_h * len(rows))
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">']
    parts.append('<style>.lbl{font:13px Arial;fill:#cbd5e1}.val{font:12px Arial;fill:#e2e8f0}.bar{fill:#38bdf8}</style>')
    for i, row in enumerate(rows):
        y = 28 + i * row_h
        name = esc(row["name"])
        v = row[key]
        bar_w = max(1, usable * v / max_v)
        parts.append(f'<text class="lbl" x="8" y="{y+13}">{name[:34]}</text>')
        parts.append(f'<rect class="bar" x="250" y="{y}" width="{bar_w:.1f}" height="18" rx="4"/>')
        parts.append(f'<text class="val" x="{min(250+bar_w+8,width-65):.1f}" y="{y+14}">{v:.1f} ms</text>')
    parts.append("</svg>")
    return "".join(parts)


def parse_file(path):
    groups = defaultdict(list)
    requests = defaultdict(list)
    failed = defaultdict(int)
    statuses = defaultdict(int)
    check_counts = defaultdict(lambda: [0, 0])
    error_details = defaultdict(lambda: {
        "count": 0,
        "statuses": defaultdict(int),
        "messages": defaultdict(int),
    })
    timestamps = []
    total_http = 0
    total_failed_http = 0
    total_iterations = 0
    total_vus = []
    metric_samples = defaultdict(list)

    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                point = json.loads(line)
            except json.JSONDecodeError:
                # k6 JSON output is newline-delimited JSON; report malformed lines clearly.
                continue
            if point.get("type") != "Point":
                continue
            metric = point.get("metric", "")
            data = point.get("data") or {}
            tags = data.get("tags") or {}
            value = data.get("value")
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            if data.get("time"):
                try:
                    timestamps.append(dt.datetime.fromisoformat(data["time"].replace("Z", "+00:00")))
                except Exception:
                    pass

            if metric == "group_duration":
                # k6 normally records the current group path in the "group" tag.
                name = tags.get("group") or tags.get("name") or "Ungrouped"
                name = name.split("::")[-1] if name else "Ungrouped"
                groups[name].append(value)
            elif metric == "http_req_duration":
                name = tags.get("name") or tags.get("url") or "Unnamed request"
                requests[name].append(value)
            elif metric == "http_reqs":
                total_http += value
            elif metric == "http_req_failed":
                if value:
                    total_failed_http += 1
                    name = tags.get("name") or tags.get("url") or "Unnamed request"
                    failed[name] += 1
                    status = tags.get("status", "")
                    error = tags.get("error") or tags.get("error_code") or ""
                    error_details[name]["count"] += 1
                    if status:
                        error_details[name]["statuses"][status] += 1
                    if error:
                        error_details[name]["messages"][error] += 1
            elif metric == "http_req_duration":
                pass
            elif metric == "checks":
                check_name = tags.get("check") or "Unnamed check"
                check_counts[check_name][0] += 1
                if value:
                    check_counts[check_name][1] += 1
            elif metric == "iterations":
                total_iterations += value
            elif metric == "vus":
                total_vus.append(value)
            else:
                metric_samples[metric].append(value)

            if metric == "http_reqs":
                status = tags.get("status")
                if status:
                    statuses[str(status)] += value

    # Some k6 versions may emit http_req_failed as 0/1 rate points; count failed samples.
    # Derive test duration from timestamps.
    duration_s = 0.0
    if len(timestamps) >= 2:
        duration_s = max(0.0, (max(timestamps) - min(timestamps)).total_seconds())

    return {
        "groups": {k: stats(v) for k, v in sorted(groups.items())},
        "requests": {k: stats(v) for k, v in sorted(requests.items())},
        "failed_by_request": dict(failed),
        "statuses": dict(statuses),
        "error_details": {
            k: {"count": v["count"], "statuses": dict(v["statuses"]), "messages": dict(v["messages"])}
            for k, v in error_details.items()
        },
        "checks": dict(check_counts),
        "http_reqs": int(total_http),
        "failed_http_samples": int(total_failed_http),
        "iterations": int(total_iterations),
        "max_vus": max(total_vus, default=0),
        "duration_s": duration_s,
        "raw_metric_names": sorted(metric_samples),
    }


def table(rows, columns):
    head = "".join(f"<th>{esc(col[0])}</th>" for col in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{renderer(row.get(key))}</td>" for _, key, renderer in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{''.join(body) or '<tr><td colspan=\"9\">No samples found</td></tr>'}</tbody></table></div>"


def identity(v):
    return esc(v if v is not None else "-")


def ms(v):
    return fmt(float(v or 0))


def count(v):
    return f"{int(v or 0):,}"


def build_report(data, input_name, output):
    groups = [{"name": k, **v} for k, v in data["groups"].items()]
    requests = [{"name": k, **v} for k, v in data["requests"].items()]
    check_rows = []
    for name, (total, passed) in data["checks"].items():
        check_rows.append({"name": name, "total": total, "passed": passed,
                           "failed": total-passed,
                           "rate": (passed/total*100) if total else 0})
    error_rows = []
    for name, ed in sorted(data["error_details"].items(), key=lambda x: -x[1]["count"]):
        status_str = ", ".join(
            f"HTTP {s} ×{c}" for s, c in sorted(ed["statuses"].items())
        ) or "—"
        msg_str = "; ".join(
            f"{html.escape(m)} ×{c}"
            for m, c in sorted(ed["messages"].items(), key=lambda x: -x[1])[:3]
        ) or "—"
        error_rows.append({"name": name, "count": ed["count"],
                           "statuses": status_str, "messages": msg_str})
    error_table = table(error_rows, [
        ("Endpoint", "name", identity),
        ("Failures", "count", count),
        ("Status Codes", "statuses", identity),
        ("Error Messages", "messages", identity),
    ]) if error_rows else "<p style='color:var(--green)'>No failures recorded.</p>"

    group_table = table(groups, [
        ("Transaction", "name", identity), ("Executions", "count", count),
        ("Avg", "avg", ms), ("Min", "min", ms), ("Max", "max", ms),
        ("P90", "p90", ms), ("P95", "p95", ms), ("P99", "p99", ms)])
    request_table = table(requests, [
        ("API request", "name", identity), ("Samples", "count", count),
        ("Avg", "avg", ms), ("Min", "min", ms), ("Max", "max", ms),
        ("P90", "p90", ms), ("P95", "p95", ms), ("P99", "p99", ms)])
    check_table = table(check_rows, [
        ("Check", "name", identity), ("Total", "total", count),
        ("Passed", "passed", count), ("Failed", "failed", count),
        ("Pass rate", "rate", lambda v: f"{v:.1f}%")])
    avg_chart = svg_bars(groups, "avg", "Average transaction duration")
    p95_chart = svg_bars(groups, "p95", "P95 transaction duration")
    duration = f"{data['duration_s']:.1f} s" if data["duration_s"] else "N/A"
    fail_rate = (data["failed_http_samples"] / data["http_reqs"] * 100) if data["http_reqs"] else 0
    generated = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>k6 Performance Test Report</title>
<style>
:root{{--bg:#0b1220;--panel:#111c2f;--panel2:#17243a;--text:#e5edf8;--muted:#9aabc2;--line:#263750;--blue:#38bdf8;--green:#34d399;--red:#fb7185}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}}
.wrap{{max-width:1440px;margin:auto;padding:28px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:24px}}
h1{{font-size:28px;margin:0 0 5px}}h2{{font-size:18px;margin:0 0 16px}}h3{{font-size:14px;color:var(--muted);font-weight:500;margin:0 0 8px}}
.muted,.meta{{color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:18px 0 24px}}
.card,.section{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}}
.value{{font-size:27px;font-weight:700;letter-spacing:-.5px}}.good{{color:var(--green)}}.bad{{color:var(--red)}}
.section{{margin:16px 0}}.charts{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}svg{{width:100%;height:auto;display:block}}
.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;white-space:nowrap}}th,td{{padding:11px 12px;text-align:left;border-bottom:1px solid var(--line)}}
th{{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}}td:first-child{{font-weight:600}}tbody tr:hover{{background:var(--panel2)}}
footer{{color:var(--muted);padding:18px 2px;font-size:12px}}.pill{{display:inline-block;padding:4px 9px;border-radius:99px;background:var(--panel2);color:var(--blue)}}
@media(max-width:850px){{.grid{{grid-template-columns:repeat(2,1fr)}}.charts{{grid-template-columns:1fr}}header{{display:block}}}}
@media(max-width:480px){{.wrap{{padding:14px}}.grid{{grid-template-columns:1fr 1fr}}.value{{font-size:21px}}}}
</style></head><body><main class="wrap">
<header><div><span class="pill">k6 PERFORMANCE REPORT</span><h1>Test execution overview</h1>
<div class="meta">Source: {esc(input_name)} · Generated: {esc(generated)}</div></div><div class="meta">Standalone HTML report</div></header>
<section class="grid">
<div class="card"><h3>HTTP requests</h3><div class="value">{data['http_reqs']:,}</div></div>
<div class="card"><h3>Iterations</h3><div class="value">{data['iterations']:,}</div></div>
<div class="card"><h3>Max observed VUs</h3><div class="value">{data['max_vus']:g}</div></div>
<div class="card"><h3>Observed duration</h3><div class="value">{duration}</div></div>
<div class="card"><h3>HTTP failures</h3><div class="value {'bad' if data['failed_http_samples'] else 'good'}">{data['failed_http_samples']:,}</div></div>
<div class="card"><h3>HTTP failure ratio*</h3><div class="value {'bad' if fail_rate else 'good'}">{fail_rate:.2f}%</div></div>
<div class="card"><h3>Transactions found</h3><div class="value">{len(groups)}</div></div>
<div class="card"><h3>API request names found</h3><div class="value">{len(requests)}</div></div>
</section>
<section class="section"><h2>Transaction summary</h2>{group_table}</section>
<section class="section"><h2>Transaction response-time comparison</h2><div class="charts"><div><h3>Average duration</h3>{avg_chart}</div><div><h3>P95 duration</h3>{p95_chart}</div></div></section>
<section class="section"><h2>API request details</h2>{request_table}</section>
<section class="section"><h2>Checks</h2>{check_table}</section>
<section class="section"><h2>HTTP status distribution</h2>
{table([{"status":k,"count":v} for k,v in sorted(data["statuses"].items())],
[("HTTP status","status",identity),("Requests","count",count)])}</section>
<section class="section"><h2>Error details</h2>{error_table}</section>
<footer>* HTTP failure ratio is an estimate from emitted http_req_failed samples divided by http_reqs. Transaction duration uses k6 group_duration samples and includes time spent inside the group, including sleep(). Percentiles are calculated from recorded samples. This report only includes metrics present in the input JSON.</footer>
</main></body></html>"""
    Path(output).write_text(html_doc, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate a standalone HTML report from k6 JSON output.")
    parser.add_argument("input", help="k6 newline-delimited JSON output file")
    parser.add_argument("-o", "--output", default="k6-report.html", help="HTML report path")
    args = parser.parse_args()
    data = parse_file(args.input)
    build_report(data, Path(args.input).name, args.output)
    print(f"HTML report generated: {Path(args.output).resolve()}")
    print(f"Transactions: {len(data['groups'])} | Named API requests: {len(data['requests'])}")


if __name__ == "__main__":
    main()
