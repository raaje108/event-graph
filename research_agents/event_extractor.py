from __future__ import annotations
from collections import Counter
from datetime import date, datetime, timezone
import re

from .constants import DATE_PATTERNS, YEARLESS_DATE_PATTERNS, YEAR_PATTERN, month_number
from .models import Article

class EventExtractor:
    """Extracts explicitly dated sentences; publication dates stay separate."""

    @staticmethod
    def _event_date(sentence: str, year_hint: int | None = None) -> tuple[str, str, str] | None:
        for idx, pattern in enumerate(DATE_PATTERNS):
            match = pattern.search(sentence)
            if not match:
                continue
            try:
                if idx == 0:
                    month, day, year = match.groups()
                    return date(int(year), month_number(month), int(day)).isoformat(), "day", "explicit full date"
                if idx == 1:
                    day, month, year = match.groups()
                    return date(int(year), month_number(month), int(day)).isoformat(), "day", "explicit full date"
                if idx == 2:
                    year, month, day = match.groups()
                    return date(int(year), int(month), int(day)).isoformat(), "day", "explicit full date"
                first, second, year = map(int, match.groups())
                parsed = date(year, second, first) if first > 12 else date(year, first, second)
                return parsed.isoformat(), "day", "explicit numeric date (month/day assumed when ambiguous)"
            except ValueError:
                return None
        if year_hint:
            for idx, pattern in enumerate(YEARLESS_DATE_PATTERNS):
                match = pattern.search(sentence)
                if not match:
                    continue
                try:
                    month, day = match.groups() if idx == 0 else (match.group(2), match.group(1))
                    parsed = date(year_hint, month_number(month), int(day))
                    return parsed.isoformat(), "day", f"month/day; year inferred from source context ({year_hint})"
                except ValueError:
                    return None
        year_match = YEAR_PATTERN.search(sentence)
        if year_match:
            year = int(year_match.group(1))
            if 1900 <= year <= datetime.now(timezone.utc).year and len(sentence) >= 45:
                return str(year), "year", "explicit year only"
        return None

    def extract(self, article: Article) -> list[dict]:
        # A search snippet or headline is useful for discovery, but it is not
        # enough evidence to create a dated historical event.
        if article.fetch_status.startswith(("rss_summary_only", "fetch_error", "no_article_text")):
            return []
        events = []
        years = Counter(int(year) for paragraph in article.paragraphs for year in YEAR_PATTERN.findall(paragraph))
        year_hint = years.most_common(1)[0][0] if years else None
        for paragraph in article.paragraphs:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“])", paragraph) if s.strip()]
            anchors = []
            for index, sentence in enumerate(sentences):
                parsed_date = self._event_date(sentence, year_hint)
                if parsed_date and len(sentence) >= 35:
                    anchors.append((index, sentence, parsed_date))
            for anchor_no, (index, sentence, parsed_date) in enumerate(anchors):
                # Keep the complete dated passage up to the next dated event.
                # When a paragraph has one date, the whole paragraph is its context.
                start = 0 if anchor_no == 0 else index
                end = anchors[anchor_no + 1][0] if anchor_no + 1 < len(anchors) else len(sentences)
                context = " ".join(sentences[start:end]).strip()
                event_date, date_precision, date_basis = parsed_date
                events.append({
                    "event_date": event_date,
                    "date_precision": date_precision,
                    "event": sentence,
                    "context": context or sentence,
                    "evidence": sentence,
                    "source_title": article.title,
                    "publisher": article.publisher,
                    "source_url": article.url,
                    "source_kind": article.source_kind,
                    "reference_page": article.reference_page,
                    "article_published_at": article.published_at,
                    "date_basis": date_basis,
                })
        return events

