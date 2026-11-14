from __future__ import annotations
import html
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .constants import USER_AGENT

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

