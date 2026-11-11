(async () => {
  const store = browser.storage.local;
  let { installId, backend } = await store.get(["installId", "backend"]);
  if (!installId) { installId = crypto.randomUUID(); await store.set({ installId }); }
  const bEl = document.getElementById("backend");
  if (backend) bEl.value = backend;
  bEl.addEventListener("change", () => store.set({ backend: bEl.value.trim() }));

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
