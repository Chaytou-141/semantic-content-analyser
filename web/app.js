"use strict";

const $ = (selector) => document.querySelector(selector);
const state = { articles: [], meta: null, view: "search", busy: false, lastLinks: null, sourceId: null };

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key === "checked" || key === "disabled") node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child !== null && child !== undefined) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function api(path, data, method = "POST") {
  const options = data === undefined ? {} : { method, headers: { "Content-Type": "application/json", "X-Workspace-Request": "true" }, body: JSON.stringify(data) };
  const response = await fetch(path, options);
  let payload;
  try { payload = await response.json(); } catch { throw new Error("The server returned an unexpected response. Check the server logs."); }
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/login") showLogin();
    let message = payload.detail || "The request could not be completed.";
    if (Array.isArray(message)) message = message.map((issue) => `${issue.loc.slice(1).join(".")}: ${issue.msg}`).join("; ");
    throw new Error(message);
  }
  return payload;
}

let toastTimer;
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $("#toast").hidden = true; }, 5000);
}

async function task(message, action) {
  if (state.busy) return;
  state.busy = true;
  $("#app-error").hidden = true;
  $("#busy-message").textContent = message;
  $("#busy").hidden = false;
  const submitButtons = [...document.querySelectorAll("button[type=submit]")];
  submitButtons.forEach((button) => { button.disabled = true; });
  try { await action(); }
  catch (error) {
    $("#app-error").textContent = error.message;
    $("#app-error").hidden = false;
    toast(error.message);
  } finally {
    state.busy = false;
    $("#busy").hidden = true;
    submitButtons.forEach((button) => { button.disabled = false; });
  }
}

function showLogin() { $("#workspace").hidden = true; $("#login").hidden = false; $("#password").focus(); }

async function loadCollection() {
  const [collection, meta] = await Promise.all([api("/api/articles"), api("/api/meta")]);
  state.articles = collection.articles;
  state.meta = meta;
  $("#collection-count").textContent = `${state.articles.length} articles in your collection`;
  const select = $("#links-source");
  const previous = select.value;
  select.replaceChildren(...state.articles.map((article) => el("option", { value: article.id, text: `${article.id} — ${article.title}` })));
  if (state.articles.some((article) => article.id === previous)) select.value = previous;
  renderCollection();
}

async function start() {
  try {
    const session = await api("/api/session");
    if (!session.authenticated) { showLogin(); return; }
    $("#login").hidden = true;
    $("#workspace").hidden = false;
    $("#sign-out").hidden = !session.password_required;
    await loadCollection();
    navigate(location.hash.slice(1) || "search");
  } catch (error) { $("#app-error").textContent = error.message; $("#app-error").hidden = false; $("#workspace").hidden = false; }
}

function navigate(view) {
  if (!["search", "links", "overlap", "collection", "evaluation"].includes(view)) view = "search";
  state.view = view;
  document.querySelectorAll(".view").forEach((section) => { section.hidden = section.id !== `view-${view}`; });
  document.querySelectorAll(".nav-item").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
  });
  history.replaceState(null, "", `#${view}`);
  $("#app-error").hidden = true;
  if (view === "evaluation") task("Loading saved evaluation results…", renderEvaluation);
}

function empty(container, title, description) {
  container.replaceChildren(el("div", { class: "empty-state" }, el("h2", { text: title }), el("p", { text: description })));
}

function articleTitle(result) {
  return el("button", { class: "result-title", text: result.title, onclick: () => openArticle(result.id) });
}

function scoreBadge(score) { return el("span", { class: "score", text: `Similarity ${score.toFixed(3)}` }); }
function metadata(result) { return el("div", { class: "article-meta" }, el("span", { text: result.id }), result.topic ? el("span", { class: "topic-tag", text: result.topic.replaceAll("_", " ") }) : null); }
function methodName(method) { return method === "embeddings" ? "Embeddings" : "TF-IDF"; }

function renderSearch(payload) {
  const container = $("#search-results");
  const methods = Object.entries(payload.results);
  const grid = el("div", { class: methods.length > 1 ? "comparison" : "" });
  for (const [method, results] of methods) {
    const section = el("div", {}, el("div", { class: "result-heading" }, el("h2", { text: `${methodName(method)} results` }), el("span", { text: `${results.length} matches · ${(payload.elapsed_ms / 1000).toFixed(2)} seconds` })));
    const list = el("div", { class: "result-list" });
    if (!results.length) empty(list, "No matches above this score.", "Try a lower minimum score or a different question. A keyword query may not share any vocabulary with this collection.");
    for (const result of results) {
      list.append(el("article", { class: "result-card" }, el("div", { class: "result-topline" }, articleTitle(result), scoreBadge(result.score)), metadata(result), el("p", { class: "passage", text: result.passage }), el("div", { class: "result-footer" }, el("span", { text: "Best matching passage" }), el("button", { class: "text-button", text: "Open article", onclick: () => openArticle(result.id) }))));
    }
    section.append(list);
    grid.append(section);
  }
  container.replaceChildren(grid, el("p", { class: "context-note", text: "Scores express similarity, not confidence or relevance percentages. Compare rankings and evidence; score sizes are not directly comparable between methods." }));
}

function safeTarget(url) {
  if (!url) return el("span", { text: "No destination URL provided. Add one in Article collection." });
  return el("a", { href: url, target: "_blank", rel: "noopener noreferrer", text: url });
}

function renderLinks(payload) {
  state.lastLinks = payload;
  const container = $("#links-results");
  container.className = "";
  const methods = Object.entries(payload.results);
  const sections = [];
  for (const [method, group] of methods) {
    const section = el("section", {}, el("div", { class: "result-heading" }, el("h2", { text: `${methodName(method)} candidates` }), el("span", { text: `${group.results.length} destinations · review required` })));
    section.append(el("div", { class: "exclusions" }, el("span", { text: `Self: ${group.excluded.self}` }), el("span", { text: `Existing links excluded: ${group.excluded.existing.length}` }), el("span", { text: `Ineligible pages excluded: ${group.excluded.disallowed.length}` })));
    const list = el("div", { class: "result-list" });
    if (!group.results.length) empty(list, "No eligible candidates found.", "Check destination eligibility, existing links and the text in this collection.");
    for (const result of group.results) {
      const saved = payload.reviews.find((review) => review.target_id === result.id);
      const note = el("input", { type: "text", maxlength: "1000", placeholder: "Optional editorial note", value: saved?.note || "", "aria-label": `Review note for ${result.id}` });
      const actions = el("div", { class: "review-actions" });
      for (const [decision, label] of [["useful", "Useful candidate"], ["not_useful", "Not useful"], ["pending", "Clear decision"]]) {
        actions.append(el("button", { class: `button small ${saved?.decision === decision ? "selected-review" : ""}`, text: label, onclick: () => task("Saving your review…", async () => {
          const review = { source_id: state.sourceId, target_id: result.id, decision, note: note.value };
          await api("/api/reviews", review);
          payload.reviews = payload.reviews.filter((row) => row.target_id !== result.id).concat(review);
          renderLinks(payload);
          toast("Review saved. No links were inserted.");
        }) }));
      }
      actions.append(el("span", { class: "review-label", text: saved && saved.decision !== "pending" ? "Review saved" : "Awaiting your review" }));
      list.append(el("article", { class: "result-card" }, el("div", { class: "result-topline" }, articleTitle(result), scoreBadge(result.score)), metadata(result), el("div", { class: "evidence" }, el("div", {}, el("span", { class: "evidence-label", text: "Source passage" }), el("p", { text: result.source_passage })), el("div", {}, el("span", { class: "evidence-label", text: "Destination evidence" }), el("p", { text: result.passage }))), el("div", { class: "result-footer" }, safeTarget(result.url)), el("label", { class: "sr-only", text: "Editorial note" }), note, el("div", { class: "result-footer" }, actions)));
    }
    section.append(list);
    sections.push(section);
  }
  container.replaceChildren(...sections);
}

function renderOverlaps(payload) {
  const container = $("#overlap-results");
  container.className = "";
  if (!payload.pairs.length) { empty(container, "No pairs above this threshold.", "Try a lower threshold. A lack of high similarity is not proof that topics never overlap."); return; }
  const list = el("div", { class: "result-list" });
  for (const pair of payload.pairs) {
    const columns = el("div", { class: "pair-grid" });
    for (const article of [pair.left, pair.right]) columns.append(el("div", {}, articleTitle(article), metadata(article), el("p", { class: "passage", text: article.passage })));
    list.append(el("article", { class: "result-card" }, el("div", { class: "pair-heading" }, el("span", { text: "Possible topic overlap · editorial review" }), scoreBadge(pair.score)), columns, el("div", { class: "result-footer" }, el("span", { text: "Check whether the pages answer different reader questions and contain unique information." }))));
  }
  container.replaceChildren(el("div", { class: "result-heading" }, el("h2", { text: `${payload.pairs.length} pairs to inspect` })), list);
}

function renderCollection() {
  const query = $("#article-filter").value.toLowerCase();
  const filtered = state.articles.filter((article) => `${article.id} ${article.title} ${article.topic}`.toLowerCase().includes(query));
  const body = $("#article-table");
  body.replaceChildren(...filtered.map((article) => el("tr", {}, el("td", {}, articleTitle(article), el("div", { class: "table-id", text: article.id })), el("td", {}, el("span", { class: "topic-tag", text: article.topic.replaceAll("_", " ") || "Uncategorised" })), el("td", { text: article.body.split(/\s+/u).filter(Boolean).length }), el("td", {}, el("span", { class: `eligibility ${article.eligible ? "" : "no"}`, text: article.eligible ? "Eligible destination" : "Excluded from links" })), el("td", {}, el("button", { class: "text-button", text: "Edit", onclick: () => openArticle(article.id) })))));
  if (!filtered.length) body.append(el("tr", {}, el("td", { colspan: "5", text: "No articles match this filter." })));
}

function formField(label, input) {
  const wrapper = el("label", { text: label });
  wrapper.append(input);
  return wrapper;
}

function openArticle(id) {
  const article = state.articles.find((row) => row.id === id);
  if (!article) return;
  const title = el("input", { value: article.title, required: "", maxlength: "200" });
  const topic = el("input", { value: article.topic, maxlength: "100" });
  const url = el("input", { type: "url", value: article.url, maxlength: "2048", placeholder: "https://example.com/article" });
  const body = el("textarea", { rows: "8", required: "", maxlength: "20000", text: article.body });
  const existing = el("input", { value: article.existing_links.join(";"), placeholder: "A04;A05" });
  const eligible = el("input", { type: "checkbox", checked: article.eligible });
  const form = el("form", { onsubmit: (event) => {
    event.preventDefault();
    task("Saving article…", async () => {
      await api(`/api/articles/${encodeURIComponent(id)}`, { ...article, title: title.value, body: body.value, topic: topic.value, url: url.value, eligible: eligible.checked, existing_links: existing.value.split(";").map((item) => item.trim()).filter(Boolean) }, "PUT");
      await loadCollection();
      invalidateResults();
      $("#article-dialog").close();
      toast("Article saved. Related review decisions were cleared.");
    });
  } }, el("p", { text: `Article ${article.id}. Saving changes clears review decisions involving this article.` }), formField("Title", title), el("div", { class: "article-form-grid" }, formField("Topic", topic), formField("Destination URL", url)), formField("Article body", body), formField("Existing destination IDs, separated by semicolons", existing), el("label", { class: "checkbox-label" }, eligible, "Eligible as a link destination"), el("button", { class: "button primary", type: "submit", text: "Save article" }));
  $("#article-details").replaceChildren(form);
  $("#article-dialog").showModal();
}

function invalidateResults() {
  state.lastLinks = null;
  empty($("#search-results"), "Collection updated.", "Run a new search to use the current article text.");
  empty($("#links-results"), "Collection updated.", "Run link discovery again to use the current text and rules.");
  empty($("#overlap-results"), "Collection updated.", "Run overlap review again to use the current article text.");
}

async function renderEvaluation() {
  const data = await api("/api/evaluation");
  const content = $("#evaluation-content");
  const grid = el("div", { class: "metric-grid" });
  for (const method of ["Embeddings", "TF-IDF"]) {
    const metrics = data.metrics.filter((row) => row.method === method);
    const table = el("table", {}, el("thead", {}, el("tr", {}, ...["Results", "Precision", "Recall"].map((heading) => el("th", { text: heading })))), el("tbody", {}, ...metrics.map((metric) => el("tr", {}, el("td", { text: `Top ${metric.k}` }), el("td", { text: `${(metric.precision * 100).toFixed(1)}%` }), el("td", { text: metric.recall === null ? "N/A" : `${(metric.recall * 100).toFixed(1)}%` })))));
    grid.append(el("div", { class: "metric-panel" }, el("h2", { text: method }), table));
  }
  const queries = el("ul", { class: "query-list" }, ...data.queries.map((query) => el("li", {}, el("strong", { text: query.query_id }), el("span", { text: query.question }))));
  content.replaceChildren(el("div", { class: "notice", text: data.notice }), el("div", { class: "result-heading" }, el("h2", { text: `${data.queries.length} saved questions · ${data.article_count} original demo articles` }), el("span", { text: "Equal weight per question" })), grid, el("div", { class: "metric-explanation" }, el("div", {}, el("h3", { text: "Precision: are the suggestions useful?" }), el("p", { text: "Relevant results found divided by results shown. Finding 2 relevant articles among 3 results gives 67% precision." })), el("div", {}, el("h3", { text: "Recall: what did we miss?" }), el("p", { text: "Relevant results found divided by all relevant articles. Finding 2 of the 4 relevant articles gives 50% recall." }))), el("h2", { class: "evaluation-heading", text: "Questions in this development set" }), queries);
}

document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.view)));
document.querySelectorAll(".close-dialog").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => { $("#search-query").value = button.dataset.example; $("#search-form").requestSubmit(); }));
$("#search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task("Searching your collection… The first run loads the model and may take a little longer.", async () => {
    const payload = await api("/api/search", { query: $("#search-query").value, method: $("#search-method").value, top_k: Number($("#search-k").value), min_score: Number($("#search-min").value) });
    renderSearch(payload);
  });
});
$("#links-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task("Finding eligible destinations and passage evidence…", async () => {
    state.sourceId = $("#links-source").value;
    renderLinks(await api("/api/links", { source_id: state.sourceId, method: $("#links-method").value, top_k: Number($("#links-k").value), min_score: 0 }));
  });
});
$("#overlap-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task("Comparing passages across your collection…", async () => {
    renderOverlaps(await api("/api/overlaps", { method: $("#overlap-method").value, threshold: Number($("#overlap-threshold").value), limit: Number($("#overlap-limit").value) }));
  });
});
$("#article-filter").addEventListener("input", renderCollection);
for (const id of ["#import-top", "#import-collection"]) $(id).addEventListener("click", () => $("#import-dialog").showModal());
$("#csv-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if (file.size > 1500000) { toast("Choose a CSV smaller than 1.5 MB."); event.target.value = ""; return; }
  $("#csv-text").value = await file.text();
});
$("#import-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!confirm("Replace this workspace's collection and clear its review decisions? Export your current collection first if needed.")) return;
  task("Validating and importing your collection…", async () => {
    const result = await api("/api/articles/import", { csv_text: $("#csv-text").value });
    await loadCollection();
    invalidateResults();
    $("#import-dialog").close();
    navigate("collection");
    toast(`Imported ${result.count} articles.`);
  });
});
$("#reset-demo").addEventListener("click", () => {
  if (!confirm("Replace the current collection with the 21 fictional demo articles and clear reviews?")) return;
  task("Restoring demo articles…", async () => { await api("/api/articles/reset", {}); await loadCollection(); invalidateResults(); toast("Demo collection restored."); });
});
$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#login-error").textContent = "";
  const button = $("#login-form button"); button.disabled = true;
  try { await api("/api/login", { password: $("#password").value }); $("#password").value = ""; await start(); }
  catch (error) { $("#login-error").textContent = error.message; }
  finally { button.disabled = false; }
});
$("#sign-out").addEventListener("click", () => task("Signing out…", async () => { await api("/api/logout", {}); showLogin(); }));
window.addEventListener("hashchange", () => navigate(location.hash.slice(1)));
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) && !$("#workspace").hidden && !document.querySelector("dialog[open]")) {
    event.preventDefault(); navigate("search"); $("#search-query").focus();
  }
});
start();
