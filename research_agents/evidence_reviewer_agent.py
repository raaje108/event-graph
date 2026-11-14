from __future__ import annotations
import re
from .models import Article

class EvidenceReviewerAgent:
    """Rejects timeline claims unless their exact evidence exists in the cited page text."""

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.casefold().split())

    def review(self, events: list[dict], articles: list[Article]) -> tuple[list[dict], list[dict]]:
        page_text = {article.url: self._normalize(" ".join(article.paragraphs)) for article in articles}
        accepted, rejected = [], []
        for event in events:
            source_text = page_text.get(event["source_url"], "")
            evidence = self._normalize(event["evidence"])
            year = event["event_date"][:4]
            supported = bool(evidence and evidence in source_text)
            if event["date_basis"].startswith("month/day; year inferred"):
                supported = supported and year in source_text
            if event["date_precision"] == "year":
                supported = supported and year in evidence
            if supported:
                event["evidence_review"] = "supported by extracted source text"
                accepted.append(event)
            else:
                event["evidence_review"] = "rejected: cited evidence could not be matched to the scraped page"
                rejected.append(event)
        return accepted, rejected

