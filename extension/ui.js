/* Creeping Hunger shared UI: used by the Firefox sidebar and the fallback web page. */
const CH = (() => {
  const LABELS = ["", "Not creepy", "A little creepy", "Somewhat creepy", "Very creepy", "Super creepy"];
  const FACES = ["", "😇", "🙂", "😬", "😱", "👹"];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const md = (s) => esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<i>$2</i>")
    .split(/\n/).map((l) => /^\s*#+\s/.test(l) ? `<p><b>${l.replace(/^\s*#+\s*/, "")}</b></p>` : /^\s*[-*•]\s+/.test(l) ? `<li>${l.replace(/^\s*[-*•]\s+/, "")}</li>` : (l.trim() ? `<p>${l}</p>` : "")).join("")
    .replace(/(<li>.*?<\/li>)+/gs, (m) => `<ul>${m}</ul>`);
  const usd = (n) => n ? "$" + Number(n).toFixed(n < 0.01 ? 5 : 4) : "";

  function chips(o, model) {
    o = o || {};
    const m = o["otari-model"] || model;
    const out = [];
    if (m) out.push(`<span class="chip model" title="Otari-Model">${esc(m)}</span>`);
    if (o["otari-provider"]) out.push(`<span class="chip" title="Otari-Provider">${esc(o["otari-provider"])}</span>`);
    const fb = o["otari-fallback"] === "true" || o.client_fallback;
    if (o["otari-fallback"] !== undefined || o.client_fallback !== undefined)
      out.push(`<span class="chip ${fb ? "warn" : ""}" title="Otari-Fallback">fallback: ${fb ? "yes" : "no"}</span>`);
    const att = o.client_attempts || o["otari-attempt-count"];
    if (att) out.push(`<span class="chip" title="Otari-Attempt-Count / client attempts">attempts: ${esc(att)}</span>`);
    if (Array.isArray(o["otari-guardrails"])) o["otari-guardrails"].forEach((g) =>
      out.push(`<span class="chip ${g.valid === false ? "bad" : ""}" title="Otari-Guardrails">guardrail ${esc(g.profile)}: ${esc(g.status)}${g.valid === false ? " ✗" : g.valid ? " ✓" : ""}</span>`));
    return out.join("");
  }

  function meter(score) {
    const segs = [1, 2, 3, 4, 5].map((i) => `<div class="seg s${i} ${score && i <= score ? "on" : ""}"></div>`).join("");
    return `<div class="meter">${segs}</div><div class="face">${score ? FACES[score] : "🤔"}</div>`;
  }

  function render(st) {
    const r = st.result;
    const steps = Object.values(st.steps).map((s) => `
      <li class="step ${s.status}">
        <div class="row"><span class="dot"></span><span class="t">${esc(s.title)}</span><span class="cost">${usd(s.cost_usd)}</span></div>
        <div class="chips">${chips(s.otari, s.model)}${s.via ? `<span class="chip">${esc(s.via)}</span>` : ""}${s.guard_mode ? `<span class="chip">guardrail via ${esc(s.guard_mode)}</span>` : ""}${s.mcp_mode ? `<span class="chip">MCP: ${esc(s.mcp_mode)}</span>` : ""}</div>
        ${s.detail ? `<div class="detail">${esc(s.detail)}</div>` : ""}
        ${s.url ? `<div class="detail"><a href="${esc(s.url)}" target="_blank">${esc(s.url)}</a></div>` : ""}
        ${s.evidence ? `<div class="detail bad">Evidence: “${esc(s.evidence)}”</div>` : ""}
        ${(s.tool_calls || []).length ? `<div class="detail">tools: ${s.tool_calls.map((c) => esc(c.name || c.type) + (c.status === "failed" ? " ✗" : " ✓")).join(", ")}</div>` : ""}
      </li>`).join("");
    const score = r?.score;
    const st7 = st.steps.compute?.data;
    const ex = r?.extraction || {};
    const rs = r?.research || {};
    return `
      ${st.error ? `<div class="error">${esc(st.error)}</div>` : ""}
      <section class="card verdict ${score ? "s" + score : ""}">
        ${meter(score)}
        <div class="label">${score ? `${score}/5 · ${esc(r.label || LABELS[score])}` : st.running ? "Sniffing around…" : "Ready when you are"}</div>
        ${r?.headline ? `<h2>${esc(r.headline)}</h2>` : ""}
        ${r?.warning_label ? `<div class="pni">⚠️ *Privacy Not Included</div>` : ""}
        ${r?.blocked ? `<div class="pni">🛡️ This page tried to give our AI orders. Blocked.</div>` : ""}
        <div class="body">${md(r?.verdict_md || st.stream.replace(/^[\s\S]*?---/, "") || "")}</div>
      </section>
      ${st.steps.read ? `<section class="card"><h3>How we got here <span class="total">${usd(st.total)} total</span></h3><ol class="steps">${steps}</ol>${st.endUser ? `<div class="chips"><span class="chip ${st.endUserOk ? "" : "warn"}" title="Otari user field">Otari user ${esc(st.endUser.slice(0, 22))}: ${st.endUserOk ? "per-user budget on" : "refused (needs service key)"}</span></div>` : ""}</section>` : ""}
      ${st7 && !st7.error ? `<section class="card"><h3>Fine print, by the numbers <span class="chip">Otari code execution</span></h3>
        <div class="stats"><div><b>${st7.reading_minutes}</b> min to read</div><div><b>${st7.fk_grade}</b> grade level</div>
        <div><b>${st7.clause_counts?.share ?? 0}</b> “share”</div><div><b>${st7.clause_counts?.third_party ?? 0}</b> “third party”</div>
        <div><b>${st7.clause_counts?.sell ?? 0}</b> “sell”</div><div><b>${st7.weasel_may_per_1k_words}</b> “may”/1k words</div></div>
        ${st7.diff_vs_archive ? `<p class="small">vs archived policy: ${Math.round(st7.diff_vs_archive.similarity * 100)}% similar, +${st7.diff_vs_archive.added_sentences} / −${st7.diff_vs_archive.removed_sentences} sentences</p>` : ""}</section>` : ""}
      ${r && !ex.blocked ? `<section class="card"><h3>What they collect</h3>
        <p class="small"><b>Sells data:</b> ${esc(ex.sells_data)} · <b>Ads sharing:</b> ${esc(ex.shares_for_ads)} · <b>AI training:</b> ${esc(ex.ai_training)}</p>
        ${(ex.red_flags || []).length ? `<p class="small"><b>Red flags</b></p><ul class="small">${ex.red_flags.slice(0, 6).map((x) => typeof x === "string" ? `<li>${esc(x)}</li>` : `<li>${esc(x.flag)}${x.quote ? `<br><q>${esc(x.quote)}</q>${x.quote_verified === false ? ` <span class="chip warn">paraphrase, not found verbatim</span>` : ""}` : ""}</li>`).join("")}</ul>` : ""}
        ${(ex.data_collected || []).length ? `<details class="small"><summary>Data collected (${ex.data_collected.length})</summary>${esc(ex.data_collected.join(", "))}</details>` : ""}</section>` : ""}
      ${r ? `<section class="card"><h3>Track record <span class="chip">MCP</span></h3>
        <p class="small"><b>Breaches:</b> ${(rs.breaches || []).length ? rs.breaches.map((b) => esc(`${b.name} (${b.date})`)).join(", ") : "none on record"}</p>
        <p class="small"><b>ToS;DR grade:</b> ${esc(rs.tosdr_grade || "n/a")}</p>
        <p class="small"><b>Old Mozilla PNI review:</b> ${rs.pni_found ? `${esc(rs.pni_people_voted || "")}${rs.pni_warning_label ? " · had the warning label" : ""}` : "none archived"}</p></section>` : ""}
      <p class="small disclaimer">Not legal advice. Not a current Mozilla *Privacy Not Included review. Archived PNI text can be out of date, and the score can be wrong.</p>
      ${(st.notes || []).length ? `<section class="card notes"><h3>Setup notes</h3><ul class="small">${st.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></section>` : ""}`;
  }

  function apply(st, e) {
    if (e.type === "step") { st.steps[e.id] = { ...(st.steps[e.id] || {}), ...e }; st.total = e.total_cost_usd; }
    else if (e.type === "token") st.stream += e.text;
    else if (e.type === "result") st.result = e;
    else if (e.type === "error") st.error = e.message;
    else if (e.type === "done") { st.notes = e.notes || []; st.total = e.total_cost_usd; st.endUser = e.end_user; st.endUserOk = e.end_user_accepted; }
  }

  function replay(events, root) {
    const st = { steps: {}, stream: "", total: 0, running: false, result: null, error: null, notes: [] };
    events.forEach((e) => apply(st, e));
    root.innerHTML = render(st);
  }

  async function run({ backend, url, page_text, page_html, install_id, force_fallback, root, button }) {
    const st = { steps: {}, stream: "", total: 0, running: true, result: null, error: null, notes: [] };
    const draw = () => (root.innerHTML = render(st));
    if (button) button.disabled = true;
    draw();
    try {
      const resp = await fetch(backend.replace(/\/$/, "") + "/api/review", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, page_text, page_html, install_id, force_fallback }),
      });
      if (!resp.ok) throw new Error(`Backend answered ${resp.status}`);
      const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await reader.read(); if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n\n")) >= 0) {
          const line = buf.slice(0, i); buf = buf.slice(i + 2);
          if (!line.startsWith("data: ")) continue;
          apply(st, JSON.parse(line.slice(6)));
          draw();
        }
      }
    } catch (err) { st.error = `Couldn't reach the Creeping Hunger backend (${err.message}). Is it running?`; }
    st.running = false; if (button) button.disabled = false; draw();
  }
  return { run, replay };
})();
