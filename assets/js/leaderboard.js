/* ============================================================================
 * leaderboard.js | Live leaderboard page (UI only — data comes from HOA.lbApi)
 * ----------------------------------------------------------------------------
 * Public to read. Joining needs Google sign-in (HOA.auth.signIn); after that
 * every finished quiz updates the student's row from result.js.
 * Punjabi-first copy, re-rendered on the site's language switch (hoa:lang).
 * ========================================================================== */
(() => {
  "use strict";

  const HOA = window.HOA;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => HOA.esc(String(s == null ? "" : s));
  const fmt = (n) => (Number(n) || 0).toLocaleString("en-IN");

  const PERIODS = ["day", "week", "month", "all"];
  let period = PERIODS.includes((location.hash || "").slice(1)) ? location.hash.slice(1) : "day";
  let state = { status: "loading", rows: [], fetchedAt: 0 };
  let mine = null;
  let rankedN = null;
  let busy = false;
  let lastForce = 0;
  let myRowObserver = null;

  /* ---------------------------------------------------------- copy ----- */
  const pa = () => !HOA.lang || HOA.lang.get() !== "en";
  const t = (en, pun) => (pa() ? pun : en);

  const COPY = {
    lbLiveText: ["Live rankings", "ਲਾਈਵ ਰੈਂਕਿੰਗ"],
    lbTagline: [
      "Real scores from real Punjab Police and PSSSB aspirants. Every correct answer on the site earns points - sign in once and your name climbs the board automatically after each quiz.",
      "ਪੰਜਾਬ ਪੁਲਿਸ ਅਤੇ PSSSB ਦੀ ਤਿਆਰੀ ਕਰ ਰਹੇ ਅਸਲੀ ਵਿਦਿਆਰਥੀਆਂ ਦੇ ਅਸਲੀ ਸਕੋਰ। ਹਰ ਸਹੀ ਜਵਾਬ ਨਾਲ points ਮਿਲਦੇ ਹਨ - ਇੱਕ ਵਾਰ sign in ਕਰੋ, ਫਿਰ ਹਰ quiz ਤੋਂ ਬਾਅਦ ਤੁਹਾਡਾ ਨਾਮ ਆਪਣੇ ਆਪ ਉੱਪਰ ਚੜ੍ਹੇਗਾ।",
    ],
    lbSeasonLab: ["Season", "ਸੀਜ਼ਨ"],
    lbSumLab1: ["Students ranked", "ਰੈਂਕ ਵਿੱਚ ਵਿਦਿਆਰਥੀ"],
    lbSumLab2: ["Top score", "ਸਭ ਤੋਂ ਵੱਧ"],
    lbSumLab3: ["Your rank", "ਤੁਹਾਡਾ ਰੈਂਕ"],
    lbColName: ["Student", "ਵਿਦਿਆਰਥੀ"],
    lbColQ: ["Quizzes", "Quiz"],
    lbColAcc: ["Accuracy", "ਸ਼ੁੱਧਤਾ"],
    lbColPts: ["Points", "Points"],
    lbRulesTitle: ["How points work", "Points ਕਿਵੇਂ ਮਿਲਦੇ ਹਨ"],
  };
  const TABS = {
    day: ["Today", "ਅੱਜ"], week: ["This week", "ਇਸ ਹਫ਼ਤੇ"],
    month: ["This month", "ਇਸ ਮਹੀਨੇ"], all: ["All time", "ਹੁਣ ਤੱਕ"],
  };
  const RULES = [
    ["<b>+10</b> for every correct answer", "ਹਰ ਸਹੀ ਜਵਾਬ ਲਈ <b>+10</b>"],
    ["<b>+50</b> bonus for 100% on a set of 10 or more", "10 ਜਾਂ ਵੱਧ ਸਵਾਲਾਂ ਵਾਲੇ set ਵਿੱਚ 100% ਲਈ <b>+50</b> bonus"],
    ["Only your <b>best</b> score on a set counts - a retake adds just the improvement",
      "ਇੱਕ set ਦਾ ਸਿਰਫ਼ ਤੁਹਾਡਾ <b>ਸਭ ਤੋਂ ਵਧੀਆ</b> ਸਕੋਰ ਗਿਣਿਆ ਜਾਂਦਾ ਹੈ - ਦੁਬਾਰਾ ਦੇਣ 'ਤੇ ਸਿਰਫ਼ ਸੁਧਾਰ ਜੁੜਦਾ ਹੈ"],
    ["The <a href=\"quiz.html?mode=daily\">Daily Challenge</a> is a new set every day",
      "<a href=\"quiz.html?mode=daily\">Daily Challenge</a> ਹਰ ਰੋਜ਼ ਨਵਾਂ set ਹੁੰਦਾ ਹੈ"],
    ["Today resets at midnight (IST), the week on Monday, the month on the 1st",
      "ਅੱਜ ਦਾ ਬੋਰਡ ਰਾਤ 12 ਵਜੇ, ਹਫ਼ਤੇ ਦਾ ਸੋਮਵਾਰ ਨੂੰ ਅਤੇ ਮਹੀਨੇ ਦਾ 1 ਤਾਰੀਖ਼ ਨੂੰ ਨਵਾਂ ਸ਼ੁਰੂ ਹੁੰਦਾ ਹੈ"],
  ];
  const PA_MONTHS = ["ਜਨਵਰੀ", "ਫ਼ਰਵਰੀ", "ਮਾਰਚ", "ਅਪ੍ਰੈਲ", "ਮਈ", "ਜੂਨ", "ਜੁਲਾਈ", "ਅਗਸਤ", "ਸਤੰਬਰ", "ਅਕਤੂਬਰ", "ਨਵੰਬਰ", "ਦਸੰਬਰ"];
  const periodName = (p) => t(TABS[p][0].toLowerCase(), TABS[p][1]);

  function applyCopy() {
    Object.entries(COPY).forEach(([id, [en, pun]]) => {
      const el = $(id);
      if (el) { el.textContent = t(en, pun); el.lang = pa() ? "pa" : "en"; }
    });
    document.querySelectorAll(".lb2-tab").forEach((b) => {
      const [en, pun] = TABS[b.dataset.period];
      b.textContent = t(en, pun);
    });
    $("lbRulesList").innerHTML = RULES.map(([en, pun]) => `<li>${t(en, pun)}</li>`).join("");
    renderSeason();
  }

  /* -------------------------------------------------------- season ----- */
  function renderSeason() {
    const d = new Date(Date.now() + 330 * 60e3);           // IST calendar
    const y = d.getUTCFullYear(), m = d.getUTCMonth();
    const start = Date.UTC(y, m, 1), end = Date.UTC(y, m + 1, 1);
    const left = Math.max(1, Math.ceil((end - d) / 864e5));
    const pct = Math.round(((d - start) / (end - start)) * 100);
    const monthEn = new Date(start).toLocaleDateString("en-IN", { month: "long", timeZone: "UTC" });
    $("lbSeasonTitle").textContent = t(`${monthEn} ${y}`, `${PA_MONTHS[m]} ${y}`);
    $("lbSeasonFill").style.width = pct + "%";
    $("lbSeasonFoot").textContent = t(
      `${left} day${left === 1 ? "" : "s"} left - the month's No. 1 is announced on our Telegram channel.`,
      `${left} ਦਿਨ ਬਾਕੀ - ਮਹੀਨੇ ਦੇ No. 1 ਦਾ ਐਲਾਨ ਸਾਡੇ Telegram channel 'ਤੇ ਹੋਵੇਗਾ।`);
  }

  /* --------------------------------------------------------- avatar ---- */
  function avatar(row) {
    const g = HOA.game;
    const ini = g ? g.initials(row.name) : (row.name || "?").charAt(0);
    const hue = g ? g.hueFor(row.uid) : 240;
    const img = row.photo
      ? `<img src="${esc(row.photo)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`
      : "";
    return `<span class="lb2-av" style="--h:${hue}" aria-hidden="true">${esc(ini)}${img}</span>`;
  }
  const you = () => `<span class="lb2-you">${t("You", "ਤੁਸੀਂ")}</span>`;

  /* --------------------------------------------------------- podium ---- */
  function renderPodium(rows) {
    const box = $("lbPodium");
    if (!rows.length) { box.innerHTML = ""; return; }
    const medals = ["🥇", "🥈", "🥉"];
    box.innerHTML = [0, 1, 2].map((i) => {
      const r = rows[i];
      if (!r) {
        return `<div class="lb2-pod lb2-pod--${i + 1} lb2-pod--empty">
          <span class="lb2-pod__medal" aria-hidden="true">${medals[i]}</span>
          <span class="lb2-av" style="--h:230">?</span>
          <span class="lb2-pod__name">${t("Your spot?", "ਤੁਹਾਡੀ ਥਾਂ?")}</span>
          <span class="lb2-pod__meta">${t("Open", "ਖਾਲੀ")}</span></div>`;
      }
      return `<div class="lb2-pod lb2-pod--${i + 1}${r.isMe ? " is-me" : ""}">
        <span class="lb2-pod__medal" aria-hidden="true">${medals[i]}</span>
        ${avatar(r)}
        <span class="lb2-pod__name" title="${esc(r.name)}">${esc(r.name)}</span>
        <span class="lb2-pod__pts">${fmt(r.points)}<small>pts</small></span>
        <span class="lb2-pod__meta">${r.accuracy}% · ${r.quizzes} ${t("quiz", "quiz")}</span>
      </div>`;
    }).join("");
  }

  /* ---------------------------------------------------------- table ---- */
  function rowHTML(r, rank) {
    const sub = r.streak > 1
      ? `🔥 ${r.streak} ${t("day streak", "ਦਿਨ ਲਗਾਤਾਰ")}`
      : (r.lastQuiz ? esc(r.lastQuiz) : "");
    return `<div class="lb2-row${r.isMe ? " is-me" : ""}" role="row"${r.isMe ? ' id="lbMyRow"' : ""}>
      <span class="c-rank" role="cell">${rank}</span>
      <span class="c-name" role="cell">${avatar(r)}
        <span class="lb2-who"><b>${esc(r.name)}${r.isMe ? you() : ""}</b><small>${sub}</small></span></span>
      <span class="c-q" role="cell">${r.quizzes}</span>
      <span class="c-acc" role="cell"><span class="lb2-acc"><i style="--w:${r.accuracy}%"></i>${r.accuracy}%</span></span>
      <span class="c-pts" role="cell">${fmt(r.points)}</span>
    </div>`;
  }

  function renderTable(rows) {
    const rest = rows.slice(3);
    $("lbRows").innerHTML = rest.map((r, i) => rowHTML(r, i + 4)).join("");
    $("lbTable").classList.toggle("is-empty", !rest.length);
  }

  function skeleton() {
    $("lbPodium").innerHTML = "";
    $("lbTable").classList.remove("is-empty");
    $("lbRows").innerHTML = '<div class="lb2-sk"></div>'.repeat(6);
    $("lbState").hidden = true;
  }

  /* --------------------------------------------------------- states ---- */
  function renderState() {
    const box = $("lbState");
    const live = $("lbLive");
    live.classList.toggle("is-off", state.status !== "live");
    if (state.status === "unconfigured") {
      box.innerHTML = `<div class="lb2-state__art">🏁</div>
        <h2>${t("The live leaderboard is almost ready", "ਲਾਈਵ ਲੀਡਰਬੋਰਡ ਜਲਦੀ ਸ਼ੁਰੂ ਹੋ ਰਿਹਾ ਹੈ")}</h2>
        <p>${t("Keep practising - your progress is saved on this device in the meantime.",
          "ਤਿਆਰੀ ਜਾਰੀ ਰੱਖੋ - ਉਦੋਂ ਤੱਕ ਤੁਹਾਡੀ progress ਇਸ device 'ਤੇ save ਹੋ ਰਹੀ ਹੈ।")}</p>
        <div class="btn-row"><a class="btn btn-primary" href="quiz.html?mode=daily">${t("Start the Daily Challenge", "Daily Challenge ਸ਼ੁਰੂ ਕਰੋ")}</a></div>`;
    } else if (state.status === "offline") {
      box.innerHTML = `<div class="lb2-state__art">📡</div>
        <h2>${t("Couldn't load the rankings", "ਰੈਂਕਿੰਗ load ਨਹੀਂ ਹੋ ਸਕੀ")}</h2>
        <p>${t("Check your internet connection and tap Refresh.", "ਆਪਣਾ internet ਚੈੱਕ ਕਰੋ ਅਤੇ Refresh ਦਬਾਓ।")}</p>`;
    } else if (state.status === "live" && !state.rows.length) {
      box.innerHTML = `<div class="lb2-state__art">🏆</div>
        <h2>${t(`Nobody on ${periodName(period)}'s board yet`, `${periodName(period)} ਦੇ ਬੋਰਡ 'ਤੇ ਹਾਲੇ ਕੋਈ ਨਹੀਂ`)}</h2>
        <p>${t("Finish any quiz now and take the No. 1 spot.", "ਹੁਣੇ ਕੋਈ ਵੀ quiz ਪੂਰਾ ਕਰੋ ਅਤੇ No. 1 'ਤੇ ਆਓ।")}</p>
        <div class="btn-row"><a class="btn btn-primary" href="quiz.html?mode=daily">${t("Start the Daily Challenge", "Daily Challenge ਸ਼ੁਰੂ ਕਰੋ")}</a>
          <a class="btn" href="index.html#subjects">${t("Browse subjects", "ਵਿਸ਼ੇ ਦੇਖੋ")}</a></div>`;
    } else {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    $("lbPodium").innerHTML = "";
    $("lbTable").classList.add("is-empty");
  }

  /* -------------------------------------------------------- summary ---- */
  function renderSummary() {
    const rows = state.rows;
    $("lbSummary").hidden = state.status !== "live";
    $("lbSumRanked").textContent = rankedN != null ? fmt(rankedN)
      : rows.length >= HOA.lbApi.LIMIT ? `${HOA.lbApi.LIMIT}+` : fmt(rows.length);
    $("lbSumTop").textContent = rows.length ? fmt(rows[0].points) : "-";
    $("lbSumMe").textContent = mine && mine.rank ? `#${fmt(mine.rank)}`
      : mine && mine.row && mine.row.points ? `${HOA.lbApi.LIMIT}+` : "-";
  }

  /* -------------------------------------------------------- my card ---- */
  function renderMe() {
    const box = $("lbMe");
    if (state.status === "unconfigured") { box.innerHTML = ""; return; }
    const auth = HOA.auth;
    if (!auth || !auth.cloudEnabled()) {
      box.innerHTML = `<div class="lb2-me__join">
        <h2>${t("Put your name on the board", "ਬੋਰਡ 'ਤੇ ਆਪਣਾ ਨਾਮ ਲਿਆਓ")}</h2>
        <p>${t("Sign in once with Google. After that, every quiz you finish adds points to your row - nothing else to do.",
          "ਇੱਕ ਵਾਰ Google ਨਾਲ sign in ਕਰੋ। ਉਸ ਤੋਂ ਬਾਅਦ ਹਰ quiz ਦੇ points ਆਪਣੇ ਆਪ ਜੁੜਦੇ ਜਾਣਗੇ।")}</p>
        <ul class="lb2-me__perks">
          <li>${t("Free, takes 3 seconds", "Free, 3 ਸਕਿੰਟ ਲੱਗਦੇ ਹਨ")}</li>
          <li>${t("Only your name and photo are shown - never your email", "ਸਿਰਫ਼ ਨਾਮ ਅਤੇ photo ਦਿਖਦੀ ਹੈ - email ਕਦੇ ਨਹੀਂ")}</li>
          <li>${t("Your progress is saved across phone and laptop", "Phone ਅਤੇ laptop ਦੋਵਾਂ 'ਤੇ progress save")}</li>
        </ul>
        <button class="btn btn-google" type="button" id="lbJoin">${t("Continue with Google", "Google ਨਾਲ ਜਾਰੀ ਰੱਖੋ")}</button>
      </div>`;
      $("lbJoin").addEventListener("click", () => {
        auth.signIn().then((ok) => { if (ok) load(true); });
      });
      return;
    }
    const u = auth.user();
    const r = mine && mine.row;
    const head = `<div class="lb2-me__head">${avatar({ uid: u.uid, name: u.name, photo: u.photo })}
      <div><div class="lb2-me__name">${esc(u.name)}</div>
      <div class="lb2-me__sub">${t("Signed in with Google", "Google ਨਾਲ signed in")}</div></div></div>`;

    if (!r || !r.points) {
      box.innerHTML = `${head}
        <p class="lb2-me__note">${t(`You're not on ${periodName(period)}'s board yet. Finish any quiz and you're in.`,
          `ਤੁਸੀਂ ਹਾਲੇ ${periodName(period)} ਦੇ ਬੋਰਡ 'ਤੇ ਨਹੀਂ ਹੋ। ਕੋਈ ਵੀ quiz ਪੂਰਾ ਕਰੋ ਅਤੇ ਤੁਸੀਂ ਬੋਰਡ 'ਤੇ ਹੋਵੋਗੇ।`)}</p>
        <a class="btn btn-primary" href="quiz.html?mode=daily">${t("Take today's Daily Challenge", "ਅੱਜ ਦਾ Daily Challenge ਦਿਓ")}</a>`;
      return;
    }
    let note = "";
    if (mine.rank && mine.rank > 1 && state.rows[mine.rank - 2]) {
      const gap = state.rows[mine.rank - 2].points - r.points + 10;
      note = t(`${fmt(gap)} more points to overtake #${mine.rank - 1}.`,
        `#${mine.rank - 1} ਤੋਂ ਅੱਗੇ ਨਿਕਲਣ ਲਈ ${fmt(gap)} points ਹੋਰ।`);
    } else if (mine.rank === 1) {
      note = t("You're No. 1 - keep going to hold the spot!", "ਤੁਸੀਂ No. 1 ਹੋ - ਇਹ ਥਾਂ ਬਣਾਈ ਰੱਖੋ!");
    }
    box.innerHTML = `${head}
      <div class="lb2-me__rank"><b>${mine.rank ? "#" + fmt(mine.rank) : HOA.lbApi.LIMIT + "+"}</b>
        <span>${t(`rank ${periodName(period)}`, `${periodName(period)} ਦਾ ਰੈਂਕ`)}</span></div>
      <div class="lb2-me__grid">
        <div class="lb2-me__cell"><b>${fmt(r.points)}</b><span>Points</span></div>
        <div class="lb2-me__cell"><b>${r.quizzes}</b><span>Quiz</span></div>
        <div class="lb2-me__cell"><b>${r.accuracy}%</b><span>${t("Accuracy", "ਸ਼ੁੱਧਤਾ")}</span></div>
      </div>
      ${note ? `<p class="lb2-me__note">${note}</p>` : ""}
      <a class="btn btn-primary" href="quiz.html?mode=daily">${t("Earn more points", "ਹੋਰ points ਕਮਾਓ")}</a>`;
  }

  /* ----------------------------------------------------- mobile dock --- */
  function renderDock() {
    const dock = $("lbDock");
    if (myRowObserver) { myRowObserver.disconnect(); myRowObserver = null; }
    const r = mine && mine.row;
    if (!r || !r.points || (mine.rank && mine.rank <= 3)) { dock.hidden = true; return; }
    dock.innerHTML = `<b>${mine.rank ? "#" + fmt(mine.rank) : HOA.lbApi.LIMIT + "+"}</b>
      ${avatar(r)}<span>${t("You", "ਤੁਸੀਂ")}</span>
      <span class="lb2-dock__pts">${fmt(r.points)} pts</span>`;
    const row = $("lbMyRow");
    if (!row || !("IntersectionObserver" in window)) { dock.hidden = false; return; }
    myRowObserver = new IntersectionObserver(([e]) => { dock.hidden = e.isIntersecting; });
    myRowObserver.observe(row);
  }

  /* ---------------------------------------------------------- render --- */
  function render() {
    applyCopy();
    document.querySelectorAll(".lb2-tab").forEach((b) => {
      const on = b.dataset.period === period;
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
    });
    if (state.status === "loading") { skeleton(); renderMe(); return; }
    renderState();
    if (state.status === "live" && state.rows.length) {
      renderPodium(state.rows);
      renderTable(state.rows);
    }
    renderSummary();
    renderMe();
    renderDock();
    renderUpdated();
  }

  function renderUpdated() {
    const el = $("lbUpdated");
    if (!state.fetchedAt) { el.textContent = t("Refresh", "Refresh"); return; }
    const s = Math.round((Date.now() - state.fetchedAt) / 1000);
    el.textContent = s < 45 ? t("Updated just now", "ਹੁਣੇ update ਹੋਇਆ")
      : t(`Updated ${Math.round(s / 60)} min ago`, `${Math.round(s / 60)} ਮਿੰਟ ਪਹਿਲਾਂ update`);
  }

  /* ------------------------------------------------------------ load --- */
  async function load(force) {
    if (busy) return;
    busy = true;
    $("lbRefresh").classList.add("is-busy");
    if (!state.rows.length || force === "tab") { state = { ...state, status: "loading" }; render(); }
    const want = period;
    try {
      const res = await HOA.lbApi.board(want, { force: force === true });
      if (want !== period) return;                    // tab changed mid-flight
      state = res;
      mine = null; rankedN = null;
      if (res.status === "live") {
        [mine, rankedN] = await Promise.all([
          HOA.lbApi.mine(want, res.rows).catch(() => null),
          HOA.lbApi.ranked(want).catch(() => null),
        ]);
      }
    } finally {
      busy = false;
      $("lbRefresh").classList.remove("is-busy");
      if (want === period) render();
    }
  }

  /* ----------------------------------------------------------- wiring --- */
  $("lbTabs").addEventListener("click", (e) => {
    const b = e.target.closest(".lb2-tab");
    if (!b || b.dataset.period === period) return;
    period = b.dataset.period;
    history.replaceState(null, "", period === "day" ? location.pathname : `#${period}`);
    busy = false;
    load("tab");
  });
  $("lbTabs").addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const i = PERIODS.indexOf(period) + (e.key === "ArrowRight" ? 1 : -1);
    const next = PERIODS[(i + PERIODS.length) % PERIODS.length];
    document.querySelector(`.lb2-tab[data-period="${next}"]`).click();
    document.querySelector(`.lb2-tab[data-period="${next}"]`).focus();
  });
  $("lbRefresh").addEventListener("click", () => {
    if (Date.now() - lastForce < 10000) { load(false); return; }  // gentle on quota
    lastForce = Date.now();
    load(true);
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && state.fetchedAt && Date.now() - state.fetchedAt > 60000) load(false);
  });
  document.addEventListener("hoa:lang", () => render());
  setInterval(renderUpdated, 30000);

  render();
  Promise.resolve(HOA.auth && HOA.auth.ready).then(() => load(false));
})();
