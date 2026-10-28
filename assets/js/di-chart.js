// @ts-check
/* ============================================================================
 * di-chart.js | Data-interpretation displays for MCQ questions
 * ----------------------------------------------------------------------------
 * DI question files (schema_version "1.1": Tabulation, Bar Graphs, Pie Chart,
 * Line Graphs) give each question a `data` list of 1-2 displays:
 *
 *   { type: "table", title, unit, headers: [..], rows: [[name, n, n], ..] }
 *   { type: "bar",   title, unit, stacked, labels: [..], series: [{ name, values }] }
 *   { type: "line",  title, unit, labels: [..], series: [{ name, values }] }
 *   { type: "pie",   title, value_type: "percent"|"degree", total, unit,
 *                    slices: [{ label, value }] }
 *
 * A value may be null (a missing-data question); it is shown as "?".
 *
 * HOA_DI.html(data) returns an HTML string (inline SVG, no library, no canvas),
 * so every page can drop it into the markup it already builds with innerHTML:
 * the quiz card, the result review and the bookmarks list. Colours come from
 * the --di-* tokens in style.css, so light and dark themes both work.
 * ========================================================================== */
(function () {
  "use strict";

  const MISSING = "?";
  const SERIES = 6; // colour slots --di-1 .. --di-6

  /** @param {any} s */
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] || c);

  /** @param {any} v */
  const isNum = (v) => typeof v === "number" && isFinite(v);

  /** @param {any} v */
  const fmt = (v) => (isNum(v) ? v.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : v === null || v === undefined ? MISSING : String(v));

  /** Round a raw step up to 1, 2, 2.5 or 5 × 10^n. @param {number} raw */
  function niceStep(raw) {
    if (!(raw > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const m = raw / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }

  /** Axis from 0 (or below, for negatives) to a round top with ~5 ticks. */
  function axis(min, max) {
    const lo = Math.min(0, min), hi = Math.max(0, max);
    const step = niceStep((hi - lo || 1) / 5);
    const top = Math.ceil((hi * 1.08) / step) * step || step;
    const bottom = Math.floor(lo / step) * step;
    const ticks = [];
    for (let t = bottom; t <= top + step / 2; t += step) ticks.push(Math.round(t * 1e6) / 1e6);
    return { min: bottom, max: top, ticks };
  }

  /** Visually hidden data table so screen readers get every number. */
  function srTable(headers, rows) {
    return `<table class="di-sr"><thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows
      .map((r) => `<tr>${r.map((c, i) => (i ? `<td>${esc(fmt(c))}</td>` : `<th>${esc(c)}</th>`)).join("")}</tr>`)
      .join("")}</tbody></table>`;
  }

  function head(item, showUnit) {
    const unit = showUnit && item.unit ? ` <span class="di-unit">(${esc(item.unit)})</span>` : "";
    return item.title || unit ? `<div class="di-title">${esc(item.title || "")}${unit}</div>` : "";
  }

  function legend(names) {
    if (names.length < 2) return "";
    return `<div class="di-legend">${names
      .map((n, i) => `<span class="di-key"><i class="di-swatch di-c${(i % SERIES) + 1}"></i>${esc(n)}</span>`)
      .join("")}</div>`;
  }

  /* ------------------------------------------------------------- TABLE -- */
  function table(item) {
    const headers = Array.isArray(item.headers) ? item.headers : [];
    const rows = Array.isArray(item.rows) ? item.rows : [];
    const body = rows
      .map((r) => `<tr>${(Array.isArray(r) ? r : [])
        .map((c, i) => i === 0
          ? `<th scope="row">${esc(fmt(c))}</th>`
          : `<td class="${isNum(c) || c === null ? "num" : ""}">${esc(fmt(c))}</td>`)
        .join("")}</tr>`)
      .join("");
    return `${head(item, true)}<div class="di-scroll"><table class="di-table"><thead><tr>${headers
      .map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  /* ------------------------------------------------------ BAR and LINE -- */
  function xy(item, kind, width) {
    const labels = (Array.isArray(item.labels) ? item.labels : []).map(String);
    const series = (Array.isArray(item.series) ? item.series : []).map((s) => ({
      name: String((s && s.name) ?? ""),
      values: labels.map((_, i) => (s && Array.isArray(s.values) && isNum(s.values[i]) ? s.values[i] : null)),
    }));
    const n = labels.length;
    if (!n || !series.length) return head(item, true);
    const stacked = kind === "bar" && item.stacked === true;

    let lo = 0, hi = 0;
    if (stacked) {
      labels.forEach((_, i) => {
        let pos = 0, neg = 0;
        series.forEach((s) => { const v = s.values[i]; if (v !== null) { if (v >= 0) pos += v; else neg += v; } });
        hi = Math.max(hi, pos); lo = Math.min(lo, neg);
      });
    } else {
      series.forEach((s) => s.values.forEach((v) => { if (v !== null) { hi = Math.max(hi, v); lo = Math.min(lo, v); } }));
    }
    const ax = axis(lo, hi);

    // Geometry (viewBox units; the SVG scales to the card width).
    const longest = Math.max(...labels.map((l) => l.length));
    // The viewBox is the real drawing width, so 12px text stays 12px on a phone.
    const W = Math.round(Math.max(300, Math.min(720, width))), padL = W < 420 ? 44 : 54, padR = 10, padT = 22;
    const slot = (W - padL - padR) / n;
    const tilt = longest * 7.5 > slot - 6;      // long labels → slanted
    const padB = tilt ? Math.min(110, 30 + longest * 5.2) : 34;
    const H = (W < 480 ? 250 : 300) + (tilt ? padB - 34 : 0);
    const plotH = H - padT - padB;
    const y = (v) => padT + plotH - ((v - ax.min) / (ax.max - ax.min)) * plotH;
    const xc = (i) => padL + slot * (i + 0.5);

    const parts = [];
    // grid + y ticks
    ax.ticks.forEach((t) => {
      const yy = y(t).toFixed(1);
      parts.push(`<line class="di-grid${t === 0 ? " di-zero" : ""}" x1="${padL}" x2="${W - padR}" y1="${yy}" y2="${yy}"/>`);
      parts.push(`<text class="di-tick" x="${padL - 6}" y="${yy}" text-anchor="end" dominant-baseline="middle">${esc(fmt(t))}</text>`);
    });
    // x labels
    labels.forEach((l, i) => {
      const x = xc(i).toFixed(1), yy = H - padB + 16;
      parts.push(tilt
        ? `<text class="di-xlab" x="${x}" y="${yy}" text-anchor="end" transform="rotate(-35 ${x} ${yy})">${esc(l)}</text>`
        : `<text class="di-xlab" x="${x}" y="${yy}" text-anchor="middle">${esc(l)}</text>`);
    });
    if (item.unit) {
      parts.push(`<text class="di-tick" x="12" y="${(padT + plotH / 2).toFixed(1)}" text-anchor="middle" transform="rotate(-90 12 ${(padT + plotH / 2).toFixed(1)})">${esc(item.unit)}</text>`);
    }

    const base = y(Math.max(ax.min, 0));
    if (kind === "bar") {
      const groupW = slot * 0.74;
      const k = stacked ? 1 : series.length;
      const bw = groupW / k;
      labels.forEach((_, i) => {
        let pos = 0, neg = 0;
        series.forEach((s, si) => {
          const v = s.values[i];
          const x0 = xc(i) - groupW / 2 + (stacked ? 0 : si * bw);
          const cls = `di-c${(si % SERIES) + 1}`;
          if (v === null) {
            if (!stacked) parts.push(`<text class="di-val" x="${(x0 + bw / 2).toFixed(1)}" y="${(base - 6).toFixed(1)}" text-anchor="middle">${MISSING}</text>`);
            return;
          }
          let y1, y2;
          if (stacked) {
            if (v >= 0) { y1 = y(pos + v); y2 = y(pos); pos += v; } else { y1 = y(neg); y2 = y(neg + v); neg += v; }
          } else { y1 = y(Math.max(v, 0)); y2 = y(Math.min(v, 0)); }
          const h = Math.max(0.5, y2 - y1);
          parts.push(`<rect class="${cls}" x="${(x0 + (stacked ? 0 : 1)).toFixed(1)}" y="${y1.toFixed(1)}" width="${Math.max(1, bw - (stacked ? 0 : 2)).toFixed(1)}" height="${h.toFixed(1)}" rx="2"/>`);
          const cx = (x0 + bw / 2).toFixed(1);
          if (stacked) {
            if (h >= 15) parts.push(`<text class="di-val di-in" x="${cx}" y="${(y1 + h / 2).toFixed(1)}" text-anchor="middle" dominant-baseline="middle">${esc(fmt(v))}</text>`);
          } else {
            const ty = v >= 0 ? y1 - 5 : y2 + 13;
            parts.push(`<text class="di-val${bw < 26 ? " di-small" : ""}" x="${cx}" y="${ty.toFixed(1)}" text-anchor="middle">${esc(fmt(v))}</text>`);
          }
        });
        if (stacked && series.length > 1 && series.some((s) => s.values[i] !== null)) {
          const tot = series.reduce((a, s) => a + (s.values[i] || 0), 0);
          parts.push(`<text class="di-val di-total-lab" x="${xc(i).toFixed(1)}" y="${(y(pos) - 5).toFixed(1)}" text-anchor="middle">${esc(fmt(tot))}</text>`);
        }
      });
    } else {
      series.forEach((s, si) => {
        const cls = `di-c${(si % SERIES) + 1}`;
        let d = "", pen = false;
        s.values.forEach((v, i) => {
          if (v === null) { pen = false; return; }
          d += `${pen ? "L" : "M"}${xc(i).toFixed(1)} ${y(v).toFixed(1)}`; pen = true;
        });
        if (d) parts.push(`<path class="di-line ${cls}" d="${d}"/>`);
      });
      // points + labels: the highest series at an x labels above, the others below
      labels.forEach((_, i) => {
        const vals = series.map((s) => s.values[i]);
        const top = Math.max(...vals.filter((v) => v !== null).concat([-Infinity]));
        vals.forEach((v, si) => {
          const cx = xc(i).toFixed(1);
          if (v === null) {
            parts.push(`<text class="di-val" x="${cx}" y="${(base - 6).toFixed(1)}" text-anchor="middle">${MISSING}</text>`);
            return;
          }
          const cls = `di-c${(si % SERIES) + 1}`;
          const py = y(v);
          parts.push(`<circle class="di-pt ${cls}" cx="${cx}" cy="${py.toFixed(1)}" r="4"/>`);
          const above = series.length === 1 || (v === top && vals.indexOf(top) === si);
          const ty = above ? py - 9 : py + 17;
          parts.push(`<text class="di-val" x="${cx}" y="${ty.toFixed(1)}" text-anchor="middle">${esc(fmt(v))}</text>`);
        });
      });
    }

    const label = `${item.title || (kind === "bar" ? "Bar graph" : "Line graph")}${item.unit ? ` (${item.unit})` : ""}`;
    const sr = srTable([""].concat(labels), series.map((s) => [s.name || label].concat(s.values)));
    return `${head(item, true)}<svg class="di-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">${parts.join("")}</svg>${legend(series.map((s) => s.name))}${sr}`;
  }

  /* --------------------------------------------------------------- PIE -- */
  function pie(item) {
    const slices = (Array.isArray(item.slices) ? item.slices : []).map((s) => ({
      label: String((s && s.label) ?? ""),
      value: s && isNum(s.value) ? s.value : null,
    }));
    const deg = item.value_type === "degree";
    const whole = deg ? 360 : 100;
    const suffix = deg ? "°" : "%";
    const known = slices.reduce((a, s) => a + (s.value || 0), 0);
    const missing = slices.filter((s) => s.value === null);
    const rest = Math.max(0, whole - known);
    // Missing slices share whatever is left so the circle still closes.
    const draw = slices.map((s) => ({ ...s, size: s.value === null ? (missing.length ? rest / missing.length : 0) : s.value }));
    const sum = draw.reduce((a, s) => a + s.size, 0) || 1;

    const R = 120, C = 140, parts = [];
    let a0 = -Math.PI / 2;
    draw.forEach((s, i) => {
      const frac = s.size / sum;
      if (frac <= 0) return;
      const a1 = a0 + frac * Math.PI * 2;
      const cls = s.value === null ? "di-cq" : `di-c${(i % SERIES) + 1}`;
      if (frac >= 0.9999) {
        parts.push(`<circle class="${cls}" cx="${C}" cy="${C}" r="${R}"/>`);
      } else {
        const x0 = C + R * Math.cos(a0), y0 = C + R * Math.sin(a0);
        const x1 = C + R * Math.cos(a1), y1 = C + R * Math.sin(a1);
        parts.push(`<path class="${cls} di-slice" d="M${C} ${C}L${x0.toFixed(2)} ${y0.toFixed(2)}A${R} ${R} 0 ${frac > 0.5 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}Z"/>`);
      }
      if (frac >= 0.045) {
        const am = (a0 + a1) / 2, rr = R * 0.66;
        const txt = s.value === null ? MISSING : `${fmt(s.value)}${suffix}`;
        parts.push(`<text class="di-val di-in" x="${(C + rr * Math.cos(am)).toFixed(1)}" y="${(C + rr * Math.sin(am)).toFixed(1)}" text-anchor="middle" dominant-baseline="middle">${esc(txt)}</text>`);
      }
      a0 = a1;
    });

    const keys = slices
      .map((s, i) => `<span class="di-key"><i class="di-swatch ${s.value === null ? "di-cq" : `di-c${(i % SERIES) + 1}`}"></i>${esc(s.label)}: <b>${s.value === null ? MISSING : esc(fmt(s.value) + suffix)}</b></span>`)
      .join("");
    const total = isNum(item.total)
      ? `<div class="di-total">${esc(item.unit === "₹" ? `Total: ₹${fmt(item.total)}` : `Total: ${fmt(item.total)}${item.unit ? " " + item.unit : ""}`)}</div>`
      : "";
    const label = item.title || "Pie chart";
    const sr = srTable(["", deg ? "Degrees" : "Percent"], slices.map((s) => [s.label, s.value]));
    return `${head(item, false)}${total}<div class="di-pie"><svg class="di-svg di-svg-pie" viewBox="0 0 ${C * 2} ${C * 2}" role="img" aria-label="${esc(label)}">${parts.join("")}</svg><div class="di-legend di-legend-pie">${keys}</div></div>${sr}`;
  }

  /* -------------------------------------------------------------- API --- */
  /** Is there anything to draw? @param {any} data */
  function has(data) {
    return Array.isArray(data) && data.some((d) => d && typeof d === "object" && d.type);
  }

  /** Width to draw at when the caller does not know its container's width. */
  function guessWidth() {
    const vw = (typeof window !== "undefined" && window.innerWidth) || 640;
    return Math.min(720, vw - (vw < 640 ? 64 : 120));
  }

  /** HTML for a question's `data` list ("" when there is nothing to draw).
      @param {any} data @param {number} [width] drawing width in CSS px */
  function html(data, width) {
    if (!has(data)) return "";
    const w = width && width > 0 ? width - 26 : guessWidth();   // 26 = block padding + border
    return data
      .filter((d) => d && typeof d === "object")
      .map((d) => {
        let inner;
        try {
          inner = d.type === "table" ? table(d)
            : d.type === "bar" || d.type === "line" ? xy(d, d.type, w)
            : d.type === "pie" ? pie(d)
            : `<div class="di-error">Unknown data type: ${esc(d.type)}</div>`;
        } catch (e) {
          console.warn("[HOA] DI render failed", e);
          inner = `<div class="di-error">This data could not be drawn.</div>`;
        }
        return `<figure class="di-block di-kind-${esc(d.type)}">${inner}</figure>`;
      })
      .join("");
  }

  /* Boxes filled by render() are redrawn at their new width after a resize or
     rotation (graphs only; tables reflow by themselves). */
  /** @type {Map<HTMLElement, any>} */
  const live = new Map();
  let resizeTimer = 0;
  function redrawAll() {
    live.forEach((data, box) => {
      if (!box.isConnected) { live.delete(box); return; }
      const w = box.clientWidth;
      if (w && String(w) !== box.dataset.diWidth) { box.dataset.diWidth = String(w); box.innerHTML = html(data, w); }
    });
  }

  /** Fill (or empty and hide) a container. @param {HTMLElement | null} box @param {any} data */
  function render(box, data) {
    if (!box) return;
    if (!has(data)) { box.innerHTML = ""; box.hidden = true; live.delete(box); return; }
    box.hidden = false;
    const w = box.clientWidth || (box.parentElement && box.parentElement.clientWidth) || 0;
    box.dataset.diWidth = String(w);
    box.innerHTML = html(data, w);
    if (data.some((d) => d && (d.type === "bar" || d.type === "line"))) live.set(box, data); else live.delete(box);
  }

  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(redrawAll, 150);
  });

  window.HOA_DI = { html, render, has };
})();
