from __future__ import annotations
import re

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

