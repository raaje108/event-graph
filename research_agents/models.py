from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Article:
    title: str
    url: str
    publisher: str
    published_at: str
    paragraphs: list[str]
    fetch_status: str = "ok"
    rss_summary: str = ""
    source_kind: str = "news search"
    reference_page: str = ""

