"use strict";

const $ = (selector) => document.querySelector(selector);
const state = { articles: [], meta: null, view: "home", busy: false, lastLinks: null, sourceId: null, hasSearched: false, pendingEvaluation: false };
const LIMITS = Object.freeze({ characters: 250000, articles: 100, body: 20000, passages: 800, selected: 40 });
const number = (value) => new Intl.NumberFormat("en-AU").format(value);

function isSampleCollection() {
  return state.articles.length === 21 && state.articles.every((a) => a.url.startsWith("https://example.com/articles/"));
}

// Display only. Never change the saved body, passage text or source offsets.
function displayText(text) { return text.replace(/:?(?:\bcontentReference\[oaicite:\d+\]\{index=\d+\})/gu, ""); }

function sharedEvidenceWords(left, right) {
  // Exact word forms only: punctuation separates tokens; case is ignored.
  // Deliberately do not stem plurals ("court" and "courts" remain different).
  const ignored = new Set("about after again also been before being between both could does each from have into more most other over same some such than that their them then there these they this those through very were what when where which while will with would your".split(" "));
  const words = (text) => [...displayText(text).matchAll(/[\p{L}\p{N}]+/gu)].map((match) => match[0].toLowerCase()).filter((word) => word.length >= 4 && /\p{L}/u.test(word) && !ignored.has(word));
  const destination = new Set(words(right));
  return [...new Set(words(left))].filter((word) => destination.has(word)).slice(0, 10);
}

function highlightedEvidence(text, words) {
  const fragment = document.createDocumentFragment();
  const shared = new Set(words);
  let cursor = 0;
  for (const match of text.matchAll(/[\p{L}\p{N}]+/gu)) {
    if (!shared.has(match[0].toLowerCase())) continue;
    fragment.append(document.createTextNode(text.slice(cursor, match.index)), el("mark", { class: "shared-word", text: match[0] }));
    cursor = match.index + match[0].length;
  }
  fragment.append(document.createTextNode(text.slice(cursor)));
  return fragment;
}

function evidence(text, label, start, end, sharedWords = []) {
  const clean = displayText(text);
  const preview = clean.length > 320 ? clean.slice(0, 320).replace(/\s+\S*$/u, "") + "…" : clean;
  const full = el("details", { class: "full-evidence" }, el("summary", { text: `Read full ${label.toLowerCase()}` }), el("pre", { text }));
  if (sharedWords.length) full.querySelector("pre").replaceChildren(highlightedEvidence(text, sharedWords));
  if (Number.isInteger(start) && Number.isInteger(end)) full.append(el("p", { class: "context-note", text: `Saved source character offsets: ${start}–${end}.` }));
  return el("div", { class: "evidence-block" }, el("p", { class: "passage evidence-preview" }, highlightedEvidence(preview, sharedWords)),
    clean !== text ? el("p", { class: "context-note", text: "A source citation marker is hidden in this preview. Full saved evidence is unchanged." }) : null, full);
}

function importComplete(count, source) {
  state.lastImport = { count, source, revision: state.revision };
  $("#import-success-title").textContent = `${count} articles imported`;
  $("#import-success-description").textContent = `${source} collection ready. Search articles, inspect link opportunities or compare content overlap.`;
  $("#import-success").hidden = false;
  $("#collection-imports").open = false;
  navigate("search");
  $("#search-query").focus();
}

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

async function api(path, data, method = "POST", expectedRevision = state.revision) {
  const headers = { "X-Workspace-Request": "true" };
  if (data !== undefined) headers["Content-Type"] = "application/json";
  if (data !== undefined && expectedRevision && path !== "/api/login" && path !== "/api/logout") headers["If-Match"] = expectedRevision;
  const options = data === undefined ? { headers } : { method, headers, body: JSON.stringify(data) };
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error("The service could not be reached. Check your connection and refresh the collection before retrying."); }
  if (response.ok && /^\/api\/reports\/(search|links|overlaps)\/pdf$/u.test(path)) return response.blob();
  let payload;
  try { payload = await response.json(); } catch { throw new Error("The service returned an unreadable result. Refresh the collection to check its state before retrying."); }
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/login" && state.passwordRequired) showLogin();
    let message = payload.detail || "The request could not be completed.";
    if (Array.isArray(message)) message = message.map((issue) => `${issue.loc.slice(1).join(".")}: ${issue.msg}`).join("; ");
    if (response.status === 409) { await loadCollection(); invalidateResults(); }
    if ([401, 410].includes(response.status) && !state.passwordRequired) message += " Reload to start a new temporary session; expired data may no longer be available.";
    if ([429, 503].includes(response.status)) message += " Wait before retrying. Repeated attempts do not reset the service budget.";
    if (/^[a-f0-9]{12}$/u.test(payload.diagnostic_reference || "")) message += ` Reference: ${payload.diagnostic_reference}.`;
    throw new Error(message);
  }
  if (path === "/api/articles" || (data !== undefined && (path.startsWith("/api/articles/") || path === "/api/articles/import" || path === "/api/website/import"))) {
    if (payload.collection_revision) state.revision = payload.collection_revision;
  } else if (payload.collection_revision && state.revision && payload.collection_revision !== state.revision) {
    await loadCollection(); invalidateResults();
    throw new Error("Collection changed. Run the analysis again using the current articles.");
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
  $("#workspace").setAttribute("aria-busy", "true");
  $("#app-error").hidden = true;
  document.querySelectorAll(".dialog-error").forEach((error) => error.remove());
  $("#busy-message").textContent = message;
  const websiteTask = $("#website-dialog").open;
  $("#busy").hidden = websiteTask;
  if (websiteTask) {
    $("#website-operation").hidden = false;
    $("#website-operation-text").textContent = message;
  }
  const submitButtons = [...document.querySelectorAll("button[type=submit]")].map((button) => ({ button, disabled: button.disabled }));
  submitButtons.forEach(({ button }) => { button.disabled = true; });
  try { await action(); }
  catch (error) {
    $("#app-error").textContent = error.message;
    $("#app-error").hidden = false;
    const dialog = document.querySelector("dialog[open]");
    if (dialog) {
      if (dialog.id === "website-dialog" && websiteRun && ["discovering", "extracting"].includes(websiteRun.phase)) {
        renderExtractionProgress(websiteRun, true);
      }
      if (dialog.id === "website-dialog") {
        $("#website-progress").textContent = "Request failed. Last confirmed counts are retained; server work may still be finishing. Retry cancellation or start a new run when ready.";
        dialog.querySelectorAll(".website-loading").forEach((node) => node.remove());
      }
      const inlineError = el("p", { class: "dialog-error", role: "alert", tabindex: "-1", text: error.message });
      (dialog.querySelector(".website-content-panel") || dialog.querySelector("form") || dialog).append(inlineError);
      inlineError.focus();
    } else $("#app-error").focus();
    toast(error.message);
  } finally {
    state.busy = false;
    $("#workspace").setAttribute("aria-busy", "false");
    $("#busy").hidden = true;
    $("#website-operation").hidden = true;
    $("#website-stop").disabled = false;
    $("#website-stop").textContent = "Cancel website run";
    submitButtons.forEach(({ button, disabled }) => { button.disabled = disabled; });
    if (state.pendingEvaluation) {
      state.pendingEvaluation = false;
      if (state.view === "evaluation") task("Loading saved evaluation results…", renderEvaluation);
    }
  }
}

function showLogin() { $("#workspace").hidden = true; $("#login").hidden = false; $("#password").focus(); }

async function loadCollection() {
  const [collection, meta] = await Promise.all([api("/api/articles"), api("/api/meta")]);
  state.articles = collection.articles;
  state.meta = meta;
  $("#website-open").hidden = !meta.website_fetch_enabled;
  $("#website-availability").hidden = Boolean(meta.website_fetch_enabled);
  $("#home-website-url").disabled = !meta.website_fetch_enabled;
  $("#home-website-submit").disabled = !meta.website_fetch_enabled;
  $("#home-website-unavailable").hidden = Boolean(meta.website_fetch_enabled);
  const sampleCollection = isSampleCollection();
  $("#home-current-collection").hidden = sampleCollection || !state.articles.length;
  $("#home-current-note").textContent = `Your ${state.articles.length} articles and saved reviews stay in this workspace. Continue analysis without importing or restoring a collection.`;
  $("#home-sample-note").textContent = sampleCollection ? "The current collection is fictional demonstration data. No website is needed." : "Sample options explain how to try fictional data. Opening them never replaces your collection.";
  $("#home-explore").textContent = sampleCollection ? "Explore sample analysis" : "View sample options";
  $("#home-explore").classList.toggle("primary", sampleCollection);
  $("#home-continue").hidden = sampleCollection || !state.articles.length;
  $("#home-continue").textContent = `Continue with your ${state.articles.length} articles`;
  $("#collection-origin").textContent = sampleCollection ? "Fictional sample collection · demonstration data" : state.articles.some((a) => /^W[a-f0-9]{16}$/u.test(a.id) && /^https?:\/\//iu.test(a.url)) ? "Your website-linked collection · inspect the original URLs and extracted text" : "Your collection · imported or edited articles";
  $("#analysis-collection-note").textContent = `${state.articles.length} articles ready. Search by topic, review link opportunities or compare overlap.`;
  const examples = sampleCollection ? ["Choosing a display fridge for a cafe", "Why does bread dough expand while resting?", "How can I arrange a cafe coffee station?"] : state.articles.slice(0, 3).map((a) => a.title);
  $(".examples").replaceChildren(el("span", { text: sampleCollection ? "Try a sample question" : "Try a title from your collection" }), ...examples.map((query) => el("button", { type: "button", "data-example": query, text: query })));
  $(".examples").hidden = !examples.length;
  $("#workspace-notice").textContent = meta.workspace_mode === "visitor"
    ? `This browser has its own temporary workspace. Data expires after ${Math.round(meta.idle_seconds / 60)} minutes without activity. Import only content you are authorised to process.`
    : "This local installation uses one shared workspace. Import only authorised content; sample restoration requires confirmation.";
  if (state.lastImport && state.lastImport.revision !== state.revision) { state.lastImport = null; $("#import-success").hidden = true; }
  $("#collection-count").textContent = `${state.articles.length} articles in your collection`;
  $("#nav-article-count").textContent = state.articles.length;
  if (!state.articles.length) $("#collection-imports").open = true;
  const select = $("#links-source");
  const previous = select.value;
  select.replaceChildren(...state.articles.map((article) => el("option", { value: article.id, text: article.title })));
  if (state.articles.some((article) => article.id === previous)) select.value = previous;
  renderCollection();
  renderCollectionRail();
  if (!state.hasSearched) renderDiscovery();
}

function browseCollection(topic = "") {
  $("#article-filter").value = topic;
  renderCollection();
  navigate("collection");
}

function renderCollectionRail() {
  const topics = new Map();
  for (const article of state.articles) {
    const topic = article.topic || "Uncategorised";
    topics.set(topic, (topics.get(topic) || 0) + 1);
  }
  const words = state.articles.reduce((count, article) => count + article.body.split(/\s+/u).filter(Boolean).length, 0);
  const topicList = el("div", { class: "rail-topics" });
  [...topics.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).forEach(([topic, count], index) => {
    topicList.append(el("button", { class: "topic-row", "aria-label": `Browse ${topic.replaceAll("_", " ")}: ${count} articles`, onclick: () => browseCollection(topic === "Uncategorised" ? "" : topic) }, el("span", { class: `topic-swatch swatch-${index % 4}`, "aria-hidden": "true" }), el("span", { text: topic.replaceAll("_", " ") }), el("span", { text: count })));
  });
  $("#collection-rail").replaceChildren(
    el("div", { class: "rail-header" }, el("h2", { text: "The collection" }), el("span", { class: "rail-symbol", "aria-hidden": "true", text: "▤" })),
    el("p", { class: "rail-summary", text: `${state.articles.length} articles across ${topics.size} topics. ${new Intl.NumberFormat().format(words)} words of source material.` }),
    topicList,
    el("button", { class: "button small rail-browse", text: "Browse all articles", onclick: () => browseCollection() }),
    el("details", { class: "method-help" }, el("summary", { text: "How matching works" }), el("p", {}, el("strong", { text: "Meaning" }), " uses embeddings to find related ideas, including different wording."), el("p", {}, el("strong", { text: "Words" }), " uses TF-IDF to compare weighted vocabulary. Choose Compare both to inspect their rankings."), el("p", { text: "Similarity is a clue to relevance, not a confidence percentage." }))
  );
}

function renderDiscovery() {
  if (!state.articles.length) { empty($("#search-results"), "No articles to analyse yet.", "Use Import to add a website or CSV collection, or restore the fictional samples with confirmation."); return; }
  const topics = new Set();
  const featured = [];
  for (const article of state.articles) {
    if (!topics.has(article.topic)) { featured.push(article); topics.add(article.topic); }
    if (featured.length === 4) break;
  }
  for (const article of state.articles) {
    if (featured.length === 4) break;
    if (!featured.includes(article)) featured.push(article);
  }
  const list = el("div", { class: "collection-preview" });
  for (const [index, article] of featured.entries()) {
    const excerpt = article.body.length > 160 ? article.body.slice(0, 160).replace(/\s+\S*$/u, "") + "…" : article.body;
    list.append(el("button", { class: "preview-row", "aria-label": `Open ${article.title}`, onclick: () => openArticle(article.id) }, el("span", { class: "preview-id", text: index + 1 }), el("span", {}, el("span", { class: "preview-title", text: article.title }), el("span", { class: "preview-excerpt", text: excerpt }), article.topic ? el("span", { class: "preview-topic", text: article.topic.replaceAll("_", " ") }) : null), el("span", { class: "preview-arrow", "aria-hidden": "true", text: "↗" })));
  }
  $("#search-results").replaceChildren(el("div", { class: "result-heading" }, el("h2", { text: "From your collection" }), el("span", { text: `${featured.length} of ${state.articles.length} articles` })), list);
}

async function start() {
  try {
    const session = await api("/api/session");
    state.passwordRequired = session.password_required;
    if (!session.authenticated) { showLogin(); return; }
    $("#login").hidden = true;
    $("#workspace").hidden = false;
    $("#sign-out").hidden = !session.password_required;
    await loadCollection();
    if (!location.hash) history.replaceState(null, "", "#home");
    navigate(location.hash.slice(1) || "home");
  } catch (error) { $("#app-error").textContent = error.message; $("#app-error").hidden = false; $("#workspace").hidden = false; }
}

function navigate(view) {
  if (!["home", "search", "links", "overlap", "collection", "evaluation"].includes(view)) view = "home";
  state.view = view;
  document.querySelectorAll(".view").forEach((section) => { section.hidden = section.id !== `view-${view}`; });
  $("#analysis-nav").hidden = !["search", "links", "overlap"].includes(view);
  document.querySelectorAll(".utility-menu").forEach((menu) => { menu.open = false; });
  document.querySelectorAll(".nav-item").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
  });
  document.querySelectorAll(".masthead-actions a[data-view]").forEach((link) => {
    const active = link.dataset.view === view || (link.dataset.view === "search" && ["links", "overlap"].includes(view));
    if (active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  });
  if (location.hash !== `#${view}`) history.pushState(null, "", `#${view}`);
  $("#app-error").hidden = true;
  if (view === "evaluation") {
    if (state.busy) state.pendingEvaluation = true;
    else task("Loading saved evaluation results…", renderEvaluation);
  }
}

function empty(container, title, description) {
  container.replaceChildren(el("div", { class: "empty-state" }, el("h2", { text: title }), el("p", { text: description })));
}

function articleTitle(result) {
  return el("button", { class: "result-title", text: result.title, onclick: () => openArticle(result.id) });
}

function scoreBadge(score) { return el("span", { class: "score", text: `Similarity ${score.toFixed(3)}` }); }
function metadata(result) {
  const generatedId = /^W[a-f0-9]{16}$/.test(result.id);
  if (generatedId && !result.topic) return null;
  return el("div", { class: "article-meta" }, generatedId ? null : el("span", { text: result.id }), result.topic ? el("span", { class: "topic-tag", text: result.topic.replaceAll("_", " ") }) : null);
}
function methodName(method) { return method === "embeddings" ? "MiniLM" : "TF-IDF"; }

function renderSearch(payload) {
  const exportButton = $('[data-export-pdf="search"]');
  exportButton.disabled = false;
  exportButton.title = "Export the completed results shown here, using their original settings";
  state.hasSearched = true;
  const container = $("#search-results");
  const methods = Object.entries(payload.results);
  const grid = el("div", { class: methods.length > 1 ? "comparison" : "" });
  for (const [method, results] of methods) {
    const section = el("div", {}, el("div", { class: "result-heading" }, el("h2", { text: `${methodName(method)} results` }), el("span", { text: `${results.length} matches · ${(payload.elapsed_ms / 1000).toFixed(2)} seconds` })));
    const list = el("div", { class: "result-list" });
    if (!results.length) empty(list, "No matches above this score.", "Try a lower minimum score or a different question. A keyword query may not share any vocabulary with this collection.");
    for (const [index, result] of results.entries()) {
      list.append(el("article", { class: "result-card" }, el("div", { class: "result-topline" }, el("div", { class: "ranked-title" }, el("span", { class: "result-rank", "aria-label": `Rank ${index + 1}`, text: index + 1 }), el("h3", {}, articleTitle(result))), scoreBadge(result.score)), metadata(result), evidence(result.passage, "matching passage", result.passage_start, result.passage_end), el("div", { class: "result-footer" }, safeTarget(result.url), el("button", { class: "text-button", text: "Read article", onclick: () => openArticle(result.id) }))));
    }
    section.append(list);
    grid.append(section);
  }
  container.replaceChildren(grid, el("p", { class: "context-note", text: "Scores express similarity, not confidence or relevance percentages. Compare rankings and evidence; score sizes are not directly comparable between methods." }));
}

function safeTarget(url) {
  if ((url || "").startsWith("https://example.com/articles/")) return el("span", { text: "Fictional sample URL; not a published article." });
  if (!/^https?:\/\//iu.test(url || "")) return el("span", { text: "No public article URL provided. Add one in Articles." });
  return el("a", { href: url, target: "_blank", rel: "noopener noreferrer", title: url, text: "Open original article" });
}

function renderLinks(payload) {
  const exportButton = $('[data-export-pdf="links"]');
  exportButton.disabled = false;
  exportButton.title = "Export the completed results shown here, using their original settings";
  state.lastLinks = payload;
  const container = $("#links-results");
  container.className = "";
  const sourceId = state.sourceId;
  const source = state.articles.find((article) => article.id === sourceId);
  if (state.linkView?.sourceId !== sourceId || state.linkView?.revision !== payload.collection_revision) {
    state.linkView = { sourceId, revision: payload.collection_revision, selected: {}, drafts: {} };
  }
  const view = state.linkView;
  const reviewFor = (id) => payload.reviews.find((review) => review.target_id === id);
  const reviewLabel = (review) => review?.decision === "useful" ? "Useful" : review?.decision === "not_useful" ? "Not useful" : "Unreviewed";
  const sections = [];
  for (const [method, group] of Object.entries(payload.results)) {
    const reviewed = group.results.filter((result) => ["useful", "not_useful"].includes(reviewFor(result.id)?.decision)).length;
    const section = el("section", { class: "method-section link-method", "aria-label": `${methodName(method)} link opportunities` },
      el("div", { class: "result-heading" }, el("h2", { text: `${methodName(method)} candidates` }), el("span", { class: "link-review-count", text: `${reviewed} of ${group.results.length} reviewed` })));
    section.append(el("div", { class: "exclusions" }, el("span", { text: `Self: ${group.excluded.self}` }), el("span", { text: `Existing links excluded: ${group.excluded.existing.length}` }), el("span", { text: `Ineligible pages excluded: ${group.excluded.disallowed.length}` })));
    if (!group.results.length) {
      const emptyList = el("div");
      empty(emptyList, "No eligible candidates found.", "Check destination eligibility, existing links and the text in this collection.");
      section.append(emptyList);
      sections.push(section);
      continue;
    }
    const tabs = el("div", { class: "link-candidates", role: "tablist", "aria-label": `${methodName(method)} destinations`, "aria-orientation": "vertical" });
    const panel = el("article", { id: `link-panel-${method}`, class: "link-detail", role: "tabpanel", tabindex: "0" });
    const buttons = [];
    const focusDetail = () => { panel.focus({ preventScroll: true }); panel.scrollIntoView({ block: "start" }); };
    const sidebar = el("div", { class: "link-overview" }, el("h3", { text: "Suggested destinations" }),
      el("p", { text: "Ranked by similarity. Select one to inspect the connection." }), tabs,
      el("button", { class: "text-button link-inspect", text: "Inspect selected evidence", onclick: focusDetail }));
    function selectCandidate(index, focusTab = false, inspect = false) {
      const result = group.results[index];
      view.selected[method] = result.id;
      buttons.forEach((button, position) => {
        button.setAttribute("aria-selected", String(position === index));
        button.tabIndex = position === index ? 0 : -1;
      });
      const saved = payload.reviews.find((review) => review.target_id === result.id);
      const draftKey = result.id; // Reviews belong to an article pair, shared by both methods.
      const note = el("input", { type: "text", name: `review_note_${method}_${result.id}`, autocomplete: "off", maxlength: "1000", placeholder: "Why would this link help the reader?…", value: view.drafts[draftKey] ?? saved?.note ?? "", "aria-label": `Editorial note for ${result.title}` });
      note.dataset.targetId = result.id;
      note.addEventListener("input", () => {
        view.drafts[draftKey] = note.value;
        document.querySelectorAll(".link-note-editor input").forEach((other) => {
          if (other.dataset.targetId === result.id) other.value = note.value;
        });
      });
      const actions = el("div", { class: "review-actions", role: "group", "aria-label": `Editorial decision for ${result.title}` });
      for (const [decision, label] of [["useful", "Useful candidate"], ["not_useful", "Not useful"], ["pending", "Clear decision"]]) {
        actions.append(el("button", { id: `link-review-${method}-${decision}`, class: `button small ${saved?.decision === decision ? "link-decision-selected" : ""}`, "aria-pressed": String(saved?.decision === decision), text: label, onclick: () => task("Saving your review…", async () => {
          const review = { source_id: sourceId, target_id: result.id, decision, note: note.value };
          await api("/api/reviews", review, "POST", payload.collection_revision);
          payload.reviews = payload.reviews.filter((row) => row.target_id !== result.id).concat(review);
          if (view.drafts[draftKey] === review.note) delete view.drafts[draftKey];
          renderLinks(payload);
          if (view.selected[method] === result.id) $(`#link-review-${method}-${decision}`)?.focus({ preventScroll: true });
          else document.querySelector(`#link-list-${method} [aria-selected=true]`)?.focus({ preventScroll: true });
          toast("Review saved. No links were inserted.");
        }) }));
      }
      const back = el("button", { class: "text-button link-back", text: "Back to destinations", onclick: () => { buttons[index].focus({ preventScroll: true }); sidebar.scrollIntoView({ block: "start" }); } });
      const route = el("div", { class: "link-route" },
        el("div", { class: "link-route-source" }, el("span", { class: "link-route-label", text: "Link from" }), source ? articleTitle(source) : el("span", { text: sourceId })),
        el("span", { class: "link-route-arrow", "aria-hidden": "true", text: "↓" }),
        el("div", { class: "link-route-target" }, el("span", { class: "link-route-label", text: "Suggested destination" }), el("h3", {}, articleTitle(result))));
      const help = el("details", { class: "link-score-help" }, el("summary", { text: "About this score" }), el("p", { text: "Cosine similarity measures mathematical closeness between passages. It is not accuracy, a probability or editorial confidence. MiniLM and TF-IDF scores are not directly comparable." }));
      const noteEditor = el("details", { class: "link-note-editor", ...(note.value ? { open: "" } : {}) }, el("summary", { text: "Editorial note" }), el("label", {}, "Saved with your next decision", note));
      panel.dataset.review = saved?.decision || "pending";
      panel.setAttribute("aria-labelledby", buttons[index].id);
      panel.replaceChildren(back,
        el("div", { class: "link-detail-topline" }, el("span", { text: `Recommendation ${index + 1} of ${group.results.length}` }), el("span", { class: "link-review-state", role: "status", text: reviewLabel(saved) })),
        el("div", { class: "link-detail-heading" }, route, el("div", { class: "link-similarity", "aria-label": `Cosine similarity ${result.score.toFixed(3)}` }, el("strong", { text: result.score.toFixed(3) }), el("span", { text: "Cosine similarity" })), help),
        el("section", { class: "link-editorial", "aria-label": "Your editorial review" }, el("p", { text: "Would this destination help the reader?" }), actions, noteEditor),
        el("div", { class: "link-evidence-heading" }, el("h4", { text: "Matching passage evidence" }), el("p", { text: "These are the passages compared, not an explanation of usefulness. Review the article intent before adding a link." })),
        el("div", { class: "link-evidence-flow", role: "group", "aria-label": "Suggested link evidence, from source to destination" },
          linkPassage(result.source_passage, "Source passage", result.source_start, result.source_end, source?.url, source?.title || sourceId, "source"),
          el("p", { class: "link-evidence-direction" }, el("span", { "aria-hidden": "true", text: "↓" }), el("span", { text: "Suggested link" })),
          linkPassage(result.passage, "Destination passage", result.passage_start, result.passage_end, result.url, result.title, "destination")));
      if (focusTab) buttons[index].focus({ preventScroll: true });
      if (inspect) focusDetail();
    }
    tabs.id = `link-list-${method}`;
    group.results.forEach((result, index) => {
      const saved = reviewFor(result.id);
      const button = el("button", { id: `link-tab-${method}-${result.id}`, class: "link-candidate", type: "button", role: "tab", "aria-controls": panel.id,
        "aria-label": `${index + 1}. ${result.title}. Similarity ${result.score.toFixed(3)}. ${reviewLabel(saved)}`,
        "data-review": saved?.decision || "pending", onclick: (event) => selectCandidate(index, true, event.detail > 0 && matchMedia("(max-width: 760px)").matches) },
      el("span", { class: "link-candidate-rank", "aria-hidden": "true", text: String(index + 1) }),
      el("span", { class: "link-candidate-copy" }, el("span", { class: "link-candidate-title", text: result.title }), el("span", { class: "link-candidate-state", text: reviewLabel(saved) })),
      el("span", { class: "link-candidate-score", "aria-hidden": "true", text: result.score.toFixed(3) }));
      button.addEventListener("keydown", (event) => {
        const next = { ArrowDown: (index + 1) % group.results.length, ArrowUp: (index + group.results.length - 1) % group.results.length, Home: 0, End: group.results.length - 1 }[event.key];
        if (next !== undefined) { event.preventDefault(); selectCandidate(next, true); }
      });
      buttons.push(button);
      tabs.append(button);
    });
    const chosen = group.results.findIndex((result) => result.id === view.selected[method]);
    selectCandidate(chosen >= 0 ? chosen : 0);
    section.append(el("div", { class: "link-workbench" }, sidebar, panel));
    sections.push(section);
  }
  container.replaceChildren(...sections);
}

function linkPassage(text, label, start, end, url, title, side) {
  // Exact prefix from the returned passage: never paraphrase or remove markers.
  const excerpt = linkExcerpt(text);
  const full = el("details", { class: "full-evidence" }, el("summary", { text: `Read full ${label.toLowerCase()}` }), el("pre", { text }));
  if (Number.isInteger(start) && Number.isInteger(end)) full.append(el("p", { class: "link-offsets", text: `Original character offsets: ${start}–${end}` }));
  const original = safeTarget(url);
  if (original.tagName === "A") original.textContent = label === "Source passage" ? "Open source article" : "Open destination article";
  const direction = side === "source" ? "Source · link from" : "Destination · link to";
  return el("section", { class: `link-passage link-passage--${side}`, "aria-label": `${direction}: ${title}` },
    el("h4", { class: "link-passage-label", text: direction }), el("h5", { class: "link-passage-title", text: title }),
    el("blockquote", { class: "link-excerpt", text: excerpt }),
    excerpt.length < text.length ? el("p", { class: "link-excerpt-note", text: "Exact excerpt. Open the full passage for context." }) : null,
    el("div", { class: "link-passage-links" }, full, original));
}

function linkExcerpt(text) {
  const characters = Array.from(text);
  if (characters.length <= 220) return text;
  const prefix = characters.slice(0, 220).join("").replace(/\s+\S*$/u, "");
  const endings = [...prefix.matchAll(/[.!?](?=\s|$)/gu)];
  const end = endings.at(-1)?.index;
  return end >= 80 ? prefix.slice(0, end + 1) : prefix;
}

function renderOverlaps(payload) {
  const exportButton = $('[data-export-pdf="overlaps"]');
  exportButton.disabled = false;
  exportButton.title = "Export the completed results shown here, using their original settings";
  const container = $("#overlap-results");
  container.className = "";
  if (!payload.pairs.length) { empty(container, "No pairs above this threshold.", "Try a lower threshold. A lack of high similarity is not proof that topics never overlap."); return; }
  const list = el("div", { class: "result-list" });
  for (const pair of payload.pairs) {
    const sharedWords = sharedEvidenceWords(pair.left.passage, pair.right.passage);
    const columns = el("div", { class: "pair-grid" });
    for (const [index, article] of [pair.left, pair.right].entries()) columns.append(el("div", {}, el("span", { class: "overlap-article-label", text: index === 0 ? "Article A" : "Article B" }), el("h3", {}, articleTitle(article)), metadata(article), evidence(article.passage, "overlap passage", article.passage_start, article.passage_end, sharedWords), safeTarget(article.url)));
    const wording = el("div", { class: "overlap-wording" },
      el("strong", { text: sharedWords.length ? `Common terms: ${sharedWords.join(" · ")}` : "No common terms highlighted. The passages may still be related in meaning." }),
      el("p", { text: "Highlighted terms appear in both passages. They do not determine the semantic similarity score." }));
    list.append(el("article", { class: "result-card" }, el("div", { class: "pair-heading" }, el("span", { text: "Possible topic overlap · editorial review" }), scoreBadge(pair.score)), wording, columns, el("div", { class: "result-footer" }, el("span", { text: "Check whether the pages answer different reader questions and contain unique information." }))));
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
  const openedRevision = state.revision;
  const article = state.articles.find((row) => row.id === id);
  if (!article) return;
  const title = el("input", { name: "title", autocomplete: "off", value: article.title, required: "", maxlength: "200" });
  const topic = el("input", { name: "topic", autocomplete: "off", value: article.topic, maxlength: "100" });
  const url = el("input", { name: "url", autocomplete: "off", spellcheck: "false", type: "url", value: article.url, maxlength: "2048", placeholder: "https://example.com/article…" });
  const body = el("textarea", { name: "body", autocomplete: "off", rows: "8", required: "", maxlength: "20000", text: article.body });
  const existing = el("input", { name: "existing_links", autocomplete: "off", spellcheck: "false", value: article.existing_links.join(";"), placeholder: "A04;A05…" });
  const eligible = el("input", { name: "eligible", type: "checkbox", checked: article.eligible });
  const form = el("form", { onsubmit: (event) => {
    event.preventDefault();
    task("Saving article…", async () => {
      await api(`/api/articles/${encodeURIComponent(id)}`, { ...article, title: title.value, body: body.value, topic: topic.value, url: url.value, eligible: eligible.checked, existing_links: existing.value.split(";").map((item) => item.trim()).filter(Boolean) }, "PUT", openedRevision);
      await loadCollection();
      invalidateResults();
      form.dataset.dirty = "false";
      $("#article-dialog").close();
      toast("Article saved. Related review decisions were cleared.");
    });
  } }, el("p", { text: `Article ${article.id}. Saving changes clears review decisions involving this article.` }), formField("Title", title), el("div", { class: "article-form-grid" }, formField("Topic", topic), formField("Destination URL", url)), formField("Article body", body), formField("Existing destination IDs, separated by semicolons", existing), el("label", { class: "checkbox-label" }, eligible, "Eligible as a link destination"), el("button", { class: "button primary", type: "submit", text: "Save article" }));
  $("#article-details").replaceChildren(form);
  $("#article-dialog").showModal();
}

function invalidateResults() {
  document.querySelectorAll("[data-export-pdf]").forEach((button) => { button.disabled = true; button.title = "Run this analysis first"; });
  state.lastLinks = null;
  state.linkView = null;
  state.hasSearched = false;
  renderDiscovery();
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

document.querySelectorAll("[data-view]").forEach((link) => link.addEventListener("click", (event) => {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
  event.preventDefault();
  navigate(link.dataset.view);
  $("#main-content").focus({ preventScroll: true });
}));
function mayClose(dialog) {
  return dialog.querySelector("form")?.dataset.dirty !== "true" || confirm("Discard the unsaved changes in this form?");
}
document.querySelectorAll(".close-dialog").forEach((button) => button.addEventListener("click", () => {
  const dialog = button.closest("dialog");
  if (mayClose(dialog)) { const form = dialog.querySelector("form"); if (form) form.dataset.dirty = "false"; dialog.close(); }
}));
document.querySelectorAll("dialog").forEach((dialog) => {
  dialog.addEventListener("input", (event) => { const form = event.target.closest("form"); if (form) form.dataset.dirty = "true"; });
  dialog.addEventListener("cancel", (event) => { if (!mayClose(dialog)) event.preventDefault(); else { const form = dialog.querySelector("form"); if (form) form.dataset.dirty = "false"; } });
});
window.addEventListener("beforeunload", (event) => {
  if (document.querySelector('dialog[open] form[data-dirty="true"]')) { event.preventDefault(); event.returnValue = ""; }
});
$(".examples").addEventListener("click", (event) => { const button = event.target.closest("[data-example]"); if (button) { $("#search-query").value = button.dataset.example; $("#search-form").requestSubmit(); } });
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
for (const id of ["#import-collection", "#home-import"]) $(id).addEventListener("click", () => {
  $(".utility-menu").open = false;
  $("#import-dialog").showModal();
});
$("#import-top").addEventListener("click", () => { navigate("collection"); $("#collection-imports").open = true; $("#collection-imports").scrollIntoView({ block: "start" }); $("#collection-imports summary").focus(); });
$("#home-explore").addEventListener("click", () => { if (isSampleCollection()) { navigate("search"); $("#search-query").focus(); } else $("#sample-dialog").showModal(); });
$("#sample-keep").addEventListener("click", (event) => { event.preventDefault(); $("#sample-dialog").close(); navigate("search"); $("#search-query").focus(); });
$("#sample-restore").addEventListener("click", () => $("#reset-demo").click());
$("#dismiss-import-success").addEventListener("click", () => { state.lastImport = null; $("#import-success").hidden = true; });
$("#home-website-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.busy || !state.meta?.website_fetch_enabled) return;
  $("#website-url").value = $("#home-website-url").value.trim();
  $("#website-method").value = "auto";
  $("#website-dialog").showModal();
  $("#website-form").requestSubmit();
});
$("#csv-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if (file.size > 1500000) { toast("Choose a CSV smaller than 1.5 MB."); event.target.value = ""; return; }
  $("#csv-text").value = await file.text();
  $("#import-form").dataset.dirty = "true";
});
$("#import-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!confirm("Replace this workspace's collection and clear its review decisions? Export your current collection first if needed.")) return;
  task("Validating and importing your collection…", async () => {
    const result = await api("/api/articles/import", { csv_text: $("#csv-text").value });
    await loadCollection();
    invalidateResults();
    $("#import-form").dataset.dirty = "false";
    $("#import-dialog").close();
    importComplete(result.count, "CSV");
    toast(`Imported ${result.count} articles.`);
  });
});
$("#reset-demo").addEventListener("click", () => {
  if (!confirm("Replace the current collection with the 21 fictional demo articles and clear reviews?")) return;
  task("Restoring demo articles…", async () => { await api("/api/articles/reset", {}); if ($("#sample-dialog").open) $("#sample-dialog").close(); await loadCollection(); invalidateResults(); navigate("search"); toast("Fictional sample collection restored."); });
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
let websiteRun = null;
let websiteCancelled = false;
let websiteLastExtractionCount = null;

function discoveryLoading(count = null) {
  if (count === null) $("#website-source-settings").open = false;
  $("#website-operation").hidden = true;
  $("#website-results").replaceChildren(el("div", { class: "website-loading", role: "status", "aria-live": "polite" },
    el("span", { class: "spinner", "aria-hidden": "true" }),
    el("h3", { text: "Discovering website articles" }),
    el("p", { text: "Checking public article feeds and sitemaps. Your saved collection stays unchanged." }),
    el("strong", { text: count === null ? "Waiting for the first discovery response..." : `${count} articles found so far` })));
}


function renderExtractionProgress(run, interrupted = false) {
  const total = run.selected.length;
  // Cancellation deliberately discards the server's extracted previews. Retain only
  // the last reported count for this run, never text from another run or a timer.
  if (websiteLastExtractionCount?.runId !== run.run_id || run.phase !== "cancelled") {
    websiteLastExtractionCount = { runId: run.run_id, processed: run.processed };
  }
  const processed = Math.min(run.phase === "cancelled" ? websiteLastExtractionCount.processed : run.processed, total);
  const stopped = interrupted || ["cancelled", "failed"].includes(run.phase);
  $("#extraction-progress").hidden = !total;
  $("#extraction-progress").dataset.state = stopped ? "stopped" : ["ready", "imported"].includes(run.phase) ? "complete" : "active";
  $("#extraction-meter").max = total || 1;
  $("#extraction-meter").value = processed;
  const prefix = run.phase === "cancelled" ? "Cancelled. Preview discarded. Last confirmed: " : stopped ? "Interrupted. Last confirmed: " : "";
  const label = `${prefix}${processed} of ${total} selected articles processed. This includes excluded or failed articles; it does not mean they were imported.`;
  $("#extraction-count").textContent = label;
  $("#extraction-meter").setAttribute("aria-valuetext", label);
  const excluded = run.failures.filter((failure) => failure.kind === "capacity").length;
  const failed = run.failures.length - excluded;
  $("#extraction-outcomes").textContent = ["ready", "imported"].includes(run.phase)
    ? `${run.articles.length} ${run.phase === "imported" ? "imported" : "ready for review (not imported)"}; ${excluded} excluded by capacity; ${failed} failed.`
    : `${excluded} excluded by capacity; ${failed} failed. Accepted article count is finalised after extraction.`;
}

function renderWebsite(run) {
  websiteRun = run;
  const stage = ["ready", "imported"].includes(run.phase) ? 2 : ["selecting", "extracting"].includes(run.phase) ? 1 : 0;
  document.querySelectorAll(".website-steps li").forEach((item, index) => {
    item.classList.toggle("complete", index < stage);
    if (index === stage) item.setAttribute("aria-current", "step"); else item.removeAttribute("aria-current");
  });
  const labels = { discovering: "Finding public articles", selecting: "Choose your articles", extracting: "Extracting article text", ready: "Review your collection", imported: "Collection imported", cancelled: "Import cancelled", failed: "This run could not finish" };
  $("#website-progress").textContent = `${labels[run.phase] || run.phase} · ${run.candidates.length} found${run.phase === "extracting" ? ` · ${run.processed} of ${run.selected.length} processed` : ""}`;
  renderExtractionProgress(run);
  $("#website-operation").hidden = true;
  const settings = $("#website-source-settings");
  if (settings.dataset.phase !== run.phase) { settings.open = false; settings.dataset.phase = run.phase; }
  $("#collection-capacity").hidden = !["extracting", "ready", "imported"].includes(run.phase);
  $("#capacity-meter").max = LIMITS.characters;
  $("#capacity-meter").value = run.characters;
  $("#capacity-meter").hidden = run.phase === "extracting";
  $("#capacity-label").textContent = `Collection capacity: ${number(run.characters)} / ${number(LIMITS.characters)} characters`;
  if (run.phase === "extracting") {
    $("#capacity-meter").removeAttribute("value");
    $("#capacity-label").textContent = `Collection capacity: calculating accepted text (${number(LIMITS.characters)}-character budget)`;
  }
  $("#capacity-label").title = run.phase === "extracting" ? "Final accepted text total is available after extraction and duplicate/template handling finish." : "Accepted title and body characters";
  $("#website-action-note").textContent = run.phase === "ready" ? "Import replaces your collection and clears its editorial reviews." : run.phase === "imported" ? "Import complete. Start another discovery to build a new collection." : "Your saved collection is unchanged until you confirm.";
  const results = $("#website-results");
  results.replaceChildren();
  if (run.phase === "discovering") discoveryLoading(run.candidates.length);
  for (const warning of run.warnings) results.append(el("p", { class: "notice", text: warning }));
  $("#website-extract").hidden = run.phase !== "selecting" || !run.candidates.length;
  $("#website-commit").hidden = run.phase !== "ready" || !run.articles.length;
  $("#website-stop").hidden = ["imported", "cancelled", "failed"].includes(run.phase);
  if (run.phase === "selecting") {
    const count = el("p", { id: "website-selection-count", text: "0 selected (maximum 40)" });
    const list = el("div", { class: "website-candidates" });
    const updateSelection = () => {
      const selected = list.querySelectorAll("input:checked").length;
      count.textContent = `${selected} selected (maximum 40)`;
      $("#website-extract").textContent = selected ? `Extract ${selected} selected article${selected === 1 ? "" : "s"}` : "Extract selected articles";
    };
    for (const item of run.candidates) {
      const input = el("input", { type: "checkbox", value: item.id, "aria-label": `Select ${item.title}` });
      input.addEventListener("change", () => {
        const selected = list.querySelectorAll("input:checked").length;
        if (selected > 40) { input.checked = false; toast("Choose up to 40 articles."); }
        updateSelection();
      });
      list.append(el("label", { class: "website-candidate" }, input, el("span", {}, item.title, el("small", { text: item.url }))));
    }
    const filter = el("input", { id: "website-filter", type: "search", placeholder: "Find an article by title or URL", "aria-label": "Filter discovered articles" });
    const noMatches = el("p", { class: "website-no-matches", text: "No articles match this filter. Try a title word or part of the URL.", hidden: "" });
    filter.addEventListener("input", () => {
      const query = filter.value.trim().toLowerCase();
      for (const row of list.children) row.hidden = !row.textContent.toLowerCase().includes(query);
      noMatches.hidden = [...list.children].some((row) => !row.hidden);
    });
    const bulk = el("button", { type: "button", class: "text-button", text: "Select first 40 shown", onclick: () => {
      list.querySelectorAll("input").forEach((input) => { input.checked = false; });
      [...list.children].filter((row) => !row.hidden).slice(0, 40).forEach((row) => { row.querySelector("input").checked = true; });
      updateSelection();
    } });
    const clear = el("button", { type: "button", class: "text-button", text: "Clear selection", onclick: () => {
      list.querySelectorAll("input").forEach((input) => { input.checked = false; }); updateSelection();
    } });
    results.append(el("div", { class: "website-selection-tools" }, filter, el("p", { class: "context-note", text: "Select first 40 shown replaces the selection with up to 40 articles matching the current filter, in the order displayed. Hidden matches are not selected. Choose fewer or shorter articles to leave room in the collection." }), el("div", { class: "website-selection-actions" }, count, bulk, clear)), list, noMatches);
    updateSelection();
  }
  const excluded = run.failures.filter((failure) => failure.kind === "capacity");
  const failed = run.failures.filter((failure) => failure.kind !== "capacity");
  for (const [items, label] of [[excluded, "Excluded by application capacity"], [failed, "Extraction failed"]]) {
    if (!items.length) continue;
    results.append(el("details", { class: "import-exclusions" }, el("summary", { text: `${label}: ${items.length} articles` }),
      ...items.map((failure) => el("p", { text: `${run.candidates.find((item) => item.id === failure.id)?.title || failure.id}: ${failure.message}` }))));
  }
  if (run.phase === "ready") {
    const other = Math.max(0, run.selected.length - run.articles.length - run.failures.length);
    results.prepend(el("div", { class: "website-preview-summary", role: "status" }, el("strong", { text: `${run.articles.length} articles ready · ${excluded.length} excluded · ${failed.length} failed` }),
      other ? el("span", { text: `${other} other articles not included; check warnings for duplicate or content-specific reasons.` }) : null));
    results.append(el("div", { class: "website-preview-summary" }, el("span", { text: `${number(run.characters)} title/body characters in the accepted preview` })),
      el("p", { text: "Open an article to check what was extracted. Import checks the final collection size and model passage limits before saving." }));
    for (const article of run.articles) {
      results.append(el("details", { class: "website-preview" }, el("summary", { text: `${article.title} (${article.body.length} characters)` }),
        el("p", { text: article.url }), el("p", { text: `${article.headings.length} headings; ${article.existing_links.length} links to selected articles` }), el("pre", { text: displayText(article.body) }),
        displayText(article.body) !== article.body ? el("details", {}, el("summary", { text: "Show original extracted text, including source citation markers" }), el("p", { class: "context-note", text: "Only this display preview is cleaned. Import and analysis retain the original text." }), el("pre", { text: article.body })) : null));
    }
    if (run.failures.length) results.append(el("label", { class: "website-candidate" }, el("input", { id: "website-partial", type: "checkbox" }), "I accept importing only the articles included in this preview."));
  }
}

async function advanceWebsite() {
  while (!websiteCancelled && ["discovering", "extracting"].includes(websiteRun.phase)) {
    $("#busy-message").textContent = websiteRun.phase === "discovering" ? "Discovering public articles…" : "Extracting selected articles…";
    renderWebsite(await api("/api/website/step", { run_id: websiteRun.run_id }, "POST", websiteRun.collection_revision));
  }
  if (websiteCancelled && websiteRun && !["imported", "cancelled"].includes(websiteRun.phase)) {
    renderWebsite(await api("/api/website/cancel", { run_id: websiteRun.run_id }, "POST", websiteRun.collection_revision));
  }
}

$("#website-open").addEventListener("click", () => $("#website-dialog").showModal());
$("#website-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task("Starting website discovery…", async () => {
    websiteCancelled = false;
    websiteRun = null;
    $("#extraction-progress").hidden = true;
    $("#collection-capacity").hidden = true;
    $("#website-commit").hidden = true;
    $("#website-extract").hidden = true;
    $("#website-stop").hidden = false;
    $("#website-progress").textContent = "Starting discovery. Your saved collection is unchanged.";
    discoveryLoading();
    renderWebsite(await api("/api/website/start", { url: $("#website-url").value, method: $("#website-method").value }));
    $("#website-form").dataset.dirty = "false";
    await advanceWebsite();
  });
});
$("#website-extract").addEventListener("click", () => task("Preparing your selection…", async () => {
  const ids = [...document.querySelectorAll(".website-candidates input:checked")].map((input) => input.value);
  if (!ids.length) throw new Error("Select at least one article.");
  renderWebsite(await api("/api/website/select", { run_id: websiteRun.run_id, ids }, "POST", websiteRun.collection_revision));
  await advanceWebsite();
}));
$("#website-stop").addEventListener("click", () => {
  websiteCancelled = true;
  $("#website-stop").disabled = true;
  $("#website-stop").textContent = "Cancellation requested...";
  $("#website-progress").textContent = "Cancellation requested. Waiting for the current request and server confirmation.";
  if (!state.busy) task("Cancelling website run…", advanceWebsite);
});
$("#website-dialog").addEventListener("close", () => {
  websiteCancelled = true;
  if (state.busy && websiteRun?.phase !== "imported") {
    $("#busy-message").textContent = "Finishing the current website request. Closing the dialog does not stop server work immediately.";
    $("#busy").hidden = false;
  }
});
$("#website-commit").addEventListener("click", async () => {
  if (state.busy || websiteRun?.phase !== "ready") return;
  const button = $("#website-commit");
  button.disabled = true;
  try {
    await task("Preparing analysis: validating article and model passage limits…", async () => {
      if (!confirm("Replace the collection with these extracted articles and clear its editorial reviews? Export first if needed.")) return;
      const result = await api("/api/website/import", { run_id: websiteRun.run_id, accept_partial: Boolean($("#website-partial")?.checked) }, "POST", websiteRun.collection_revision);
      websiteRun.phase = "imported";
      renderWebsite(websiteRun); // Reopening must not offer a stale replacement action.
      $("#website-dialog").close();
      $("#busy-message").textContent = "Loading your imported collection. Run an analysis when ready.";
      $("#busy").hidden = false;
      await loadCollection(); invalidateResults(); importComplete(result.count, "Website");
      toast(`Imported ${result.count} website articles. You can now search, review links and compare overlap.`);
    });
  } finally {
    button.disabled = false;
  }
});

window.addEventListener("hashchange", () => navigate(location.hash.slice(1)));
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) && !$("#workspace").hidden && !document.querySelector("dialog[open]")) {
    event.preventDefault();
    if (state.view === "home") $("#home-website-url").focus();
    else { navigate("search"); $("#search-query").focus(); }
  }
});
start();

document.querySelectorAll("[data-export-pdf]").forEach((button) => button.addEventListener("click", () => task("Preparing PDF report...", async () => {
  const section = button.dataset.exportPdf;
  const blob = await api(`/api/reports/${section}/pdf`, {});
  const url = URL.createObjectURL(blob);
  const link = el("a", { href: url, download: `${section}-analysis.pdf` });
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  toast("PDF downloaded for this completed analysis. Truncated findings are labelled.");
})));
