from __future__ import annotations
from collections import Counter
import re
from typing import Iterable
from urllib.parse import urlparse

from .constants import TRUSTED_DOMAINS, TRUSTED_PUBLISHER_NAMES
from .topic_relevance_agent import TopicRelevanceAgent

class SourceQualityAgent:
    """Checks publisher identity, removes duplicates, and balances source coverage."""

    @staticmethod
    def trusted_host(host: str, domains: set[str]) -> bool:
        host = host.lower().removeprefix("www.")
        if host.endswith((".gov", ".gov.uk", ".gov.au", ".gov.in", ".gc.ca", ".govt.nz", ".edu", ".edu.au", ".int", ".mil")):
            return True
        return any(host == domain or host.endswith("." + domain) for domain in domains)

    def select(self, candidate_batches: list[dict], limit: int, extra_domains: Iterable[str] = (), topic: str = "") -> list[dict]:
        domains = TRUSTED_DOMAINS | {d.lower().lstrip(".") for d in extra_domains}
        relevance = TopicRelevanceAgent(topic) if topic else None
        selected, seen, per_publisher = [], set(), Counter()
        candidates = [candidate for batch in candidate_batches for candidate in batch["candidates"]]
        if relevance:
            def candidate_score(candidate: dict) -> tuple[int, int]:
                title = candidate["title"]
                text = f"{title} {candidate.get('rss_summary', '')}"
                historical_format = bool(re.search(r"\b(timeline|chronology|history|historical|key events|major events|court ruling|judgment)\b", title, re.I))
                host = (urlparse(candidate["url"]).hostname or "").lower()
                direct_publisher_link = host not in {"news.google.com", "www.google.com", "google.com"}
                chronology_page = candidate.get("source_kind") == "Wikipedia article"
                return (relevance.match_count(title) * 3 + relevance.match_count(text) +
                        (4 if historical_format else 0) + (8 if direct_publisher_link else 0) +
                        (10 if chronology_page else 0),
                        1 if candidate.get("source_kind") in {"Wikipedia reference", "Wikipedia article"} else 0)
            candidates.sort(key=candidate_score, reverse=True)
        for candidate in candidates:
            relevance_text = f"{candidate['title']} {candidate.get('rss_summary', '')}"
            if candidate.get("source_kind") in {"Wikipedia reference", "Wikipedia article"}:
                reference_context = f"{candidate.get('reference_page_title', '')} {candidate.get('reference_page_context', '')}"
                if relevance and (not relevance.is_relevant(reference_context) or
                                  not relevance.is_relevant_text(candidate["title"])):
                    continue
            elif relevance and not relevance.is_relevant(relevance_text):
                continue
            url_host = (urlparse(candidate["url"]).hostname or "").lower().removeprefix("www.")
            source_host = (urlparse(candidate["publisher_url"]).hostname or "").lower().removeprefix("www.")
            publisher = candidate["publisher"]
            publisher_key = re.sub(r"[^a-z0-9 ]", "", publisher.lower()).strip()
            trusted_name = publisher_key in TRUSTED_PUBLISHER_NAMES or any(
                publisher_key.endswith(" " + name) for name in TRUSTED_PUBLISHER_NAMES
            )
            wikipedia_article = candidate.get("source_kind") == "Wikipedia article" and url_host.endswith("wikipedia.org")
            if not (wikipedia_article or self.trusted_host(url_host, domains) or self.trusted_host(source_host, domains) or trusted_name):
                continue
            identity = source_host or publisher_key or url_host
            dedupe_key = (url_host, candidate["url"], candidate["title"].casefold())
            if not candidate["url"] or dedupe_key in seen or per_publisher[identity] >= 5:
                continue
            seen.add(dedupe_key)
            per_publisher[identity] += 1
            candidate["publisher"] = publisher or source_host or url_host
            selected.append(candidate)
            if len(selected) >= limit:
                break
        return selected

