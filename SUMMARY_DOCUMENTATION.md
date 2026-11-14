# Topic-to-Timeline Research Agent

This project accepts a free-form past-event topic, discovers relevant news and reference pages, extracts dated statements, and creates a chronological report with links to supporting articles. It has no event-specific behavior: the same agents handle disasters, political events, court cases, scientific discoveries, conflicts, company events, and other historical topics.

## Run the topic research prototype

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python topic_timeline.py "Silicon Valley Bank collapse" --output svb_timeline.md --json svb_timeline.json
```

You can narrow the event dates and add sources you trust:

```powershell
python topic_timeline.py "Apollo 11 mission" --from-date 1969-07-16 --to-date 1969-07-24 --allow-domain nasa.gov
```

The report defaults to `research_timeline.md`. The optional JSON file retains every fetched article, its extracted paragraphs, and the evidence sentence for each timeline entry.

No AI API key is required. The overview and timeline are assembled directly from the scraped article sentences and linked to the pages they came from.

## Multi-agent workflow

1. **ResearchPlannerAgent** turns the topic into multiple search tasks.
2. **NewsSearchAgent workers** run those searches independently and in parallel.
3. **WikipediaReferenceAgent** finds relevant encyclopedia pages, uses their dated text and tables to seed historical chronology, and extracts external links from their References lists.
4. **SourceQualityAgent** checks publisher identity, removes duplicates, and balances search results with Wikipedia-cited links.
5. **ArticleScraperAgent workers** fetch publisher pages independently and in parallel.
6. **ArticleContextAgent** selects relevant background passages from each scraped page.
7. **TimelineAnalystAgent workers** extract dated claims and retain the complete event passage up to the next dated claim.
8. **EvidenceReviewerAgent** checks each claim against the exact scraped source text and rejects unsupported claims.
9. **EventConflictReviewerAgent** flags likely conflicting dates for related event claims instead of silently choosing one.
10. **TimelineEditor** orders and merges supported events while preserving citations.
11. **ReportWriterAgent** writes the evidence-backed overview and report.

Each agent lives in its own module under `research_agents/`. `research_agents/research_pipeline.py` coordinates the workflow and passes each stage's results to the next. `topic_timeline.py` remains the command-line entry point for compatibility. The orchestrator delegates tasks to specialized agents and includes the run trace in the JSON output. These are independent, rule-based software agents; no hosted language model or AI API key is used. The topic argument is free-form. Discovery makes searches from the entered topic, and relevance checks compare source text with the topic terms rather than relying on a list of known events.

## Scope and limitations

- Discovery tries multiple Bing News RSS and Google News RSS queries and filters results to known news organizations, official government domains, and configured sources. Search coverage is not exhaustive; add domains with `--allow-domain` when appropriate.
- Publisher pages may block automated requests or require a subscription. Such pages are listed with a fetch status; the program does not silently substitute sample content.
- The extractor uses full dates, dates with a year inferred from other years in the same article, and year-only statements from fetched article text. RSS snippets and headlines can help find a source but cannot create timeline events on their own. It labels inferred dates and flags likely date disagreements.
- Google News article links are resolved to publisher URLs through an undocumented Google endpoint. Google can change or rate-limit this endpoint; if that happens, the report marks the failure and preserves any usable RSS summary.
- Wikipedia provides a broad chronology and citation leads, clearly labeled in the report. Linked publisher references are fetched and listed separately when accessible.
- Respect each publisher's terms and robots guidance. Use modest request volume; this prototype fetches at most 50 pages per run and pauses briefly between pages.

## Existing SVB preprocessing demo

`pipeline.py` continues to run the original fixed-topic scraper, preprocessing, and TF-IDF similarity demonstration. Its vectors are TF-IDF features rather than general-purpose semantic embeddings. The topic-to-timeline workflow is implemented in the `research_agents/` package and launched through `topic_timeline.py`.
