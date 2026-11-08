"use strict";
(() => {
  const data = JSON.parse(document.getElementById("review-data").textContent);
  const registry = data.registry;
  const fields = ["schema_version","packet_id","item_id","item_type","case_id","source_id","target_id","reviewer","independence_attested","decision","reason","provisional_revealed"];
  const allowed = new Set(["useful","not_useful","unsure","unreviewed"]);
  const key = `semantic-review-3e:${registry.packet_id}`;
  const $ = (id) => document.getElementById(id);
  const nodes = new Map();
  let state = { reviewer: "", attest: false, rows: {} };

  function node(tag, text, attrs = {}) {
    const n = document.createElement(tag);
    if (text !== undefined && text !== null) n.textContent = text;
    for (const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);
    return n;
  }
  function message(text) { $("message").textContent = text; $("message").hidden = !text; }
  function row(id) { return state.rows[id] || { decision:"unreviewed", reason:"", provisional_revealed:false }; }
  function save() {
    try { localStorage.setItem(key, JSON.stringify(state)); }
    catch { message("This browser cannot save the draft. Export a CSV to keep your decisions."); }
  }
  function refresh(applyFilters = true) {
    const counts = { useful:0, not_useful:0, unsure:0, unreviewed:0 };
    let visible = 0;
    for (const item of data.items) {
      const decision = row(item.item_id).decision;
      counts[decision]++;
      const status = $("status").value;
      const show = ($("task").value === "all" || $("task").value === item.case_id) &&
        (status === "all" || status === decision || (status === "decided" && ["useful","not_useful"].includes(decision)));
      if (applyFilters) nodes.get(item.item_id).card.hidden = !show;
      if (!nodes.get(item.item_id).card.hidden) visible++;
    }
    $("progress").textContent = `${counts.useful + counts.not_useful} of 59 decided · ${counts.unsure} unsure · ${counts.unreviewed} unreviewed`;
    $("empty").hidden = visible > 0;
  }
  function fullArticle(article) {
    const box = node("div");
    box.append(node("h3", article.title), node("p", article.url, {class:"url"}));
    const details = node("details");
    details.append(node("summary", "Read the full saved article"), node("pre", article.body, {class:"fulltext"}));
    box.append(details);
    return box;
  }
  function render() {
    $("reviewer").value = state.reviewer;
    $("attest").checked = state.attest;
    $("items").replaceChildren(); nodes.clear();
    data.items.forEach((item,index) => {
      const current = row(item.item_id);
      const card = node("article", null, {class:"card", "data-item-id":item.item_id});
      card.append(node("p", `${index+1} / 59 · ${item.case_id} · ${item.item_type === "overlap" ? "Overlap investigation" : item.kind === "related" ? "Related article" : "Internal-link recommendation"}`, {class:"case"}));
      card.append(node("h2", data.articles[item.target_id].title), node("p", item.criterion, {class:"criterion"}));
      const articles = node("div", null, {class:"articles"});
      const source = node("div");
      source.append(node("h3", item.item_type === "overlap" ? "Article A" : "Source"));
      if (item.source_id) source.append(fullArticle(data.articles[item.source_id]));
      else source.append(node("p", "Question-based task — no source article."), node("p", item.question));
      const target = node("div"); target.append(node("h3", item.item_type === "overlap" ? "Article B" : "Target article"), fullArticle(data.articles[item.target_id]));
      articles.append(source,target); card.append(articles);
      const linkText = item.existing_link === null ? "Existing-link status: not applicable to a question-based task." :
        `Existing-link status in saved collection: ${item.source_id} → ${item.target_id}: ${item.existing_link ? "already linked" : "not linked"}${item.item_type === "overlap" ? `; reverse direction: ${item.reverse_existing_link ? "already linked" : "not linked"}` : ""}.`;
      card.append(node("p", linkText, {class:"url"}));
      item.evidence.forEach((e,index) => {
        const block = node("div"); block.append(node("h3", `Supporting passages ${item.evidence.length > 1 ? index+1 : ""}`));
        const columns = node("div", null, {class:"evidence"});
        const left = node("div"); left.append(node("h3", item.source_id ? "Source passage" : "Source question"), node("pre", e.source_passage || item.question));
        const right = node("div"); right.append(node("h3", "Target passage"), node("pre", e.target_passage)); columns.append(left,right);
        const method = node("details", null, {class:"retrieval"});
        method.append(node("summary", "Show retrieval method, rank and similarity"), node("p", `${e.method === "embeddings" ? "MiniLM" : "TF-IDF"} · rank ${e.rank} · similarity ${e.score}. Not an editorial confidence score.`));
        block.append(columns,method); card.append(block);
      });
      const rating = node("fieldset", null, {class:"rating"}); rating.append(node("legend", "Your independent decision"));
      const choices = node("div", null, {class:"choices"});
      for (const [value,label] of [["useful","Useful"],["not_useful","Not useful"],["unsure","Unsure"]]) {
        const input = node("input", null, {type:"radio",name:`decision-${item.item_id}`,value}); input.checked = current.decision === value;
        input.addEventListener("change", () => { state.rows[item.item_id] = {...row(item.item_id),decision:value}; save(); refresh(false); });
        const labelNode = node("label"); labelNode.append(input, document.createTextNode(label)); choices.append(labelNode);
      }
      rating.append(choices); card.append(rating);
      const reasonLabel = node("label", "Reason (optional)", {class:"reason"});
      const reason = node("textarea", null, {maxlength:"2000",rows:"2","aria-label":`Reason for ${item.item_id}`}); reason.value = current.reason;
      reason.addEventListener("input", () => { state.rows[item.item_id] = {...row(item.item_id),reason:reason.value}; save(); });
      reasonLabel.append(reason); card.append(reasonLabel);
      const ai = node("details", null, {class:"ai-note"}); ai.append(node("summary", "Show provisional AI judgement (optional)"));
      if (!item.ai_notes.length) ai.append(node("p", "No provisional AI judgement was recorded for this pair. No label has been invented."));
      for (const note of item.ai_notes) ai.append(node("strong", note.label), node("p", note.rationale), node("p", note.provenance));
      ai.addEventListener("toggle", () => { if (ai.open) { state.rows[item.item_id] = {...row(item.item_id),provisional_revealed:true}; save(); } });
      card.append(ai);
      const next = node("button", "Next unreviewed", {type:"button"});
      next.addEventListener("click", () => $("next").click()); card.append(next);
      $("items").append(card); nodes.set(item.item_id,{card});
    });
    refresh();
  }
  function parseCSV(text) {
    text = text.replace(/^\uFEFF/, "");
    const rows = []; let current = [], value = "", quoted = false, afterQuote = false;
    for (let i=0; i<text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i+1] === '"') { value += '"'; i++; }
        else if (c === '"') { quoted = false; afterQuote = true; }
        else value += c;
      } else if (c === '"') {
        if (value || afterQuote) throw new Error("Malformed CSV quote.");
        quoted = true;
      } else if (c === ",") { current.push(value); value=""; afterQuote=false; }
      else if (c === "\r" || c === "\n") {
        if (c === "\r" && text[i+1] === "\n") i++;
        current.push(value); rows.push(current); current=[]; value=""; afterQuote=false;
      } else {
        if (afterQuote) throw new Error("Unexpected text after a CSV quote.");
        value += c;
      }
    }
    if (quoted) throw new Error("Unclosed CSV quote.");
    if (value || current.length || afterQuote) { current.push(value); rows.push(current); }
    return rows;
  }
  function importedState(text) {
    const rows = parseCSV(text);
    if (JSON.stringify(rows.shift()) !== JSON.stringify(fields)) throw new Error("Use the CSV exported by this packet.");
    const result = {reviewer:"",attest:false,rows:{}};
    const names = new Set(), attestations = new Set();
    const expected = new Map(registry.items.map(item => [item.item_id,item]));
    if (!rows.length || rows.length > 59) throw new Error("CSV must contain 1–59 distinct packet items.");
    for (const values of rows) {
      if (values.length !== fields.length) throw new Error("Malformed CSV row.");
      const r = Object.fromEntries(fields.map((key,index) => [key,values[index]]));
      if (r.schema_version !== "1" || r.packet_id !== registry.packet_id) throw new Error("This CSV belongs to a different packet/version.");
      const item = expected.get(r.item_id);
      if (!item || result.rows[r.item_id]) throw new Error("Unknown or duplicate item in CSV.");
      for (const key of ["item_type","case_id","source_id","target_id"]) if (r[key] !== item[key]) throw new Error("Source, target or task differs from this packet.");
      if (!allowed.has(r.decision) || !["true","false"].includes(r.independence_attested) || !["true","false"].includes(r.provisional_revealed) || r.reviewer.length > 101 || r.reason.length > 2001) throw new Error("Unsupported decision/length or attestation.");
      if (r.reviewer) names.add(r.reviewer);
      attestations.add(r.independence_attested);
      result.rows[r.item_id] = {decision:r.decision,reason:r.reason,provisional_revealed:r.provisional_revealed === "true"};
    }
    if (names.size > 1 || attestations.size > 1) throw new Error("Resume one reviewer's file with consistent attestation.");
    result.reviewer = [...names][0] || ""; result.attest = [...attestations][0] === "true";
    return result;
  }
  function csvCell(value, freeText=false) {
    value = String(value);
    if (freeText && /^[=+@\-\t\r\n]/.test(value)) value = "'" + value;
    return '"' + value.replaceAll('"','""') + '"';
  }
  $("export").addEventListener("click", () => {
    const rows = [fields.map(v => csvCell(v)).join(",")];
    for (const item of registry.items) {
      const r = row(item.item_id);
      const values = {schema_version:"1",packet_id:registry.packet_id,...item,reviewer:state.reviewer,
        independence_attested:String(state.attest),decision:r.decision,reason:r.reason,provisional_revealed:String(r.provisional_revealed)};
      rows.push(fields.map(k => csvCell(values[k], ["reviewer","reason"].includes(k))).join(","));
    }
    const url = URL.createObjectURL(new Blob(["\uFEFF" + rows.join("\r\n") + "\r\n"],{type:"text/csv;charset=utf-8"}));
    const a = node("a",null,{href:url,download:`phase3e-review-${registry.packet_id.slice(0,10)}.csv`});
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
  });
  $("import").addEventListener("change", async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      if (file.size > 1024*1024) throw new Error("Choose a CSV smaller than 1 MiB.");
      const next = importedState(await file.text()); // Validate every row before replacing a draft.
      state = next; save(); render(); message("Review CSV restored. Nothing has been submitted.");
    } catch (error) { message(error.message); }
    event.target.value = "";
  });
  $("reviewer").addEventListener("input", () => { state.reviewer = $("reviewer").value; save(); });
  $("attest").addEventListener("change", () => { state.attest = $("attest").checked; save(); });
  $("task").addEventListener("change", refresh); $("status").addEventListener("change", refresh);
  $("next").addEventListener("click", () => {
    refresh();
    const next = data.items.find(item => !nodes.get(item.item_id).card.hidden && row(item.item_id).decision === "unreviewed");
    if (next) { const card = nodes.get(next.item_id).card; card.scrollIntoView(); card.querySelector('input[type=radio]').focus({preventScroll:true}); }
    else message("No unreviewed items in this filter. Change Show or Task to continue.");
  });
  $("clear").addEventListener("click", () => {
    if (!confirm("Clear this browser's draft? Export a CSV first if you want to keep it.")) return;
    state={reviewer:"",attest:false,rows:{}}; save(); render(); message("Browser draft cleared; exported CSVs are unchanged.");
  });
  for (const caseId of [...new Set(data.items.map(item => item.case_id))]) $("task").append(node("option",caseId,{value:caseId}));
  try {
    const draft = JSON.parse(localStorage.getItem(key) || "null");
    if (draft && typeof draft.reviewer === "string" && typeof draft.attest === "boolean" && draft.rows) {
      state.reviewer = draft.reviewer.slice(0,100); state.attest = draft.attest;
      for (const item of data.items) { const r = draft.rows[item.item_id]; if (r && allowed.has(r.decision) && typeof r.reason === "string") state.rows[item.item_id] = {decision:r.decision,reason:r.reason.slice(0,2001),provisional_revealed:r.provisional_revealed===true}; }
    }
  } catch { message("Draft could not be restored. Import a CSV or start a new review."); }
  render();
})();
