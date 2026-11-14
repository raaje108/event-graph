from __future__ import annotations
from datetime import date
import re

class TimelineEditor:
    """Sorts and conservatively merges repeated claims without losing citations."""

    @staticmethod
    def review(events: list[dict], start: date | None = None, end: date | None = None) -> list[dict]:
        merged: dict[tuple[str, str], dict] = {}
        for event in events:
            value = event["event_date"]
            if len(value) == 4:
                event_start, event_end = date(int(value), 1, 1), date(int(value), 12, 31)
            else:
                event_start = event_end = date.fromisoformat(value)
            if start and event_end < start or end and event_start > end:
                continue
            key = (event["event_date"], re.sub(r"\W+", " ", event["event"].lower()).strip())
            if key not in merged:
                merged[key] = {**event, "sources": []}
            citation = {k: event[k] for k in ("publisher", "source_title", "source_url", "article_published_at", "evidence", "source_kind", "reference_page")}
            if citation not in merged[key]["sources"]:
                merged[key]["sources"].append(citation)
        return sorted(merged.values(), key=lambda item: (item["event_date"], item["event"].casefold()))

