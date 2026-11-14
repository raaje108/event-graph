from __future__ import annotations
import re

from .constants import YEAR_PATTERN
from .models import Article
from .topic_relevance_agent import TopicRelevanceAgent

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

