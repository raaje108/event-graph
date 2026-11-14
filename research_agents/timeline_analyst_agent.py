from __future__ import annotations
from .event_extractor import EventExtractor
from .models import Article

class TimelineAnalystAgent:
    """Extracts dated event claims from one article at a time."""

    def analyze(self, article: Article) -> list[dict]:
        return EventExtractor().extract(article)

