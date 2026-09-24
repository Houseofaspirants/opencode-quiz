/* ============================================================================
 * bookmarks.js | Saved (bookmarked) questions - stored locally on device
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc } = HOA;
  const wrap = document.getElementById("bookmarkList");
  const empty = document.getElementById("bmEmpty");
  const countEl = document.getElementById("bmCount");
  const clearBtn = document.getElementById("bmClear");

  function render() {
    const list = HOA.bookmarks.all();
    countEl.textContent = list.length;
    clearBtn.classList.toggle("hidden", !list.length);

    if (!list.length) {
      wrap.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");

    wrap.innerHTML = list
      .map(
        (b) => `
      <article class="card bookmark-card" data-key="${esc(b.key)}">
        <div class="bm-head">
          <span class="badge">${esc(b.subjectName || "Quiz")}</span>
          <span class="badge badge-muted">${esc(b.topicName || "")}</span>
          <button class="btn btn-sm btn-danger" data-remove="${esc(b.key)}" style="margin-left:auto">Remove</button>
        </div>
        <p class="bm-q">${b.id ? `<b>Q${b.id}.</b> ` : ""}${esc(b.q)}</p>
        <div class="bm-actions">
          <button class="btn btn-sm btn-soft" data-reveal>Show answer</button>
          <a class="btn btn-sm" href="${esc(b.href || "#")}">Open quiz</a>
        </div>
        <div class="bm-answer">
          <div class="review-ans">
            <div class="ans-line ok"><span class="tag">Correct</span><span>${esc(
              b.correctText ?? "—"
            )}</span></div>
            ${
              b.explanation
                ? `<div class="review-note"><b>Explanation:</b> ${esc(b.explanation)}</div>`
                : ""
            }
            ${
              b.reference
                ? `<p class="review-ref"><b>Reference:</b> ${esc(b.reference)}</p>`
                : ""
            }
          </div>
        </div>
      </article>`
      )
      .join("");
  }

  wrap.addEventListener("click", (e) => {
    const rm = e.target.closest("[data-remove]");
    if (rm) {
      HOA.bookmarks.remove(rm.dataset.remove);
      HOA.toast("Bookmark removed");
      render();
      return;
    }
    const rev = e.target.closest("[data-reveal]");
    if (rev) {
      const box = rev.closest(".bookmark-card").querySelector(".bm-answer");
      const shown = box.classList.toggle("show");
      rev.textContent = shown ? "Hide answer" : "Show answer";
    }
  });

  clearBtn?.addEventListener("click", () => {
    if (confirm("Remove all bookmarks from this device?")) {
      HOA.bookmarks.clear();
      HOA.toast("All bookmarks cleared");
      render();
    }
  });

  render();
})();
