from __future__ import annotations
import re
from urllib.parse import quote_plus

class ResearchPlannerAgent:
    """Creates separate search tasks so coverage isn't tied to one query wording."""

    @staticmethod
    def context_for(topic: str) -> dict:
        normalized = " ".join(topic.split())
        return {
            "normalized_topic": normalized,
            "search_queries": [
                normalized,
                f"{normalized} timeline key events",
                f"{normalized} history chronology dates causes consequences",
            ],
        }

    def plan(self, topic: str, providers: tuple[str, ...] = ("bing", "google")) -> list[dict]:
        search_queries = self.context_for(topic)["search_queries"]
        jobs = []
        for query in search_queries:
            for provider in providers:
                if provider == "bing":
                    url = f"https://www.bing.com/news/search?q={quote_plus(query)}&format=rss"
                else:
                    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
                jobs.append({"provider": provider, "query": query, "feed_url": url})
        return jobs

