/* ============================================================================
 * leaderboard.js | Global Leaderboard page controller
 * ----------------------------------------------------------------------------
 * Components (one function each, all pure render + one shared state):
 *   StatsCards · SeasonCard · LeaderboardTabs · Filters · SearchBar
 *   SkeletonLoader · LeaderboardCard · MyRankCard · ProfileModal · QuizBoards
 *
 * Data comes exclusively from HOA.lbApi (assets/js/leaderboard-api.js), which
 * picks the backend. This file never touches a database.
 *
 * Existing behaviour is untouched: HOA.leaderboard (core.js) and
 * HOA.auth.syncResult (auth.js) still record every attempt exactly as before;
 * the global board is a read-side only.
 * ========================================================================== */
(() => {
  "use strict";

  const { esc, fmtTime, countUp } = HOA;
  const game = HOA.game;
  const api = HOA.lbApi;

  const $ = (id) => document.getElementById(id);
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  const isPhone = () => window.matchMedia("(max-width: 767px)").matches;

  /* ------------------------------------------------------------- STATE --- */
  const state = {
    period: "day",
    exam: "all",
    category: "all",
    sort: "score",
    search: "",
    page: 1,
    entries: [],
    total: 0,
    hasMore: false,
    loading: false,
    seq: 0,
    firstPaint: true,
  };

  const MEDALS = { 1: "🥇", 2: "🥈", 3: "🥉" };
  const PERIOD_LABEL = { day: "today", week: "this week", month: "this month", all: "all time" };

  /* rAF is throttled (and may never run) in a backgrounded tab — so every
   * animated value is written to the DOM FIRST and only then animated. A
   * stuck "0" on a real phone is worse than a missed count-up. */
  const fmt = (v) => (Number(v) || 0).toLocaleString("en-IN");

  function animNum(el, value, suffix) {
    const final = fmt(value) + (suffix || "");
    el.textContent = final;
    if (!reduce.matches && document.visibilityState === "visible") countUp(el, Number(value) || 0, suffix || "");
  }

  function growTo(el, pct) {
    const p = Math.max(0, Math.min(100, Number(pct) || 0));
    if (reduce.matches || document.visibilityState !== "visible") { el.style.width = p + "%"; return; }
    el.style.width = "0%";
    requestAnimationFrame(() => { el.style.width = p + "%"; });
  }

  /* ================================================= STATS CARDS ========= */
  const StatsCards = {
    render(s) {
      const cards = [
        { ico: "👨‍🎓", v: s.students, lab: "Total Students" },
        { ico: "📝", v: s.attempts, lab: "Total Quiz Attempts" },
        { ico: "🏆", v: s.highestToday, suf: "%", lab: "Highest Score Today" },
        { ico: "⭐", v: s.accuracy, suf: "%", lab: "Average Accuracy" },
        { ico: "🔥", v: s.activeToday, lab: "Active Students Today", wide: true },
      ];
      const nodes = $("lbStats").querySelectorAll(".lb-stat");
      cards.forEach((c, i) => {
        const node = nodes[i];
        if (!node) return;
        node.className = "lb-stat" + (c.wide ? " lb-stat--wide" : "");
        node.innerHTML =
          `<span class="lb-stat__ico" aria-hidden="true">${c.ico}</span>` +
          `<b class="lb-stat__num">0</b>` +
          `<span class="lb-stat__lab">${c.lab}</span>`;
        const num = node.querySelector(".lb-stat__num");
        animNum(num, c.v, c.suf || "");
      });
    },
  };

  /* ================================================== SEASON CARD ======== */
  const SeasonCard = {
    render() {
      const s = game.season();
      $("lbSeasonTitle").textContent = s.label;
      $("lbSeasonEnds").textContent = `Ends in ${s.endsInDays} Day${s.endsInDays === 1 ? "" : "s"}`;
      $("lbSeasonFoot").textContent =
        `Runs ${s.startedOn} – ${s.endsOn}. Top performers earn exclusive recognition.`;
      const fill = $("lbSeasonFill");
      growTo(fill, s.progressPct);
    },
  };

  /* ============================================ LEADERBOARD TABS ========= */
  const LeaderboardTabs = {
    tabs: [],
    ink: null,
    init() {
      this.tabs = [...document.querySelectorAll(".lb-tab")];
      this.ink = $("lbTabsInk");
      this.tabs.forEach((t) => {
        t.addEventListener("click", () => this.select(t));
        t.addEventListener("keydown", (e) => {
          const i = this.tabs.indexOf(t);
          let n = -1;
          if (e.key === "ArrowRight") n = (i + 1) % this.tabs.length;
          if (e.key === "ArrowLeft") n = (i - 1 + this.tabs.length) % this.tabs.length;
          if (e.key === "Home") n = 0;
          if (e.key === "End") n = this.tabs.length - 1;
          if (n >= 0) { e.preventDefault(); this.tabs[n].focus(); this.select(this.tabs[n]); }
        });
      });
      window.addEventListener("resize", () => this.moveInk());
      this.moveInk();
    },
    select(btn) {
      this.tabs.forEach((t) => {
        const on = t === btn;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
      });
      this.moveInk();
      state.period = btn.dataset.period;
      state.page = 1;
      state.entries = [];
      refresh({ skeleton: true });
    },
    moveInk() {
      const active = this.tabs.find((t) => t.getAttribute("aria-selected") === "true");
      if (!active || !this.ink) return;
      const box = active.getBoundingClientRect();
      const host = active.parentElement.getBoundingClientRect();
      if (!box.width) return;
      this.ink.style.width = box.width + "px";
      this.ink.style.transform = `translateX(${box.left - host.left}px)`;
      // keep the active tab in view when the strip scrolls
      active.scrollIntoView({ block: "nearest", inline: "nearest",
        behavior: reduce.matches ? "auto" : "smooth" });
    },
  };

  /* ==================================================== FILTERS ========== */
  const Filters = {
    init() {
      this.renderExams();
      this.renderCategories();
      $("lbSort").addEventListener("change", (e) => {
        state.sort = e.target.value;
        state.page = 1;
        refresh({ skeleton: true });
      });
    },
    chips(host, items, key) {
      host.innerHTML = items
        .map((it) =>
          `<button type="button" class="lb-chip" data-val="${esc(it.id)}" ` +
          `aria-pressed="${state[key] === it.id ? "true" : "false"}">${esc(it.label)}</button>`)
        .join("");
      host.querySelectorAll(".lb-chip").forEach((c) =>
        c.addEventListener("click", () => {
          state[key] = c.dataset.val;
          host.querySelectorAll(".lb-chip").forEach((o) =>
            o.setAttribute("aria-pressed", o === c ? "true" : "false"));
          c.scrollIntoView({ block: "nearest", inline: "nearest",
            behavior: reduce.matches ? "auto" : "smooth" });
          state.page = 1;
          refresh({ skeleton: true });
        })
      );
    },
    renderExams() {
      const tax = api.taxonomy;
      const items = (tax && tax.examFilters) || [{ id: "all", label: "All Exams" }];
      this.chips($("lbExamChips"), items, "exam");
    },
    renderCategories() {
      const tax = api.taxonomy;
      const items = (tax && tax.categoryFilters) || [{ id: "all", label: "All Categories" }];
      this.chips($("lbCatChips"), items, "category");
    },
  };

  /* ==================================================== SEARCH BAR ======= */
  const SearchBar = {
    timer: null,
    init() {
      const input = $("lbSearch");
      const clear = $("lbSearchClear");
      input.addEventListener("input", () => {
        clear.hidden = !input.value;
        clearTimeout(this.timer);
        this.timer = setTimeout(() => {
          state.search = input.value.trim();
          state.page = 1;
          refresh({ skeleton: true });
        }, 220);
      });
      clear.addEventListener("click", () => {
        input.value = "";
        clear.hidden = true;
        input.focus();
        state.search = "";
        state.page = 1;
        refresh({ skeleton: true });
      });
    },
  };

  /* ================================================= SKELETON LOADER ====== */
  const SkeletonLoader = {
    show() {
      $("lbSkeleton").hidden = false;
      $("lbList").hidden = true;
      $("lbEmpty").classList.remove("is-on");
    },
    hide() {
      $("lbSkeleton").hidden = true;
      $("lbList").hidden = false;
    },
  };

  /* ================================================= EMPTY STATE ========== */
  const EmptyState = {
    set(on, msg) {
      const box = $("lbEmpty");
      box.classList.toggle("is-on", !!on);
      if (on) {
        const p = box.querySelector("p");
        p.textContent = msg || "Be the first to complete today's quiz.";
        $("lbList").hidden = true;
        $("lbMoreWrap").hidden = true;
      }
    },
  };

  /* =============================================== LEADERBOARD CARD ====== */
  const LeaderboardCard = {
    avatar(e, cls) {
      const hue = game.hueFor(e.userId);
      const style = `background:linear-gradient(135deg,hsl(${hue} 70% 58%),hsl(${(hue + 42) % 360} 72% 46%))`;
      const inner = e.profilePhoto
        ? `<img src="${esc(e.profilePhoto)}" alt="" width="44" height="44" loading="lazy">`
        : esc(game.initials(e.name));
      return `<span class="lb-avatar ${cls || ""}" style="${style}" aria-hidden="true">${inner}</span>`;
    },

    statChips(e) {
      const chips = [
        `<span class="lb-ms lb-ms--score">🎯 <b>${e.score}/${e.totalQuestions}</b></span>`,
        `<span class="lb-ms">📈 <b>${e.accuracy}%</b></span>`,
        e.timeTaken ? `<span class="lb-ms">⏱ <b>${fmtTime(e.timeTaken)}</b></span>` : "",
        `<span class="lb-ms lb-ms--streak">🔥 <b>${e.streak}</b> day${e.streak === 1 ? "" : "s"}</span>`,
        `<span class="lb-ms lb-ms--quiz">📝 <span>${esc(e.quizName)}</span></span>`,
      ];
      return chips.join("");
    },

    badgesHTML(e) {
      const list = (e.badges || []).filter((b) => b && b.earned);
      if (!list.length) {
        return `<span class="lb-kv__k">Badges</span><span class="lb-kv__v">None yet — keep practising</span>`;
      }
      return (
        `<span class="lb-kv__k">Badges</span>` +
        `<span class="lb-badges" style="margin-top:6px">` +
        list.map((b) => `<span class="lb-badge" title="${esc(b.desc)}">${b.icon} ${esc(b.name)}</span>`).join("") +
        `</span>`
      );
    },

    kv(k, v) {
      return `<div class="lb-kv"><span class="lb-kv__k">${k}</span><span class="lb-kv__v">${v}</span></div>`;
    },

    row(e) {
      const medal = MEDALS[e.rank];
      const cls = ["lb-row"];
      if (e.rank <= 3) cls.push(`lb-row--${e.rank}`);
      if (e.isMe) cls.push("is-me");
      const date = e.attemptDate
        ? new Date(e.attemptDate).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
        : "—";
      const earned = (e.badges || []).filter((b) => b && b.earned).length;

      return `<li class="${cls.join(" ")}" data-uid="${esc(e.userId)}" data-rank="${e.rank}">
        <div class="lb-row__main">
          <span class="lb-rank" aria-label="Rank ${e.rank}">${medal || e.rank}</span>

          <div class="lb-who">
            ${this.avatar(e)}
            <span class="lb-who__txt">
              <button type="button" class="lb-who__name" data-profile="${esc(e.userId)}">
                <span>${esc(e.name)}</span>${e.verified ? '<i class="lb-verified" title="Verified account">✔</i>' : ""}
                ${earned
                  ? `<i class="lb-sub__b" title="${earned} badge${earned === 1 ? "" : "s"} earned">🏅${earned}</i>`
                  : ""}
              </button>
              <span class="lb-who__sub">
                <i class="lb-sub__u">@${esc(e.username)}</i>
                <span class="lb-sub__m"><b>Lv ${e.level}</b> · ${game.fmtInt(e.xp)} XP · ${date}</span>
                <i class="lb-sub__d">${date}</i>
                ${e.isMe ? '<span class="lb-you">You</span>' : ""}
              </span>
            </span>
          </div>

          <div class="lb-xp">
            <span class="lb-xp__lvl">Lv ${e.level}</span>
            <b class="lb-xp__val">${game.fmtInt(e.xp)}</b>
            <span class="lb-xp__lab">XP</span>
          </div>

          <div class="lb-stats-row">${this.statChips(e)}</div>

          <button type="button" class="lb-toggle" aria-expanded="false"
                  aria-label="Show details for ${esc(e.name)}">▾</button>
        </div>

        <div class="lb-detail">
          <div class="lb-detail__grid">
            ${this.kv("Rank", `#${e.rank}`)}
            ${this.kv("Level", e.level)}
            ${this.kv("XP", game.fmtInt(e.xp))}
            ${this.kv("Score", `${e.score}/${e.totalQuestions}`)}
            ${this.kv("Accuracy", `${e.accuracy}%`)}
            ${this.kv("Time Taken", e.timeTaken ? fmtTime(e.timeTaken) : "—")}
            ${this.kv("Quiz", esc(e.quizName))}
            ${this.kv("Current Streak", `${e.streak} day${e.streak === 1 ? "" : "s"}`)}
            ${this.kv("Attempt Date", date)}
            <div class="lb-kv lb-kv--full">${this.badgesHTML(e)}</div>
          </div>
        </div>
      </li>`;
    },

    /** FLIP: rows that already existed glide to their new rank. */
    render(entries) {
      const list = $("lbList");
      const first = new Map();
      if (!state.firstPaint && !reduce.matches) {
        list.querySelectorAll(".lb-row").forEach((n) =>
          first.set(n.dataset.uid, n.getBoundingClientRect().top));
      }
      const html = entries.map((e) => this.row(e)).join("");
      if (state.firstPaint) {
        list.innerHTML = html;
        if (!reduce.matches) list.querySelectorAll(".lb-row").forEach((n) => n.classList.add("is-enter"));
        state.firstPaint = false;
      } else {
        list.innerHTML = html;
        if (!reduce.matches && first.size) {
          list.querySelectorAll(".lb-row").forEach((n) => {
            const prev = first.get(n.dataset.uid);
            if (prev == null) return;
            const dy = prev - n.getBoundingClientRect().top;
            if (!dy) return;
            n.style.transition = "none";
            n.style.transform = `translateY(${dy}px)`;
            requestAnimationFrame(() => {
              n.style.transition = "transform .42s cubic-bezier(.22,1,.36,1)";
              n.style.transform = "";
            });
          });
        }
      }
      bindRowInteractions();
    },
  };

  function bindRowInteractions() {
    $("lbList").querySelectorAll(".lb-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const row = btn.closest(".lb-row");
        const open = row.classList.toggle("is-open");
        btn.setAttribute("aria-expanded", open ? "true" : "false");
      });
    });
    $("lbList").querySelectorAll("[data-profile]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const entry = state.entries.find((e) => e.userId === btn.dataset.profile);
        if (entry) ProfileModal.open(entry, btn);
      });
    });
  }

  /* ================================================== MY RANK CARD ======= */
  const MyRankCard = {
    async render() {
      const me = await api.myRank({ period: state.period, sort: state.sort });
      const side = $("lbSide");
      if (!me || !me.rank) {
        $("lbMyRankVal").textContent = "—";
        $("lbMyRankOf").textContent = "Complete a quiz to appear";
        $("lbMyXp").textContent = "0";
        $("lbMyFoot").textContent =
          "Finish your first quiz and your rank, XP and percentile appear here.";
        side.hidden = false;
        return;
      }
      $("lbMyRankVal").textContent = "#" + game.fmtInt(me.rank);
      $("lbMyRankOf").textContent = `of ${game.fmtInt(me.total)} students`;
      animNum($("lbMyXp"), me.xp);
      $("lbMyLevel").textContent = me.progress.level;
      $("lbMyPct").textContent = me.percentile + "%";

      const p = me.progress;
      const lab = p.maxed
        ? "Max level reached"
        : `${game.fmtInt(p.have)} / ${game.fmtInt(p.need)} XP to Level ${p.level + 1}`;
      $("lbMyProgLab").textContent = lab;
      $("lbMyProgPct").textContent = Math.round(p.pct) + "%";
      const track = $("lbMyTrack");
      track.setAttribute("aria-valuenow", String(Math.round(p.pct)));
      const fill = $("lbMyFill");
      growTo(fill, p.pct);

      $("lbMyFoot").textContent = me.nextRank && me.nextRank.gap > 0
        ? `Need ${game.fmtInt(me.nextRank.gap)} more XP to reach rank #${me.nextRank.rank}.`
        : "You are at the top — hold that streak.";
      side.hidden = false;
    },
  };

  /* ================================================== PROFILE MODAL ======= */
  const ProfileModal = {
    lastFocus: null,
    open(entry, trigger) {
      const modal = $("lbModal");
      this.lastFocus = trigger || document.activeElement;
      modal.hidden = false;
      document.documentElement.classList.add("lb-locked");
      this.render({ loading: true, entry });
      api.profile(entry)
        .then((p) => this.render({ profile: p, entry }))
        .catch((e) => {
          console.warn("[leaderboard] profile failed:", e && e.message);
          this.render({ profile: null, entry });
        });
      $("lbModalX").focus();
      document.addEventListener("keydown", this.onKey);
    },
    close() {
      const modal = $("lbModal");
      if (modal.hidden) return;
      modal.hidden = true;
      document.documentElement.classList.remove("lb-locked");
      document.removeEventListener("keydown", this.onKey);
      if (this.lastFocus && this.lastFocus.focus) this.lastFocus.focus();
    },
    onKey(e) {
      if (e.key === "Escape") { ProfileModal.close(); return; }
      if (e.key !== "Tab") return;
      const panel = $("lbModalPanel");
      const f = [...panel.querySelectorAll(
        'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])')]
        .filter((n) => n.offsetParent !== null);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    },

    kv(k, v) {
      return `<div class="lb-kv"><span class="lb-kv__k">${k}</span><span class="lb-kv__v">${v}</span></div>`;
    },

    render({ profile, entry }) {
      const e = profile || entry;
      const avatarHost = $("lbModalAvatar");
      const hue = game.hueFor(e.userId);
      avatarHost.style.background =
        `linear-gradient(135deg,hsl(${hue} 70% 58%),hsl(${(hue + 42) % 360} 72% 46%))`;
      avatarHost.innerHTML = e.photo
        ? `<img src="${esc(e.photo)}" alt="" width="78" height="78">`
        : esc(game.initials(e.name));

      $("lbModalName").innerHTML =
        esc(e.name) + (e.verified ? '<i class="lb-verified" title="Verified account">✔</i>' : "");
      $("lbModalHandle").textContent = "@" + e.username;

      const chips = [];
      if (e.rank) chips.push(`<span class="badge">🏅 Rank #${game.fmtInt(e.rank)}</span>`);
      chips.push(`<span class="badge">⭐ Level ${e.level || 1}</span>`);
      chips.push(`<span class="badge">🔥 ${e.streak || 0} day streak</span>`);
      if (e.isMe) chips.push(`<span class="badge">You</span>`);
      $("lbModalChips").innerHTML = chips.join("");

      if (!profile) {
        $("lbModalBody").innerHTML =
          `<div class="lb-modal__sec"><div class="lb-modal__h">Profile</div>` +
          `<p class="muted text-sm">Full statistics for this student are unavailable right now. ` +
          `Try again in a moment.</p></div>`;
        return;
      }

      const p = profile.progress;
      const badges = (profile.badges || []);
      const recent = profile.recent || [];

      $("lbModalBody").innerHTML = `
        <div class="lb-modal__sec">
          <div class="lb-modal__h">Level progress</div>
          <div class="lb-modal__prog">
            <div class="lb-my__prog-lab">
              <span>${p.maxed ? "Max level reached"
                : `${game.fmtInt(p.have)} / ${game.fmtInt(p.need)} XP to Level ${p.level + 1}`}</span>
              <span>${Math.round(p.pct)}%</span>
            </div>
            <div class="lb-track" role="progressbar" aria-valuemin="0" aria-valuemax="100"
                 aria-valuenow="${Math.round(p.pct)}">
              <span class="lb-track__fill" style="width:${p.pct}%"></span>
            </div>
          </div>
        </div>

        <div class="lb-modal__sec">
          <div class="lb-modal__h">Statistics</div>
          <div class="lb-modal__grid">
            ${this.kv("Current Rank", profile.rank ? "#" + game.fmtInt(profile.rank) : "—")}
            ${this.kv("Total XP", game.fmtInt(profile.xp))}
            ${this.kv("Accuracy", profile.accuracy + "%")}
            ${this.kv("Total Tests", game.fmtInt(profile.totalTests))}
            ${this.kv("Correct Answers", game.fmtInt(profile.correct))}
            ${this.kv("Wrong Answers", game.fmtInt(profile.wrong))}
            ${this.kv("Average Time", profile.avgTime ? fmtTime(profile.avgTime) : "—")}
            ${this.kv("Current Streak", profile.streak + " day" + (profile.streak === 1 ? "" : "s"))}
            ${this.kv("Longest Streak", profile.longestStreak + " day" + (profile.longestStreak === 1 ? "" : "s"))}
            ${profile.percentile ? this.kv("Percentile", profile.percentile + "%") : ""}
          </div>
        </div>

        <div class="lb-modal__sec">
          <div class="lb-modal__h">Badges</div>
          <div class="lb-badges">
            ${badges.length
              ? badges.map((b, i) =>
                  `<span class="lb-badge ${b.earned ? "lb-badge--new" : "lb-badge--off"}" ` +
                  `style="animation-delay:${i * 70}ms" title="${esc(b.desc)}">${b.icon} ${esc(b.name)}</span>`)
                .join("")
              : '<span class="muted text-sm">No badges yet.</span>'}
          </div>
        </div>

        <div class="lb-modal__sec">
          <div class="lb-modal__h">Recent Quiz History</div>
          ${recent.length
            ? `<ul class="lb-hist">${recent.map((r) => `
                <li>
                  <span class="lb-hist__n">${esc(r.quizName)}</span>
                  <span class="lb-hist__s">${r.correct}/${r.total} · ${r.accuracy}%</span>
                  <span class="lb-hist__t">${r.at
                    ? new Date(r.at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
                    : (r.seconds ? fmtTime(r.seconds) : "")}</span>
                </li>`).join("")}</ul>`
            : '<p class="muted text-sm">No attempts recorded yet.</p>'}
        </div>`;
    },
  };

  /* ================================================== QUIZ BOARDS ======== */
  const QuizBoards = {
    render(list) {
      const host = $("lbQuizBoards");
      if (!list.length) {
        host.innerHTML =
          `<div class="card card-pad lb-qcard"><div class="empty-state" style="border:0;padding:0">` +
          `<div class="lb-empty__art" aria-hidden="true">📝</div>` +
          `<h2>No quiz boards yet.</h2><p>Complete a quiz and its own leaderboard appears here.</p>` +
          `<div class="btn-row mt-3" style="justify-content:center">` +
          `<a class="btn btn-primary" href="quiz.html?mode=daily">Start a quiz</a></div></div></div>`;
        return;
      }
      host.innerHTML = list
        .map((b) => `
          <div class="card lb-qcard">
            <div class="lb-qcard__top">
              <span class="lb-qcard__name">${esc(b.quizName)}</span>
              <span class="lb-qcard__n">${game.fmtInt(b.total)} players</span>
            </div>
            ${b.entries.length
              ? `<ol class="lb-podium">${b.entries.map((e, i) => `
                  <li>
                    <span class="lb-podium__m" aria-hidden="true">${MEDALS[i + 1] || i + 1}</span>
                    <span class="lb-podium__n">${esc(e.name)}</span>
                    <span class="lb-podium__s">${e.score}/${e.totalQuestions} · ${e.accuracy}%</span>
                  </li>`).join("")}</ol>`
              : '<div class="lb-qcard__empty">No attempts in this period yet.</div>'}
          </div>`)
        .join("");
    },
  };

  /* ================================================= SOURCE DISCLOSURE ==== */
  function renderSource() {
    const n = api.notice;
    const box = $("lbSource");
    const map = {
      live: { cls: "lb-source lb-source--live", ico: "🌐" },
      sample: { cls: "lb-source lb-source--sample", ico: "🧪" },
      local: { cls: "lb-source", ico: "📱" },
    };
    const m = map[n.kind] || map.local;
    box.className = m.cls;
    const label = { live: "Global rankings", sample: "Sample rankings", local: "This device" };
    box.textContent = `${m.ico} ${label[n.kind] || label.local}`;

    const notice = $("lbNotice");
    const dismissed = HOA.db.get("lbNoticeDismissed", "");
    if (n.kind !== "live" && dismissed !== n.kind) {
      $("lbNoticeText").textContent = n.text;
      notice.classList.remove("hidden");
    } else {
      notice.classList.add("hidden");
    }
  }

  /* ==================================================== REFRESH ========== */
  async function refresh({ skeleton = false, append = false } = {}) {
    const seq = ++state.seq;
    state.loading = true;
    if (skeleton && !append) SkeletonLoader.show();

    try {
      const res = await api.list({
        period: state.period, exam: state.exam, category: state.category,
        sort: state.sort, search: state.search, page: state.page,
      });
      if (seq !== state.seq) return; // stale — a newer request already won

      state.entries = append ? state.entries.concat(res.entries) : res.entries;
      state.total = res.total;
      state.hasMore = res.hasMore;

      SkeletonLoader.hide();
      EmptyState.set(!state.entries.length,
        state.search
          ? `No student matches “${state.search}”. Try a different name.`
          : `Be the first to complete today's quiz.`);

      if (state.entries.length) {
        LeaderboardCard.render(state.entries);
        $("lbCount").textContent =
          `${game.fmtInt(state.total)} student${state.total === 1 ? "" : "s"} · showing ${PERIOD_LABEL[state.period]}`;
      } else {
        $("lbList").innerHTML = "";
        $("lbCount").textContent = "";
      }

      $("lbMoreWrap").hidden = !(state.hasMore && state.entries.length);
      renderSource();
    } catch (err) {
      console.error("[leaderboard] render failed:", err);
      SkeletonLoader.hide();
      EmptyState.set(true, "Rankings could not be loaded. Please try again.");
    } finally {
      if (seq === state.seq) state.loading = false;
    }
  }

  async function loadMore() {
    if (state.loading || !state.hasMore) return;
    state.page += 1;
    await refresh({ append: true });
  }

  async function loadExtras() {
    try {
      const [s, boards] = await Promise.all([
        api.stats({ period: state.period }),
        api.quizBoards({ period: state.period }),
      ]);
      StatsCards.render(s || {});
      QuizBoards.render(boards || []);
    } catch (err) {
      console.warn("[leaderboard] extras failed:", err);
    }
  }

  /* ======================================================= INIT ========== */
  function init() {
    if (!api || !game) {
      console.error("[leaderboard] gamification/api layer missing");
      return;
    }

    SeasonCard.render();
    LeaderboardTabs.init();
    SearchBar.init();

    api.init()
      .then(() => {
        Filters.init();
        refresh({ skeleton: true });
        loadExtras();
        MyRankCard.render();
      })
      .catch((err) => {
        console.error("[leaderboard] boot failed:", err);
        SkeletonLoader.hide();
        EmptyState.set(true, "Rankings could not be loaded. Please try again.");
      });

    // Infinite scroll (falls back to the visible "Load more" button).
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver(
        (entries) => {
          if (entries.some((e) => e.isIntersecting)) loadMore();
        },
        { rootMargin: "400px 0px" }
      );
      io.observe($("lbSentinel"));
    }
    $("lbMore").addEventListener("click", loadMore);

    // Modal wiring
    $("lbModalX").addEventListener("click", () => ProfileModal.close());
    $("lbModal").addEventListener("click", (e) => {
      if (e.target === $("lbModal")) ProfileModal.close();
    });

    // Notice dismissal
    $("lbNoticeX").addEventListener("click", () => {
      $("lbNotice").classList.add("hidden");
      HOA.db.set("lbNoticeDismissed", api.source);
    });

    // Re-rank when the cloud session changes (sign-in / sign-out).
    if (HOA.auth && typeof HOA.auth.cloudEnabled === "function") {
      window.addEventListener("storage", () => refresh({ skeleton: true }));
    }

    // Recompute the tab pill on breakpoint changes (the strip re-flows).
    window.addEventListener("resize", () => LeaderboardTabs.moveInk());
    document.fonts && document.fonts.ready
      ? document.fonts.ready.then(() => LeaderboardTabs.moveInk())
      : LeaderboardTabs.moveInk();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
