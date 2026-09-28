import argparse
import html
import json
import subprocess
import sys
from pathlib import Path


def render_html_report(report_path, html_path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    results = report.get("results", [])
    totals = report.get("metrics", {}).get("_totals", {})
    rows = []

    for finding in results:
        severity = finding.get("issue_severity", "UNKNOWN").upper()
        severity_class = severity.lower()
        filename = finding.get("filename", "")
        line_number = finding.get("line_number", "")
        location = f"{filename}:{line_number}"
        cwe = finding.get("issue_cwe") or {}
        cwe_name = cwe.get("name", "") if isinstance(cwe, dict) else ""
        code = finding.get("code", "")
        cwe_html = f'<p class="cwe">{html.escape(cwe_name)}</p>' if cwe_name else ""
        code_html = f"<pre>{html.escape(code)}</pre>" if code else ""
        rows.append(
            "<tr>"
            f'<td><span class="severity {html.escape(severity_class)}">'
            f"{html.escape(severity)}</span></td>"
            f'<td><code>{html.escape(finding.get("test_id", ""))}</code></td>'
            f"<td><code>{html.escape(location)}</code></td>"
            f'<td>{html.escape(finding.get("issue_text", ""))}'
            f"{cwe_html}{code_html}</td>"
            "</tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="4">No findings reported.</td></tr>')

    errors = report.get("errors", [])
    errors_html = "".join(f"<li>{html.escape(str(error))}</li>" for error in errors)
    document = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Bandit Security Audit</title>
    <style>
        :root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #202923; background: #f4f6f3; }}
        body {{ max-width: 1200px; margin: 0 auto; padding: 32px 20px; }}
        h1 {{ margin: 0 0 6px; font-size: 1.8rem; }}
        .generated {{ margin: 0; color: #526157; }}
        .summary {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 24px 0; }}
        .metric {{ min-width: 120px; padding: 14px 18px; border: 1px solid #d6ded7; background: #fff; }}
        .metric strong {{ display: block; font-size: 1.4rem; }}
        .metric span {{ color: #526157; font-size: .85rem; }}
        .table-wrap {{ overflow-x: auto; border: 1px solid #d6ded7; background: #fff; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; border-bottom: 1px solid #e2e8e3; text-align: left; vertical-align: top; }}
        th {{ background: #eaf0eb; font-size: .8rem; text-transform: uppercase; }}
        code, pre {{ font-family: ui-monospace, monospace; font-size: .85rem; }}
        pre {{ max-width: 680px; overflow-x: auto; padding: 10px; background: #f4f6f3; }}
        .severity {{ display: inline-block; padding: 3px 7px; font-size: .75rem; font-weight: 700; }}
        .high {{ background: #f8d9d5; color: #76251b; }}
        .medium {{ background: #f8e7bd; color: #664500; }}
        .low {{ background: #dcefe2; color: #245333; }}
        .unknown {{ background: #e4e8e5; color: #344139; }}
        .cwe {{ margin: 6px 0 0; color: #526157; font-size: .85rem; }}
        .errors {{ padding: 12px 16px; border-left: 4px solid #a33427; background: #f8d9d5; }}
    </style>
</head>
<body>
    <h1>Bandit Security Audit</h1>
    <p class="generated">Generated: {html.escape(str(report.get("generated_at", "unknown")))}</p>
    <section class="summary" aria-label="Finding summary">
        <div class="metric"><strong>{len(results)}</strong><span>Total findings</span></div>
        <div class="metric"><strong>{totals.get("SEVERITY.HIGH", 0)}</strong><span>High severity</span></div>
        <div class="metric"><strong>{totals.get("SEVERITY.MEDIUM", 0)}</strong><span>Medium severity</span></div>
        <div class="metric"><strong>{totals.get("SEVERITY.LOW", 0)}</strong><span>Low severity</span></div>
        <div class="metric"><strong>{totals.get("loc", 0)}</strong><span>Lines analyzed</span></div>
    </section>
    {f'<section class="errors"><strong>Scanner errors</strong><ul>{errors_html}</ul></section>' if errors else ''}
    <div class="table-wrap">
        <table>
            <thead><tr><th>Severity</th><th>Rule</th><th>Location</th><th>Finding</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </div>
</body>
</html>
"""
    html_path.write_text(document, encoding="utf-8")
    print(f"Bandit HTML report: {html_path}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Run or render a Bandit security audit."
    )
    parser.add_argument(
        "--beautify",
        action="store_true",
        help="Render the existing JSON report as HTML without running Bandit.",
    )
    arguments = parser.parse_args()

    repository_root = Path(__file__).resolve().parents[1]
    report_path = repository_root / "audit" / "bandit-report.json"
    html_path = repository_root / "audit" / "bandit-report.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if arguments.beautify:
        if not report_path.is_file():
            print(f"Bandit JSON report not found: {report_path}", file=sys.stderr)
            return 2
        return render_html_report(report_path, html_path)

    docker_arguments = [
        "docker",
        "run",
        "--rm",
        "--volume",
        f"{repository_root}:/workspace",
        "--workdir",
        "/workspace",
        "ghcr.io/pycqa/bandit/bandit:latest",
        "-r",
        "src",
        "-f",
        "json",
        "-o",
        "audit/bandit-report.json",
    ]
    print(f"Bandit JSON report: {report_path}", flush=True)
    return subprocess.run(docker_arguments, cwd=repository_root, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
