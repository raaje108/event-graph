from __future__ import annotations

def generate_overview(report: dict) -> str:
    """Builds a citation-backed narrative directly from scraped event text; no model key required."""
    if not report["timeline"]:
        return ""
    grouped = {}
    for event in report["timeline"]:
        grouped.setdefault(event["event_date"], []).append(event)
    lines = []
    for event_date, events in grouped.items():
        date_label = f"In {event_date}" if len(event_date) == 4 else f"On {event_date}"
        details = []
        citations = []
        for event in events:
            context = event.get("context", event["event"])
            if context not in details:
                details.append(context)
            for source in event["sources"]:
                source_note = {"Wikipedia reference": " (Wikipedia reference)", "Wikipedia article": " (Wikipedia article)"}.get(source.get("source_kind"), "")
                label = source["publisher"] + source_note
                citation = f"[{label}]({source['source_url']})"
                if citation not in citations:
                    citations.append(citation)
        lines.append(f"**{date_label}:** " + " ".join(details) + " " + " ".join(citations))
    return "\n\n".join(lines)


def render_markdown(report: dict) -> str:
    lines = [f"# Research timeline: {report['topic']}", "",
             f"Generated: {report['generated_at']}", "",
             f"Interpreted topic: {report.get('topic_interpretation', report['topic'])}", "",
             f"Selected {report['source_count']} relevant sources; "
             f"{len(report['timeline'])} dated event statements survived extraction and review.", "",
             "## What happened", ""]
    if report.get("overview"):
        lines.extend([report["overview"], ""])
    elif not report["timeline"]:
        lines.extend(["The fetched source pages contained no usable dated event text. Check the source statuses below; this is an extraction failure, not a completed timeline.", ""])
    lines.extend(["## Timeline", ""])
    if not report["timeline"]:
        lines.append("No dated event sentences were extracted. Review the fetched page statuses and summaries below.")
    for item in report["timeline"]:
        lines.extend([f"### {item['event_date']}", "", item.get("context", item["event"]), "",
                      f"Date basis: {item['date_basis']}.", ""])
        if item.get("date_conflict_review"):
            lines.extend([f"**Date conflict:** {item['date_conflict_review']} Other dates extracted: {', '.join(item['date_conflict'])}.", ""])
        for source in item["sources"]:
            source_note = {"Wikipedia reference": " (Wikipedia reference)", "Wikipedia article": " (Wikipedia article)"}.get(source.get("source_kind"), "")
            label = source["publisher"] + source_note
            lines.append(f"Evidence: [{label} — {source['source_title']}]({source['source_url']})")
            if source.get("reference_page") and source.get("source_kind") == "Wikipedia reference":
                lines.append(f"Listed in Wikipedia references: [{source['reference_page']}]({source['reference_page']})")
            elif source.get("source_kind") == "Wikipedia article" and source.get("reference_page"):
                lines.append(f"Wikipedia article: [{source['reference_page']}]({source['reference_page']})")
            if source["article_published_at"]:
                lines.append(f"Article publication date: {source['article_published_at']}")
        lines.append("")
    lines.extend(["## Sources", ""])
    for article in report["articles"]:
        source_label = {"Wikipedia reference": "Wikipedia reference", "Wikipedia article": "Wikipedia article"}.get(article.get("source_kind"), article["publisher"])
        ref_note = f" (found in [Wikipedia]({article['reference_page']}))" if article.get("reference_page") else ""
        lines.append(f"- [{source_label} — {article['title']}]({article['url']}){ref_note} — {article['fetch_status']}; {len(article['paragraphs'])} paragraphs")
    lines.extend(["", "## Key details from sources", ""])
    for source in report.get("source_details", []):
        source_label = ("Wikipedia reference: " if source.get("source_kind") == "Wikipedia reference" else
                        "Wikipedia article: " if source.get("source_kind") == "Wikipedia article" else "") + source["publisher"]
        lines.append(f"### [{source_label} — {source['title']}]({source['url']})")
        if source.get("reference_page"):
            lines.append(f"Wikipedia citation list: [{source['reference_page']}]({source['reference_page']})")
        if source.get("published_at"):
            lines.append(f"Published: {source['published_at']}")
        if source["key_passages"]:
            lines.extend(f"- {passage}" for passage in source["key_passages"])
        else:
            lines.append(f"No usable article text was extracted ({source['fetch_status']}).")
        lines.append("")
    lines.extend(["", "## Method notes", ""])
    lines.extend(f"- {note}" for note in report["limitations"])
    return "\n".join(lines) + "\n"


class ReportWriterAgent:
    """Writes the final answer from reviewed event records without a hosted model."""

    def create_overview(self, report: dict) -> str:
        return generate_overview(report)

    def render(self, report: dict) -> str:
        return render_markdown(report)

