/* ============================================================================
 * contact.js | Contact form - static site friendly (opens the user's mail app)
 * No backend required. Swap `mailto:` for a Formspree endpoint later.
 * ========================================================================== */
(() => {
  "use strict";
  const form = document.getElementById("contactForm");
  if (!form) return;

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const name = String(data.get("name") || "").trim();
    const email = String(data.get("email") || "").trim();
    const topic = String(data.get("topic") || "General").trim();
    const msg = String(data.get("message") || "").trim();

    if (!name || !email || !msg) {
      HOA.toast("Please fill your name, email and message.");
      return;
    }

    const subject = encodeURIComponent(`[HOA Portal] ${topic} - ${name}`);
    const body = encodeURIComponent(
      `Name: ${name}\nEmail: ${email}\nTopic: ${topic}\n\n${msg}`
    );
    // Primary path: hand off to the visitor's mail client (works with zero backend).
    window.location.href = `mailto:contact@houseofaspirants.com?subject=${subject}&body=${body}`;
    HOA.toast("Opening your mail app… you can also DM us on Telegram 📨", 3200);
  });
})();
