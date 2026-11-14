"""Topic-to-timeline research prototype.

The pipeline has four specialist stages: source discovery, page extraction,
dated claim extraction, and timeline review. It uses public Bing News RSS for
discovery and keeps each event attached to the sentence and URL that support it.
"""

from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
import html
import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "TopicTimelineResearch/0.1 (educational project)"
TRUSTED_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "npr.org",
    "nytimes.com", "wsj.com", "ft.com", "cnn.com", "theguardian.com",
    "aljazeera.com", "bloomberg.com", "cnbc.com", "pbs.org", "abcnews.go.com",
    "cbsnews.com", "nbcnews.com", "usatoday.com", "time.com", "politico.com",
    "thehill.com", "axios.com", "economist.com", "france24.com", "dw.com",
    "cbc.ca", "abc.net.au", "theconversation.com", "federalreserve.gov",
    "sec.gov", "fdic.gov", "justice.gov", "congress.gov", "gov.uk",
    "bankofengland.co.uk", "ecb.europa.eu", "who.int", "un.org",
    "thehindu.com", "indianexpress.com", "hindustantimes.com", "timesofindia.indiatimes.com",
    "abc.net.au", "thecanadianpressnews.ca", "scmp.com", "straitstimes.com",
    "japantimes.co.jp", "koreaherald.com", "haaretz.com", "lemonde.fr", "spiegel.de",
    "elpais.com", "corriere.it", "thelocal.com",
}
TRUSTED_PUBLISHER_NAMES = {
    "reuters", "associated press", "ap", "bbc", "npr", "new york times",
    "wall street journal", "financial times", "cnn", "the guardian", "guardian",
    "al jazeera", "bloomberg", "cnbc", "pbs", "abc news", "cbs news",
    "nbc news", "usa today", "time", "politico", "the hill", "axios",
    "the economist", "france 24", "dw", "cbc", "abc australia", "the conversation",
    "federal reserve", "fdic", "u.s. securities and exchange commission", "sec",
    "u.s. department of justice", "department of justice", "congress.gov",
    "bank of england", "european central bank", "world health organization", "un news",
    "the hindu", "indian express", "hindustan times", "times of india", "scmp",
    "south china morning post", "straits times", "japan times", "korea herald",
    "haaretz", "le monde", "der spiegel", "el pais", "corriere della sera",
}
MONTH = ("January February March April May June July August September October "
         "November December").split()
MONTH_PATTERN = "January|Jan\\.?|February|Feb\\.?|March|Mar\\.?|April|Apr\\.?|May|June|Jun\\.?|July|Jul\\.?|August|Aug\\.?|September|Sep\\.?|October|Oct\\.?|November|Nov\\.?|December|Dec\\.?"
def month_number(value: str) -> int:
    normalized = value.strip().rstrip(".").casefold()
    for index, month in enumerate(MONTH, start=1):
        if normalized == month.casefold() or normalized == month[:3].casefold():
            return index
    raise ValueError(f"Unknown month: {value}")

DATE_PATTERNS = [
    re.compile(rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(\d{{4}})\b", re.I),
    re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_PATTERN})[,]?\s+(\d{{4}})\b", re.I),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b"),
]
YEARLESS_DATE_PATTERNS = [
    re.compile(rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", re.I),
    re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_PATTERN})\b", re.I),
]
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")


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


class TopicRelevanceAgent:
    """Rejects pages and event claims that do not actually discuss the requested topic."""

    STOP_WORDS = {"the", "and", "for", "from", "with", "about", "what", "when", "where", "who", "how", "was", "were", "its", "that", "this", "into", "near", "has", "had", "have", "on", "in", "of", "to", "a", "an"}
    GENERIC_TERMS = {"war", "conflict", "history", "timeline", "chronology", "event", "events", "crisis", "story", "overview", "key", "major", "causes", "consequences"}

    def __init__(self, topic: str):
        self.context = ResearchPlannerAgent.context_for(topic)
        self.topic_terms = {word.casefold() for word in re.findall(r"[A-Za-z0-9]+", self.context["normalized_topic"])
                            if word.casefold() not in self.STOP_WORDS | self.GENERIC_TERMS and len(word) > 1}

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {word.casefold() for word in re.findall(r"[A-Za-z0-9]+", text)}

    def match_count(self, text: str) -> int:
        words = self._tokens(text)
        matched = 0
        for term in self.topic_terms:
            if term in words or any(len(word) >= 5 and SequenceMatcher(None, term, word).ratio() >= 0.80 for word in words):
                matched += 1
        return matched

    def is_relevant_text(self, text: str) -> bool:
        if not self.topic_terms:
            return False
        # Body text often uses a short name, pronouns, or a related wording;
        # source selection separately requires a stronger topic match.
        return self.match_count(text) >= 1

    def is_relevant(self, text: str, reference_page_title: str = "") -> bool:
        return self.is_relevant_text(f"{text} {reference_page_title}")


class NewsSearchAgent:
    """One independent worker per provider/query pair; returns raw candidates."""

    def search(self, job: dict) -> dict:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        try:
            response = session.get(job["feed_url"], timeout=20)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            candidates = []
            for item in root.findall(".//item"):
                source = item.find("{*}Source")
                if source is None:
                    source = item.find("{*}source")
                link = (item.findtext("link") or "").strip()
                parsed_link = urlparse(link)
                if parsed_link.hostname and parsed_link.hostname.endswith("bing.com"):
                    target = parse_qs(parsed_link.query).get("url", [""])[0]
                    if target:
                        link = unquote(target)
                publisher = source.text.strip() if source is not None and source.text else ""
                candidates.append({
                    "title": html.unescape(item.findtext("title") or "Untitled"),
                    "url": link,
                    "publisher": publisher,
                    "publisher_url": source.get("url", "") if source is not None else "",
                    "published_at": item.findtext("pubDate") or "",
                    "rss_summary": BeautifulSoup(item.findtext("description") or "", "html.parser").get_text(" ", strip=True),
                    "discovery_provider": job["provider"],
                    "discovery_query": job["query"],
                    "source_kind": "news search",
                    "reference_page": "",
                })
            return {"job": job, "candidates": candidates, "error": ""}
        except (requests.RequestException, ET.ParseError) as exc:
            return {"job": job, "candidates": [], "error": str(exc)}


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


class SourceResearchOrchestratorAgent:
    """Plans delegated searches, runs agents concurrently, then reviews their sources."""

    def __init__(self):
        self.planner = ResearchPlannerAgent()
        self.search_agent = NewsSearchAgent()
        self.wikipedia_agent = WikipediaReferenceAgent()
        self.quality_agent = SourceQualityAgent()

    def research(self, topic: str, limit: int, extra_domains: Iterable[str] = ()) -> tuple[list[dict], list[dict], list[dict]]:
        jobs = self.planner.plan(topic)
        with ThreadPoolExecutor(max_workers=4) as pool:
            search_future = pool.map(self.search_agent.search, jobs)
            wiki_future = pool.submit(self.wikipedia_agent.discover, topic, max(limit, 10))
            batches = list(search_future)
            wiki_batch = wiki_future.result()
        reserve = min(max(1, limit // 4), max(0, limit - 1))
        wiki_sources = self.quality_agent.select([wiki_batch], reserve, extra_domains, topic) if reserve else []
        search_sources = self.quality_agent.select(batches, limit - len(wiki_sources), extra_domains, topic)
        sources = search_sources + wiki_sources
        if len(sources) < limit:
            used = {source["url"] for source in sources}
            additional = self.quality_agent.select(batches, limit, extra_domains, topic)
            sources.extend(source for source in additional if source["url"] not in used and len(sources) < limit)
        if not sources:
            errors = [batch["error"] for batch in batches if batch["error"]]
            detail = "; ".join(errors) if errors else "No result passed the trusted-publisher checks."
            raise RuntimeError(f"Research planner found no usable sources: {detail}")
        run_trace = [{"provider": batch["job"]["provider"], "query": batch["job"]["query"],
                      "candidate_count": len(batch["candidates"]), "error": batch["error"]}
                     for batch in batches]
        run_trace.append({"provider": "wikipedia", "query": topic,
                          "candidate_count": len(wiki_batch["candidates"]), "error": wiki_batch["error"]})
        return sources, run_trace, wiki_batch.get("reference_pages", [])


class PageReader:
    """Fetches article text while retaining the canonical URL and publication date."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _resolve_google_news_url(self, url: str) -> str:
        """Resolve current Google News RSS wrapper IDs to their publisher URL.

        Google's current links use an undocumented batchexecute endpoint. This
        resolver is intentionally isolated so a Google format change is visible
        and can fall back to the RSS summary instead of pretending to scrape an article.
        """
        parsed = urlparse(url)
        if parsed.hostname not in {"news.google.com", "www.news.google.com"}:
            return url
        parts = parsed.path.split("/")
        try:
            article_id = parts[parts.index("articles") + 1]
        except (ValueError, IndexError):
            return url
        page = self.session.get(f"https://news.google.com/articles/{article_id}", timeout=20,
                                headers={"Cookie": "CONSENT=PENDING+987", "Accept-Language": "en-US,en;q=0.9"})
        page.raise_for_status()
        signature_match = re.search(r'data-n-a-sg=["\']([^"\']+)', page.text)
        timestamp_match = re.search(r'data-n-a-ts=["\'](\d+)', page.text)
        if not signature_match or not timestamp_match:
            raise ValueError("Google News article link could not be resolved (missing redirect metadata)")
        inner = [
            "garturlreq",
            [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
             "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
            article_id,
            int(timestamp_match.group(1)),
            signature_match.group(1),
        ]
        outer = [[ ["Fbv4je", json.dumps(inner, separators=(",", ":"))] ]]
        rpc = self.session.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            data={"f.req": json.dumps(outer, separators=(",", ":"))},
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                     "Origin": "https://news.google.com", "Referer": "https://news.google.com/",
                     "X-Same-Domain": "1"},
            timeout=20,
        )
        rpc.raise_for_status()
        body = rpc.text.split("\n\n", 1)[-1]
        payload = json.loads(body)
        frame = next((row for row in payload if isinstance(row, list) and len(row) > 2 and row[0] == "wrb.fr"), None)
        if not frame or not frame[2]:
            raise ValueError("Google News did not return a publisher URL")
        decoded = json.loads(frame[2])
        target = decoded[1] if isinstance(decoded, list) and len(decoded) > 1 else ""
        if not target.startswith("https://"):
            raise ValueError("Google News returned an invalid publisher URL")
        return target

    def read(self, result: dict) -> Article:
        try:
            resolved_url = self._resolve_google_news_url(result["url"])
            response = self.session.get(resolved_url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            structured = self._structured_article(soup)
            description = (self._meta(soup, "og:description") or self._meta(soup, "description") or
                           result.get("rss_summary", ""))
            for node in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                node.decompose()
            canonical = soup.find("link", rel="canonical")
            canonical_url = canonical.get("href") if canonical and canonical.get("href") else response.url
            title = (structured.get("headline") or self._meta(soup, "og:title") or
                     (soup.title.get_text(" ", strip=True) if soup.title else result["title"]))
            published = (self._meta(soup, "article:published_time") or
                         self._meta(soup, "datePublished") or structured.get("datePublished") or result["published_at"])
            body = soup.find("article") or soup
            paragraphs = []
            for p in body.find_all("p"):
                text = " ".join(p.get_text(" ", strip=True).split())
                if len(text) >= 45:
                    paragraphs.append(text)
            if result.get("source_kind") == "Wikipedia article":
                for row in soup.select(".mw-parser-output table tr"):
                    text = " | ".join(" ".join(cell.get_text(" ", strip=True).split())
                                      for cell in row.find_all(["th", "td"], recursive=False))
                    if len(text) >= 45:
                        paragraphs.append(text)
            if not paragraphs and structured.get("articleBody"):
                paragraphs = [p.strip() for p in re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z0-9])", structured["articleBody"]) if len(p.strip()) >= 45]
            summary = description
            if not paragraphs and len(summary) >= 45:
                paragraphs = [summary]
                status = "rss_summary_only (publisher page blocked or empty)"
            else:
                status = "ok" if paragraphs else "no_article_text (possibly paywalled or blocked)"
            return Article(title.strip(), canonical_url, result["publisher"], published, paragraphs, status, summary,
                           result.get("source_kind", "news search"), result.get("reference_page", ""))
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            summary = result.get("rss_summary", "")
            usable_summary = [summary] if len(summary) >= 45 else []
            status = f"rss_summary_only (article link failed: {exc})" if usable_summary else f"fetch_error: {exc}"
            return Article(result["title"], result["url"], result["publisher"], result["published_at"], usable_summary, status, summary,
                           result.get("source_kind", "news search"), result.get("reference_page", ""))

    @staticmethod
    def _meta(soup: BeautifulSoup, key: str) -> str:
        for attrs in ({"property": key}, {"name": key}, {"itemprop": key}):
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                return tag["content"].strip()
        return ""

    @staticmethod
    def _structured_article(soup: BeautifulSoup) -> dict:
        def visit(value):
            if isinstance(value, list):
                for child in value:
                    found = visit(child)
                    if found:
                        return found
            elif isinstance(value, dict):
                kind = value.get("@type", "")
                if isinstance(kind, list):
                    kind = " ".join(kind)
                if any(name in str(kind).lower() for name in ("article", "report", "news")):
                    return {key: value.get(key, "") for key in ("headline", "articleBody", "datePublished")}
                for child in value.values():
                    found = visit(child)
                    if found:
                        return found
            return {}

        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                found = visit(json.loads(script.string or script.get_text()))
                if found:
                    return found
            except (json.JSONDecodeError, TypeError):
                continue
        return {}


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


class ArticleScraperAgent:
    """Fetches and extracts one publisher page as an isolated delegated task."""

    def scrape(self, source: dict) -> Article:
        return PageReader().read(source)


class TimelineAnalystAgent:
    """Extracts dated event claims from one article at a time."""

    def analyze(self, article: Article) -> list[dict]:
        return EventExtractor().extract(article)


class ArticleContextAgent:
    """Finds concise, relevant source passages for background and undated details."""

    def summarize(self, article: Article, topic: str, limit: int = 5) -> list[str]:
        relevance = TopicRelevanceAgent(topic)
        topic_terms = relevance.topic_terms
        sentences = []
        for paragraph in article.paragraphs:
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“])", paragraph):
                sentence = " ".join(sentence.split())
                if len(sentence) < 55:
                    continue
                if not relevance.is_relevant_text(sentence):
                    continue
                words = {word.casefold() for word in re.findall(r"[A-Za-z0-9]{3,}", sentence)}
                score = 2 * len(words & topic_terms)
                if YEAR_PATTERN.search(sentence) or re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b", sentence, re.I):
                    score += 3
                if re.search(r"\b(after|before|because|announced|began|led to|resulted|caused|following|during|collapsed|closed|launched|signed|elected|discovered)\b", sentence, re.I):
                    score += 2
                if score:
                    sentences.append((score, sentence))
        selected, seen = [], set()
        for _, sentence in sorted(sentences, key=lambda item: (-item[0], item[1])):
            key = sentence.casefold()
            if key in seen:
                continue
            seen.add(key)
            selected.append(sentence if len(sentence) <= 320 else sentence[:317].rsplit(" ", 1)[0] + "…")
            if len(selected) >= limit:
                break
        return selected


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


class EventConflictReviewerAgent:
    """Flags likely duplicate event claims that sources assign different dates."""

    def review(self, events: list[dict], topic: str) -> tuple[list[dict], list[dict]]:
        topic_words = TopicRelevanceAgent(topic).topic_terms
        groups: dict[str, list[dict]] = {}
        for event in events:
            words = {w.casefold() for w in re.findall(r"[A-Za-z0-9]{3,}", event["event"])}
            signature_words = sorted(words & topic_words)
            if signature_words:
                groups.setdefault(" ".join(signature_words), []).append(event)
        conflicts = set()
        for group in groups.values():
            dates = sorted({event["event_date"] for event in group})
            if len(dates) > 1:
                conflicts.update(dates)
                for event in group:
                    event["date_conflict"] = dates
                    event["date_conflict_review"] = "Potentially related sources report different dates; review the cited evidence."
        return events, sorted(conflicts)


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


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def run_research(topic: str, limit: int = 20, start: date | None = None,
                 end: date | None = None, extra_domains: Iterable[str] = ()) -> dict:
    """Runs the delegated research agents and assembles their reviewed findings."""
    source_orchestrator = SourceResearchOrchestratorAgent()
    sources, search_runs, wikipedia_pages = source_orchestrator.research(topic, limit, extra_domains)

    scraper = ArticleScraperAgent()
    with ThreadPoolExecutor(max_workers=3) as pool:
        articles = list(pool.map(scraper.scrape, sources))

    context_agent = ArticleContextAgent()
    source_details = [
        {"title": article.title, "publisher": article.publisher, "url": article.url,
         "source_kind": article.source_kind, "reference_page": article.reference_page,
         "published_at": article.published_at, "fetch_status": article.fetch_status,
         "key_passages": context_agent.summarize(article, topic)}
        for article in articles
    ]

    analyst = TimelineAnalystAgent()
    with ThreadPoolExecutor(max_workers=3) as pool:
        event_batches = list(pool.map(analyst.analyze, articles))
    extracted_events = [event for batch in event_batches for event in batch]
    relevance_agent = TopicRelevanceAgent(topic)
    # Check the dated sentence itself. A relevant source can contain unrelated
    # dates in author biographies, sidebars, or adjacent historical background.
    relevant_events = [event for event in extracted_events
                       if relevance_agent.is_relevant_text(event["event"])]
    irrelevant_event_count = len(extracted_events) - len(relevant_events)
    reviewed_events, rejected_events = EvidenceReviewerAgent().review(relevant_events, articles)
    reviewed_events, date_conflicts = EventConflictReviewerAgent().review(reviewed_events, topic)
    timeline = TimelineEditor.review(reviewed_events, start=start, end=end)
    report = {
        "topic": topic,
        "topic_interpretation": ResearchPlannerAgent.context_for(topic)["normalized_topic"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "Delegated multi-agent research: parallel search, publisher verification, parallel scraping, context extraction, dated event analysis, evidence review, and timeline editing",
        "agent_run": [
            {"agent": "ResearchPlannerAgent", "status": "completed", "delegated_search_tasks": len(search_runs)},
            {"agent": "NewsSearchAgent", "status": "completed", "tasks": search_runs},
            {"agent": "WikipediaReferenceAgent", "status": "completed", "reference_pages": wikipedia_pages},
            {"agent": "SourceQualityAgent", "status": "completed", "trusted_sources_selected": len(sources)},
            {"agent": "ArticleScraperAgent", "status": "completed", "pages_scraped": len(articles)},
            {"agent": "ArticleContextAgent", "status": "completed", "source_briefs_created": len(source_details)},
            {"agent": "TimelineAnalystAgent", "status": "completed", "event_claims_extracted": len(extracted_events)},
            {"agent": "TopicRelevanceAgent", "status": "completed", "claims_kept": len(relevant_events), "off_topic_claims_removed": irrelevant_event_count},
            {"agent": "EvidenceReviewerAgent", "status": "completed", "claims_supported": len(reviewed_events), "claims_rejected": len(rejected_events)},
            {"agent": "EventConflictReviewerAgent", "status": "completed", "conflicting_dates": date_conflicts},
            {"agent": "TimelineEditor", "status": "completed", "timeline_entries": len(timeline)},
            {"agent": "ReportWriterAgent", "status": "completed"},
        ],
        "limitations": [
            "The search engine is not exhaustive; source quality depends on its result ranking.",
            "Paywalls and blocked pages may leave only an RSS or metadata summary.",
            "Month/day dates without a year use the dominant year in that article and are labeled as inferred.",
            "Different sourced accounts are retained separately unless their dated sentences match exactly.",
            "Wikipedia references are supplementary pointers; each linked publisher page is fetched and checked separately.",
        ],
        "source_count": len(sources),
        "rejected_event_claims": len(rejected_events),
        "articles": [asdict(article) for article in articles],
        "source_details": source_details,
        "timeline": timeline,
    }
    report["overview"] = ReportWriterAgent().create_overview(report)
    return report


def generate_overview(report: dict) -> str:
    """Builds a citation-backed narrative directly from scraped event text; no model key required."""
    if not report["timeline"]:
        return ""
    grouped = {}
    for event in report["timeline"]:
        grouped.setdefault(event["event_date"], []).append(event)
    lines = []
    for event_date, events in grouped.items():
        date_label = f"In {event_date}" if len(event_date) == 4 else f"On {event_date}"
        details = []
        citations = []
        for event in events:
            context = event.get("context", event["event"])
            if context not in details:
                details.append(context)
            for source in event["sources"]:
                source_note = {"Wikipedia reference": " (Wikipedia reference)", "Wikipedia article": " (Wikipedia article)"}.get(source.get("source_kind"), "")
                label = source["publisher"] + source_note
                citation = f"[{label}]({source['source_url']})"
                if citation not in citations:
                    citations.append(citation)
        lines.append(f"**{date_label}:** " + " ".join(details) + " " + " ".join(citations))
    return "\n\n".join(lines)


def render_markdown(report: dict) -> str:
    lines = [f"# Research timeline: {report['topic']}", "",
             f"Generated: {report['generated_at']}", "",
             f"Interpreted topic: {report.get('topic_interpretation', report['topic'])}", "",
             f"Selected {report['source_count']} relevant sources; "
             f"{len(report['timeline'])} dated event statements survived extraction and review.", "",
             "## What happened", ""]
    if report.get("overview"):
        lines.extend([report["overview"], ""])
    elif not report["timeline"]:
        lines.extend(["The fetched source pages contained no usable dated event text. Check the source statuses below; this is an extraction failure, not a completed timeline.", ""])
    lines.extend(["## Timeline", ""])
    if not report["timeline"]:
        lines.append("No dated event sentences were extracted. Review the fetched page statuses and summaries below.")
    for item in report["timeline"]:
        lines.extend([f"### {item['event_date']}", "", item.get("context", item["event"]), "",
                      f"Date basis: {item['date_basis']}.", ""])
        if item.get("date_conflict_review"):
            lines.extend([f"**Date conflict:** {item['date_conflict_review']} Other dates extracted: {', '.join(item['date_conflict'])}.", ""])
        for source in item["sources"]:
            source_note = {"Wikipedia reference": " (Wikipedia reference)", "Wikipedia article": " (Wikipedia article)"}.get(source.get("source_kind"), "")
            label = source["publisher"] + source_note
            lines.append(f"Evidence: [{label} — {source['source_title']}]({source['source_url']})")
            if source.get("reference_page") and source.get("source_kind") == "Wikipedia reference":
                lines.append(f"Listed in Wikipedia references: [{source['reference_page']}]({source['reference_page']})")
            elif source.get("source_kind") == "Wikipedia article" and source.get("reference_page"):
                lines.append(f"Wikipedia article: [{source['reference_page']}]({source['reference_page']})")
            if source["article_published_at"]:
                lines.append(f"Article publication date: {source['article_published_at']}")
        lines.append("")
    lines.extend(["## Sources", ""])
    for article in report["articles"]:
        source_label = {"Wikipedia reference": "Wikipedia reference", "Wikipedia article": "Wikipedia article"}.get(article.get("source_kind"), article["publisher"])
        ref_note = f" (found in [Wikipedia]({article['reference_page']}))" if article.get("reference_page") else ""
        lines.append(f"- [{source_label} — {article['title']}]({article['url']}){ref_note} — {article['fetch_status']}; {len(article['paragraphs'])} paragraphs")
    lines.extend(["", "## Key details from sources", ""])
    for source in report.get("source_details", []):
        source_label = ("Wikipedia reference: " if source.get("source_kind") == "Wikipedia reference" else
                        "Wikipedia article: " if source.get("source_kind") == "Wikipedia article" else "") + source["publisher"]
        lines.append(f"### [{source_label} — {source['title']}]({source['url']})")
        if source.get("reference_page"):
            lines.append(f"Wikipedia citation list: [{source['reference_page']}]({source['reference_page']})")
        if source.get("published_at"):
            lines.append(f"Published: {source['published_at']}")
        if source["key_passages"]:
            lines.extend(f"- {passage}" for passage in source["key_passages"])
        else:
            lines.append(f"No usable article text was extracted ({source['fetch_status']}).")
        lines.append("")
    lines.extend(["", "## Method notes", ""])
    lines.extend(f"- {note}" for note in report["limitations"])
    return "\n".join(lines) + "\n"


class ReportWriterAgent:
    """Writes the final answer from reviewed event records without a hosted model."""

    def create_overview(self, report: dict) -> str:
        return generate_overview(report)

    def render(self, report: dict) -> str:
        return render_markdown(report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Research a past event and build a cited, dated timeline.")
    parser.add_argument("topic", help="Event or subject to research")
    parser.add_argument("--limit", type=int, default=20, help="Maximum trusted news pages to fetch (default: 20)")
    parser.add_argument("--from-date", dest="start", help="Keep events on/after YYYY-MM-DD")
    parser.add_argument("--to-date", dest="end", help="Keep events on/before YYYY-MM-DD")
    parser.add_argument("--allow-domain", action="append", default=[], help="Additional trusted domain; repeat as needed")
    parser.add_argument("--output", default="research_timeline.md", help="Markdown report path")
    parser.add_argument("--json", dest="json_output", help="Optional JSON evidence bundle path")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 50:
        parser.error("--limit must be between 1 and 50")
    try:
        report = run_research(args.topic, args.limit, parse_date(args.start), parse_date(args.end), args.allow_domain)
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        parser.exit(1, f"Research stopped before generating a report: {exc}\nCheck network access, then try again.\n")
    output = Path(args.output)
    output.write_text(ReportWriterAgent().render(report), encoding="utf-8")
    print(f"Wrote {output.resolve()} ({len(report['timeline'])} dated events, {len(report['articles'])} sources fetched).")
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {Path(args.json_output).resolve()}")
    failed = sum(article["fetch_status"] != "ok" for article in report["articles"])
    print(f"Pages with extraction/fetch issues: {failed}. Review the source list in the report.")


if __name__ == "__main__":
    main()
