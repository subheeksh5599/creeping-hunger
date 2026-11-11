(async () => {
  const store = browser.storage.local;
  let { installId, backend } = await store.get(["installId", "backend"]);
  if (!installId) { installId = crypto.randomUUID(); await store.set({ installId }); }
  const bEl = document.getElementById("backend");
  if (backend) bEl.value = backend;
  bEl.addEventListener("change", () => store.set({ backend: bEl.value.trim() }));

  // Highlights a quote in the open tab; if it isn't there, opens the policy at a text fragment and highlights it there.
  function highlight(quote) {
    const words = quote.split(/\s+/).filter(Boolean);
    for (const q of [quote, words.slice(0, 10).join(" "), words.slice(0, 6).join(" ")]) {
      getSelection().removeAllRanges();
      if (!q || !window.find(q, false, false, true, false, false, false)) continue;
      const range = getSelection().getRangeAt(0);
      const mark = document.createElement("mark");
      mark.style.cssText = "background:#ffe14d;color:#000;outline:3px solid #ff5a1f";
      try { range.surroundContents(mark); getSelection().removeAllRanges(); mark.scrollIntoView({ block: "center" }); }
      catch { range.startContainer.parentElement?.scrollIntoView({ block: "center" }); }
      return true;
    }
    return false;
  }
  const highlightIn = async (tabId, quote) => {
    try { const [res] = await browser.scripting.executeScript({ target: { tabId }, func: highlight, args: [quote] }); return res.result; }
    catch { return false; }
  };
  document.addEventListener("click", async (ev) => {
    const a = ev.target.closest("a.onpage");
    if (!a) return;
    ev.preventDefault();
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    if (await highlightIn(tab.id, a.dataset.quote)) { a.textContent = "Highlighted on this page"; return; }
    const opened = await browser.tabs.create({ url: a.href });
    const done = (id, info) => {
      if (id !== opened.id || info.status !== "complete") return;
      browser.tabs.onUpdated.removeListener(done);
      highlightIn(id, a.dataset.quote);
    };
    browser.tabs.onUpdated.addListener(done);
    a.textContent = "Opened the policy with the quote highlighted";
  });

  document.getElementById("go").addEventListener("click", async () => {
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    let page_text = null, page_html = null;
    try {
      const [res] = await browser.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => ({ text: document.body.innerText.slice(0, 60000), html: document.documentElement.outerHTML.slice(0, 400000) }),
      });
      page_text = res.result.text; page_html = res.result.html;
    } catch (e) { /* privileged page: backend will fetch it */ }
    CH.run({
      backend: bEl.value.trim(), url: tab.url, page_text, page_html, install_id: installId,
      force_fallback: document.getElementById("fallback").checked,
      root: document.getElementById("app"), button: document.getElementById("go"),
    });
  });
})();
