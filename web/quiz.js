/* Quiz: 7 кроків, відповіді зберігаються в sessionStorage, події для Google Tag Manager у window.dataLayer. */
(function () {
  "use strict";

  const API = "/api";
  const STORE_KEY = "fixright_quiz_v1";
  const body = document.getElementById("quizBody");
  const backBtn = document.getElementById("backBtn");
  const progress = document.getElementById("progress");
  const stepLabel = document.getElementById("stepLabel");
  const stepHint = document.getElementById("stepHint");
  window.dataLayer = window.dataLayer || [];

  const ICONS = {
    fridge: '<rect x="11" y="4" width="26" height="40" rx="3"/><path d="M11 18h26M16 10v4M16 23v7"/>',
    washer: '<rect x="9" y="5" width="30" height="38" rx="3"/><circle cx="24" cy="27" r="10"/><path d="M9 13h30M15 9h3"/><path d="M18 28c2.5-2 4 2 6.5 0s4 2 5.5 0"/>',
    dryer: '<rect x="9" y="5" width="30" height="38" rx="3"/><circle cx="24" cy="27" r="10"/><circle cx="24" cy="27" r="5"/><path d="M9 13h30M31 9h3"/>',
    dishwasher: '<rect x="9" y="5" width="30" height="38" rx="3"/><path d="M9 14h30M14 9.5h8M15 22v14M21 22v14M27 22v14M33 22v14M13 36h22"/>',
    oven: '<rect x="8" y="5" width="32" height="38" rx="3"/><path d="M8 15h32"/><circle cx="14" cy="10" r="1.6"/><circle cx="20" cy="10" r="1.6"/><circle cx="26" cy="10" r="1.6"/><rect x="13" y="20" width="22" height="16" rx="2"/>',
    other: '<path d="M30.5 9.5a8 8 0 0 0-9.7 10.3L10.5 30.1a3 3 0 1 0 4.3 4.3l10.3-10.3a8 8 0 0 0 10.3-9.7l-4.6 4.6-3.9-1.1-1.1-3.9z"/>',
  };
  const CHECK = '<svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>';

  let cfg = null;
  let token = "";
  let step = 0;
  let state = load() || { answers: {}, step: 0 };
  step = state.step || 0;

  const STEPS = [
    { key: "appliance", render: stepAppliance },
    { key: "problem", render: stepProblem },
    { key: "brand", render: stepBrand },
    { key: "age", render: stepAge },
    { key: "urgency", render: stepUrgency },
    { key: "zip", render: stepZip },
    { key: "contact", render: stepContact },
  ];

  // ---------- helpers ----------
  function load() {
    try { return JSON.parse(sessionStorage.getItem(STORE_KEY)); } catch (e) { return null; }
  }
  function save() {
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify({ answers: state.answers, step })); } catch (e) { /* приватний режим */ }
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function track(event, data) { window.dataLayer.push(Object.assign({ event }, data || {})); }
  function appliance() { return cfg.appliances.find((a) => a.id === state.answers.appliance); }

  function utm() {
    const p = new URLSearchParams(location.search);
    const saved = state.answers.utm || {};
    const out = {};
    ["source", "medium", "campaign", "term", "content"].forEach((k) => { out[k] = p.get("utm_" + k) || saved[k] || ""; });
    out.gclid = p.get("gclid") || saved.gclid || "";
    return out;
  }

  function show(html) {
    body.innerHTML = '<div class="step">' + html + "</div>";
    const pct = Math.round((step / STEPS.length) * 100);
    progress.style.width = pct + "%";
    progress.parentElement.setAttribute("aria-valuenow", pct);
    stepLabel.textContent = step < STEPS.length ? `Step ${step + 1} of ${STEPS.length}` : "Done";
    stepHint.textContent = step < STEPS.length ? (STEPS.length - step <= 2 ? "Almost there" : "~1 minute") : "";
    backBtn.hidden = step === 0 || step >= STEPS.length;
  }

  function go(n) {
    step = Math.max(0, Math.min(n, STEPS.length));
    save();
    STEPS[step] ? STEPS[step].render() : null;
    track("quiz_step", { quiz_step: step + 1, quiz_step_name: STEPS[step] ? STEPS[step].key : "done" });
    const top = document.getElementById("quiz").getBoundingClientRect().top;
    if (top < 0) window.scrollBy({ top: top - 80, behavior: "smooth" });
  }

  function pick(key, value, next = true) {
    state.answers[key] = value;
    if (key === "appliance") delete state.answers.problem; // інша техніка — інші несправності
    save();
    body.querySelectorAll("[data-v]").forEach((b) => b.classList.toggle("on", b.dataset.v === value));
    if (next) setTimeout(() => go(step + 1), 180);
  }

  function bindPicks(key) {
    body.querySelectorAll("[data-v]").forEach((b) => b.addEventListener("click", () => pick(key, b.dataset.v)));
  }

  function summary() {
    const a = state.answers;
    const parts = [appliance() && appliance().label, a.problem, a.brand !== "Other / not sure" ? a.brand : ""].filter(Boolean);
    return '<div class="summary">' + parts.map((p) => `<span>${esc(p)}</span>`).join("") + "</div>";
  }

  // ---------- steps ----------
  function stepAppliance() {
    show(`<h2 class="q">What needs fixing?</h2><p class="q-sub">Pick the appliance — we'll take it from there.</p>
      <div class="tiles">${cfg.appliances.map((a) => `
        <button type="button" class="tile${state.answers.appliance === a.id ? " on" : ""}" data-v="${a.id}">
          <svg viewBox="0 0 48 48" aria-hidden="true">${ICONS[a.icon]}</svg>${esc(a.label)}</button>`).join("")}
      </div>`);
    bindPicks("appliance");
  }

  function stepProblem() {
    const a = appliance();
    if (!a) return go(0);
    show(`<h2 class="q">What's going on with your ${esc(a.label.toLowerCase())}?</h2><p class="q-sub">Choose the closest match.</p>
      <div class="opts">${a.problems.map((p) => `<button type="button" class="opt${state.answers.problem === p ? " on" : ""}" data-v="${esc(p)}">${esc(p)}</button>`).join("")}</div>`);
    bindPicks("problem");
  }

  function stepBrand() {
    show(`<h2 class="q">What brand is it?</h2><p class="q-sub">Helps the technician bring the right parts.</p>
      <div class="chips">${cfg.brands.map((b) => `<button type="button" class="chip${b.startsWith("Other") ? " wide" : ""}${state.answers.brand === b ? " on" : ""}" data-v="${esc(b)}">${esc(b)}</button>`).join("")}</div>`);
    bindPicks("brand");
  }

  function stepAge() {
    show(`<h2 class="q">How old is it?</h2><p class="q-sub">A rough guess is fine.</p>
      <div class="opts">${cfg.ages.map((x) => `<button type="button" class="opt${state.answers.age === x ? " on" : ""}" data-v="${esc(x)}">${esc(x)}</button>`).join("")}</div>`);
    bindPicks("age");
  }

  function stepUrgency() {
    const sub = { asap: "Same-day slots fill up by noon", quote: "No visit yet — just a price idea" };
    show(`<h2 class="q">When do you need a technician?</h2><p class="q-sub">We'll offer the nearest available window.</p>
      <div class="opts">${cfg.urgency.map((u) => `<button type="button" class="opt${state.answers.urgency === u.id ? " on" : ""}" data-v="${u.id}">
        <span>${esc(u.label)}${sub[u.id] ? `<small>${sub[u.id]}</small>` : ""}</span></button>`).join("")}</div>`);
    bindPicks("urgency");
  }

  function stepZip() {
    show(`<h2 class="q">What's your ZIP code?</h2><p class="q-sub">We'll check that a technician covers your area.</p>
      <div class="field"><input class="input zip" id="zip" inputmode="numeric" autocomplete="postal-code" maxlength="5" placeholder="78704" value="${esc(state.answers.zip || "")}" aria-label="ZIP code"></div>
      <div id="zipNote"></div>
      <button type="button" class="btn" id="zipNext">Continue</button>`);
    const input = document.getElementById("zip");
    const note = document.getElementById("zipNote");
    const nextBtn = document.getElementById("zipNext");
    let checked = "";
    input.focus();
    input.addEventListener("input", () => {
      input.value = input.value.replace(/\D/g, "").slice(0, 5);
      input.classList.remove("bad");
      if (input.value.length === 5) check();
      else { note.innerHTML = ""; checked = ""; }
    });
    async function check() {
      const zip = input.value;
      if (checked === zip) return true;
      try {
        const r = await fetch(`${API}/zip/${zip}`).then((x) => x.json());
        checked = zip;
        note.innerHTML = r.in_area
          ? `<div class="note ok">✓ Great news — we have technicians near ${zip}.</div>`
          : `<div class="note warn">We may not cover ${zip} yet. Leave your details and we'll check with partners nearby.</div>`;
        state.answers.in_area = r.in_area;
      } catch (e) { checked = zip; }
      return true;
    }
    nextBtn.addEventListener("click", async () => {
      if (!/^\d{5}$/.test(input.value)) { input.classList.add("bad"); note.innerHTML = '<div class="err">Enter a 5-digit ZIP code</div>'; return; }
      await check();
      state.answers.zip = input.value;
      go(step + 1);
    });
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") nextBtn.click(); });
    if (input.value.length === 5) check();
  }

  function formatPhone(v) {
    let d = v.replace(/\D/g, "");
    if (d.length > 10 && d[0] === "1") d = d.slice(1);
    d = d.slice(0, 10);
    if (d.length < 4) return d.length ? `(${d}` : "";
    if (d.length < 7) return `(${d.slice(0, 3)}) ${d.slice(3)}`;
    return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
  }

  function stepContact() {
    const a = state.answers;
    show(`<h2 class="q">Where should we send your estimate?</h2><p class="q-sub">A dispatcher will call to confirm the time — no spam, ever.</p>
      ${summary()}
      <form id="leadForm" novalidate>
        <div class="field"><label for="name">Your name</label>
          <input class="input" id="name" name="name" autocomplete="name" placeholder="John Smith" value="${esc(a.name || "")}"><div class="err" data-for="name"></div></div>
        <div class="field"><label for="phone">Mobile phone</label>
          <input class="input" id="phone" name="phone" type="tel" inputmode="tel" autocomplete="tel-national" placeholder="(512) 555-0123" value="${esc(a.phone || "")}"><div class="err" data-for="phone"></div></div>
        <div class="field"><label for="email">Email <small>(optional)</small></label>
          <input class="input" id="email" name="email" type="email" autocomplete="email" placeholder="you@example.com" value="${esc(a.email || "")}"><div class="err" data-for="email"></div></div>
        <div class="hp" aria-hidden="true"><label>Website <input name="website" tabindex="-1" autocomplete="off"></label></div>
        <label class="check"><input type="checkbox" id="consent" ${a.consent ? "checked" : ""}>
          <span>I agree that FixRight may call or text me at this number about my repair request. Consent is not a condition of purchase. Msg &amp; data rates may apply.</span></label>
        <div class="err" data-for="consent"></div>
        <div class="err" data-for="form"></div>
        <button class="btn" type="submit" id="submitBtn">Get my estimate</button>
      </form>`);
    const form = document.getElementById("leadForm");
    const phone = document.getElementById("phone");
    phone.addEventListener("input", () => { phone.value = formatPhone(phone.value); });
    // помилку поля прибираємо, щойно користувач почав його виправляти
    form.addEventListener("input", (e) => {
      const key = e.target.id;
      e.target.classList.remove("bad");
      const err = body.querySelector(`.err[data-for="${key}"]`);
      if (err) err.textContent = "";
    });
    ["name", "phone", "email"].forEach((id) => document.getElementById(id).addEventListener("change", (e) => { state.answers[id] = e.target.value; save(); }));
    form.addEventListener("submit", submit);
  }

  function setErrors(errors) {
    body.querySelectorAll(".err[data-for]").forEach((el) => { el.textContent = errors[el.dataset.for] || ""; });
    body.querySelectorAll(".input").forEach((el) => el.classList.toggle("bad", !!errors[el.name]));
    const first = Object.keys(errors).find((k) => document.getElementById(k));
    if (first) document.getElementById(first).focus();
  }

  function validate(data) {
    const e = {};
    if (data.name.trim().length < 2) e.name = "Please enter your name";
    if (data.phone.replace(/\D/g, "").replace(/^1(?=\d{10}$)/, "").length !== 10) e.phone = "Enter a 10-digit US phone number";
    if (data.email && !/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(data.email)) e.email = "Enter a valid email or leave it empty";
    if (!data.consent) e.consent = "Please check the box so we can contact you";
    return e;
  }

  async function submit(ev) {
    ev.preventDefault();
    const form = ev.target;
    const btn = document.getElementById("submitBtn");
    const a = state.answers;
    const data = {
      appliance: a.appliance, problem: a.problem, brand: a.brand, age: a.age, urgency: a.urgency, zip: a.zip,
      name: form.name.value.trim(), phone: form.phone.value, email: form.email.value.trim(),
      consent: document.getElementById("consent").checked, website: form.website.value,
      utm: utm(), page_url: location.href.slice(0, 500), form_token: token,
    };
    const errors = validate(data);
    setErrors(errors);
    if (Object.keys(errors).length) return;
    btn.disabled = true;
    btn.textContent = "Sending…";
    try {
      const r = await fetch(`${API}/leads`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
      const res = await r.json().catch(() => ({}));
      if (r.ok && res.ok) {
        track("lead_submitted", { lead_id: res.id, appliance: data.appliance, urgency: data.urgency, in_service_area: res.in_area });
        try { sessionStorage.removeItem(STORE_KEY); } catch (e) { /* ignore */ }
        return done(res, data);
      }
      if (res.errors) {
        // помилка в попередніх кроках (ZIP тощо) — повертаємо туди
        const stepFor = { appliance: 0, problem: 1, brand: 2, age: 3, urgency: 4, zip: 5 };
        const k = Object.keys(res.errors).find((x) => x in stepFor);
        if (k) return go(stepFor[k]);
        setErrors(res.errors);
      } else {
        setErrors({ form: res.error || "Something went wrong. Please try again or call us at (512) 555-0100." });
        if (r.status === 400) refreshToken();
      }
    } catch (e) {
      setErrors({ form: "No connection. Please check your internet and try again." });
    }
    btn.disabled = false;
    btn.textContent = "Get my estimate";
  }

  function done(res, data) {
    step = STEPS.length;
    const first = esc(data.name.split(" ")[0]);
    const when = cfg.urgency.find((u) => u.id === data.urgency).label;
    const msg = data.urgency === "quote"
      ? "We'll call you shortly with a price range for this repair."
      : res.in_area ? "A dispatcher will call you within 15 minutes (7am–9pm) to confirm your arrival window."
        : "We'll check coverage for your ZIP code and call you back today.";
    show(`<div class="done"><div class="done__icon">${CHECK}</div>
      <h3>Thanks, ${first}! You're all set.</h3><p>${msg}</p>
      <dl class="ticket">
        <div><span>Request</span><b>#${res.id}</b></div>
        <div><span>Appliance</span><b>${esc(appliance().label)} · ${esc(data.problem)}</b></div>
        <div><span>When</span><b>${esc(when)}</b></div>
        <div><span>We'll call</span><b>${esc(formatPhone(data.phone))}</b></div>
      </dl>
      <p style="font-size:14px">Need help right now? Call <a href="tel:+15125550100"><b>(512) 555-0100</b></a></p></div>`);
    progress.style.width = "100%";
  }

  async function refreshToken() {
    try { token = (await fetch(`${API}/token`).then((r) => r.json())).token; } catch (e) { /* відправка поверне помилку */ }
  }

  backBtn.addEventListener("click", () => go(step - 1));

  // ---------- старт ----------
  (async function init() {
    try {
      [cfg] = await Promise.all([fetch(`${API}/quiz`).then((r) => r.json()), refreshToken()]);
    } catch (e) {
      body.innerHTML = '<p class="q-sub">Couldn\'t load the form. Please call us at <b>(512) 555-0100</b>.</p>';
      return;
    }
    state.answers.utm = utm();
    if (step >= STEPS.length) step = 0;
    go(step);
  })();
})();
