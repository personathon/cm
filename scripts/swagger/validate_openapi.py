#!/usr/bin/env python3
"""Fetch and perform basic structural validation of an OpenAPI JSON URL."""
import argparse, json, sys, urllib.error, urllib.request

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True)
    ap.add_argument("--timeout", type=int, default=20)
    a = ap.parse_args()
    req = urllib.request.Request(a.url, headers={"Accept":"application/json", "User-Agent":"cm-openapi-validator/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=a.timeout) as res:
            status, body, ctype = res.status, res.read().decode("utf-8"), res.headers.get("Content-Type","")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as e:
        print(f"ERROR: unable to retrieve URL: {e}", file=sys.stderr); return 2
    try: spec = json.loads(body)
    except json.JSONDecodeError:
        print("ERROR: response is not JSON. Use the /v3/api-docs JSON endpoint.", file=sys.stderr); return 3
    version, paths = spec.get("openapi"), spec.get("paths")
    if not isinstance(version, str) or not version.startswith("3."):
        print(f"ERROR: expected OpenAPI 3.x, got {version!r}", file=sys.stderr); return 4
    if not isinstance(paths, dict):
        print("ERROR: missing or invalid paths object", file=sys.stderr); return 5
    methods = {"get","post","put","patch","delete","options","head","trace"}
    ops = [(m.upper(), p) for p, item in paths.items() if isinstance(item,dict) for m in item if m.lower() in methods]
    print(f"HTTP status: {status}\nContent-Type: {ctype}\nOpenAPI: {version}")
    print(f"Title: {spec.get('info',{}).get('title','untitled')}\nPaths: {len(paths)}\nOperations: {len(ops)}")
    for method, path in ops: print(f"  {method:6} {path}")
    if not ops: print("WARNING: no HTTP operations found"); return 6
    print("Basic OpenAPI validation passed."); return 0
if __name__ == "__main__": raise SystemExit(main())
