// @ts-check
/* ============================================================================
 * rank2.js | Rank 2 Blueprint — proof state
 * ----------------------------------------------------------------------------
 * The gallery itself lives in proof.js so the homepage and this page share one
 * implementation. All this file decides is what a reader sees when there are
 * no scans to show: a trust page that sits on an empty spinner is worse than
 * one that says plainly what it can and cannot prove today.
 * ========================================================================== */
(async () => {
  "use strict";
  const pending = document.getElementById("proofPending");
  if (!pending) return;

  let found = [];
  try {
    found = await (window.HOA && window.HOA.proof ? window.HOA.proof : []);
  } catch {
    found = [];
  }

  /* Scans exist → proof.js has already revealed the gallery. They do not →
     say so honestly instead of leaving a skeleton in the answer-sheets block. */
  if (!found.length) pending.hidden = false;
})();
