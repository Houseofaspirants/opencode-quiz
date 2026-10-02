/* ============================================================================
 * auth.js | Student access flow — Google sign-in (Firebase), anonymous-first
 * ----------------------------------------------------------------------------
 * Study content is public: quizzes, mocks, notes and landing pages open with
 * no sign-in at all. Google sign-in is asked for only where an account adds
 * something — the personalised pages (progress, leaderboard) — and, if
 * auth.gateQuizzes is switched on, at quiz entry too. Signed-in students
 * never see the modal again.
 *
 * Config: data/site.json → "auth" (ships inside data/index.json):
 *   enabled      false = this file is completely inert
 *   requireLogin true  = progress + leaderboard ask for sign-in first
 *                        (false = nothing in the site asks)
 *   preview      true  = demo sign-in until real Firebase keys are pasted
 *   firebase     { apiKey, authDomain, projectId, appId, ... } — public web
 *                config (safe to ship; firestore.rules guards the data)
 *
 * Modes (auto-selected): firebase (keys present) > preview > unconfigured > off.
 * Preview never talks to the network and switches itself off the moment real
 * keys exist, so there is no "demo mode" foot-gun in production.
 *
 * Firestore layout (see firestore.rules at the repo root):
 *   users/{uid}                      profile + merged progress stats
 *   users/{uid}/attempts/{resultId}  one document per completed quiz
 *   scores/{uid}                     ONE public leaderboard row per student:
 *                                    all-time points plus a field per live
 *                                    period (d20261002 / w202640 / m202610),
 *                                    so every board is a single-field query
 *                                    (no composite index to create).
 * ========================================================================== */
(() => {
  "use strict";

  const S_KEY = "authSession";    // local session mirror → instant gating
  const SYNC_KEY = "authSyncAt";  // throttles cloud stats pulls (30 minutes)
  const PEND_KEY = "authPending"; // survives the redirect sign-in round-trip
  const FB_VER = "10.12.2";

  let cfg = null;                 // site.auth from index.json
  let mode = "off";               // firebase | preview | unconfigured | off
  let session = HOA.db.get(S_KEY, null);
  let modal = null;               // overlay element
  let resolver = null;            // pending gate Promise resolver
  let gateP = null;               // the pending gate Promise itself
  let busy = false;
  let lastFocus = null;
  let gateTarget = null;          // URL the student was heading to
  let sdk = null, sdkP = null;
  let gLinked = false;

  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => HOA.esc(String(s == null ? "" : s));

  /* Which pages demand sign-in. Anonymous-first: every study page (quizzes,
     mocks, notes, landing pages) is public; only the personal dashboard asks
     who you are, plus quizzes when auth.gateQuizzes opts back in. The
     leaderboard is PUBLIC to read — joining it is what needs an account, and
     leaderboard.js offers that sign-in inline. */
  const ACCOUNT_PAGE_RX = /progress\.html$/;
  const QUIZ_PAGE_RX = /(quiz|mock)\.html$/;

  /* ---------------------------------------------------------- modal UI --- */
  const G_LOGO = `<svg class="g-logo" viewBox="0 0 48 48" width="18" height="18" aria-hidden="true" focusable="false">
    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
    <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
  </svg>`;

  const MODAL_HTML = `
  <div class="auth-overlay hidden" id="authOverlay">
    <div class="auth-modal" role="dialog" aria-modal="true" aria-labelledby="authTitle" aria-describedby="authDesc">
      <button class="icon-btn auth-close" type="button" data-auth-action="close" aria-label="Close sign-in dialog">✕</button>
      <h2 class="auth-title" id="authTitle">Continue with Google</h2>
      <p class="auth-tagline" id="authDesc">Sign in to save your quiz progress, performance, and rankings.</p>
      <p class="auth-benefits-label">Benefits:</p>
      <ul class="auth-benefits">
        <li>Complete login in just 2–3 seconds</li>
        <li>No password required</li>
        <li>Secure Google Authentication</li>
        <li>Save quiz history automatically</li>
        <li>Track your overall performance</li>
        <li>View your Dashboard</li>
        <li>Appear on the Leaderboard</li>
      </ul>
      <div class="auth-error hidden" id="authError" role="alert"></div>
      <button class="btn btn-google" id="googleBtn" type="button">
        ${G_LOGO}<span class="g-label">Continue with Google</span>
      </button>
      <p class="auth-preview hidden" id="authPreviewNote">Preview mode — real Google sign-in goes live automatically when you paste your Firebase keys (README §20).</p>
    </div>
  </div>`;

  function injectModal() {
    if (modal || !document.body) return;
    const holder = document.createElement("div");
    holder.innerHTML = MODAL_HTML.trim();
    modal = holder.firstElementChild;
    document.body.appendChild(modal);
    modal.addEventListener("mousedown", (e) => {
      if (e.target === modal) dismiss();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !modal.classList.contains("hidden")) dismiss();
    });
  }

  /* ------------------------------------------------------------- state --- */
  function gates(path) {
    if (mode === "off" || !cfg || cfg.enabled === false) return false;
    if (cfg.requireLogin === false) return false;      // hard "everything open"
    if (ACCOUNT_PAGE_RX.test(path)) return true;       // progress + leaderboard
    return cfg.gateQuizzes === true && QUIZ_PAGE_RX.test(path);
  }
  const required = () => gates(location.pathname);
  const signedIn = () => !!session;
  const cloudEnabled = () => mode === "firebase" && !!session && session.provider === "google";
  const isMe = (uid) => !!session && !!uid && session.uid === uid;

  function setSession(p) {
    session = p;
    HOA.db.set(S_KEY, p);
  }
  function clearSession() {
    session = null;
    HOA.db.remove(S_KEY);
  }

  /* ------------------------------------------------------------- gate ---- */
  /** Resolves true when `path` may be opened, false when the student
   *  dismissed. Checking the TARGET path matters: a link from a public page
   *  to a gated one must open the modal before we navigate, not after. */
  function ensurePath(path) {
    return ready.then(() => {
      if (!gates(path) || signedIn()) return true;
      return openGate();
    });
  }

  /** Resolves true when the page we are already on may be shown. */
  function ensure() {
    return ensurePath(location.pathname);
  }

  function openGate() {
    if (resolver) return gateP; // modal already open — share one Promise
    injectModal();
    $("#authPreviewNote").classList.toggle("hidden", mode !== "preview");
    $("#authError").classList.add("hidden");
    modal.classList.remove("hidden");
    document.documentElement.classList.add("auth-open"); // scroll lock
    lastFocus = document.activeElement;
    gateP = new Promise((res) => { resolver = res; });
    $("#googleBtn").focus();
    // A Firebase session may already exist even though our mirror was lost —
    // onAuthStateChanged (wired below) will complete the gate silently.
    if (mode === "firebase") loadFirebase().catch(() => {});
    return gateP;
  }

  function closeModalUI() {
    if (!modal) return;
    modal.classList.add("hidden");
    document.documentElement.classList.remove("auth-open");
    setBusy(false);
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (_) {} }
  }

  function dismiss() {
    if (busy || !resolver) return;
    const res = resolver;
    resolver = null; gateP = null;
    closeModalUI();
    res(false);
  }

  function finishGate(ok) {
    const res = resolver;
    resolver = null; gateP = null;
    closeModalUI();
    if (res) res(ok);
  }

  /* --------------------------------------------------- sign-in outcomes --- */
  function profileOf(u) {
    return {
      uid: u.uid,
      name: u.displayName || (u.email || "").split("@")[0] || "Student",
      email: u.email || "",
      photo: u.photoURL || null,
      provider: "google",
    };
  }

  async function completeSignIn(profile, opts = {}) {
    setSession(profile);
    renderAccount();
    if (mode === "firebase") {
      try { await upsertProfile(profile); } catch (e) { console.warn("[HOA.auth] profile sync:", e && e.message); }
      try { await pullStats(true); } catch (e) { console.warn("[HOA.auth] stats sync:", e && e.message); }
    }
    const pending = opts.redirect;
    finishGate(true);
    if (pending) location.replace(pending);
  }

  async function handleGoogle() {
    if (busy) return;
    $("#authError").classList.add("hidden");

    if (mode === "preview") {
      setBusy(true, "Signing in…");
      await new Promise((r) => setTimeout(r, 900));
      setBusy(false);
      return completeSignIn({
        uid: "preview-" + Math.random().toString(36).slice(2, 10),
        name: "Preview Student",
        email: "preview@houseofaspirants.in",
        photo: null,
        provider: "preview",
      });
    }

    if (mode === "unconfigured") {
      return showError("Google sign-in isn’t configured yet — paste your Firebase web config into data/site.json (README §20), or set auth.preview to true to demo the flow.");
    }

    setBusy(true, "Opening Google…");
    try {
      const { auth, firebase } = await loadFirebase();
      const GoogleAuthProvider = firebase.auth.GoogleAuthProvider;
      if (auth.currentUser) {                       // remembered from before
        setBusy(false);
        return completeSignIn(profileOf(auth.currentUser));
      }
      const cred = await signInWithPopup(auth, new GoogleAuthProvider());
      setBusy(false);
      return completeSignIn(profileOf(cred.user));
    } catch (err) {
      setBusy(false);
      const code = (err && err.code) || "";
      if (code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request") {
        return showError("Sign-in was cancelled — tap “Continue with Google” whenever you’re ready.");
      }
      if (code === "auth/popup-blocked") {          // fall back to full-page flow
        try {
          sessionStorage.setItem(PEND_KEY, gateTarget || location.href);
          await sdk.auth.signInWithRedirect(new sdk.firebase.auth.GoogleAuthProvider());
          return;
        } catch (e2) { return showError(errText(e2)); }
      }
      showError(errText(err));
    }
  }

  function errText(err) {
    const code = (err && err.code) || "";
    const map = {
      "auth/operation-not-allowed": "Google sign-in is switched off — enable it in Firebase Console → Authentication → Sign-in method.",
      "auth/unauthorized-domain": "This domain isn’t authorised yet — add it in Firebase Console → Authentication → Settings → Authorised domains (README §20).",
      "auth/invalid-api-key": "The Firebase config looks wrong — re-copy the web config into data/site.json (README §20).",
      "auth/configuration-not-found": "Google sign-in isn’t enabled for this Firebase project yet (README §20).",
      "auth/network-request-failed": "Network error — check your connection and try again.",
      "auth/internal-error": "Sign-in hit a snag — please try again in a moment.",
    };
    return map[code] || "Sign-in failed — please try again.";
  }

  function showError(msg) {
    const el = $("#authError");
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  function setBusy(on, label) {
    busy = on;
    const btn = $("#googleBtn");
    if (!btn || !modal) return;
    btn.classList.toggle("is-loading", on);
    btn.disabled = on;
    modal.querySelector(".auth-modal").setAttribute("aria-busy", on ? "true" : "false");
    modal.querySelector('[data-auth-action="close"]').disabled = on;
    $(".g-label", btn).textContent = on ? (label || "Signing in…") : "Continue with Google";
  }

  /* -------------------------------------------------- Firebase (lazy) ---- */
  function preconnectGstatic() {
    if (gLinked || document.querySelector('link[rel="preconnect"][href="https://www.gstatic.com"]')) { gLinked = true; return; }
    const l = document.createElement("link");
    l.rel = "preconnect";
    l.href = "https://www.gstatic.com";
    l.crossOrigin = "anonymous";
    document.head.appendChild(l);
    gLinked = true;
  }

  function loadScript(src) {
    return new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = src; s.async = true;
      s.onload = res;
      s.onerror = () => rej(new Error("failed to load " + src));
      document.head.appendChild(s);
    });
  }

  /** Loads app + auth + firestore compat SDKs on demand, then initialises. */
  function loadFirebase() {
    if (sdk) return Promise.resolve(sdk);
    if (sdkP) return sdkP;
    preconnectGstatic();
    const base = `https://www.gstatic.com/firebasejs/${FB_VER}/`;
    sdkP = loadScript(base + "firebase-app-compat.js")
      .then(() => Promise.all([
        loadScript(base + "firebase-auth-compat.js"),
        loadScript(base + "firebase-firestore-compat.js"),
      ]))
      .then(() => {
        const f = cfg.firebase || {};
        if (!window.firebase.apps.length) {
          window.firebase.initializeApp({
            apiKey: f.apiKey, authDomain: f.authDomain, projectId: f.projectId,
            appId: f.appId, messagingSenderId: f.messagingSenderId,
            storageBucket: f.storageBucket,
          });
        }
        const auth = window.firebase.auth();
        const db = window.firebase.firestore();
        // Resume a sign-in that went through the full-page redirect flow.
        auth.getRedirectResult().then((res) => {
          if (res && res.user) {
            const pend = sessionStorage.getItem(PEND_KEY);
            sessionStorage.removeItem(PEND_KEY);
            completeSignIn(profileOf(res.user), pend ? { redirect: pend } : {});
          }
        }).catch(() => {});
        // Keep the mirror honest: another tab may have signed out.
        auth.onAuthStateChanged((u) => {
          if (u) {
            if (!session || session.uid !== u.uid) {
              setSession(profileOf(u));
              renderAccount();
              if (resolver) completeSignIn(profileOf(u));
            }
          } else if (session && session.provider === "google") {
            clearSession();
            renderAccount();
          }
        });
        sdk = { auth, db, firebase: window.firebase };
        return sdk;
      })
      .catch((e) => { sdkP = null; throw e; });
    return sdkP;
  }

  const signInWithPopup = (auth, provider) => auth.signInWithPopup(provider);

  /* --------------------------------------------------- cloud storage ----- */
  function usersRef(db, uid) { return db.collection("users").doc(uid); }

  async function upsertProfile(p) {
    const { db } = await loadFirebase();
    const ref = usersRef(db, p.uid);
    const snap = await ref.get();
    const now = Date.now();
    if (!snap.exists) {
      await ref.set({
        name: p.name, email: p.email, photo: p.photo, provider: "google",
        createdAt: now, lastLoginAt: now, updatedAt: now,
        stats: localStats(),
      }, { merge: true });
    } else {
      await ref.update({ name: p.name, email: p.email, photo: p.photo, lastLoginAt: now, updatedAt: now });
    }
  }

  const localStats = () => HOA.progress.get();

  function mergeStats(a, b) {
    if (!b) return a;
    const days = Array.from(new Set([...(a.days || []), ...(b.days || [])])).sort().slice(-120);
    const history = [...(a.history || []), ...(b.history || [])].slice(-100);
    const max = (x, y) => Math.max(Number(x) || 0, Number(y) || 0);
    return {
      ...a,
      quizzes: max(a.quizzes, b.quizzes),
      correct: max(a.correct, b.correct),
      answered: max(a.answered, b.answered),
      studySeconds: max(a.studySeconds, b.studySeconds),
      best: max(a.best, b.best),
      days, history,
      lastSubject: a.lastSubject || b.lastSubject || "",
    };
  }

  /** Pull cloud stats → merge into this device → push the merged snapshot. */
  async function pullStats(force) {
    if (!cloudEnabled()) return;
    const last = HOA.db.get(SYNC_KEY, 0);
    if (!force && Date.now() - last < 30 * 60 * 1000) return;
    const { db } = await loadFirebase();
    const ref = usersRef(db, session.uid);
    const snap = await ref.get();
    const remote = snap.exists ? snap.data().stats : null;
    const merged = mergeStats(localStats(), remote);
    HOA.db.set("progress", merged);
    await ref.set({ stats: merged, updatedAt: Date.now() }, { merge: true });
    HOA.db.set(SYNC_KEY, Date.now());
  }

  /* ------------------------------------------------------ leaderboard --- */
  /* Points: 10 per correct answer, +50 for a perfect score on a set of 10+.
   * Only a student's BEST result on a given set counts — re-taking the same
   * set adds just the improvement, so the board rewards new practice rather
   * than farming one easy set. The Daily Challenge key carries the date, so
   * it is a fresh set every day. */
  const PTS = Object.freeze({ correct: 10, perfect: 50, perfectMin: 10 });
  const MAX_DAYS = 60;

  function pointsFor(r) {
    const total = Math.max(0, Number(r.total) || 0);
    const correct = Math.max(0, Math.min(Number(r.correct) || 0, total));
    return correct * PTS.correct + (total >= PTS.perfectMin && correct === total ? PTS.perfect : 0);
  }

  /** Period keys in India time (IST), the clock every student lives on.
   *  firestore.rules recomputes these exact strings from request.time, so the
   *  formulas must stay identical on both sides (week = floor((doy-dow+10)/7),
   *  Monday-start, numbered within the IST calendar year). */
  function periodKeys(t) {
    const d = new Date((Number(t) || Date.now()) + 330 * 60e3); // IST as UTC
    const y = d.getUTCFullYear(), m = d.getUTCMonth() + 1, day = d.getUTCDate();
    const p2 = (n) => String(n).padStart(2, "0");
    const doy = Math.round((Date.UTC(y, m - 1, day) - Date.UTC(y, 0, 1)) / 864e5) + 1;
    const dow = d.getUTCDay() || 7;                       // 1 Mon … 7 Sun
    const wk = Math.floor((doy - dow + 10) / 7);
    return {
      iso: `${y}-${p2(m)}-${p2(day)}`,
      d: `d${y}${p2(m)}${p2(day)}`,
      w: `w${y}${p2(wk)}`,
      m: `m${y}${p2(m)}`,
    };
  }

  /** Stable, Firestore-safe id for "the same set" (mock ids drop the nonce). */
  function quizKey(r) {
    let k = String(r.key || "");
    if (!k) k = `${r.mode || "topic"}:${r.title || "quiz"}`;
    if (k.startsWith("mock:")) k = k.split(":").slice(0, 3).join(":");
    return k.toLowerCase().replace(/[^a-z0-9_-]+/g, "_").slice(0, 120);
  }

  function streakOf(days, todayIso) {
    const set = new Set(days);
    const d = new Date(todayIso + "T00:00:00Z");
    if (!set.has(todayIso)) d.setUTCDate(d.getUTCDate() - 1);
    let n = 0;
    while (set.has(d.toISOString().slice(0, 10))) { n++; d.setUTCDate(d.getUTCDate() - 1); }
    return n;
  }

  /** Pure: previous scores doc + one finished attempt → the next doc. */
  function nextScore(prev, r, me, now) {
    const P = prev || {};
    const keys = periodKeys(now);
    const pts = pointsFor(r);
    const qk = quizKey(r);
    const best = { ...(P.best || {}) };
    const gained = Math.max(0, pts - (Number(best[qk]) || 0));
    if (pts > (Number(best[qk]) || 0)) best[qk] = pts;
    const total = Math.max(0, Number(r.total) || 0);
    const correct = Math.max(0, Math.min(Number(r.correct) || 0, total));

    const per = {};
    ["d", "w", "m"].forEach((p) => {
      const old = (P.per && P.per[p] && P.per[p].k === keys[p]) ? P.per[p] : { k: keys[p], quizzes: 0, correct: 0, answered: 0 };
      per[p] = { k: keys[p], quizzes: old.quizzes + 1, correct: old.correct + correct, answered: old.answered + total };
    });
    const days = Array.from(new Set([...(P.days || []), keys.iso])).sort().slice(-MAX_DAYS);

    // set() WITHOUT merge: last period's d…/w…/m… fields fall away on their own.
    const doc = {
      uid: me.uid,
      name: String(me.name || "Aspirant").trim().slice(0, 40) || "Aspirant",
      photo: me.photo || null,
      pts: (Number(P.pts) || 0) + gained,
      quizzes: (Number(P.quizzes) || 0) + 1,
      correct: (Number(P.correct) || 0) + correct,
      answered: (Number(P.answered) || 0) + total,
      best, days, streak: streakOf(days, keys.iso), per,
      last: { quiz: String(r.title || "Quiz").slice(0, 80), percent: Number(r.percent) || 0, at: Number(r.at) || now },
    };
    ["d", "w", "m"].forEach((p) => {
      const kept = P[keys[p]] != null ? Number(P[keys[p]]) || 0 : 0;
      doc[keys[p]] = kept + gained;
    });
    return { doc, gained, pts };
  }

  /** One call from the result page: attempt history + leaderboard + stats.
   *  Resolves { gained, total, today } (or null when not signed in). */
  async function syncResult(r) {
    if (!cloudEnabled() || !r) return null;
    let out = null;
    try {
      const { db, firebase } = await loadFirebase();
      const uid = session.uid;
      const at = Number(r.at) || Date.now();
      await usersRef(db, uid).collection("attempts").doc(String(r.id || at)).set({
        title: r.title || "", mode: r.mode || "topic",
        subject: r.subjectName || "", quiz: r.title || "",
        percent: Number(r.percent) || 0, correct: Number(r.correct) || 0,
        total: Number(r.total) || 0, attempted: Number(r.attempted) || 0,
        seconds: Number(r.seconds) || 0, at,
      }, { merge: true });

      const ref = db.collection("scores").doc(uid);
      out = await db.runTransaction(async (tx) => {
        const snap = await tx.get(ref);
        const res = nextScore(snap.exists ? snap.data() : null, r, session, Date.now());
        tx.set(ref, { ...res.doc, updatedAt: firebase.firestore.FieldValue.serverTimestamp() });
        const k = periodKeys(Date.now());
        return { gained: res.gained, total: res.doc.pts, today: res.doc[k.d] };
      });
      // The leaderboard page caches reads for 60 s — drop them so the new
      // points show the moment the student opens it.
      try {
        Object.keys(sessionStorage).filter((x) => x.startsWith("lb2:"))
          .forEach((x) => sessionStorage.removeItem(x));
      } catch (_) {}
      await pullStats(true);
    } catch (e) {
      console.warn("[HOA.auth] cloud sync failed (attempt saved locally):", e && e.message);
    }
    return out;
  }

  /** Field to rank by for a board period: day | week | month | all. */
  function boardField(period, t) {
    const k = periodKeys(t);
    return period === "day" ? k.d : period === "week" ? k.w : period === "month" ? k.m : "pts";
  }

  /** Top of one board — a single-field query, so no index setup is needed. */
  async function fetchBoard(period, limit) {
    const { db } = await loadFirebase();
    const field = boardField(period);
    const snap = await db.collection("scores").orderBy(field, "desc").limit(Number(limit) || 50).get();
    return snap.docs.map((d) => ({ ...d.data(), id: d.id, score: Number(d.get(field)) || 0 }))
      .filter((x) => x.score > 0);
  }
  const fetchScores = (limit) => fetchBoard("all", limit);

  /** The signed-in student's own row (null when signed out or not yet ranked). */
  async function fetchMine() {
    if (!cloudEnabled()) return null;
    const { db } = await loadFirebase();
    const snap = await db.collection("scores").doc(session.uid).get();
    return snap.exists ? { ...snap.data(), id: snap.id } : null;
  }

  /** How many students score above `value` on a board (null if unsupported). */
  async function countAbove(period, value) {
    const { db } = await loadFirebase();
    const q = db.collection("scores").where(boardField(period), ">", Number(value) || 0);
    if (typeof q.count !== "function") return null;
    try { const agg = await q.count().get(); return agg.data().count; } catch (_) { return null; }
  }

  async function signOut() {
    const wasPreview = session && session.provider === "preview";
    if (cloudEnabled()) {
      try { const { auth } = await loadFirebase(); await auth.signOut(); } catch (_) {}
    }
    clearSession();
    HOA.db.remove(SYNC_KEY);
    renderAccount();
    HOA.toast(wasPreview ? "Signed out of preview mode." : "Signed out.");
  }

  /* ------------------------------------------------- account rendering --- */
  function faceHTML(p, cls) {
    if (p.photo) return `<img class="${cls}" src="${esc(p.photo)}" alt="" width="44" height="44" loading="lazy">`;
    return `<span class="${cls} aa-initial" aria-hidden="true">${esc((p.name || "?").trim().charAt(0).toUpperCase() || "?")}</span>`;
  }

  function accountHTML(p) {
    const preview = p.provider === "preview";
    return `
      ${faceHTML(p, "aa-avatar")}
      <div class="aa-meta">
        <div class="aa-name">${esc(p.name || "Student")}</div>
        <div class="aa-sub">${esc(p.email)}${preview ? ' · <b class="aa-preview">Preview mode</b>' : " · Signed in with Google"}</div>
      </div>
      <div class="aa-actions">
        <a class="btn btn-sm" href="leaderboard.html">🏅 Leaderboard</a>
        <button class="btn btn-sm btn-soft" type="button" data-auth-action="signout">Sign out</button>
      </div>`;
  }

  function renderAccount() {
    const box = document.getElementById("authAccount");
    if (box) {
      if (session) { box.innerHTML = accountHTML(session); box.classList.remove("hidden"); }
      else { box.innerHTML = ""; box.classList.add("hidden"); }
    }
    const chip = document.getElementById("authChip");
    if (chip) {
      if (session) {
        chip.classList.remove("hidden");
        const face = $("#authChipFace");
        if (face) face.innerHTML = session.photo
          ? `<img src="${esc(session.photo)}" alt="" width="20" height="20">`
          : esc((session.name || "?").trim().charAt(0).toUpperCase() || "?");
        chip.setAttribute("title", session.name || "Your account");
        chip.setAttribute("aria-label", `Your account — ${session.name || ""}`);
      } else {
        chip.classList.add("hidden");
      }
    }
  }

  /* ------------------------------------------------------ page wiring ---- */
  document.addEventListener("click", (e) => {
    const act = e.target && e.target.closest ? e.target.closest("[data-auth-action]") : null;
    if (act) {
      const a = act.dataset.authAction;
      if (a === "close") return dismiss();
      if (a === "signout") return signOut();
    }
    if (e.target && e.target.closest && e.target.closest("#googleBtn")) return handleGoogle();

    /* ---- gate the pages that actually need an account (links) ---- */
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const link = e.target && e.target.closest ? e.target.closest("a[href]") : null;
    if (!link || (link.target && link.target !== "_self") || link.hasAttribute("download")) return;
    let url;
    try { url = new URL(link.getAttribute("href"), location.href); } catch (_) { return; }
    if (url.origin !== location.origin) return;
    if (!gates(url.pathname)) return;   // anonymous-first: never block content
    e.preventDefault();
    gateTarget = url.pathname + url.search + url.hash;
    ensurePath(url.pathname)
      .then((ok) => { if (ok) location.href = gateTarget; })
      .catch(() => { location.href = gateTarget; })   // fail open, never trap
      .then(() => { gateTarget = null; });
  });

  /* -------------------------------------------------------------- boot --- */
  async function bootGate() {
    // Direct visit / programmatic entry to a gated page while signed out.
    // NOTE: calls openGate() directly — awaiting ensure() inside `ready`
    // would deadlock (ensure waits on ready, ready waits on this).
    if (!required() || signedIn()) return;
    const ok = await openGate();
    if (ok) location.reload();
    else location.replace("index.html");
  }

  const ready = (async () => {
    let site = {};
    try { site = (await HOA.loadIndex()).site || {}; } catch (_) {}
    cfg = site.auth || {};
    if (cfg.enabled === false) { mode = "off"; return; }

    const f = cfg.firebase || {};
    if (f.apiKey && f.projectId && f.authDomain) mode = "firebase";
    else if (cfg.preview) mode = "preview";
    else mode = "unconfigured";

    if (mode === "unconfigured") {
      console.warn("[HOA.auth] Google sign-in is not configured — add Firebase keys to data/site.json (README §20) or set auth.preview = true.");
    }
    // Demo profiles only exist in preview mode; real Google sessions only in
    // firebase mode — switching modes invalidates the other kind.
    if (session &&
        ((session.provider === "preview" && mode !== "preview") ||
         (session.provider === "google" && mode !== "firebase"))) {
      clearSession();
    }
    if (mode === "firebase") {
      loadFirebase()
        .then(() => pullStats(false))
        .catch((e) => console.warn("[HOA.auth] SDK unavailable:", e && e.message));
    }
    injectModal();
    renderAccount();
    bootGate(); // not awaited: `ready` must stay resolvable for page scripts
  })();

  /* ------------------------------------------------------------- API ----- */
  HOA.auth = {
    ready, ensure, signedIn, cloudEnabled, isMe,
    user: () => session,
    // Which backend auth is running against — firebase | preview | unconf | off.
    // HOA.lbApi picks its data source from this (never from the session).
    get mode() { return mode; },
    fetchScores, fetchBoard, fetchMine, countAbove, syncResult, signOut,
    /** Opens Google sign-in straight from a click (keeps the popup gesture);
     *  resolves true once signed in, false if the student backs out. */
    signIn: () => { const p = openGate(); if (mode === "firebase") handleGoogle(); return p; },
    // Pure helpers shared with the leaderboard page (and unit-checked).
    pointsFor, periodKeys, boardField, nextScore, quizKey, PTS,
  };
})();
