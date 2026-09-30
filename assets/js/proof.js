// @ts-check
/* ============================================================================
 * proof.js | Proof of achievement — shared by the homepage and the blueprint
 * ----------------------------------------------------------------------------
 * One gallery, two pages. Extracted from home.js so the Rank 2 Blueprint can
 * show the same scans without the code existing twice.
 *
 * Every entry is probed with a HEAD request, so a scan that has not been
 * added yet costs a few hundred bytes instead of a downloaded 404 body. A card
 * is built only for a file that really exists on disk — if none do, the
 * section keeps its `hidden` attribute and the page claims nothing.
 *
 * To switch it on, drop the scans into assets/img/proof/ under these names
 * (edit title/note here if you would rather word them differently).
 *
 * `window.HOA.proof` resolves to the list that was found, so a page can react
 * when there is nothing to show — the blueprint uses it to replace a skeleton
 * with an honest note rather than leaving a spinner on a trust page.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc } = HOA;

  const PROOF_ITEMS = [
    { file: "official-result.jpg", title: "Official Result",
      note: "Final result of the Punjab Police Sub-Inspector examination." },
    { file: "official-merit-list.jpg", title: "Official Merit List",
      note: "Provisional merit list carrying the rank and the marks." },
    { file: "answer-sheet-1.jpg", title: "Answer Sheet 1",
      note: "Scanned answer sheet for paper 1." },
    { file: "answer-sheet-2.jpg", title: "Answer Sheet 2",
      note: "Scanned answer sheet for paper 2." },
    { file: "training-photos.jpg", title: "Training Photos",
      note: "Training photographs from the academy." },
    { file: "appointment-letter.jpg", title: "Appointment Letter",
      note: "Issue of appointment letter." },
  ];

  HOA.proof = Promise.resolve([]);

  const proofSection = document.getElementById("proofSection");
  const proofGrid = document.getElementById("proofGrid");
  const proofLb = document.getElementById("proofLightbox");
  if (!proofSection || !proofGrid || !proofLb) return;

  const base = "assets/img/proof/";
  const exists = await Promise.all(
    PROOF_ITEMS.map((it) =>
      fetch(base + it.file, { method: "HEAD" })
        .then((r) => r.ok)
        .catch(() => false)
    )
  );
  const found = PROOF_ITEMS.filter((_, i) => exists[i]);
  HOA.proof = Promise.resolve(found);

  if (!found.length) return;

  proofGrid.innerHTML = found
    .map(
      (it) => `
    <button class="proof-card" type="button"
            data-src="${base}${it.file}" data-title="${esc(it.title)}"
            data-note="${esc(it.note)}">
      <span class="proof-thumb">
        <img src="${base}${it.file}" alt="${esc(it.title)}" width="800" height="600" loading="lazy" decoding="async">
        <span class="proof-zoom">Click to enlarge</span>
      </span>
      <h3>${esc(it.title)}</h3>
      <p>${esc(it.note)}</p>
    </button>`
    )
    .join("");
  proofSection.hidden = false;

  /* getElementById types these as HTMLElement; the lightbox's image needs the
     HTMLImageElement surface (src, alt, naturalWidth), so narrow it here
     rather than sprinkling casts through the handler below. */
  const lbImg = /** @type {HTMLImageElement | null} */ (
    document.getElementById("proofLbImg")
  );
  const lbCap = document.getElementById("proofLbCap");
  const lbClose = document.getElementById("proofClose");
  const closeLb = () => {
    proofLb.hidden = true;
    document.documentElement.style.overflow = "";
  };

  proofGrid.addEventListener("click", (e) => {
    const card = /** @type {HTMLElement | null} */ (
      /** @type {Element} */ (e.target).closest(".proof-card")
    );
    if (!card || !lbImg || !lbCap) return;
    lbImg.src = card.dataset.src || "";
    lbImg.alt = card.dataset.title || "";
    /* The HTML width/height are a placeholder ratio; correct them to the real
       ones so object-fit never letterboxes a portrait scan. */
    const sync = () => {
      if (lbImg.naturalWidth) {
        lbImg.width = lbImg.naturalWidth;
        lbImg.height = lbImg.naturalHeight;
      }
    };
    if (lbImg.complete) sync();
    else lbImg.addEventListener("load", sync, { once: true });
    lbCap.textContent = `${card.dataset.title} — ${card.dataset.note}`;
    proofLb.hidden = false;
    document.documentElement.style.overflow = "hidden";
    lbClose?.focus();
  });
  lbClose?.addEventListener("click", closeLb);
  /* Click the backdrop (not the figure) or Escape to dismiss. */
  proofLb.addEventListener("click", (e) => {
    if (e.target === proofLb) closeLb();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !proofLb.hidden) closeLb();
  });
})();
