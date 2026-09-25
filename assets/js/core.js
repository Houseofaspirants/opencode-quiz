/* ============================================================================
 * core.js | House of Aspirants Quiz Portal
 * ----------------------------------------------------------------------------
 * Shared, dependency-free core:
 *   1.  Storage layer        (namespaced localStorage + safe fallback)
 *   2.  Data layer           (auto-detected index + JSON question loader)
 *   3.  Theme                (dark / light toggle, persisted)
 *   4.  Navigation           (dropdown, mobile drawer, active state)
 *   5.  Instant search       (subjects + topics, Ctrl+K)
 *   6.  UI helpers           (toast, count-up, reveal, back-to-top)
 *   7.  Student features     (bookmarks, progress, achievements, leaderboard)
 *   8.  PWA                  (service-worker registration + install button)
 *
 * Every student feature talks to `HOA.db` only, so a future backend
 * (Firebase / Supabase / Node+Express) can replace one file without
 * touching the UI code.
 * ========================================================================== */

const HOA = (() => {
  "use strict";

  /* ======================================================== 1. STORAGE ==== */
  const PREFIX = "hoa:";
  const memory = new Map(); // fallback when localStorage is blocked

  const db = {
    get(key, fallback = null) {
      try {
        const raw = localStorage.getItem(PREFIX + key);
        return raw === null ? fallback : JSON.parse(raw);
      } catch {
        return memory.has(key) ? memory.get(key) : fallback;
      }
    },
    set(key, value) {
      memory.set(key, value);
      try {
        localStorage.setItem(PREFIX + key, JSON.stringify(value));
      } catch {
        /* private mode: keep in-memory for this session */
      }
    },
    remove(key) {
      memory.delete(key);
      try {
        localStorage.removeItem(PREFIX + key);
      } catch { /* ignore */ }
    },
  };

  /* ====================================================== 2. DATA LAYER === */
  let indexPromise = null;

  /** Loads data/index.json once and caches it for the whole session. */
  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch("data/index.json", { cache: "no-cache" })
        .then((r) => {
          if (!r.ok) throw new Error("index " + r.status);
          return r.json();
        })
        .then((idx) => {
          // Keep a copy for instant offline boot.
          db.set("indexCache", idx);
          return idx;
        })
        .catch((err) => {
          console.warn("[HOA] index.json unavailable, using cache:", err.message);
          const cached = db.get("indexCache");
          if (cached) return cached;
          return { stats: {}, subjects: [], site: {} };
        });
    }
    return indexPromise;
  }

  /** Fetches one topic JSON file (one quiz) and normalises its questions. */
  async function loadQuestions(file) {
    const res = await fetch(file, { cache: "no-cache" });
    if (!res.ok) throw new Error("Cannot load " + file);
    const data = await res.json();
    const raw = Array.isArray(data) ? data : data.questions || data.mcqs || data.quiz || [];
    const meta = Array.isArray(data) ? {} : data;
    return { meta, questions: normalizeQuestions(raw) };
  }

  /**
   * Accepts many authoring styles so adding MCQs stays beginner friendly:
   *   correct: 0 | "A" | "a" | exact option text
   *   keys: q/question, options/opts, correct/answer/key
   */
  function normalizeQuestions(list) {
    if (!Array.isArray(list)) return [];
    return list.map((item, i) => {
      const q = { ...(item || {}) };
      const text = q.q ?? q.question ?? "";
      const options = q.options ?? q.opts ?? [];
      let correct = q.correct ?? q.answer ?? q.key ?? null;

      if (typeof correct === "string") {
        const letter = correct.trim().toUpperCase().charCodeAt(0) - 65;
        if (/^[A-Z]$/i.test(correct.trim()) && letter < options.length) {
          correct = letter;                       // "B" -> 1
        } else {
          const idx = options.findIndex(
            (o) => String(o).trim().toLowerCase() === correct.trim().toLowerCase()
          );
          correct = idx;                          // exact text -> index
        }
      }
      return {
        id: i + 1,
        q: String(text),
        options: options.map(String),
        correct: Number.isInteger(correct) && correct >= 0 ? correct : null,
        explanation: q.explanation || q.solution || "",   // only shown if present
        reference: q.reference || q.ref || "",            // only shown if present
        difficulty: q.difficulty || "",
        topic: q.topic || "",
        subject: q.subject || "",
      };
    });
  }

  /* ========================================================== 3. THEME ==== */
  const THEME_KEY = "theme";
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = t === "dark" ? "#0b1020" : "#4f46e5";
    document.querySelectorAll("[data-theme-icon]").forEach((el) => {
      el.textContent = t === "dark" ? "☀️" : "🌙";
    });
  }
  function initTheme() {
    const saved = db.get(THEME_KEY);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(saved || (prefersDark ? "dark" : "light"));
    document.addEventListener("click", (e) => {
      if (e.target.closest("[data-action='toggle-theme']")) {
        const next =
          document.documentElement.getAttribute("data-theme") === "dark"
            ? "light"
            : "dark";
        db.set(THEME_KEY, next);
        applyTheme(next);
        toast(next === "dark" ? "Dark mode on 🌙" : "Light mode on ☀️");
      }
    });
  }

  /* ============================================ 3b. SHARED PAGE CHROME ====
   * One source of truth for <header>, mobile drawer, search modal and footer.
   * Pages just render <div data-site-header></div> / <div data-site-footer></div>,
   * so navigation edits happen in exactly one file.
   * ======================================================================= */
  const SUBJECT_LINKS = [
    ["gk", "🏛️", "General Knowledge"],
    ["quant", "➗", "Quantitative Aptitude"],
    ["reasoning", "🧠", "Reasoning"],
    ["punjabi", "ਸ", "Punjabi"],
    ["english", "Aa", "English"],
    ["computer", "💻", "Computer"],
    ["current-affairs", "📰", "Current Affairs"],
  ];

  function renderChrome() {
    const head = document.querySelector("[data-site-header]");
    if (head) head.innerHTML = HEADER_HTML();
    const foot = document.querySelector("[data-site-footer]");
    if (foot) foot.innerHTML = FOOTER_HTML();
  }

  const HEADER_HTML = () => `
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="index.html" aria-label="House of Aspirants Quiz Portal - go to home">
        <img class="brand-logo" src="assets/img/logo-sm.png" width="38" height="38" alt="House of Aspirants logo" title="House of Aspirants" decoding="async">
        <span class="brand-name">House of Aspirants <span class="brand-sub">Quiz Portal</span></span>
      </a>

      <nav class="main-nav" aria-label="Primary">
        <ul class="nav-list">
          <li><a class="nav-link" data-nav="home" href="index.html">Home</a></li>
          <li class="nav-drop" data-nav-drop>
            <button class="nav-link nav-drop-btn" aria-haspopup="true" aria-expanded="false">
              Subjects
              <svg class="nav-caret" width="12" height="12" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
            </button>
            <div class="nav-drop-menu" data-subject-list>
              ${SUBJECT_LINKS.map(
                ([id, icon, name]) =>
                  `<a data-nav="${id}" href="subject.html?subject=${id}">${icon} ${name}</a>`
              ).join("")}
            </div>
          </li>
          <li><a class="nav-link" data-nav="daily" href="quiz.html?mode=daily">Daily Quiz</a></li>
          <li><a class="nav-link" data-nav="mock" href="mock.html">Mock Tests</a></li>
          <li><a class="nav-link" data-nav="bookmarks" href="bookmarks.html">Bookmarks</a></li>
          <li><a class="nav-link" data-nav="about" href="about.html">About</a></li>
          <li><a class="nav-link" data-nav="contact" href="contact.html">Contact</a></li>
        </ul>
      </nav>

      <div class="header-actions">
        <button class="icon-btn" data-action="open-search" aria-label="Search (Ctrl+K)">🔍</button>
        <button class="icon-btn" data-action="toggle-theme" aria-label="Toggle dark mode">
          <span data-theme-icon>🌙</span>
        </button>
        <a class="icon-btn auth-chip hidden" id="authChip" href="progress.html" title="Your account" aria-label="Your account">
          <span class="auth-chip-face" id="authChipFace">?</span>
        </a>
        <button class="btn btn-sm btn-soft install-bar hidden" data-action="install-app">⬇ Install</button>
        <a class="btn btn-sm btn-telegram" href="https://t.me/HouseOfAspirant" target="_blank" rel="noopener">✈ Telegram</a>
        <button class="icon-btn menu-toggle" data-action="open-menu" aria-label="Open menu" aria-expanded="false">☰</button>
      </div>
    </div>
  </header>

  <div class="mobile-menu" id="mobileMenu">
    <div class="mm-head">
      <span class="mm-title">🏠 House of Aspirants</span>
      <button class="icon-btn" data-action="close-menu" aria-label="Close menu">✕</button>
    </div>
    <a class="mm-link" data-nav="home" href="index.html">🏠 Home</a>

    <p class="mm-group">Subjects</p>
    <div data-subject-list>
      ${SUBJECT_LINKS.map(
        ([id, icon, name]) =>
          `<a class="mm-link" data-nav="${id}" href="subject.html?subject=${id}"><span class="mm-emoji">${icon}</span> ${name}</a>`
      ).join("")}
    </div>
    <a class="mm-link" href="subject.html?subject=gk&amp;category=punjab-gk"><span class="mm-emoji">📌</span> Punjab GK</a>

    <p class="mm-group">Practice</p>
    <a class="mm-link" data-nav="daily" href="quiz.html?mode=daily">📅 Daily Quiz</a>
    <a class="mm-link" data-nav="mock" href="mock.html">🧪 Mock Tests</a>
    <a class="mm-link" data-nav="bookmarks" href="bookmarks.html">★ Bookmarks</a>
    <a class="mm-link" data-nav="progress" href="progress.html">📊 My Progress</a>
    <a class="mm-link" data-nav="leaderboard" href="leaderboard.html">🏆 Leaderboard</a>

    <p class="mm-group">More</p>
    <a class="mm-link" data-nav="about" href="about.html">ℹ️ About</a>
    <a class="mm-link" data-nav="articles" href="articles.html">📚 Study Guides</a>
    <a class="mm-link" data-nav="contact" href="contact.html">✉️ Contact</a>
    <button class="mm-link" data-action="toggle-theme"><span data-theme-icon>🌙</span> Toggle theme</button>
    <button class="mm-link" data-action="install-app">⬇ Install App</button>
    <a class="mm-link mm-tg" href="https://t.me/HouseOfAspirant" target="_blank" rel="noopener">✈ Join Telegram</a>
  </div>

  <div class="search-overlay hidden" id="searchOverlay" role="dialog" aria-label="Search">
    <div class="search-panel">
      <div class="search-box">
        <span aria-hidden="true">🔍</span>
        <input id="searchInput" type="search" placeholder="Search subjects and topics…"
               autocomplete="off" aria-label="Search subjects and topics">
        <span class="kbd">Ctrl K</span>
        <button class="icon-btn" data-action="close-search" aria-label="Close search">✕</button>
      </div>
      <div class="search-results" id="searchResults"></div>
    </div>
  </div>`;

  const FOOTER_HTML = () => `
  <footer class="site-footer">
    <div class="container">
      <div class="footer-grid">
        <div class="footer-brand">
          <a class="brand" href="index.html">
            <img class="brand-logo" src="assets/img/logo-sm.png" width="38" height="38" alt="" title="House of Aspirants" loading="lazy" decoding="async">
            <span class="brand-name">House of Aspirants<span class="brand-sub">Quiz Portal</span></span>
          </a>
          <p>Practice Daily. Crack Punjab Police. A free, fast and offline-ready MCQ portal for
             Punjab Police, PSSSB and competitive exam aspirants.</p>
          <div class="social-row">
            <a class="social-link" href="https://t.me/HouseOfAspirant" target="_blank" rel="noopener">✈ Telegram</a>
            <a class="social-link" href="https://instagram.com/si.gurpreetsingh.pp" target="_blank" rel="noopener">📸 Instagram</a>
            <a class="social-link" href="https://youtube.com/@houseofaspirants-y5s" target="_blank" rel="noopener">▶ YouTube</a>
          </div>
        </div>

        <div class="footer-col">
          <h2>Practice</h2>
          <a href="quiz.html?mode=daily">Daily Quiz</a>
          <a href="mock.html">Mock Tests</a>
          <a href="subject.html?subject=gk">Previous Year Questions</a>
          <a href="subject.html?subject=current-affairs">Expected MCQs</a>
          <a href="bookmarks.html">Bookmarks</a>
          <a href="progress.html">My Progress</a>
          <a href="leaderboard.html">Leaderboard</a>
        </div>

        <div class="footer-col">
          <h2>Subjects</h2>
          <a href="index.html#subjects">All Subjects</a>
          <a href="subject.html?subject=gk&amp;category=punjab-gk">📌 Punjab GK</a>
          ${SUBJECT_LINKS.map(
            ([id, , name]) => `<a href="subject.html?subject=${id}">${name}</a>`
          ).join("")}
        </div>

        <div class="footer-col">
          <h2>Company</h2>
          <a href="about.html">About</a>
          <a href="articles.html">Study Guides</a>
          <a href="contact.html">Contact</a>
          <a href="https://t.me/HouseOfAspirant" target="_blank" rel="noopener">Join Telegram</a>
          <a href="privacy.html">Privacy Policy</a>
          <a href="terms.html">Terms of Use</a>
        </div>
      </div>

      <div class="footer-bottom">
        <span>© <span data-year>2026</span> House of Aspirants. All rights reserved.</span>
        <nav aria-label="Legal">
          <a href="privacy.html">Privacy</a>
          <a href="terms.html">Terms</a>
          <a href="contact.html">Contact</a>
        </nav>
      </div>
    </div>
  </footer>

  <button class="icon-btn to-top" id="toTop" aria-label="Back to top">⬆</button>
  <div class="toast-wrap"></div>`;

  /* ==================================================== 4. NAVIGATION ===== */
  function initNav() {
    const body = document.body;
    const page = body.dataset.page || "";

    // --- Desktop subject dropdown -----------------------------------------
    const drop = document.querySelector("[data-nav-drop]");
    if (drop) {
      const btn = drop.querySelector(".nav-drop-btn");
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const open = drop.classList.toggle("open");
        btn.setAttribute("aria-expanded", String(open));
      });
      document.addEventListener("click", (e) => {
        if (!drop.contains(e.target)) {
          drop.classList.remove("open");
          btn.setAttribute("aria-expanded", "false");
        }
      });
    }

    // --- Mobile drawer -----------------------------------------------------
    const drawer = document.getElementById("mobileMenu");
    const openBtn = document.querySelector("[data-action='open-menu']");
    const closeBtn = document.querySelector("[data-action='close-menu']");
    const setDrawer = (open) => {
      if (!drawer) return;
      drawer.classList.toggle("open", open);
      document.body.style.overflow = open ? "hidden" : "";
      openBtn?.setAttribute("aria-expanded", String(open));
    };
    openBtn?.addEventListener("click", () => setDrawer(true));
    closeBtn?.addEventListener("click", () => setDrawer(false));
    drawer?.addEventListener("click", (e) => {
      if (e.target.closest("a")) setDrawer(false);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") setDrawer(false);
    });

    // --- Active state ------------------------------------------------------
    // Subject pages read ?subject=… so the right menu item highlights.
    const subjectId = page === "subject"
      ? new URLSearchParams(location.search).get("subject") || ""
      : "";
    if (subjectId) body.dataset.subject = subjectId;

    const mark = (el) => el && el.classList.add("is-active");
    // Highlight by page key (home, daily, mock…) and by subject key
    // (static subject links carry data-nav="gk" etc.).
    const keys = [page, subjectId].filter(Boolean);
    keys.forEach((k) =>
      document.querySelectorAll(`[data-nav="${k}"], [data-nav-subject="${k}"]`).forEach(mark)
    );

    // Append dynamically detected subjects (new folders in /questions) to both
    // menus. Static entries from SUBJECT_LINKS are deduped by their href.
    loadIndex().then((idx) => {
      document.querySelectorAll("[data-subject-list]").forEach((list) => {
        const isMobile = !!list.closest(".mobile-menu");
        (idx.subjects || []).forEach((s) => {
          const href = `subject.html?subject=${encodeURIComponent(s.id)}`;
          if (list.querySelector(`a[href="${href}"]`)) return; // already static
          const a = document.createElement("a");
          a.href = href;
          if (!isMobile) a.className = "nav-link";
          else a.className = "mm-link";
          a.dataset.navSubject = s.id;
          a.innerHTML = isMobile
            ? `<span class="mm-emoji">${s.icon}</span> ${esc(s.name)}`
            : `${s.icon} ${esc(s.name)} <span class="cnt">${
                s.topics.filter((t) => t.available).length || ""
              }</span>`;
          if (body.dataset.subject === s.id) a.classList.add("is-active");
          list.appendChild(a);
        });
      });
    });

    // --- Footer / drawer year ---------------------------------------------
    document.querySelectorAll("[data-year]").forEach((el) => {
      el.textContent = String(new Date().getFullYear());
    });
  }

  /* ============================================== 5. INSTANT SEARCH ======= */
  function initSearch() {
    const triggers = document.querySelectorAll("[data-action='open-search']");
    const overlay = document.getElementById("searchOverlay");
    if (!overlay) return;
    const input = overlay.querySelector("#searchInput");
    const results = overlay.querySelector("#searchResults");
    const close = () => {
      overlay.classList.add("hidden");
      document.body.style.overflow = "";
    };
    const open = () => {
      overlay.classList.remove("hidden");
      document.body.style.overflow = "hidden";
      setTimeout(() => input.focus(), 30);
    };
    triggers.forEach((t) => t.addEventListener("click", open));
    overlay.querySelector("[data-action='close-search']")?.addEventListener("click", close);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        overlay.classList.contains("hidden") ? open() : close();
      }
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT" &&
          document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        open();
      }
    });

    loadIndex().then((idx) => {
      // Build a flat search index once: subjects + categories + topics.
      const flat = [];
      (idx.subjects || []).forEach((s) => {
        flat.push({ type: "subject", label: s.name, sub: `${s.topics.length} topics`,
                    href: `subject.html?subject=${s.id}`, icon: s.icon });
        const catNames = {};
        (s.categories || []).forEach((c) => {
          catNames[c.id] = c.name;
          flat.push({ type: "category", label: c.name, sub: s.name,
                      href: `subject.html?subject=${s.id}&category=${c.id}`,
                      icon: c.icon || s.icon });
        });
        s.topics.forEach((t) =>
          flat.push({
            type: "topic", label: t.name,
            sub: t.category ? `${catNames[t.category] || t.category} · ${s.name}` : s.name,
            href: t.available
              ? `quiz.html?subject=${s.id}&topic=${t.id}${t.category ? `&category=${t.category}` : ""}`
              : `subject.html?subject=${s.id}${t.category ? `&category=${t.category}` : ""}`,
            icon: s.icon, count: t.count,
          })
        );
      });

      const render = (q) => {
        const term = q.trim().toLowerCase();
        if (!term) {
          results.innerHTML = `<p class="muted text-sm center">Type a subject or topic name…</p>`;
          return;
        }
        const hits = flat.filter((f) => f.label.toLowerCase().includes(term)).slice(0, 12);
        results.innerHTML = hits.length
          ? hits.map((h) => `
            <a class="quiz-card card" href="${h.href}">
              <span class="qc-icon">${h.icon}</span>
              <span><h3>${esc(h.label)}</h3>
              <span class="qc-sub">${esc(h.sub)}${h.type === "topic" ? ` · ${h.count ?? 0} Q` : ""}</span></span>
              <span class="qc-go">→</span>
            </a>`).join("")
          : `<div class="empty-state"><div class="es-icon">🔎</div>
             <h3>No match</h3><p>Nothing found for “${esc(q)}”. Try another keyword.</p></div>`;
      };
      render("");
      input.addEventListener("input", () => render(input.value));
      results.addEventListener("click", (e) => {
        if (e.target.closest("a")) close();
      });
    });
  }

  /* ==================================================== 6. UI HELPERS ===== */
  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /* Dynamic SEO helpers — pages addressed by query params (?subject=, ?topic=,
     ?mode=) refresh their own canonical / robots / social tags so every topic
     has a unique, indexable identity. Safe to call more than once. */
  function seo({ title, canonical, robots, ogTitle, ogDescription, description } = {}) {
    if (title) document.title = title;

    /* Unique meta description per topic/category (ogDescription doubles as it
       when no explicit description is passed). */
    const desc = description || ogDescription;
    if (desc) {
      let d = document.querySelector('meta[name="description"]');
      if (!d) {
        d = document.createElement("meta");
        d.name = "description";
        document.head.appendChild(d);
      }
      d.content = desc;
    }

    if (robots) {
      let m = document.querySelector('meta[name="robots"]');
      if (!m) {
        m = document.createElement("meta");
        m.name = "robots";
        document.head.appendChild(m);
      }
      m.content = robots;
    }

    if (canonical) {
      let l = document.querySelector('link[rel="canonical"]');
      if (!l) {
        l = document.createElement("link");
        l.rel = "canonical";
        document.head.appendChild(l);
      }
      l.href = canonical;
    }

    const setPair = (key, val) => {
      if (!val) return;
      let og = document.querySelector(`meta[property="og:${key}"]`);
      if (!og) {
        og = document.createElement("meta");
        og.setAttribute("property", `og:${key}`);
        document.head.appendChild(og);
      }
      og.content = val;
      const tw = document.querySelector(`meta[name="twitter:${key}"]`);
      if (tw) tw.content = val;
    };
    setPair("title", ogTitle || title);
    setPair("description", desc);
    /* og:url must mirror the canonical — otherwise every ?subject= variant
       shares one og:url and social scrapers see duplicate metadata. */
    if (canonical) setPair("url", canonical);
  }

  let toastTimer = null;
  function toast(msg, ms = 2200) {
    let wrap = document.querySelector(".toast-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.className = "toast-wrap";
      document.body.appendChild(wrap);
    }
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    wrap.appendChild(el);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.remove(), ms);
  }

  /** Animates a number from 0 to `target` when it scrolls into view. */
  function countUp(el, target, suffix = "") {
    const dur = 1100;
    const start = performance.now();
    const step = (now) => {
      const p = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      const val = Math.round(target * eased);
      el.textContent = val.toLocaleString("en-IN") + suffix;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function initReveal() {
    const els = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window) || !els.length) {
      els.forEach((e) => e.classList.add("in"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((en) => {
          if (en.isIntersecting) {
            en.target.classList.add("in");
            io.unobserve(en.target);
          }
        }),
      { threshold: 0.12 }
    );
    els.forEach((e) => io.observe(e));
  }

  function initBackToTop() {
    const btn = document.getElementById("toTop");
    if (!btn) return;
    window.addEventListener(
      "scroll",
      () => btn.classList.toggle("show", window.scrollY > 520),
      { passive: true }
    );
    btn.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  /** Formats seconds as HH:MM:SS (or MM:SS under an hour). */
  function fmtTime(sec) {
    sec = Math.max(0, Math.round(sec));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    const p = (n) => String(n).padStart(2, "0");
    return h ? `${p(h)}:${p(m)}:${p(s)}` : `${p(m)}:${p(s)}`;
  }

  /* ============================ 7a. BOOKMARKS ============================ */
  const bookmarks = {
    all: () => db.get("bookmarks", []),
    has: (key) => db.get("bookmarks", []).some((b) => b.key === key),
    toggle(entry) {
      const list = db.get("bookmarks", []);
      const i = list.findIndex((b) => b.key === entry.key);
      if (i >= 0) {
        list.splice(i, 1);
        db.set("bookmarks", list);
        return false;
      }
      list.unshift({ ...entry, savedAt: Date.now() });
      db.set("bookmarks", list.slice(0, 500)); // cap for storage safety
      return true;
    },
    remove: (key) => {
      const list = db.get("bookmarks", []).filter((b) => b.key !== key);
      db.set("bookmarks", list);
    },
    clear: () => db.set("bookmarks", []),
  };

  /* ====================== 7b. PROGRESS + ACHIEVEMENTS ==================== */
  const progress = {
    get: () =>
      db.get("progress", {
        quizzes: 0, correct: 0, answered: 0,
        studySeconds: 0, days: [], best: 0, history: [],
      }),
    /** Called once per submitted quiz. */
    record({ correct, total, attempted, seconds, subject }) {
      const p = progress.get();
      p.quizzes += 1;
      p.correct += correct;
      p.answered += Math.max(attempted, 0);
      p.studySeconds += Math.max(0, Math.round(seconds || 0));
      const today = new Date().toISOString().slice(0, 10);
      if (!p.days.includes(today)) p.days.push(today);
      p.days = p.days.slice(-120); // keep 120 days of history
      const pct = total ? Math.round((correct / total) * 100) : 0;
      if (pct > p.best) p.best = pct;
      // Per-quiz percentages → used for the "average score" card.
      p.history = [...(p.history || []), pct].slice(-100);
      p.lastSubject = subject || p.lastSubject || "";
      db.set("progress", p);
      return p;
    },
    /** Consecutive active days ending today (or yesterday). */
    streak() {
      const days = new Set(progress.get().days);
      if (!days.size) return 0;
      const d = new Date();
      if (!days.has(iso(d))) d.setDate(d.getDate() - 1); // allow grace day
      let n = 0;
      while (days.has(iso(d))) {
        n++;
        d.setDate(d.getDate() - 1);
      }
      return n;
    },
    weeklyStreak() {
      // consecutive ISO weeks with at least one quiz
      const weeks = new Set(
        progress.get().days.map((day) => {
          const d = new Date(day + "T00:00:00");
          d.setDate(d.getDate() + 4 - ((d.getDay() + 6) % 7)); // week Thu anchor
          return new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
            .toISOString()
            .slice(0, 10);
        })
      );
      if (!weeks.size) return 0;
      const d = new Date();
      d.setDate(d.getDate() + 4 - ((d.getDay() + 6) % 7));
      let key = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
        .toISOString().slice(0, 10);
      if (!weeks.has(key)) {
        d.setDate(d.getDate() - 7);
        key = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
          .toISOString().slice(0, 10);
      }
      let n = 0;
      while (weeks.has(key)) {
        n++;
        const t = new Date(key + "T00:00:00");
        t.setDate(t.getDate() - 7);
        key = t.toISOString().slice(0, 10);
      }
      return n;
    },
  };
  const iso = (d) => d.toISOString().slice(0, 10);

  /** Milestone badges - purely derived from progress, never seeded. */
  function achievements() {
    const p = progress.get();
    const acc = p.answered ? Math.round((p.correct / p.answered) * 100) : 0;
    return [
      { id: "first",  icon: "🎯", name: "First Step",   desc: "Complete 1 quiz",        got: p.quizzes >= 1 },
      { id: "ten",    icon: "🔟", name: "Warm Up",      desc: "Complete 10 quizzes",     got: p.quizzes >= 10 },
      { id: "fifty",  icon: "🚀", name: "Relentless",   desc: "Complete 50 quizzes",     got: p.quizzes >= 50 },
      { id: "streak3",icon: "🔥", name: "On Fire",      desc: "3 day streak",            got: progress.streak() >= 3 },
      { id: "streak7",icon: "⚡", name: "Unstoppable",  desc: "7 day streak",            got: progress.streak() >= 7 },
      { id: "acc80",  icon: "🏆", name: "Sharpshooter", desc: "80% lifetime accuracy",   got: acc >= 80 },
      { id: "best90", icon: "🌟", name: "High Roller",  desc: "Score 90%+ in a quiz",    got: p.best >= 90 },
      { id: "time5h", icon: "⏱️", name: "Marathon",     desc: "5 hours of practice",     got: p.studySeconds >= 5 * 3600 },
    ];
  }

  /* ========================= 7c. LEADERBOARD =============================
   * Storage-first today, API-ready tomorrow.
   * To move to a backend later, only these 3 methods change:
   *   submit() -> POST /api/scores      get() -> GET  /api/scores
   * ======================================================================= */
  const leaderboard = {
    submit(entry) {
      const rows = db.get("scores", []);
      // Keep the caller's timestamp when given so ranks can match the attempt.
      rows.push({ id: uid(), at: Date.now(), ...entry });
      rows.sort((a, b) => b.percent - a.percent || b.correct - a.correct);
      db.set("scores", rows.slice(0, 300));
    },
    get(period = "today") {
      const now = Date.now();
      const day = 864e5;
      return db.get("scores", []).filter((r) => {
        if (period === "today") return now - r.at < day;
        if (period === "week") return now - r.at < 7 * day;
        return true; // all-time
      });
    },
    rankOf(id, period = "all") {
      return leaderboard.get(period).findIndex((r) => r.id === id) + 1;
    },
  };

  const uid = () =>
    Date.now().toString(36) + Math.random().toString(36).slice(2, 8);

  /* ==================================================== 8. PWA =========== */
  function initPWA() {
    // --- Service worker (offline support) ---------------------------------
    if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("sw.js").catch((e) =>
          console.warn("[HOA] SW registration failed:", e.message)
        );
      });
    }

    // --- Install button ---------------------------------------------------
    let deferred = null;
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferred = e;
      document.querySelectorAll("[data-action='install-app']").forEach((b) => {
        b.classList.remove("hidden");
        b.classList.add("show");
      });
    });
    document.addEventListener("click", async (e) => {
      if (!e.target.closest("[data-action='install-app']")) return;
      if (deferred) {
        deferred.prompt();
        await deferred.userChoice;
        deferred = null;
      } else {
        toast("Use your browser menu → “Add to Home Screen” 📲", 3200);
      }
    });
    window.addEventListener("appinstalled", () => {
      toast("Installed! Open House of Aspirants from your home screen ✅");
      document.querySelectorAll("[data-action='install-app']").forEach((b) => b.classList.add("hidden"));
    });
  }

  /* ================================================== INITIALISE ========= */
  function init() {
    renderChrome();
    initTheme();
    initNav();
    initSearch();
    initReveal();
    initBackToTop();
    initPWA();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  return {
    db, loadIndex, loadQuestions, normalizeQuestions,
    toast, esc, seo, countUp, fmtTime, uid,
    bookmarks, progress, achievements, leaderboard,
  };
})();

window.HOA = HOA;
