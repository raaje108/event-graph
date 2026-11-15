const $ = (selector) => document.querySelector(selector);
const form = $("#research-form");
const submitButton = $("#submit-button");
const hero = $("#hero");
const loading = $("#loading-state");
const results = $("#results");
const emptyState = $("#empty-state");
let pollTimer = null;
let activeReport = null;

$("#options-toggle").addEventListener("click", () => {
  const filters = $("#filters");
  filters.hidden = !filters.hidden;
  $("#options-toggle").innerHTML = filters.hidden ? 'Filters <span>+</span>' : 'Filters <span>−</span>';
});

document.querySelectorAll("[data-topic]").forEach((button) => {
  button.addEventListener("click", () => {
    $("#topic").value = button.dataset.topic;
    $("#topic").focus();
  });
});

$("#new-search").addEventListener("click", () => {
  results.hidden = true;
  hero.hidden = false;
  emptyState.hidden = false;
  $("#topic").focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideError();
  const topic = $("#topic").value.trim();
  if (!topic) return;
  setBusy(true, "Preparing your research…");
  try {
    const response = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic,
        limit: Number($("#source-limit").value),
        start: $("#start-date").value || null,
        end: $("#end-date").value || null,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not start research.");
    pollJob(data.job_id, topic);
  } catch (error) {
    setBusy(false);
    showError(error.message || "Could not connect to EventGraph. Is the local server running?");
  }
});

function setBusy(busy, message = "Searching sources and building your event graph…") {
  submitButton.disabled = busy;
  submitButton.querySelector("span").textContent = busy ? "Researching…" : "Build timeline";
  hero.hidden = busy;
  emptyState.hidden = busy;
  results.hidden = true;
  loading.hidden = !busy;
  $("#loading-message").textContent = message;
  if (busy) $("#loading-title").textContent = "Connecting the dots…";
}

async function pollJob(jobId, topic) {
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.error || "Research status was lost.");
    $("#loading-message").textContent = job.message || "Working through the sources…";
    if (job.status === "completed") {
      clearTimeout(pollTimer);
      setBusy(false);
      activeReport = job.result;
      renderReport(activeReport);
      return;
    }
    if (job.status === "failed") throw new Error(job.message || "Research failed.");
    pollTimer = setTimeout(() => pollJob(jobId, topic), 1100);
  } catch (error) {
    clearTimeout(pollTimer);
    setBusy(false);
    showError(error.message || "Research stopped unexpectedly.");
  }
}

function renderReport(report) {
  results.hidden = false;
  hero.hidden = true;
  emptyState.hidden = true;
  $("#result-topic").textContent = report.topic_interpretation || report.topic;
  const timeline = report.timeline || [];
  const articles = report.articles || [];
  const years = timeline.map((item) => String(item.event_date));
  const range = years.length ? `${years.reduce((a,b)=>a<b?a:b)} — ${years.reduce((a,b)=>a>b?a:b)}` : "No dated events found";
  $("#results-subtitle").textContent = timeline.length
    ? `${timeline.length} evidence-backed moments · generated ${formatGenerated(report.generated_at)}`
    : `No dated event statements survived review · generated ${formatGenerated(report.generated_at)}`;
  $("#metrics").innerHTML = [
    metric("EVENTS MAPPED", timeline.length, true),
    metric("SOURCES REVIEWED", report.source_count ?? articles.length),
    metric("TIMESPAN", range),
    metric("RESEARCH MODE", "Multi-agent · no key"),
  ].join("");
  $("#source-count").textContent = `${articles.length} SOURCES`;
  renderGraph(timeline);
  renderSources(articles);
  renderNotes(report.limitations || []);
  if (timeline.length) selectEvent(0);
  else $("#detail-panel").innerHTML = '<div class="detail-empty"><div class="detail-orbit">∅</div><span class="panel-kicker">NO DATED MOMENTS</span><p>Check the source list below. Some pages may be blocked, or the fetched text may not contain explicit event dates.</p></div>';
  window.scrollTo({ top: results.offsetTop - 20, behavior: "smooth" });
}

function metric(label, value, accent = false) {
  return `<div class="metric${accent ? " metric-accent" : ""}"><span>${escapeHTML(label)}</span><b>${escapeHTML(value)}</b></div>`;
}

function renderGraph(timeline) {
  const canvas = $("#graph-canvas");
  const nodes = $("#graph-nodes");
  const svg = $("#graph-svg");
  if (!timeline.length) {
    canvas.style.width = "100%";
    nodes.innerHTML = '<div class="no-graph">No graph points to display for this search.</div>';
    svg.innerHTML = "";
    $("#graph-range").textContent = "";
    return;
  }
  const step = 286;
  const width = Math.max($("#graph-scroll").clientWidth, timeline.length * step + 70);
  const axisY = 300;
  canvas.style.width = `${width}px`;
  canvas.style.height = "606px";
  $("#graph-range").textContent = `${timeline.length} CONNECTED MOMENTS`;
  const points = timeline.map((event, index) => ({
    event,
    x: 35 + index * step + 122,
    y: axisY + (index % 2 === 0 ? -20 : 20),
    top: index % 2 === 0,
  }));
  const paths = [];
  paths.push(`<line class="graph-axis" x1="20" y1="${axisY}" x2="${width - 24}" y2="${axisY}"/>`);
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1];
    paths.push(`<path class="graph-link" d="M ${a.x} ${a.y} C ${a.x + 70} ${a.y}, ${b.x - 70} ${b.y}, ${b.x} ${b.y}"/>`);
  }
  paths.push(`<defs><filter id="glow"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>`);
  points.forEach((point, index) => {
    const cardTop = point.top ? 14 : 385;
    const cardEdge = point.top ? 160 : 385;
    paths.push(`<line class="graph-tick" x1="${point.x}" y1="${point.y}" x2="${point.x}" y2="${cardEdge}"/>`);
    paths.push(`<circle cx="${point.x}" cy="${point.y}" r="${index === 0 ? 7 : 5}" ${index === 0 ? 'filter="url(#glow)"' : ""}/>`);
  });
  svg.setAttribute("viewBox", `0 0 ${width} 606`);
  svg.innerHTML = paths.join("");
  nodes.innerHTML = points.map(({ event, x, top }, index) => {
    const eventDate = formatEventDate(event.event_date);
    const text = event.event || event.context || "Dated event";
    const sourceCount = event.sources?.length || 0;
    return `<button class="event-card ${top ? "top" : "bottom"}" style="left:${x - 123}px" data-index="${index}" aria-label="Open event ${escapeHTML(eventDate)}: ${escapeHTML(text)}">
      <span class="event-date">${escapeHTML(eventDate)}</span>
      <span class="event-title">${escapeHTML(text)}</span>
      <span class="event-meta"><span>${sourceCount} EVIDENCE ${sourceCount === 1 ? "SOURCE" : "SOURCES"}</span><b>OPEN ↗</b></span>
    </button>`;
  }).join("");
  nodes.querySelectorAll(".event-card").forEach((button) => button.addEventListener("click", () => selectEvent(Number(button.dataset.index))));
}

function selectEvent(index) {
  const event = activeReport?.timeline?.[index];
  if (!event) return;
  document.querySelectorAll(".event-card").forEach((button) => button.classList.toggle("selected", Number(button.dataset.index) === index));
  const sources = event.sources || [];
  const conflict = event.date_conflict_review
    ? `<div class="conflict-note">${escapeHTML(event.date_conflict_review)} ${escapeHTML((event.date_conflict || []).join(", "))}</div>`
    : "";
  const evidence = sources.length ? `<div class="evidence-title">EVIDENCE & REFERENCES</div><div class="evidence-list">${sources.map((source) => `<a class="evidence-link" href="${safeURL(source.source_url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(source.source_title || source.publisher || "Open source")}<small>${escapeHTML(source.publisher || "Source")}${source.source_kind ? ` · ${escapeHTML(source.source_kind)}` : ""}</small></a>`).join("")}</div>` : '<p class="detail-body">No source links were attached to this event.</p>';
  $("#detail-panel").innerHTML = `<div class="detail-content"><div class="detail-date">${escapeHTML(formatEventDate(event.event_date))}</div><h3>${escapeHTML(event.event || "Event detail")}</h3><div class="detail-body">${escapeHTML(event.context || event.event || "")}</div>${conflict}${evidence}</div>`;
}

function renderSources(articles) {
  const list = $("#sources-list");
  if (!articles.length) {
    list.innerHTML = '<p class="no-sources">No sources were returned for this research.</p>';
    return;
  }
  list.innerHTML = articles.map((article) => {
    const initial = (article.publisher || "?").replace(/^www\./, "").slice(0, 2).toUpperCase();
    const label = article.source_kind === "Wikipedia article" ? "Wikipedia chronology" : article.source_kind === "Wikipedia reference" ? "Wikipedia citation" : article.publisher;
    const status = article.fetch_status || "source found";
    return `<a class="source-card" href="${safeURL(article.url)}" target="_blank" rel="noopener noreferrer"><span class="source-icon">${escapeHTML(initial)}</span><span class="source-info"><b>${escapeHTML(article.title || label)}</b><small>${escapeHTML(label)} · ${escapeHTML(status)}</small></span></a>`;
  }).join("");
}

function renderNotes(notes) {
  const box = $("#report-note");
  box.innerHTML = notes.length ? `<span class="panel-kicker">RESEARCH NOTES</span><ul>${notes.map((note) => `<li>${escapeHTML(note)}</li>`).join("")}</ul>` : "";
}

function formatEventDate(value) {
  const text = String(value || "");
  if (/^\d{4}$/.test(text)) return text;
  const date = new Date(`${text}T00:00:00`);
  return Number.isNaN(date.getTime()) ? text : new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }).format(date);
}
function formatGenerated(value) {
  if (!value) return "just now";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "just now" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}
function safeURL(value) {
  try { const url = new URL(value, window.location.href); return ["http:", "https:"].includes(url.protocol) ? url.href : "#"; }
  catch { return "#"; }
}
function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
function showError(message) {
  const toast = $("#error-toast");
  toast.textContent = message;
  toast.hidden = false;
}
function hideError() { $("#error-toast").hidden = true; }
