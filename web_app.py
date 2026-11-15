"""Local web interface for the EventGraph research pipeline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import uuid

from research_agents.research_pipeline import parse_date, run_research

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
WORKERS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="eventgraph-research")


def _ui_report(report: dict) -> dict:
    """Keep the browser payload focused on graph, evidence, and source details."""
    articles = [
        {key: article.get(key, "") for key in
         ("title", "publisher", "url", "source_kind", "reference_page", "published_at", "fetch_status")}
        for article in report.get("articles", [])
    ]
    return {
        "topic": report.get("topic", ""),
        "topic_interpretation": report.get("topic_interpretation", ""),
        "generated_at": report.get("generated_at", ""),
        "source_count": report.get("source_count", len(articles)),
        "timeline": report.get("timeline", []),
        "articles": articles,
        "agent_run": report.get("agent_run", []),
        "limitations": report.get("limitations", []),
    }


def _run_job(job_id: str, topic: str, limit: int, start: str | None, end: str | None) -> None:
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "running"
        JOBS[job_id]["message"] = "Searching sources and building your event graph…"
    try:
        report = run_research(topic, limit=limit, start=parse_date(start), end=parse_date(end))
        with JOBS_LOCK:
            JOBS[job_id].update(status="completed", message="Research complete", result=_ui_report(report))
    except Exception as exc:  # Keep the web worker alive and return a useful error to the UI.
        with JOBS_LOCK:
            JOBS[job_id].update(status="failed", message=str(exc))


class EventGraphHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            self._send_json({"status": "ok", "service": "EventGraph"})
            return
        if path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                response = dict(job) if job else None
            self._send_json(response or {"error": "Research job not found"}, 200 if job else 404)
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/research":
            self._send_json({"error": "Not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 16_384:
                raise ValueError("Request body must be between 2 bytes and 16 KB")
            data = json.loads(self.rfile.read(length))
            topic = " ".join(str(data.get("topic", "")).split())
            if not topic or len(topic) > 200:
                raise ValueError("Enter a topic between 1 and 200 characters")
            limit = int(data.get("limit", 20))
            if not 1 <= limit <= 50:
                raise ValueError("Source limit must be between 1 and 50")
            start, end = data.get("start") or None, data.get("end") or None
            start_date, end_date = parse_date(start), parse_date(end)
            if start_date and end_date and start_date > end_date:
                raise ValueError("Start date must be earlier than or equal to end date")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, 400)
            return

        job_id = uuid.uuid4().hex
        with JOBS_LOCK:
            JOBS[job_id] = {"status": "queued", "message": "Queued for research"}
        WORKERS.submit(_run_job, job_id, topic, limit, start, end)
        self._send_json({"job_id": job_id}, 202)

    def log_message(self, format: str, *args) -> None:
        print(f"[EventGraph] {self.address_string()} - {format % args}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the EventGraph local web app")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind (default: localhost only)")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), EventGraphHandler)
    print(f"EventGraph is running at http://{args.host}:{args.port} — press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping EventGraph…")
    finally:
        server.server_close()
        WORKERS.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
