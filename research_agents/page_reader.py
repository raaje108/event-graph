from __future__ import annotations
import json
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .constants import USER_AGENT
from .models import Article

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

