from __future__ import annotations
import argparse
import json
from pathlib import Path
import requests

from .report_writer_agent import ReportWriterAgent
from .research_pipeline import parse_date, run_research

def main() -> None:
    parser = argparse.ArgumentParser(description="Research a past event and build a cited, dated timeline.")
    parser.add_argument("topic", help="Event or subject to research")
    parser.add_argument("--limit", type=int, default=20, help="Maximum trusted news pages to fetch (default: 20)")
    parser.add_argument("--from-date", dest="start", help="Keep events on/after YYYY-MM-DD")
    parser.add_argument("--to-date", dest="end", help="Keep events on/before YYYY-MM-DD")
    parser.add_argument("--allow-domain", action="append", default=[], help="Additional trusted domain; repeat as needed")
    parser.add_argument("--output", default="research_timeline.md", help="Markdown report path")
    parser.add_argument("--json", dest="json_output", help="Optional JSON evidence bundle path")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 50:
        parser.error("--limit must be between 1 and 50")
    try:
        report = run_research(args.topic, args.limit, parse_date(args.start), parse_date(args.end), args.allow_domain)
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        parser.exit(1, f"Research stopped before generating a report: {exc}\nCheck network access, then try again.\n")
    output = Path(args.output)
    output.write_text(ReportWriterAgent().render(report), encoding="utf-8")
    print(f"Wrote {output.resolve()} ({len(report['timeline'])} dated events, {len(report['articles'])} sources fetched).")
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {Path(args.json_output).resolve()}")
    failed = sum(article["fetch_status"] != "ok" for article in report["articles"])
    print(f"Pages with extraction/fetch issues: {failed}. Review the source list in the report.")

