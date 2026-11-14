from __future__ import annotations
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

from .research_planner_agent import ResearchPlannerAgent
from .topic_relevance_agent import TopicRelevanceAgent

class WikipediaReferenceAgent:
    """Finds a relevant Wikipedia page and extracts its cited external references."""

    def discover(self, topic: str, limit: int = 10) -> dict:
        session = requests.Session()
        session.headers.update({"User-Agent": "TopicTimelineResearch/0.1 (educational; contact: project user)"})
        try:
            topic_context = ResearchPlannerAgent.context_for(topic)
            relevance = TopicRelevanceAgent(topic)
            wiki_queries = [topic_context["normalized_topic"], *topic_context["search_queries"]]
            pages, seen_titles = [], set()
            for query in wiki_queries:
                search = session.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 5},
                    timeout=20,
                )
                search.raise_for_status()
                for page in search.json().get("query", {}).get("search", []):
                    title = page.get("title", "")
                    if title and title.casefold() not in seen_titles:
                        seen_titles.add(title.casefold())
                        pages.append(page)
            candidates = []
            reference_pages = []
            for result in pages[:8]:
                title = result.get("title", "")
                if not title:
                    continue
                page_url = "https://en.wikipedia.org/wiki/" + quote_plus(title).replace("+", "_")
                response = session.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={"action": "parse", "page": title, "prop": "text", "format": "json"},
                    timeout=20,
                )
                response.raise_for_status()
                html_text = response.json().get("parse", {}).get("text", {}).get("*", "")
                soup = BeautifulSoup(html_text, "html.parser")
                page_paragraphs = [" ".join(p.get_text(" ", strip=True).split()) for p in soup.select(".mw-parser-output > p")]
                page_context = " ".join([title, result.get("snippet", ""), *page_paragraphs[:8]])
                if not relevance.is_relevant(page_context, title):
                    continue
                reference_pages.append({"title": title, "url": page_url, "reference_count": 0})
                candidates.append({
                    "title": title,
                    "url": page_url,
                    "publisher": "Wikipedia",
                    "publisher_url": "https://en.wikipedia.org",
                    "published_at": "",
                    "rss_summary": "",
                    "discovery_provider": "wikipedia_article",
                    "discovery_query": topic,
                    "source_kind": "Wikipedia article",
                    "reference_page": page_url,
                    "reference_page_title": title,
                    "reference_page_context": page_context,
                })
                seen_urls = set()
                page_candidate_count = 0
                for citation in soup.select("ol.references li"):
                    citation_text = " ".join(citation.get_text(" ", strip=True).split())
                    for anchor in citation.select("a[href^='http']"):
                        url = anchor.get("href", "").split("#", 1)[0]
                        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
                        if not url.startswith("https://") or host.endswith("wikipedia.org") or url in seen_urls:
                            continue
                        seen_urls.add(url)
                        candidates.append({
                            "title": citation_text[:500] or anchor.get_text(" ", strip=True) or host,
                            "url": url,
                            "publisher": host,
                            "publisher_url": f"https://{host}",
                            "published_at": "",
                            "rss_summary": "",
                            "discovery_provider": "wikipedia_reference",
                            "discovery_query": topic,
                            "source_kind": "Wikipedia reference",
                            "reference_page": page_url,
                            "reference_page_title": title,
                            "reference_page_context": page_context,
                        })
                        reference_pages[-1]["reference_count"] += 1
                        page_candidate_count += 1
                        # Spread Wikipedia leads across relevant pages. A single
                        # broad article can have hundreds of citations that do
                        # not all support the queried event.
                        if page_candidate_count >= 4:
                            break
                    if page_candidate_count >= 4:
                        break
                if len(candidates) >= limit * 3:
                    break
            return {"job": {"provider": "wikipedia", "query": topic}, "candidates": candidates,
                    "error": "" if candidates else "No external references found on matching Wikipedia pages.",
                    "reference_pages": reference_pages}
        except (requests.RequestException, ValueError, KeyError) as exc:
            return {"job": {"provider": "wikipedia", "query": topic}, "candidates": [],
                    "error": str(exc), "reference_pages": []}

