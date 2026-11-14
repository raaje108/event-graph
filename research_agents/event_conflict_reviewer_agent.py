from __future__ import annotations
import re

from .research_planner_agent import ResearchPlannerAgent
from .topic_relevance_agent import TopicRelevanceAgent

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

