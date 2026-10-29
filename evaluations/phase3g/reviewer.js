"use strict";
(() => {
  const data = JSON.parse(document.getElementById("review-data").textContent);
  const fields = ["schema_version","packet_id","item_id","case_id","source_id","target_id","reviewer","human_attested","prior_exposure","decision","reason"];
  const decisions = new Set(["useful","not_useful","unsure","unreviewed"]);
  const exposures = new Set(["unreported","none","screened","unsure"]);
  const key = `semantic-review-3g:${data.packet_id}`;
  const $ = id => document.getElementById(id);
  const cards = new Map();
  const blank = () => ({reviewer:"",attest:false,exposure:"unreported",rows:{}});
  let state = blank();
  const row = id => state.rows[id] || {decision:"unreviewed",reason:""};
  function node(tag,text,attrs={}) {
    const n=document.createElement(tag);
    if (text !== undefined && text !== null) n.textContent=text;
    for (const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);
    return n;
  }
  function message(text) { $("message").textContent=text; $("message").hidden=!text; }
  function save() {
    try { localStorage.setItem(key,JSON.stringify(state)); }
    catch { message("Draft storage unavailable. Export CSV to keep your decisions."); }
  }
  function refresh(filter=true) {
    const counts={useful:0,not_useful:0,unsure:0,unreviewed:0}; let visible=0;
    for (const item of data.items) {
      const d=row(item.item_id).decision; counts[d]++;
      const show=($("task").value==="all" || $("task").value===item.case_id) &&
        ($("status").value==="all" || $("status").value===d || ($("status").value==="decided" && ["useful","not_useful"].includes(d)));
      if (filter) cards.get(item.item_id).hidden=!show;
      if (!cards.get(item.item_id).hidden) visible++;
    }
    $("progress").textContent=`${counts.useful+counts.not_useful} of ${data.items.length} decided · ${counts.unsure} unsure · ${counts.unreviewed} unreviewed`;
    $("empty").hidden=visible>0;
  }
  function article(id) {
    const a=data.articles[id], box=node("div");
    box.append(node("h3",a.title),node("p",a.url,{class:"url"}));
    const details=node("details");details.append(node("summary","Read the full saved article"),node("pre",a.body,{class:"fulltext"}));
    box.append(details);return box;
  }
  function render() {
    $("reviewer").value=state.reviewer;$("attest").checked=state.attest;$("exposure").value=state.exposure;
    $("items").replaceChildren();cards.clear();
    for (const [index,item] of data.items.entries()) {
      const card=node("article",null,{class:"card","data-item-id":item.item_id});
      card.append(node("p",`${index+1} / ${data.items.length} · ${item.case_id} · ${item.kind==="related" ? "Related article" : "Additional internal link"}`,{class:"case"}),
        node("h2",data.articles[item.target_id].title),node("p",item.question),node("p",item.criterion,{class:"criterion"}));
      const columns=node("div",null,{class:"articles"}),source=node("div"),target=node("div");
      source.append(node("h3","Source"));
      source.append(item.source_id ? article(item.source_id) : node("p","Question-based task; no source article."));
      target.append(node("h3","Proposed destination"),article(item.target_id));columns.append(source,target);card.append(columns);
      card.append(node("p",item.existing_link===null ? "Existing-link status: not applicable to a question-based task." : `Already linked from source in the saved collection: ${item.existing_link ? "yes" : "no"}.`,{class:"url"}));
      for (const passage of item.passages) {
        const evidence=node("div",null,{class:"evidence"}),left=node("div"),right=node("div");
        left.append(node("h3",item.source_id ? "Original source passage" : "Source question"),node("pre",passage.source_passage || item.question));
        right.append(node("h3","Original destination passage"),node("pre",passage.target_passage));evidence.append(left,right);card.append(evidence);
      }
      const rating=node("fieldset",null,{class:"rating"}),choices=node("div",null,{class:"choices"});rating.append(node("legend","Your decision"));
      for (const [value,label] of [["useful","Useful"],["not_useful","Not useful"],["unsure","Unsure"]]) {
        const input=node("input",null,{type:"radio",name:`decision-${item.item_id}`,value});input.checked=row(item.item_id).decision===value;
        input.addEventListener("change",()=>{state.rows[item.item_id]={...row(item.item_id),decision:value};save();refresh(false);});
        const wrapper=node("label");wrapper.append(input,document.createTextNode(label));choices.append(wrapper);
      }
      rating.append(choices);card.append(rating);
      const label=node("label","Reason (optional)",{class:"reason"}),reason=node("textarea",null,{maxlength:"2000",rows:"2","aria-label":`Reason for ${item.item_id}`});reason.value=row(item.item_id).reason;
      reason.addEventListener("input",()=>{state.rows[item.item_id]={...row(item.item_id),reason:reason.value};save();});label.append(reason);card.append(label);
      const next=node("button","Next unreviewed",{type:"button"});next.addEventListener("click",()=>$("next").click());card.append(next);
      $("items").append(card);cards.set(item.item_id,card);
    }
    refresh();
  }
  function parseCSV(text) {
    text=text.replace(/^\uFEFF/,"");const rows=[];let current=[],value="",quoted=false,after=false;
    for (let i=0;i<text.length;i++) {
      const c=text[i];
      if (quoted) {
        if (c==='"' && text[i+1]==='"') {value+='"';i++;}
        else if (c==='"') {quoted=false;after=true;}
        else value+=c;
      } else if (c==='"') {if(value || after) throw Error("Malformed CSV quote.");quoted=true;}
      else if (c===",") {current.push(value);value="";after=false;}
      else if (c==="\r" || c==="\n") {
        if(c==="\r" && text[i+1]==="\n") i++;current.push(value);rows.push(current);current=[];value="";after=false;
      } else {if(after) throw Error("Unexpected text after quote.");value+=c;}
    }
    if(quoted) throw Error("Unclosed CSV quote.");
    if(value || current.length || after) {current.push(value);rows.push(current);}
    return rows;
  }
  function imported(text) {
    const rows=parseCSV(text);
    if(JSON.stringify(rows.shift())!==JSON.stringify(fields)) throw Error("Use a CSV exported by this new round; earlier review files are incompatible.");
    if(!rows.length || rows.length>data.items.length) throw Error("Invalid number of review items.");
    const expected=new Map(data.items.map(i=>[i.item_id,i])),next=blank(),provenance=new Set();
    for(const values of rows) {
      if(values.length!==fields.length) throw Error("Missing/extra CSV fields.");
      const r=Object.fromEntries(fields.map((k,n)=>[k,values[n]])),item=expected.get(r.item_id);
      if(r.schema_version!=="3g-1" || r.packet_id!==data.packet_id) throw Error("Different packet/version.");
      if(!item || Object.hasOwn(next.rows,r.item_id)) throw Error("Unknown/duplicate item.");
      for(const k of ["case_id","source_id","target_id"]) if(r[k]!==item[k]) throw Error("Source, target or task mismatch.");
      if(!decisions.has(r.decision) || !exposures.has(r.prior_exposure) || !["true","false"].includes(r.human_attested) || r.reviewer.length>101 || r.reason.length>2001) throw Error("Invalid decision/provenance/length.");
      provenance.add(JSON.stringify([r.reviewer,r.human_attested,r.prior_exposure]));
      next.reviewer=r.reviewer;next.attest=r.human_attested==="true";next.exposure=r.prior_exposure;
      next.rows[r.item_id]={decision:r.decision,reason:r.reason};
    }
    if(provenance.size!==1) throw Error("One reviewer with consistent provenance is required.");return next;
  }
  function cell(value,free=false) {
    value=String(value);if(free && /^[=+@\-\t\r\n]/.test(value)) value="'"+value;
    return '"'+value.replaceAll('"','""')+'"';
  }
  $("export").addEventListener("click",()=>{
    const rows=[fields.map(v=>cell(v)).join(",")];
    for(const item of data.items) {
      const r={schema_version:"3g-1",packet_id:data.packet_id,...item,reviewer:state.reviewer,human_attested:String(state.attest),prior_exposure:state.exposure,...row(item.item_id)};
      rows.push(fields.map(k=>cell(r[k],["reviewer","reason"].includes(k))).join(","));
    }
    const url=URL.createObjectURL(new Blob(["\uFEFF"+rows.join("\r\n")+"\r\n"],{type:"text/csv;charset=utf-8"}));
    const a=node("a",null,{href:url,download:`phase3g-review-${data.packet_id.slice(0,10)}.csv`});document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  $("import").addEventListener("change",async e=>{
    const file=e.target.files[0];if(!file)return;
    try {if(file.size>1024*1024) throw Error("CSV exceeds 1 MiB.");const next=imported(await file.text());state=next;save();render();message("Draft restored; nothing submitted.");}
    catch(error){message(error.message);}e.target.value="";
  });
  $("reviewer").addEventListener("input",()=>{state.reviewer=$("reviewer").value;save();});
  $("attest").addEventListener("change",()=>{state.attest=$("attest").checked;save();});
  $("exposure").addEventListener("change",()=>{state.exposure=$("exposure").value;save();});
  $("task").addEventListener("change",()=>refresh());$("status").addEventListener("change",()=>refresh());
  $("next").addEventListener("click",()=>{refresh();const item=data.items.find(i=>!cards.get(i.item_id).hidden && row(i.item_id).decision==="unreviewed");if(item){const card=cards.get(item.item_id);card.scrollIntoView();card.querySelector("input[type=radio]").focus({preventScroll:true});}else message("No unreviewed items in this filter.");});
  $("clear").addEventListener("click",()=>{if(confirm("Clear this round's browser draft? Export first to keep it.")){state=blank();save();render();}});
  for(const id of [...new Set(data.items.map(i=>i.case_id))].sort()) $("task").append(node("option",id,{value:id}));
  try {
    const draft=JSON.parse(localStorage.getItem(key)||"null");
    if(draft && typeof draft.reviewer==="string" && draft.reviewer.length<=101 && typeof draft.attest==="boolean" && exposures.has(draft.exposure) && draft.rows) {
      state={reviewer:draft.reviewer,attest:draft.attest,exposure:draft.exposure,rows:{}};
      for(const item of data.items) {const r=draft.rows[item.item_id];if(r && decisions.has(r.decision) && typeof r.reason==="string" && r.reason.length<=2001)state.rows[item.item_id]={decision:r.decision,reason:r.reason};}
    }
  } catch {message("Draft unavailable. Resume from a new-round CSV.");}
  render();
})();
