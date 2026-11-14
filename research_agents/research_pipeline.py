from __future__ import annotations
from dataclasses import asdict
from datetime import date, datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from .models import Article
from .research_planner_agent import ResearchPlannerAgent
from .source_research_orchestrator_agent import SourceResearchOrchestratorAgent
from .article_scraper_agent import ArticleScraperAgent
from .article_context_agent import ArticleContextAgent
from .timeline_analyst_agent import TimelineAnalystAgent
from .topic_relevance_agent import TopicRelevanceAgent
from .evidence_reviewer_agent import EvidenceReviewerAgent
from .event_conflict_reviewer_agent import EventConflictReviewerAgent
from .timeline_editor import TimelineEditor
from .report_writer_agent import ReportWriterAgent

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

