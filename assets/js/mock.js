// @ts-check
/* ============================================================================
 * mock.js | Mock Test page
 * Step 1 asks which exam the student is preparing for (one dropdown - short
 * on a phone, where most students practise). Step 2 shows that
 * paper's real pattern (data/mock-patterns.json): sections, questions per
 * section, time, marking and the easy/medium/hard mix, plus how many of its
 * questions are still NEW for this student (HOA.seen). quiz.js builds the
 * paper. "Custom mock" keeps the free builder (any subject, count, time).
 * Zero questions live in this file - everything is read from /questions.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc } = HOA;
  const $ = (id) => /** @type {any} */ (document.getElementById(id));
  const examWrap = $("mockExams");
  if (!examWrap) return;

  const [idx, cfg, hubs] = await Promise.all([
    HOA.loadIndex(),
    fetch("data/mock-patterns.json", { cache: "no-cache" }).then((r) => r.json()).catch(() => ({ exams: [] })),
    fetch("data/exam-hubs.json", { cache: "no-cache" }).then((r) => r.json()).catch(() => ({ exams: [] })),
  ]);
  /** guide slug (content/strategy) -> its exam page (data/exam-hubs.json) */
  const HUB_FILE = Object.fromEntries((hubs.exams || []).map((x) => [x.guide, x.file]));
  const SUBJECTS = idx.subjects || [];
  const exams = (cfg.exams || []).filter((e) => (e.papers || []).length);
  const startBtn = $("mockStart");
  const quickBtn = $("mockStartQuick"); // phones only (CSS), mirrors startBtn
  /** @param {boolean} off */
  const setStart = (off) => { startBtn.disabled = off; if (quickBtn) quickBtn.disabled = off; };
  const statusEl = $("mockStatus");
  const params = new URLSearchParams(location.search);

  /* -------------------------------------------- pool + freshness helpers */
  const expand = (list) =>
    (list || []).flatMap((x) => (String(x).startsWith("@") ? cfg[String(x).slice(1)] || [] : [x]));
  /** Topics a section draws from (same rule quiz.js uses). */
  const topicsFor = (sec) => {
    const inc = new Set(expand(sec.from));
    const exc = new Set(expand(sec.exclude));
    const out = [];
    for (const s of SUBJECTS) {
      for (const t of s.topics) {
        if (!t.available || !t.count) continue;
        const ids = [s.id, `${s.id}/${t.category || ""}`];
        if (ids.some((x) => inc.has(x)) && !ids.some((x) => exc.has(x))) out.push({ s, t });
      }
    }
    return out;
  };
  /** { total, fresh } question counts across every section of a paper. */
  const poolOf = (paper) => {
    const ranks = HOA.seen.ranks();
    const done = new Set();
    let total = 0, fresh = 0;
    (paper.sections || []).forEach((sec) => topicsFor(sec).forEach(({ s, t }) => {
      const k = s.id + "/" + t.id;
      if (done.has(k)) return;
      done.add(k);
      total += t.count;
      for (let n = 1; n <= t.count; n++) if (!ranks.has(HOA.seen.key(s.id, t.id, n))) fresh++;
    }));
    return { total, fresh };
  };
  const qCount = (paper) => (paper.sections || []).reduce((n, s) => n + (Number(s.questions) || 0), 0);
  const mixOf = (exam) => ({ ...(cfg.difficulty || {}), ...(exam.difficulty || {}) });

  /* --------------------------------------------------- Step 1: the exam */
  const remembered = HOA.db.get("mockExam", null) || {};
  let examId = params.get("exam") || remembered.exam || (exams[0] && exams[0].id) || "custom";
  if (examId !== "custom" && !exams.some((e) => e.id === examId)) examId = exams[0] ? exams[0].id : "custom";
  let paperId = params.get("paper") || remembered.paper || "";

  /** Dropdown group for an exam: the recruiting body, read from its name. */
  const groupOf = (e) =>
    /police/i.test(e.name) ? "Punjab Police · ਪੰਜਾਬ ਪੁਲਿਸ"
      : /^psssb/i.test(e.name) ? "PSSSB"
        : "PPSC";
  const groups = new Map();
  exams.forEach((e) => {
    const g = groupOf(e);
    groups.set(g, [...(groups.get(g) || []), e]);
  });
  examWrap.innerHTML =
    [...groups].map(([g, list]) => `<optgroup label="${esc(g)}">${
      list.map((e) => `<option value="${esc(e.id)}">${e.icon || "📝"} ${esc(e.name)}</option>`).join("")
    }</optgroup>`).join("") +
    `<optgroup label="Other · ਹੋਰ"><option value="custom">🛠️ Custom mock - choose subject, questions, time</option></optgroup>`;

  /* ------------------------------------------------ Step 2: the pattern */
  function render() {
    examWrap.value = examId;
    const custom = examId === "custom";
    const info = $("mockExamInfo");
    $("mockCustom").classList.toggle("hidden", !custom);
    $("mockPlanWrap").classList.toggle("hidden", custom);
    if (custom) {
      $("mockStep2Title").textContent = "Custom mock settings";
      info.innerHTML = `<span lang="pa">ਆਪਣਾ ਵਿਸ਼ਾ, ਸਵਾਲ ਅਤੇ ਸਮਾਂ ਚੁਣੋ</span>`;
      setStart(totalQ === 0);
      return;
    }
    const exam = exams.find((e) => e.id === examId);
    const paper = exam.papers.find((p) => p.id === paperId) || exam.papers[0];
    paperId = paper.id;
    $("mockStep2Title").textContent = `${exam.name} pattern`;
    const neg0 = Number(paper.negative) || 0;
    info.innerHTML = `<span lang="pa">${esc(exam.pa || "")}</span>` +
      `<span class="mock-exam-chips"><span class="badge badge-muted">${qCount(paper)} Q</span>` +
      `<span class="badge badge-muted">${paper.minutes} min</span>` +
      `<span class="badge badge-muted">${neg0 ? "−" + neg0 + " per wrong" : "No negative"}</span></span>`;

    // Paper picker (SI / Head Constable have two merit papers).
    $("mockPapers").innerHTML = exam.papers.length > 1
      ? exam.papers.map((p) => `
        <button type="button" class="btn ${p.id === paperId ? "btn-primary" : "btn-soft"}"
          data-paper="${esc(p.id)}">${esc(p.name)} · ${esc(p.pa || "")}</button>`).join("")
      : "";

    const mix = mixOf(exam);
    const neg = Number(paper.negative) || 0;
    const rows = paper.sections.map((s) => {
      const have = topicsFor(s).reduce((n, x) => n + x.t.count, 0);
      return `<tr>
        <td>${esc(s.name)}<span class="muted text-sm" style="display:block">${esc(s.pa || "")}${
          s.qualifying ? " · qualifying" : ""}</span></td>
        <td style="text-align:right;font-weight:700">${Number(s.questions) || 0}</td>
        <td style="text-align:right" class="muted text-sm">${have ? have + " in bank" : "⚠ none yet"}</td>
      </tr>`;
    }).join("");
    $("mockPlan").innerHTML = `
      <thead><tr><th>Section · ਹਿੱਸਾ</th><th style="text-align:right">Questions</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr><th>Total</th><th style="text-align:right">${qCount(paper)}</th><th></th></tr></tfoot>`;

    $("mockFacts").innerHTML = [
      `⏱ <b>${paper.minutes} min</b>`,
      `✅ <b>${paper.marks}</b> mark${paper.marks === 1 ? "" : "s"} per right answer`,
      neg ? `❌ <b>−${neg}</b> per wrong answer` : `No negative marking`,
      `🎯 Easy ${mix.easy}% · Medium ${mix.medium}% · Hard ${mix.hard}%`,
    ].map((x) => `<li>${x}</li>`).join("");

    const pool = poolOf(paper);
    const need = qCount(paper);
    $("mockFresh").innerHTML = pool.fresh >= need
      ? `✨ <b>${pool.fresh}</b> of ${pool.total} questions in this paper's bank are <b>new for you</b>. ` +
        `Every mock serves unseen questions first - no repeats.`
      : `You have seen almost every question in this bank (${pool.fresh} new of ${pool.total}). ` +
        `New questions come first; the rest are the ones you saw longest ago.`;
    const hub = exam.guide ? HUB_FILE[exam.guide] : "";
    $("mockGuide").innerHTML = hub
      ? `<a class="ilink" href="${esc(hub.replace(/\.html$/, ""))}">Official ${esc(exam.name)} syllabus &amp; pattern →</a>`
      : "";
    setStart(pool.total === 0);
  }

  examWrap.addEventListener("change", () => {
    examId = examWrap.value;
    paperId = "";
    render();
  });
  $("mockPapers").addEventListener("click", (e) => {
    const b = /** @type {HTMLElement} */ (e.target).closest("[data-paper]");
    if (!b) return;
    paperId = b.getAttribute("data-paper") || "";
    render();
  });
  $("mockResetSeen")?.addEventListener("click", () => {
    if (!confirm("Start fresh? Every question will count as new again.")) return;
    HOA.seen.clear();
    render();
  });

  /* ------------------------------------------- Custom mock (free builder) */
  const subjects = SUBJECTS.map((s) => ({
    ...s,
    qCount: s.topics.filter((t) => t.available).reduce((n, t) => n + t.count, 0),
  }));
  const totalQ = subjects.reduce((n, s) => n + s.qCount, 0);
  const subjWrap = $("mockSubjects");
  subjWrap.innerHTML =
    `<option value="all" selected>📘 All subjects - mixed mock (${totalQ} Q)</option>` +
    subjects.map((s) => `<option value="${esc(s.id)}" ${s.qCount ? "" : "disabled"}>${s.icon} ${esc(s.name)} (${
      s.qCount ? s.qCount + " Q" : "empty"})</option>`).join("");

  statusEl.textContent = totalQ
    ? `${totalQ} questions in the bank · ${HOA.seen.count()} already served to you.`
    : "No questions available yet.";

  /* ------------------------------------------- Sign-in (asked, optional) */
  async function renderAccount() {
    const box = $("mockAccount");
    if (!box) return;
    const auth = HOA.auth;
    if (!auth || auth.mode === "off") { box.classList.add("hidden"); return; }
    await auth.ready;
    if (auth.signedIn()) {
      const u = auth.user() || {};
      box.innerHTML = `✅ Signed in${u.name ? " as <b>" + esc(u.name) + "</b>" : ""} - your score goes to your dashboard and the leaderboard.`;
      return;
    }
    box.innerHTML = `
      <p class="text-sm" style="margin-bottom:8px"><b>Sign in to save this mock</b> to your dashboard and the leaderboard.
      <span class="muted">ਸਾਈਨ ਇਨ ਕਰੋ ਤਾਂ ਜੋ ਤੁਹਾਡਾ ਨਤੀਜਾ ਸੇਵ ਹੋਵੇ।</span></p>
      <button type="button" class="btn btn-soft btn-block" id="mockSignIn">Continue with Google</button>
      <p class="muted text-sm mt-1">Or just press Start - guests can take every mock.</p>`;
    $("mockSignIn").addEventListener("click", async () => {
      await auth.signIn();
      renderAccount();
    });
  }
  renderAccount();

  render();

  /* --------------------------------------------------------- Start ------- */
  const start = async () => {
    // Anonymous-first: ensure() only blocks when auth.gateQuizzes is on.
    const ok = !HOA.auth || (await HOA.auth.ensure());
    if (!ok) return;
    if (examId === "custom") {
      const subject = subjWrap.value || "all";
      location.href = `quiz.html?mode=mock&subject=${encodeURIComponent(subject)}` +
        `&count=${$("mockCount").value}&minutes=${$("mockMinutes").value}&pattern=${$("mockMix").value || "exam"}`;
      return;
    }
    HOA.db.set("mockExam", { exam: examId, paper: paperId });
    HOA.db.remove("mockPaper"); // a new attempt always draws a new paper
    location.href = `quiz.html?mode=mock&exam=${encodeURIComponent(examId)}` +
      `&paper=${encodeURIComponent(paperId)}&t=${Date.now()}`;
  };
  startBtn.addEventListener("click", start);
  quickBtn?.addEventListener("click", start);
})();
