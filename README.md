# Chronicle Research Agent

Chronicle Research Agent is a no-API-key, multi-agent NLP project that researches a past event from a topic prompt and builds a cited chronology. It searches news RSS feeds, follows relevant Wikipedia references, scrapes accessible publisher pages, extracts dated passages, checks evidence, and writes Markdown and JSON reports.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python topic_timeline.py "French Revolution" --output french_revolution_timeline.md --json french_revolution_timeline.json
```

To research another topic, replace `French Revolution`. For example:

```powershell
python topic_timeline.py "Ayodhya land dispute" --output ayodhya_timeline.md --json ayodhya_timeline.json
```

No LLM API key is required. The output links dated statements to the page text used as evidence. Wikipedia article text can provide historical chronology, with linked publisher references listed separately. Search snippets and headlines are not treated as evidence for timeline events.

## Agents

- `ResearchPlannerAgent` creates topic-specific search queries.
- `NewsSearchAgent` workers search news RSS feeds concurrently.
- `WikipediaReferenceAgent` finds relevant Wikipedia pages, their dated text, and cited sources.
- `SourceQualityAgent` filters and ranks sources.
- `ArticleScraperAgent` workers fetch pages concurrently.
- `ArticleContextAgent` selects topic-related passages.
- `TimelineAnalystAgent` extracts dated claims.
- `TopicRelevanceAgent` filters unrelated claims.
- `EvidenceReviewerAgent` checks extracted evidence against fetched page text.
- `EventConflictReviewerAgent` flags likely date conflicts.
- `TimelineEditor` orders and merges supported claims.
- `ReportWriterAgent` writes the final Markdown report.

More detail is in [SUMMARY_DOCUMENTATION.md](SUMMARY_DOCUMENTATION.md).

## Existing NLP coursework artifacts

The folder also includes the original SVB scraping, preprocessing, TF-IDF/vector preparation pipeline, sample datasets and reports, and notebooks. These artifacts are included in the repository.

## Limitations

- Search coverage depends on the available RSS results.
- Publisher pages can block scraping or require subscriptions.
- When a page cannot be fetched, its RSS snippet may be shown for context, but it cannot create timeline entries.
- Historical coverage depends on the relevant encyclopedia and publisher pages being reachable and containing dated text.
- The date extractor does not invent missing dates or resolve uncertain chronology without evidence.
