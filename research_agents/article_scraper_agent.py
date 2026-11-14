from __future__ import annotations
from .page_reader import PageReader

class ArticleScraperAgent:
    """Fetches and extracts one publisher page as an isolated delegated task."""

    def scrape(self, source: dict) -> Article:
        return PageReader().read(source)

