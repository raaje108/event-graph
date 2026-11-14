from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from .research_planner_agent import ResearchPlannerAgent
from .news_search_agent import NewsSearchAgent
from .wikipedia_reference_agent import WikipediaReferenceAgent
from .source_quality_agent import SourceQualityAgent

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

