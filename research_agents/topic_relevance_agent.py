from __future__ import annotations
from difflib import SequenceMatcher
import re
from .research_planner_agent import ResearchPlannerAgent

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

