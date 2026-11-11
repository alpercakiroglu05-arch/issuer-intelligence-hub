/* Issuer Intelligence Hub, web front end.  OWNER: C3.
   Every number comes from the engine through web/server.py (/api/*). Words come from the LLM or the template fallback.
   One home per requirement (docs/REQUIREMENTS.md): Dashboard = trading profile (I, II, III), Impact card = event impact
   (V, VI, own calendar import) + AI summary, Compare = VII, Report = IV/VIII (all exports), Ideas = next ideas + data.
   The IR analyst (agent dock, ai/agent.py) is on every page and can open any of them with one click. */
"use strict";

/* ============================== helpers ============================== */
const $ = s => document.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const S = {lang: "en", uni: [], status: null, isin: null, iss: null, page: "dashboard", sel: null, cards: {}, ai: {},
  cmp: {type: null, index: "ALL", data: null}, chat: [], metric: "turnover", dock: false, busy: false, addEv: false,
  rep: {a: true, peers: true, liq: true, anom: true, card: true, ai: true, key: null}};
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const de = () => S.lang === "de";
const L = (en, d) => de() ? d : en;
const NA = "–";
const isN = v => v !== null && v !== undefined && typeof v === "number" && !Number.isNaN(v);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const nf = (v, d = 1) => new Intl.NumberFormat(de() ? "de-DE" : "en-GB", {minimumFractionDigits: d, maximumFractionDigits: d}).format(Math.abs(v));
const sg = (v, s) => v < 0 ? "−" : (s && v > 0 ? "+" : "");
function P(x, d = 1, s = true) { if (!isN(x)) return NA; const v = x * 100, rv = Math.round(v * 10 ** d) / 10 ** d; return sg(rv, s) + nf(v, d) + (de() ? " %" : "%"); }
const X = (v, d = 1) => isN(v) ? nf(v, d) + "×" : NA;
const BPS = (v, d = 1) => isN(v) ? nf(v, d) + (de() ? " Bp." : " bps") : NA;
const N0 = v => isN(v) ? new Intl.NumberFormat(de() ? "de-DE" : "en-GB").format(Math.round(v)) : NA;
function EUR(v, d = 1) {
  if (!isN(v)) return NA;
  const a = Math.abs(v); let n = v, u = "";
  if (a >= 1e9) { n = v / 1e9; u = de() ? " Mrd. €" : "bn"; } else if (a >= 1e6) { n = v / 1e6; u = de() ? " Mio. €" : "m"; }
  else if (a >= 1e3) { n = v / 1e3; u = de() ? " Tsd. €" : "k"; d = 0; } else { u = de() ? " €" : ""; d = 0; }
  return de() ? sg(n) + nf(n, d) + u : sg(n) + "€" + nf(n, d) + u;
}
const PX = v => isN(v) ? (de() ? nf(v, 2) + " €" : "€" + nf(v, 2)) : NA;
const MS = [["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."]];
const ML = [["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]];
function dS(s) { if (!s) return NA; const [, m, d] = String(s).slice(0, 10).split("-").map(Number); return de() ? `${d}. ${MS[1][m - 1]}` : `${d} ${MS[0][m - 1]}`; }
function dL(s) { if (!s) return NA; const [y, m, d] = String(s).slice(0, 10).split("-").map(Number); return de() ? `${d}. ${ML[1][m - 1]} ${y}` : `${d} ${ML[0][m - 1]} ${y}`; }
const f1 = n => (Math.round(n * 10) / 10).toString();
const ARR = `<svg class="arr" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M2 8h11M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
const arrow = (deg, cls = "nt") => `<svg class="ar ${cls}" viewBox="0 0 16 16" style="transform:rotate(${deg}deg)" aria-hidden="true"><path d="M2.5 8h10.5M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>`;
const arrRel = (a, b) => { if (!isN(a) || !isN(b) || !b) return ""; const r = a / b; return arrow(r > 1.25 ? -90 : r > 1.05 ? -45 : r < .8 ? 90 : r < .95 ? 45 : 0); };
const arrRet = v => !isN(v) ? "" : arrow(v > .015 ? -90 : v > .003 ? -45 : v < -.015 ? 90 : v < -.003 ? 45 : 0, v > .003 ? "up" : v < -.003 ? "dn" : "nt");
const enc = s => encodeURIComponent(s);
const median = a => { const b = a.filter(isN).sort((x, y) => x - y); return b.length ? b[Math.floor(b.length / 2)] : null; };
const roll = (a, w) => a.map((_, i) => median(a.slice(Math.max(0, i - w + 1), i + 1)));
const minOf = t => { const [h, m] = t.split(":").map(Number); return (h - 9) * 60 + m; };

/* readable company names from exchange short names ("CTS EVENTIM KGAA" -> "CTS Eventim") */
const NAMES = {EVD: "CTS Eventim", EVT: "Evotec", HDD: "Heidelberger Druck", GXI: "Gerresheimer", SAP: "SAP", ENR: "Siemens Energy", RHM: "Rheinmetall", DB1: "Deutsche Börse", DBK: "Deutsche Bank", MUV2: "Munich Re", ALV: "Allianz", SIE: "Siemens", IFX: "Infineon", DTE: "Deutsche Telekom", BAS: "BASF", BAYN: "Bayer", BMW: "BMW", MBG: "Mercedes-Benz Group", VOW3: "Volkswagen", ADS: "adidas", AIR: "Airbus", DHL: "DHL Group", EOAN: "E.ON", RWE: "RWE", MRK: "Merck", HEN3: "Henkel", BEI: "Beiersdorf", ZAL: "Zalando", VNA: "Vonovia", CBK: "Commerzbank", HNR1: "Hannover Rück", MTX: "MTU Aero Engines", SHL: "Siemens Healthineers", FRE: "Fresenius", FME: "Fresenius Medical Care", CON: "Continental", DTG: "Daimler Truck", QIA: "Qiagen", SY1: "Symrise", HEI: "Heidelberg Materials", BNR: "Brenntag", G1A: "GEA Group", G24: "Scout24", HOT: "Hochtief"};
const DROP = new Set(["O.N.", "O.N", "ON", "INH", "INH.", "NA", "NA.", "VNA", "NAM.", "NAM", "EO", "SP.ADR", "VZO", "ST", "ST.", "+", "-", "CO.", "KGAA", "SE", "AG", "&"]);
function nice(u) {
  if (!u) return "";
  if (NAMES[u.ticker]) return NAMES[u.ticker];
  const w = String(u.name).replace(/\.?(INH|O\.N|NAM|VNA)\.?(?=\s|$)/gi, "").replace(/\s+/g, " ").split(" ").filter(t => t && !DROP.has(t.toUpperCase()) && !/\d/.test(t));
  return w.map(t => t.length <= 3 ? t : t.charAt(0) + t.slice(1).toLowerCase()).join(" ").replace(/\.$/, "") || u.ticker;
}
const U = isin => S.uni.find(u => u.isin === isin);

async function api(path, opt) {
  const r = await fetch(path, opt);
  const j = await r.json().catch(() => ({error: r.statusText}));
  if (!r.ok) throw new Error(j.error || r.status);
  return j;
}
const post = (p, b) => api(p, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(b)});

function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.add("on"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("on"), 2000); }
function vt(fn) {
  let done = false; const run = () => { if (!done) { done = true; fn(); } };
  if (document.startViewTransition && !reduced && !document.hidden) {
    const t = document.startViewTransition(run); [t.ready, t.finished, t.updateCallbackDone].forEach(p => p.catch(e => console.warn("view transition:", e)));
    setTimeout(() => { if (!done) { t.skipTransition && t.skipTransition(); run(); } }, 1200);   /* never leave the page stuck on a stalled transition */
    return t;
  }
  run(); const c = $("#app .content"); c && c.classList.add("enter");
}

/* ISIN check digit (ISO 6166): letters -> numbers (A=10), Luhn over the digit string */
function isinValid(s) {
  if (!/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(s)) return false;
  const digits = s.split("").map(c => /[A-Z]/.test(c) ? String(c.charCodeAt(0) - 55) : c).join("");
  let sum = 0, dbl = false;
  for (let i = digits.length - 1; i >= 0; i--) { let n = +digits[i]; if (dbl) { n *= 2; if (n > 9) n -= 9; } sum += n; dbl = !dbl; }
  return sum % 10 === 0;
}
function search(q, max = 7) {
  q = q.trim().toLowerCase(); if (!q) return S.uni.filter(u => u.hero).slice(0, max);
  const sc = u => {
    const n = nice(u).toLowerCase(), t = u.ticker.toLowerCase(), i = u.isin.toLowerCase();
    if (i === q || t === q) return 100; if (i.startsWith(q)) return 80; if (t.startsWith(q)) return 70;
    if (n.startsWith(q)) return 60; if (n.includes(q) || u.name.toLowerCase().includes(q)) return 40; if (i.includes(q)) return 30; return 0;
  };
  return S.uni.map(u => [sc(u), u]).filter(x => x[0] > 0).sort((a, b) => b[0] - a[0] || b[1].avg_turnover_eur - a[1].avg_turnover_eur).slice(0, max).map(x => x[1]);
}
const suggRow = (u, i, sel) => `<li role="option" data-isin="${u.isin}" aria-selected="${i === sel}"><span class="tk">${esc(u.ticker)}</span><span class="nm"><b>${esc(nice(u))}</b><small>${u.isin}</small></span><span class="ix">${u.index}${u.member_now ? "" : "*"}</span></li>`;

/* ============================== gate (ISIN entry) ============================== */
const G = {sel: 0, list: []};
function gateText() {
  $("#g-kicker").textContent = L("Issuer Intelligence Hub · Xetra 2026", "Issuer Intelligence Hub · Xetra 2026");
  const words = L("Decode your share.", "Verstehen Sie Ihre Aktie.").split(" ");
  $("#g-title").innerHTML = words.map((w, i) => `<span class="w"><span style="--i:${i}">${esc(w)}</span></span>`).join(" ");
  const days = S.status ? 213 : 213;
  $("#g-sub").textContent = L(`Enter your company's ISIN. The hub reads ${days} trading days of Xetra data for it: volume, spreads, auctions, who trades, and how the share reacted to every announcement.`,
    `Geben Sie die ISIN Ihres Unternehmens ein. Der Hub liest dafür ${days} Handelstage an Xetra: Umsatz, Spreads, Auktionen, wer handelt, und wie die Aktie auf jede Meldung reagiert hat.`);
  $("#g-in").placeholder = L("e.g. DE0005470306, EVD or CTS Eventim", "z. B. DE0005470306, EVD oder CTS Eventim");
  $("#g-go-t").textContent = L("Open panel", "Panel öffnen");
  const heroes = S.uni.filter(u => u.hero);
  $("#g-picks").innerHTML = `<span>${L("Showcase shares:", "Beispielaktien:")}</span>` + heroes.map(u => `<button type="button" data-pick="${u.isin}"><b>${u.ticker}</b>${esc(nice(u))}</button>`).join("");
  $$(".lang button").forEach(b => b.setAttribute("aria-pressed", b.dataset.v === S.lang));
  anatomy($("#g-in").value);
}
function gateBg() {
  const W = 1440, H = 900, svg = $("#gate-bg"); svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  let out = "";
  for (let k = 0; k < 22; k++) {
    let y = H * (.45 + rnd() * .4); let d = `M0,${f1(y)}`;
    for (let x = 0; x <= W; x += 12) { y += (rnd() - .5) * 18 + (k === 9 && x > W * .55 && x < W * .6 ? 9 : 0); d += `L${x},${f1(y)}`; }
    out += `<path d="${d}" pathLength="1" class="${k === 9 ? "hot" : ""}" style="animation-delay:${(k * .06).toFixed(2)}s"/>`;
  }
  svg.innerHTML = out;
}
function gateTape() {
  const items = S.uni.map(u => `<span><b>${u.ticker}</b> ${u.isin} · ${u.index}</span>`).join("");
  $("#g-tape").innerHTML = `<div class="run">${items}${items}</div>`;
}
function anatomy(raw) {
  const q = raw.replace(/\s+/g, "").toUpperCase();
  const typing = /^[A-Z]{1,2}([A-Z0-9]{0,10})$/.test(q) && (/\d/.test(q) || q.length <= 2) && q.length <= 12;
  let code = "", match = null;
  if (typing) { code = q; match = S.uni.find(u => u.isin === q) || null; }
  else if (G.list[G.sel]) { match = G.list[G.sel]; code = match.isin; }
  const full = code.length === 12, ok = full && isinValid(code);
  const cell = (i) => { const c = code[i] || ""; return `<span class="cell ${c ? "on" : ""} ${full ? (ok ? "ok" : "bad") : ""}" style="--i:${i}">${c}</span>`; };
  const grp = (from, to, cap) => `<div class="grp"><div class="cells">${Array.from({length: to - from}, (_, k) => cell(from + k)).join("")}</div><span class="cap">${cap}</span></div>`;
  let verdict = "";
  if (full && ok && match) verdict = `<b>${esc(nice(match))}</b> · ${match.index} · ${L("check digit ✓", "Prüfziffer ✓")}`;
  else if (full && ok) verdict = L("Valid ISIN, but not a DAX, MDAX or SDAX share in 2026.", "Gültige ISIN, aber 2026 nicht in DAX, MDAX oder SDAX.");
  else if (full) verdict = L("The check digit does not match. Please check the code.", "Die Prüfziffer passt nicht. Bitte Code prüfen.");
  else verdict = L("12 characters: country, national ID, check digit.", "12 Zeichen: Land, nationale Kennung, Prüfziffer.");
  const prev = $("#g-anat").dataset.code;
  if (prev === code + "|" + S.lang) return;
  $("#g-anat").dataset.code = code + "|" + S.lang;
  $("#g-anat").innerHTML = grp(0, 2, L("Country", "Land")) + grp(2, 11, L("National ID (NSIN)", "Nationale Kennung (NSIN)")) + grp(11, 12, L("Check", "Prüfz.")) + `<div class="verdict">${verdict}</div>`;
}
function gateSugg() {
  const q = $("#g-in").value;
  G.list = search(q); G.sel = Math.min(G.sel, Math.max(0, G.list.length - 1));
  const el = $("#g-sugg");
  el.innerHTML = G.list.map((u, i) => suggRow(u, i, G.sel)).join("") || `<li class="m" style="display:block">${L("No DAX, MDAX or SDAX share matches.", "Keine passende DAX-, MDAX- oder SDAX-Aktie.")}</li>`;
  el.classList.toggle("on", document.activeElement === $("#g-in") && q.trim().length > 0);
  anatomy(q);
}
function resolveGate() {
  const q = $("#g-in").value.replace(/\s+/g, "").toUpperCase();
  const exact = S.uni.find(u => u.isin === q || u.ticker === q);
  if (exact) return exact;
  if (/^[A-Z]{2}[A-Z0-9]{10}$/.test(q)) return null;
  return G.list[G.sel] || null;
}
async function openIsin(isin, {fromGate = true, then = null} = {}) {
  const u = U(isin); if (!u) return;
  const steps = [L("Reading 213 trading days on Xetra", "213 Xetra-Handelstage werden gelesen"), L("Benchmarking against index, similar-size stocks and sector", "Vergleich mit Index, ähnlich großen Aktien und Sektor"),
    L("Finding unusual days and matching the event calendar", "Auffällige Tage finden und mit dem Kalender abgleichen"), L("Preparing your dashboard", "Ihr Dashboard wird vorbereitet")];
  let timer;
  if (fromGate) {
    $("#gl-nm").textContent = nice(u);
    $("#gl-steps").innerHTML = steps.map(s => `<li><i></i>${esc(s)}</li>`).join("");
    $("#g-load").classList.add("on");
    let k = 0; const tick = () => { $$("#gl-steps li").forEach((li, i) => { li.classList.toggle("on", i === k); li.classList.toggle("done", i < k); }); $("#gl-bar").style.width = Math.min(92, (k + 1) * 23) + "%"; k = Math.min(steps.length - 1, k + 1); };
    tick(); timer = setInterval(tick, reduced ? 50 : 420);
  }
  try {
    const t0 = performance.now();
    const iss = await api(`/api/issuer?isin=${isin}`);
    if (fromGate) { const wait = Math.max(0, (reduced ? 0 : 1500) - (performance.now() - t0)); await new Promise(r => setTimeout(r, wait)); }
    clearInterval(timer);
    if (fromGate) { $$("#gl-steps li").forEach(li => { li.classList.remove("on"); li.classList.add("done"); }); $("#gl-bar").style.width = "100%"; await new Promise(r => setTimeout(r, reduced ? 0 : 250)); }
    const changed = S.isin !== isin;
    S.isin = isin; S.iss = iss; mergeUserEvents(); if (changed) { S.sel = null; S.chat = []; S.rep.key = null; }
    if (then) then();
    vt(() => { $("#gate").classList.add("hidden"); $("#g-load").classList.remove("on"); $("#ws").classList.remove("hidden"); render(); window.scrollTo(0, 0); });
  } catch (e) {
    clearInterval(timer); $("#g-load").classList.remove("on");
    $("#g-err").textContent = L("Could not load this share: ", "Laden fehlgeschlagen: ") + e.message;
    if (!fromGate) toast(e.message);
  }
}
function backToGate() {
  S.dock = false; $("#dock").classList.add("hidden");
  vt(() => { $("#ws").classList.add("hidden"); $("#gate").classList.remove("hidden"); $("#g-in").value = ""; $("#g-err").textContent = ""; gateText(); history.replaceState(null, "", "#"); });
  setTimeout(() => $("#g-in").focus(), 400);
}

/* ============================== chrome ============================== */
const PAGES = ["dashboard", "card", "compare", "report", "ideas"];
const NAV = {dashboard: ["Dashboard", "Übersicht"], card: ["Impact card", "Impact Card"], compare: ["Compare", "Vergleich"], report: ["IR snapshot", "IR-Snapshot"], ideas: ["Ideas", "Ideen"]};
const nav = p => NAV[p][de() ? 1 : 0];
function chrome() {
  document.documentElement.lang = S.lang;
  const u = U(S.isin);
  $("#nav").innerHTML = PAGES.map((p, i) => `<button data-go="${p}" ${S.page === p ? 'aria-current="page"' : ""}><span class="n">0${i + 1}</span>${nav(p)}</button>`).join("") + `<span class="nav-ind" id="navind"></span>`;
  placeInd();
  $$(".lang button").forEach(b => b.setAttribute("aria-pressed", b.dataset.v === S.lang));
  const m = S.iss.meta;
  $("#stamp").innerHTML = L(`Xetra data as of the close on <b>${dL(m.last_date)}</b> · ${m.days} trading days since ${dS(m.first_date)} · ${S.uni.length} shares`, `Xetra-Daten bis Handelsschluss <b>${dL(m.last_date)}</b> · ${m.days} Handelstage seit ${dS(m.first_date)} · ${S.uni.length} Aktien`);
  const live = S.status && S.status.llm;
  $("#ai-dot").classList.toggle("on", !!live);
  $("#ai-dot span").textContent = live ? L(`AI: ${S.status.model}`, `KI: ${S.status.model}`) : L("AI: template mode", "KI: Vorlagenmodus");
  $("#co").innerHTML = `<button class="co-btn" data-act="co" aria-expanded="false" aria-haspopup="true"><span class="tk">${u.ticker}</span><span><b>${esc(nice(u))}</b><small>${u.isin} · ${u.index}</small></span><svg class="chev" width="14" height="14" viewBox="0 0 16 16"><path d="M3 6l5 5 5-5" fill="none" stroke="currentColor" stroke-width="2"/></svg></button>
    <div class="co-pop" id="co-pop"><input id="co-in" placeholder="${L("Switch company: ISIN, ticker or name", "Unternehmen wechseln: ISIN, Ticker oder Name")}" autocomplete="off" spellcheck="false"><ul class="sugg" id="co-sugg"></ul><button class="back" data-act="gate">${L("Back to ISIN entry", "Zurück zur ISIN-Eingabe")} ${ARR}</button></div>`;
  const li = (t, go) => `<li><svg width="14" height="14" viewBox="0 0 16 16"><path d="M2 8h11M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="2"/></svg>${go ? `<a href="#" data-go="${go}">${t}</a>` : `<span>${t}</span>`}</li>`;
  $("#foot").innerHTML = `<div class="fcols">
    <div><h4>Issuer Intelligence Hub</h4><ul>${PAGES.map(p => li(nav(p), p)).join("")}</ul></div>
    <div><h4>${L("Data", "Daten")}</h4><ul>${li("Xetra OHLC & auctions")}${li("Xetra flow dynamics")}${li("Xetra Liquidity Measure (XLM)")}${li("Xetra on-book trades (1-min bars)")}${li(L("Index constituents · event calendar", "Indexlisten · Ereigniskalender"))}</ul></div>
    <div><h4>${L("Method", "Methode")}</h4><ul>${li(L("Numbers come from the engine", "Zahlen kommen aus der Engine"))}${li(L("Words come from the LLM", "Texte kommen vom LLM"))}${li(L("Every figure in a text is checked", "Jede Zahl im Text wird geprüft"))}${li(L("Causes are verified by people", "Ursachen prüfen Menschen"))}</ul></div>
    <div><h4>${L("Project", "Projekt")}</h4><ul>${li("Futury Build Days #4, Frankfurt")}${li(L("Deutsche Börse challenge", "Deutsche-Börse-Challenge"))}${li(L("A module for the Issuer Services Hub", "Ein Modul für den Issuer Services Hub"))}</ul></div></div>
    <div class="fbot"><span>${L("Concept prototype for Futury Build Days 2026. Not an official Deutsche Börse product. Not investment advice.", "Konzept-Prototyp für Futury Build Days 2026. Kein offizielles Produkt der Deutschen Börse. Keine Anlageberatung.")}</span><span>${L("Keys", "Tasten")}: 1–5 · A ${L("analyst", "Analyst")}</span></div>`;
}
function placeInd() { const a = $("#nav [aria-current=page]"), i = $("#navind"); if (!a || !i) return; i.style.left = a.offsetLeft + "px"; i.style.width = a.offsetWidth + "px"; }
function segThumb() { $$(".seg").forEach(g => { const b = g.querySelector("[aria-pressed=true]"), th = g.querySelector(".th"); if (b && th) { th.style.left = b.offsetLeft + "px"; th.style.width = b.offsetWidth + "px"; } }); }
const seg = (act, opts, cur) => `<div class="seg"><span class="th"></span>${opts.map(([v, t]) => `<button data-act="${act}" data-v="${v}" aria-pressed="${v === cur}">${t}</button>`).join("")}</div>`;
function setHash() { const s = S.sel; history.replaceState(null, "", `#/${S.isin}/${S.page}${s && S.page === "card" ? `/${s.day}${s.event_id ? "/" + s.event_id : ""}` : ""}`); }

/* ============================== bands ============================== */
function band() {
  const u = U(S.isin), name = nice(u);
  if (S.page === "dashboard") return dashBand(u, name);
  const t = {
    card: [L("Impact card", "Impact Card"), L("Pick an announcement or an unusual day, or add your own calendar. The card shows how the share reacted, measured against its own normal state.", "Wählen Sie eine Meldung oder einen auffälligen Tag, oder ergänzen Sie Ihren eigenen Kalender. Die Karte zeigt die Reaktion der Aktie im Vergleich zu ihrem Normalzustand.")],
    compare: [L("Compare events", "Ereignisse vergleichen"), L("Every event of the same type across DAX, MDAX and SDAX in 2026, measured with the card's own definitions.", "Alle Ereignisse desselben Typs in DAX, MDAX und SDAX 2026, gemessen mit den Definitionen der Karte.")],
    report: [L("IR snapshot", "IR-Snapshot"), L("Build a one-page report for the board or investors, in English or German.", "Ein einseitiger Bericht für Vorstand oder Investoren, auf Deutsch oder Englisch.")],
    ideas: [L("What IR needs next", "Was IR als Nächstes braucht"), L("Ideas built on the same data, and the data each one still needs.", "Ideen auf derselben Datenbasis, und welche Daten jeweils noch fehlen.")]
  }[S.page];
  return `<section class="band"><div class="wrap band-in"><div class="kicker">${esc(name)} · <b>${u.isin}</b></div><h1>${t[0]}</h1><p class="lede">${t[1]}</p></div></section>`;
}
function dashBand(u, name) {
  const k = S.iss.kpis, lt = S.iss.liquidity, s = S.iss.series;
  const prices = s.price.filter(isN), last = prices[prices.length - 1], first = prices[0];
  const to = k.median_turnover_eur, xl = k.median_xlm_25k_bps, cat = k.liquidity_check.category_estimate;
  const vw = {improved: L("improved", "verbessert"), worsened: L("worsened", "verschlechtert"), mixed: L("mixed", "gemischt"), stable: L("stable", "stabil")}[lt.verdict] || L("open", "offen");
  const lede = L(`Over the 60 trading days to ${dS(S.iss.meta.last_date)} ${esc(name)} traded a median of <b>${EUR(to.stock)}</b> a day (${S.iss.meta.index} median ${EUR(to.index_median)}) at a trading cost of <b>${BPS(xl.stock)}</b> for a €25k order (index ${BPS(xl.index_median)}). Liquidity has <b>${vw === "stable" ? "stayed stable" : vw}</b> compared with the 60 days before.`,
    `In den 60 Handelstagen bis ${dS(S.iss.meta.last_date)} handelte ${esc(name)} im Median <b>${EUR(to.stock)}</b> pro Tag (${S.iss.meta.index}-Median ${EUR(to.index_median)}) bei Handelskosten von <b>${BPS(xl.stock)}</b> für eine 25-T€-Order (Index ${BPS(xl.index_median)}). Die Liquidität ist im Vergleich zu den 60 Tagen davor <b>${vw}</b>.`);
  return `<section class="band"><div class="wrap band-in">
    <div class="kicker">${u.index} · ISIN <b>${u.isin}</b> · Xetra${u.sector ? " · " + esc(u.sector) : ""}</div>
    <h1>${esc(name)}</h1><p class="lede">${lede}</p>
    <p class="band-acts"><a class="pill" href="/api/export?isin=${u.isin}&lang=${S.lang}" download>${L("Export IR report (PDF)", "IR-Report exportieren (PDF)")} ↓</a></p>
    <dl class="facts">
      <div><dt>${L("Closing auction", "Schlussauktion")} · ${dL(S.iss.meta.last_date)}</dt><dd>${PX(last)}</dd></div>
      <div><dt>${L("Since 2 Jan", "Seit 2. Jan.")}</dt><dd>${P(last / first - 1)}</dd></div>
      <div><dt>${L("Liquidity trend", "Liquiditätstrend")}</dt><dd>${vw.charAt(0).toUpperCase() + vw.slice(1)}</dd></div>
      <div><dt>${L("Xetra category (est.)", "Xetra-Kategorie (Schätz.)")}</dt><dd>${cat}<small>${cat === "A" ? L("no Designated Sponsor needed", "kein Designated Sponsor nötig") : L("Designated Sponsor needed", "Designated Sponsor nötig")}</small></dd></div>
      <div><dt>${L("Unusual days in 2026", "Auffällige Tage 2026")}</dt><dd>${S.iss.anomalies.length}</dd></div>
    </dl></div></section>`;
}

/* ============================== 1 dashboard: trading profile ============================== */
const METRICS = () => [["turnover", L("Turnover", "Umsatz")], ["xlm", L("Spread & cost (XLM)", "Spread & Kosten (XLM)")], ["auction", L("Auctions", "Auktionen")], ["who", L("Who trades", "Wer handelt")], ["price", L("Price", "Kurs")]];
function pDashboard() {
  const iss = S.iss, idx = iss.meta.index;
  const note = {turnover: L(`Daily order-book turnover. Grey line: ${idx} median. Blue bars: unusual days.`, `Täglicher Orderbuch-Umsatz. Graue Linie: ${idx}-Median. Blaue Balken: auffällige Tage.`),
    xlm: L(`Xetra Liquidity Measure (XLM): what it costs to buy and sell €25k at once, spread plus price impact, in basis points. Lower is cheaper. Grey: ${idx} median.`, `Xetra Liquidity Measure (XLM): Kosten für Kauf und Verkauf von 25 T€ auf einmal, Spread plus Preiseinfluss, in Basispunkten. Niedriger ist günstiger. Grau: ${idx}-Median.`),
    auction: L(`Share of turnover traded in auctions (opening, intraday, closing), 10-day median. Grey: ${idx} median.`, `Anteil des Umsatzes in Auktionen, 10-Tage-Median. Grau: ${idx}-Median.`),
    who: L("Share of one-sided turnover by participant type, 10-day median (Xetra flow dynamics).", "Anteil am einseitigen Umsatz nach Teilnehmertyp, 10-Tage-Median (Xetra Flow Dynamics)."),
    price: L(`Closing auction price. Grey: ${idx} median return, rebased to the same start.`, `Schlussauktionskurs. Grau: ${idx}-Medianrendite, auf denselben Start indexiert.`)}[S.metric];
  return `
  <section class="sec wrap rv">
    <div class="sec-head"><div><h2 class="h2">${L("Trading over time", "Handel im Zeitverlauf")}</h2><p class="sec-note">${note} ${L("Markers: calendar events (■) and unusual days (▲). Click one to open its impact card.", "Marker: Kalenderereignisse (■) und auffällige Tage (▲). Anklicken öffnet die Impact Card.")}</p></div>
      ${seg("metric", METRICS(), S.metric)}</div>
    <div class="chart" id="tchart">${timeChart()}</div>
  </section>
  <section class="sec wrap"><div class="cols-21">
    <div class="rv">${peersBlock()}</div>
    <div class="rv" style="--d:.1s">${liqBlock()}</div>
  </div></section>
  ${S.iss.cost_curve ? `<section class="sec wrap rv">${curveBlock()}</section>` : ""}
  <section class="sec wrap rv">${anomBlock()}</section>`;
}
function timeChart() {
  const s = S.iss.series, n = s.date.length, W = 1160, H = 350, ml = 60, mr = 14, mt = 56, mb = 28, PH = H - mt - mb, cw = (W - ml - mr) / n;
  const x = i => ml + (i + .5) * cw;
  const evDays = new Map(S.iss.events.map(e => [String(e.reaction_day).slice(0, 10), e]));
  const anDays = new Map(S.iss.anomalies.map(a => [a.peak_date, a]));
  const di = new Map(s.date.map((d, i) => [d, i]));
  let series = [], kind = "line", fmt = v => v, yMin = 0, yMax = 1, area = null;
  if (S.metric === "turnover") { series = [[s.turnover_eur, "var(--navy)"], [s.index_turnover_eur, "var(--graphite)"]]; kind = "bars"; fmt = v => EUR(v, 0); yMax = Math.max(...s.turnover_eur.filter(isN)) * 1.05; }
  if (S.metric === "xlm") { series = [[s.xlm_25k, "var(--navy)"], [s.index_xlm_25k, "var(--graphite)"]]; fmt = v => BPS(v, 0); yMax = Math.max(...s.xlm_25k.filter(isN), ...s.index_xlm_25k.filter(isN)) * 1.1; }
  if (S.metric === "auction") { series = [[roll(s.auction_share, 10), "var(--navy)"], [roll(s.index_auction_share, 10), "var(--graphite)"]]; fmt = v => P(v, 0, false); yMax = 1; }
  if (S.metric === "who") { kind = "stack"; area = [[roll(s.mm_share, 10), "var(--graphite)", L("Market makers", "Market Maker")], [roll(s.agent_share, 10), "var(--navy)", L("Clients (agent)", "Kunden (Agent)")], [roll(s.prop_share, 10), "var(--sky)", L("Proprietary", "Eigenhandel")]]; fmt = v => P(v, 0, false); yMax = 1; }
  if (S.metric === "price") { const p0 = s.price.find(isN); let c = p0; const idxLine = s.index_ret.map((r, i) => i === 0 ? p0 : (c *= 1 + (isN(r) ? r : 0))); series = [[s.price, "var(--navy)"], [idxLine, "var(--graphite)"]]; fmt = PX; const all = [...s.price, ...idxLine].filter(isN); yMin = Math.min(...all) * .95; yMax = Math.max(...all) * 1.04; }
  const y = v => mt + (yMax - v) / (yMax - yMin) * PH;
  let g = "";
  for (let k = 0; k <= 4; k++) { const v = yMin + (yMax - yMin) * k / 4; g += `<line x1="${ml}" x2="${W - mr}" y1="${f1(y(v))}" y2="${f1(y(v))}" class="gl"/><text x="${ml - 8}" y="${f1(y(v) + 4)}" class="ax" text-anchor="end">${fmt(v)}</text>`; }
  let pm = ""; s.date.forEach((d, i) => { const m = d.slice(5, 7); if (m !== pm) { pm = m; g += `<line x1="${f1(x(i) - cw / 2)}" x2="${f1(x(i) - cw / 2)}" y1="${mt + PH}" y2="${mt + PH + 5}" stroke="#bdbdbd"/><text x="${f1(x(i) - cw / 2 + 4)}" y="${mt + PH + 19}" class="ax">${MS[de() ? 1 : 0][+m - 1]}</text>`; } });
  let body = "";
  if (kind === "bars") {
    body += s.turnover_eur.map((v, i) => { if (!isN(v)) return ""; const d = s.date[i], c = evDays.has(d) ? "var(--navy)" : anDays.has(d) ? "var(--sky)" : "var(--bar)"; return `<rect class="bar" style="--i:${i}" x="${f1(x(i) - cw * .38)}" y="${f1(y(v))}" width="${f1(cw * .76)}" height="${f1(mt + PH - y(v))}" fill="${c}"/>`; }).join("");
    body += `<path d="${line(series[1][0], x, y)}" fill="none" stroke="var(--graphite)" stroke-width="1.6" class="draw d2" pathLength="1"/>`;
  } else if (kind === "stack") {
    let base = new Array(n).fill(0);
    area.forEach(([a, c], k) => { const tot = i => (isN(area[0][0][i]) ? area[0][0][i] : 0) + (isN(area[1][0][i]) ? area[1][0][i] : 0) + (isN(area[2][0][i]) ? area[2][0][i] : 0) || 1;
      const top = a.map((v, i) => base[i] + (isN(v) ? v : 0) / tot(i));
      const d = top.map((v, i) => `${i ? "L" : "M"}${f1(x(i))},${f1(y(v))}`).join("") + base.map((v, i) => `L${f1(x(n - 1 - i))},${f1(y(base[n - 1 - i]))}`).join("") + "Z";
      body += `<path d="${d}" fill="${c}" opacity="${k === 1 ? .9 : .75}" class="ann" style="--i:${k - 5}"/>`; base = top; });
  } else {
    series.slice().reverse().forEach(([a, c], k) => { body += `<path d="${line(a, x, y)}" fill="none" stroke="${c}" stroke-width="${k ? 2 : 1.5}" stroke-linejoin="round" class="draw ${k ? "" : "d2"}" pathLength="1"/>`; });
    if (S.metric === "auction") body += s.auction_share.map((v, i) => isN(v) ? `<circle cx="${f1(x(i))}" cy="${f1(y(Math.min(v, 1)))}" r="1.6" fill="var(--navy)" opacity=".25"/>` : "").join("");
  }
  let marks = "";
  const SHORT = {DIVIDEND_EX: "DIV", GUIDANCE: "GUID"}; let lastX = -1e9, lane = 0;
  [...S.iss.events].sort((a, b) => String(a.reaction_day).localeCompare(String(b.reaction_day))).forEach((e, k) => { const i = di.get(String(e.reaction_day).slice(0, 10)); if (i === undefined) return; lane = x(i) - lastX < 46 ? (lane + 1) % 3 : 0; lastX = x(i); const ly = mt - 26 - lane * 13; marks += `<g class="ann" style="--i:${k % 6}" data-card="${s.date[i]}" data-ev="${esc(e.event_id)}" data-tip="${enc(`<span class="t">${esc(e.type)} · ${dL(s.date[i])}</span><br>${esc(e.title)}`)}" cursor="pointer"><line x1="${f1(x(i))}" x2="${f1(x(i))}" y1="${mt - 18}" y2="${mt + PH}" stroke="var(--navy)" stroke-width="1" stroke-dasharray="2 3" opacity=".45"/><rect x="${f1(x(i) - 4)}" y="${ly}" width="8" height="8" fill="var(--navy)"/><text x="${f1(x(i) + 7)}" y="${ly + 8}" class="axb" fill="var(--navy)" font-size="11">${esc(SHORT[e.type] || e.type)}</text></g>`; });
  S.iss.anomalies.forEach((a, k) => { const i = di.get(a.peak_date); if (i === undefined || evDays.has(a.peak_date)) return; marks += `<g class="ann" style="--i:${k % 6}" data-card="${a.peak_date}" data-tip="${enc(`<span class="t">${dL(a.peak_date)}</span><br>${esc(reasonL(a.reason))}<br>${L("abnormal", "abnormal")} ${P(a.peak_abn_ret)} · ${X(a.max_vol_ratio)} ${L("turnover", "Umsatz")}`)}" cursor="pointer"><path d="M${f1(x(i))},${mt + PH - 9} l5,9 h-10z" fill="var(--sky)"/></g>`; });
  const legend = kind === "stack" ? `<g transform="translate(${ml},${H + 10})">${area.map(([, c, t], k) => `<rect x="${k * 150}" y="0" width="10" height="10" fill="${c}"/><text x="${k * 150 + 16}" y="9" class="ax">${t}</text>`).join("")}</g>` : "";
  return `<svg viewBox="0 0 ${W} ${H + (legend ? 26 : 0)}" id="tsvg">${g}${body}${marks}${legend}<g class="xh" id="txh"><line y1="${mt}" y2="${mt + PH}" stroke="var(--ink)"/></g><rect class="hit" id="thit" x="${ml}" y="${mt}" width="${W - ml - mr}" height="${PH - 12}"/></svg>`;
}
function line(a, x, y) { let d = "", pen = false; a.forEach((v, i) => { if (!isN(v)) { pen = false; return; } d += `${pen ? "L" : "M"}${f1(x(i))},${f1(y(v))}`; pen = true; }); return d; }
const reasonL = r => !de() ? r : String(r).replace("volume spike", "Umsatzspitze").replace("stock-specific move", "titelspezifische Bewegung").replace("spread widening", "Spreadausweitung");
function peersBlock() {
  const p = S.iss.peers, g = p.groups.filter(x => x.values && x.n > 0);
  const rows = [["turnover_eur", L("Turnover per day", "Umsatz pro Tag"), v => EUR(v)], ["xlm_25k", L("Trading cost €25k (XLM)", "Handelskosten 25 T€ (XLM)"), v => BPS(v)],
    ["auction_share", L("Auction share", "Auktionsanteil"), v => P(v, 0, false)], ["agent_share", L("Client (agent) share", "Anteil Kundenorders"), v => P(v, 0, false)], ["volatility", L("Volatility (annualised)", "Volatilität (annualisiert)"), v => P(v, 0, false)]];
  const SZ = {large: L("large", "groß"), mid: L("mid", "mittel"), small: L("small", "klein")};
  const lab = x => x.key === "index" ? `${S.iss.meta.index}` : x.key === "size" ? L("Similar size", "Ähnliche Größe") : esc(x.name);
  const sec = g.find(x => x.key === "sector");
  const members = sec && sec.members.length ? `<b>${esc(sec.name)}</b>: ${sec.members.map(m => esc(nice({ticker: m.ticker, name: m.name}))).join(", ")}${sec.n > sec.members.length ? " …" : ""}. ` : "";
  return `<div class="sec-head"><div><h2 class="h2">${L("Peer benchmark", "Peer-Vergleich")}</h2><p class="sec-note">${L("Medians of the last 60 trading days, per peer group: index, sector, and size. Arrows compare you with the index median.", "Mediane der letzten 60 Handelstage je Vergleichsgruppe: Index, Sektor und Größe. Pfeile vergleichen mit dem Indexmedian.")}</p></div></div>
  <table class="tbl"><thead><tr><th></th><th class="r">${S.iss.meta.ticker}</th>${g.map(x => `<th class="r">${lab(x)} <span style="font-weight:400">(${x.n})</span></th>`).join("")}<th class="ic"></th></tr></thead>
  <tbody>${rows.map(([k, t, f]) => `<tr><td>${t}</td><td class="r"><b>${f(p.stock[k])}</b></td>${g.map(x => `<td class="r m">${f(x.values[k])}</td>`).join("")}<td class="ic">${arrRel(p.stock[k], g[0] && g[0].values[k])}</td></tr>`).join("")}</tbody></table>
  <p class="sec-note">${members}${L("Size = turnover tercile of all 174 shares (market capitalisation is not in the Xetra data).", "Größe = Umsatz-Terzil aller 174 Aktien (Marktkapitalisierung ist nicht in den Xetra-Daten).")}</p>`;
}
/* trading cost by order size (engine/xlm.py): the on-demand version of the Stock Report's XLM table */
function curveBlock() {
  const c = S.iss.cost_curve, rows = c.rows.filter(r => isN(r.stock_bps) && r.stock_fill >= .5 || isN(r.peer_bps)), s = c.summary;
  const W = 760, H = 270, ml = 56, mr = 20, mt = 18, mb = 40, xs = rows.map(r => Math.log10(r.notional_eur));
  const x0 = Math.min(...xs), x1 = Math.max(...xs), x = v => ml + (Math.log10(v) - x0) / (x1 - x0 || 1) * (W - ml - mr);
  const vals = rows.flatMap(r => [r.stock_fill >= .5 ? r.stock_bps : null, r.peer_bps]).filter(v => isN(v) && v > 0);
  const l0 = Math.log10(Math.min(...vals) * .8), l1 = Math.log10(Math.max(...vals) * 1.25);   /* log scale: €10k tickets and blocks on one chart */
  const y = v => mt + (1 - (Math.log10(v) - l0) / (l1 - l0)) * (H - mt - mb);
  let g = "";
  [5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000].filter(v => Math.log10(v) >= l0 && Math.log10(v) <= l1).forEach(v => { g += `<line x1="${ml}" x2="${W - mr}" y1="${f1(y(v))}" y2="${f1(y(v))}" class="gl"/><text x="${ml - 8}" y="${f1(y(v) + 4)}" class="ax" text-anchor="end">${N0(v)}</text>`; });
  rows.forEach(r => g += `<text x="${f1(x(r.notional_eur))}" y="${H - mb + 18}" class="ax" text-anchor="middle">${esc(r.label)}</text>`);
  const ln = (k, col, w, dash) => { const pts = rows.filter(r => isN(r[k + "_bps"]) && (k === "peer" || r.stock_fill >= .5)); return `<path d="${pts.map((r, i) => `${i ? "L" : "M"}${f1(x(r.notional_eur))},${f1(y(r[k + "_bps"]))}`).join("")}" fill="none" stroke="${col}" stroke-width="${w}" ${dash ? 'stroke-dasharray="4 4"' : ""} class="draw" pathLength="1"/>` + pts.map(r => `<circle cx="${f1(x(r.notional_eur))}" cy="${f1(y(r[k + "_bps"]))}" r="${k === "stock" ? 4 : 3}" fill="${k === "stock" ? "#fff" : col}" stroke="${col}" stroke-width="2" data-tip="${enc(`<span class="t">${esc(r.label)} ${L("order", "Order")}</span><br>${k === "stock" ? S.iss.meta.ticker : L("Peers", "Peers")} ${BPS(r[k + "_bps"], 0)}${k === "stock" ? `<br>${L("book absorbed it on", "Buch nahm sie auf an")} ${P(r.stock_fill, 0, false)} ${L("of days", "der Tage")}` : ""}`)}"/>`).join(""); };
  const big = s.largest_absorbed_label;
  return `<div class="cols-21"><div><div class="sec-head"><div><h2 class="h2">${L("Trading cost by order size", "Handelskosten nach Ordergröße")}</h2><p class="sec-note">${L(`Median XLM over the last 60 trading days, from a €10k ticket to a block. Dashed: ${S.iss.meta.index} peers. Sizes the order book could not absorb on most days are left out.`, `Median-XLM der letzten 60 Handelstage, von 10 T€ bis zum Block. Gestrichelt: ${S.iss.meta.index}-Peers. Größen, die das Orderbuch an den meisten Tagen nicht aufnehmen konnte, fehlen.`)}</p></div></div>
    <div class="chart"><svg viewBox="0 0 ${W} ${H}">${g}<text x="${ml}" y="${mt - 6}" class="ax">bps (${L("log scale", "log. Skala")})</text>${ln("peer", "var(--graphite)", 1.6, true)}${ln("stock", "var(--navy)", 2.4)}</svg></div></div>
    <div><dl class="facts facts--stack">
      <div><dt>${L("€100k order costs", "100-T€-Order kostet")}</dt><dd>${BPS(s.cost_100k_bps, 0)}<small>${L("peers", "Peers")} ${BPS(s.peer_cost_100k_bps, 0)}</small></dd></div>
      <div><dt>${L("€1m order costs", "1-Mio.-€-Order kostet")}</dt><dd>${BPS(s.cost_1m_bps, 0)}<small>${L("peers", "Peers")} ${BPS(s.peer_cost_1m_bps, 0)}</small></dd></div>
      <div><dt>${L("Largest order the book absorbs on most days", "Größte Order, die das Buch meist aufnimmt")}</dt><dd>${big ? esc(big) : NA}</dd></div></dl>
      <p class="sec-note">${L("Why IR cares: an institutional investor building a position needs to know what a block costs. This is the number behind a Designated Sponsor conversation.", "Warum IR das braucht: Ein institutioneller Investor, der eine Position aufbaut, will wissen, was ein Block kostet. Das ist die Zahl hinter dem Gespräch mit dem Designated Sponsor.")}</p></div></div>`;
}
const CTX = c => !c ? "" : String(c).split(/,\s*/).map(k => ({index_event: L("index change", "Indexänderung"), index_change: L("index membership change", "Indexwechsel"), quarterly_expiry: L("quarterly expiry", "großer Verfall"), monthly_expiry: L("monthly expiry", "Monatsverfall"), month_end_review: L("index review date", "Index-Review-Tag"), market_wide_volume: L("market-wide volume", "marktweiter Umsatz")}[k] || k)).join(", ");
function liqBlock() {
  const lt = S.iss.liquidity, k = S.iss.kpis.liquidity_check, idx = S.iss.meta.index;
  const vw = {improved: L("Liquidity improved.", "Die Liquidität hat sich verbessert."), worsened: L("Liquidity worsened.", "Die Liquidität hat sich verschlechtert."), mixed: L("Liquidity is mixed.", "Die Liquidität ist gemischt."), stable: L("Liquidity is stable.", "Die Liquidität ist stabil.")}[lt.verdict] || L("Not enough history yet.", "Noch zu wenig Historie.");
  const row = (t, a, b, ch, ich, f, lowGood) => `<tr><td>${t}</td><td class="r m">${f(a)}</td><td class="r"><b>${f(b)}</b></td><td class="r">${P(ch, 0)}</td><td class="r m">${P(ich, 0)}</td></tr>`;
  const okX = k.median_xlm_25k_bps_4m <= 100, okT = k.avg_turnover_eur_4m >= 2.5e6;
  const ruler = (lbl, v, txt, th, thTxt, max, ok, lowGood) => { const pv = Math.min(v / max, 1) * 100, t = th / max * 100;
    return `<div class="ruler"><div class="top"><span>${lbl}</span><b class="nt">${txt} <span class="m" style="font-weight:400">${ok ? "✓" : "✕"} ${thTxt}</span></b></div><div class="trk">
      <div style="left:0;right:0;top:9px;height:4px;background:var(--tile)"></div><div style="top:9px;height:4px;${lowGood ? `left:0;width:${t}%` : `left:${t}%;right:0`};background:var(--sky-soft)"></div>
      <div style="left:${t}%;top:2px;height:18px;width:1.5px;background:var(--ink)"></div><div class="barx" style="left:0;top:9px;height:4px;width:${pv}%;background:var(--navy)"></div>
      <div style="left:calc(${pv}% - 6px);top:5px;width:12px;height:12px;border-radius:50%;background:#fff;border:2.5px solid var(--navy)"></div></div></div>`; };
  return `<h2 class="h2">${L("Has liquidity improved?", "Hat sich die Liquidität verbessert?")}</h2>
  <p class="verdict" style="margin-top:12px"><b>${vw}</b> ${esc(de() ? "" : lt.help || "")}</p>
  <table class="tbl"><thead><tr><th>${L("Last 60 vs previous 60 days", "Letzte 60 vs. vorherige 60 Tage")}</th><th class="r">${L("Before", "Vorher")}</th><th class="r">${L("Now", "Jetzt")}</th><th class="r">${L("Change", "Änderung")}</th><th class="r">${idx}</th></tr></thead><tbody>
  ${row(L("Trading cost €25k", "Handelskosten 25 T€"), lt.stock.xlm_25k_bps.before, lt.stock.xlm_25k_bps.now, lt.xlm_25k_change_pct, lt.index_xlm_25k_change_pct, BPS)}
  ${row(L("Turnover per day", "Umsatz pro Tag"), lt.stock.turnover_eur.before, lt.stock.turnover_eur.now, lt.turnover_change_pct, lt.index_turnover_change_pct, EUR)}</tbody></table>
  <h3 class="h3" style="margin-top:30px">${L("Xetra liquidity category (estimate)", "Xetra-Liquiditätskategorie (Schätzung)")}</h3>
  ${ruler(L("Cost to trade €25k, 4-month median", "Handelskosten 25 T€, 4-Monats-Median"), k.median_xlm_25k_bps_4m, BPS(k.median_xlm_25k_bps_4m), 100, "≤ 100", 150, okX, true)}
  ${ruler(L("Turnover per day, 4-month average", "Umsatz pro Tag, 4-Monats-Schnitt"), k.avg_turnover_eur_4m, EUR(k.avg_turnover_eur_4m), 2.5e6, "≥ " + EUR(2.5e6), Math.max(5e6, k.avg_turnover_eur_4m * 1.25), okT, false)}
  <p class="sec-note">${okX && okT ? L("Category A: no Designated Sponsor needed for continuous trading.", "Kategorie A: kein Designated Sponsor für den fortlaufenden Handel nötig.") : L("Category B: continuous trading needs a Designated Sponsor.", "Kategorie B: fortlaufender Handel braucht einen Designated Sponsor.")} ${L("Rule: Being Public Guide, p. 32.", "Regel: Being Public Guide, S. 32.")}</p>`;
}
function anomBlock() {
  const a = S.iss.anomalies;
  if (!a.length) return `<h2 class="h2">${L("Unusual days", "Auffällige Tage")}</h2><p class="empty">${L("No unusual days in 2026.", "Keine auffälligen Tage in 2026.")}</p>`;
  return `<div class="sec-head"><div><h2 class="h2">${L("Unusual days", "Auffällige Tage")}</h2><p class="sec-note">${L("Turnover z ≥ 3, stock-specific move z ≥ 3 or spread ≥ 2× normal. Consecutive days are merged. The data shows that something happened, not why: causes come from the calendar; market mechanics (index changes, expiries, market-wide days) are flagged so they are not mistaken for company news.", "Umsatz-z ≥ 3, titelspezifische Bewegung z ≥ 3 oder Spread ≥ 2× normal. Aufeinanderfolgende Tage werden zusammengefasst. Die Daten zeigen, dass etwas passiert ist, nicht warum: Ursachen kommen aus dem Kalender; Marktmechanik (Indexänderungen, Verfallstage, marktweite Tage) wird markiert, damit sie nicht als Unternehmensnachricht gilt.")}</p></div></div>
  <table class="tbl"><thead><tr><th>${L("Date", "Datum")}</th><th>${L("What was unusual", "Was auffiel")}</th><th class="r">${L("Abnormal", "Abnormal")}</th><th class="ic"></th><th class="r">${L("Turnover", "Umsatz")}</th><th>${L("Calendar · market context", "Kalender · Marktkontext")}</th><th></th></tr></thead><tbody>
  ${a.map(x => `<tr class="go" data-card="${x.peak_date}" ${x.event ? `data-ev="${esc(x.event.event_id)}"` : ""}><td><b>${dS(x.start)}${x.days > 1 ? " – " + dS(x.end) : ""}</b></td><td class="m">${esc(reasonL(x.reason))}</td><td class="r"><b>${P(x.peak_abn_ret)}</b></td><td class="ic">${arrRet(x.peak_abn_ret)}</td><td class="r">${X(x.max_vol_ratio)}</td>
    <td>${x.event ? `<span class="tag">${esc(x.event.type)}</span> <span class="m" style="font-size:13px">${esc(x.event.title.slice(0, 60))}${x.event.title.length > 60 ? "…" : ""}</span>` : x.context ? `<span class="tag g">${L("MARKET", "MARKT")}</span> <span class="m" style="font-size:13px">${esc(CTX(x.context))}</span>` : `<span class="m" style="font-size:13px">${L("no entry, cause open", "kein Eintrag, Ursache offen")}</span>`}${x.event && x.context ? `<div class="m" style="font-size:12px;margin-top:2px">${L("also", "auch")}: ${esc(CTX(x.context))}</div>` : ""}</td>
    <td class="r"><span class="link" style="white-space:nowrap">${L("Impact card", "Impact Card")} ${ARR}</span></td></tr>`).join("")}</tbody></table>`;
}

/* ============================== 2 impact card: event impact ============================== */
const keyOf = (sel, isin = S.isin) => `${isin}|${sel.day}|${sel.event_id || ""}`;
function defaultSel() {
  const a = [...S.iss.anomalies].sort((p, q) => q.severity - p.severity)[0];
  if (a) return {day: a.peak_date, event_id: a.event ? a.event.event_id : null};
  const e = S.iss.events[S.iss.events.length - 1];
  return e ? {day: String(e.reaction_day).slice(0, 10), event_id: e.event_id} : {day: S.iss.meta.last_date, event_id: null};
}
const TIMING = t => ({pre_open: L("before the open", "vor Handelsbeginn"), intraday: L("during trading", "während des Handels"), post_close: L("after the close", "nach Handelsschluss")}[t] || L("time unknown", "Zeit unbekannt"));
const TYPE = t => ({NOTABLE_DAY: L("Unusual days", "Auffällige Tage"), FY: L("Full-year results", "Jahresergebnisse"), Q1: L("Q1 results", "Q1-Ergebnisse"), H1: L("Half-year results", "Halbjahresergebnisse"), Q3: L("Q3 results", "Q3-Ergebnisse"),
  DIVIDEND_EX: L("Ex-dividend days", "Ex-Dividenden-Tage"), AGM: L("AGMs", "Hauptversammlungen"), ADHOC: L("Ad hoc releases", "Ad-hoc-Meldungen"), GUIDANCE: L("Guidance changes", "Prognoseänderungen"), MA: L("M&A news", "M&A-Nachrichten"), INDEX: L("Index changes", "Indexänderungen"), CMD: L("Capital markets days", "Kapitalmarkttage")}[t] || t);
function pCard() {
  if (!S.sel) S.sel = defaultSel();
  const sel = S.sel, evs = [...S.iss.events].sort((a, b) => String(b.reaction_day).localeCompare(String(a.reaction_day)));
  const evDays = new Set(evs.map(e => String(e.reaction_day).slice(0, 10)));
  const un = S.iss.anomalies.filter(a => !evDays.has(a.peak_date));
  const cur = (day, id) => sel.day === day && (sel.event_id || null) === (id || null);
  const list = `<aside class="evlist rv" aria-label="${L("Events", "Ereignisse")}">
    <h4>${L("Announcements (calendar)", "Meldungen (Kalender)")}</h4>
    <div class="ev-tools"><button class="link" data-act="addev">+ ${L("Add event", "Ereignis hinzufügen")}</button><label class="link">${L("Import calendar", "Kalender importieren")}<input type="file" id="evfile" accept=".csv,.ics,.txt" hidden></label></div>
    ${S.addEv ? evForm() : ""}
    ${evs.length ? evs.map(e => { const d = String(e.reaction_day).slice(0, 10); return `<button data-card="${d}" data-ev="${esc(e.event_id)}" aria-current="${cur(d, e.event_id)}"><span class="d"><span>${dS(d)} ${e.time_local ? `<span class="m" style="font-weight:400">· ${esc(e.time_local)}</span>` : ""}</span><span class="tag ${e.user ? "s" : ""}">${e.user ? L("OWN", "EIGEN") + " · " : ""}${esc(e.type)}</span></span><span class="t">${String(e.verified) === "1" ? "✓ " : ""}${esc(e.title)}</span></button>`; }).join("") : `<p class="m" style="font-size:14px">${L("No calendar entries for this share yet.", "Noch keine Kalendereinträge für diese Aktie.")}</p>`}
    <h4>${L("Unusual days without an entry", "Auffällige Tage ohne Eintrag")}</h4>
    ${un.length ? un.map(a => `<button data-card="${a.peak_date}" aria-current="${cur(a.peak_date, null)}"><span class="d"><span>${dS(a.peak_date)}</span><span class="tag s">${P(a.peak_abn_ret)}</span></span><span class="t">${esc(reasonL(a.reason))}</span></button>`).join("") : `<p class="m" style="font-size:14px">${L("None.", "Keine.")}</p>`}
  </aside>`;
  const k = keyOf(sel), d = S.cards[k];
  return `<div class="wrap"><div class="ic-layout">${list}<div id="cardslot">${d ? cardHTML(d) : `<div class="card"><div class="card-head"><span class="ttl">${L("Impact card", "Impact Card")}</span><span class="id">${L("computing…", "wird berechnet…")}</span></div><div class="card-sec"><div class="skel"></div></div><div class="card-sec"><div class="skel" style="min-height:300px"></div></div></div>`}</div></div></div>`;
}
async function loadCard() {
  const sel = S.sel, k = keyOf(sel);
  if (!S.cards[k]) {
    try { S.cards[k] = await api(cardURL(S.isin, sel.day, sel.event_id)); }
    catch (e) { $("#cardslot") && ($("#cardslot").innerHTML = `<p class="empty">${L("Could not build the card: ", "Karte konnte nicht berechnet werden: ")}${esc(e.message)}</p>`); return; }
    if (S.page !== "card" || keyOf(S.sel) !== k) return;
    const slot = $("#cardslot"); slot.innerHTML = cardHTML(S.cards[k]); after(slot);
  }
  runAI(k, S.lang);
}
function cardHTML(d) {
  const c = d.card, p = c.price, v = c.volume, l = c.liquidity, a = c.auctions || {}, pa = c.participants, cm = c.comparison, e = c.event, row = d.event_row || {};
  const neg = (p.abn_ret || 0) < 0, col = neg ? "var(--down)" : "var(--up)";
  const id = e.event_id || `${c.ticker}_UNUSUAL_${e.reaction_day.replace(/-/g, "")}`;
  const notable = e.type === "NOTABLE_DAY";
  const [dt, tm] = (e.datetime_local || "").split(" ");
  const timing = notable ? L(`Detected from trading on <b>${dL(e.reaction_day)}</b>`, `Aus dem Handel erkannt am <b>${dL(e.reaction_day)}</b>`)
    : `${L("Published", "Veröffentlicht")} <b>${dS(dt)}${tm ? " " + tm : ""}</b> · ${TIMING(e.timing)}${e.timing_source === "inferred_from_trading" ? L(" (inferred from trading)", " (aus dem Handel abgeleitet)") : ""} → ${L("reaction", "Reaktion")} <b>${dS(e.reaction_day)}</b>`;
  const ver = notable ? L("No calendar entry. The cause is not in the data and has not been verified.", "Kein Kalendereintrag. Die Ursache steht nicht in den Daten und ist nicht verifiziert.")
    : String(e.event_id || "").startsWith("USR_") ? L("From your own calendar (not checked against a source)", "Aus Ihrem eigenen Kalender (nicht mit einer Quelle geprüft)")
    : (String(row.verified) === "1" ? L("✓ Date and time verified against the source", "✓ Datum und Uhrzeit mit der Quelle geprüft") : L("Source not yet verified", "Quelle noch nicht geprüft"));
  const pct = (t, x, med) => `<div class="pct-row"><span>${t}</span><span class="trk"><i class="barx" style="width:${(x || 0) * 100}%"></i>${isN(med) ? "" : ""}</span><b class="nt">${isN(x) ? Math.floor(x * 100) + "%" : NA}</b></div>`;
  /* rank counts this event, n counts only the others: the group is n + 1 (rank_of from the engine once it exists) */
  const rankOf = cm ? (Number.isInteger(cm.rank_of) ? cm.rank_of : cm.n + 1) : null;
  const cmpBlock = cm ? `<div><div class="big-cap">${L("How it ranks", "Einordnung")}</div>
      <p style="margin:0 0 10px;font-size:15px">${L(`Rank ${cm.rank_abs_abn_ret} of ${rankOf} (incl. this day) among ${cm.group_type === "NOTABLE_DAY" ? "unusual days" : TYPE(cm.group_type)} (${cm.group_index}). Bigger than:`, `Rang ${cm.rank_abs_abn_ret} von ${rankOf} (inkl. dieses Tages) unter ${cm.group_type === "NOTABLE_DAY" ? "auffälligen Tagen" : TYPE(cm.group_type)} (${cm.group_index}). Größer als:`)}</p>
      ${pct(L("Stock-specific move", "Titelspezifische Bewegung"), cm.abs_abn_ret_pctile)}${pct(L("Turnover vs normal", "Umsatz vs. normal"), cm.vol_ratio_pctile)}${pct(L("Trading cost vs normal", "Handelskosten vs. normal"), cm.xlm_ratio_pctile)}
      <button class="link" data-act="cmpthis" data-type="${esc(cm.group_type)}" data-index="${esc(cm.group_index)}" style="margin-top:8px">${L("See all of them", "Alle ansehen")} ${ARR}</button></div>` : `<div class="m">${L("No comparison group yet.", "Noch keine Vergleichsgruppe.")}</div>`;
  const mini = (val, base, max) => isN(val) && isN(base) ? `<div class="mini"><i class="barx" style="width:${Math.min(100, val / max * 100)}%"></i><em style="left:${Math.min(100, base / max * 100)}%" data-tip="${enc(L("normal", "normal"))}"></em></div>` : "";
  const vmax = Math.max(v.turnover_eur || 0, v.baseline_eur || 0);
  const inst = `<div class="inst">
    <div><div class="k">${L("Turnover", "Umsatz")}</div><div class="v">${X(v.ratio)}</div><div class="s">${EUR(v.turnover_eur)} ${L("vs", "vs.")} ${EUR(v.baseline_eur)} ${L("normal", "normal")}</div>${mini(v.turnover_eur, v.baseline_eur, vmax)}</div>
    <div><div class="k">${L("Trading cost €25k", "Handelskosten 25 T€")}</div><div class="v">${X(l.ratio)}</div><div class="s">${BPS(l.xlm_25k_bps)} ${L("vs", "vs.")} ${BPS(l.xlm_25k_baseline_bps)}${isN(l.days_to_normal) ? ` · ${L("normal again after", "normal nach")} ${l.days_to_normal} ${l.days_to_normal === 1 ? L("day", "Tag") : L("days", "Tagen")}` : ""}</div>${mini(l.xlm_25k_bps, l.xlm_25k_baseline_bps, Math.max(l.xlm_25k_bps || 0, l.xlm_25k_baseline_bps || 0))}</div>
    <div><div class="k">${L("Opening auction", "Eröffnungsauktion")}</div><div class="v">${X(a.open_auction_ratio)}</div><div class="s">${EUR(a.open_auction_eur)} · ${L("price", "Kurs")} <b>${P(a.open_auction_move)}</b> ${L("vs prev. close", "vs. Vortag")} (${L("typical", "üblich")} ±${P(a.open_auction_move_baseline_abs, 1, false)})</div></div>
    <div><div class="k">${L("Closing auction", "Schlussauktion")}</div><div class="v">${X(a.close_auction_ratio)}</div><div class="s">${EUR(a.close_auction_eur)} · ${P(a.close_auction_share, 0, false)} ${L("of the day", "des Tages")} (${L("normal", "normal")} ${P(a.close_auction_share_baseline, 0, false)}) · ${L("price", "Kurs")} <b>${P(a.close_auction_move)}</b> ${L("vs last trade", "vs. letztem Handel")}</div></div></div>`;
  const imb = pa.agent_aggr_imbalance, ib = pa.agent_aggr_imbalance_baseline;
  const flows = `<div class="flows">
    <div class="row"><span>${L("Client (agent) share", "Anteil Kunden (Agent)")}</span><div class="trk" style="height:12px"><div class="b barx" style="left:0;top:0;width:${(pa.agent_share || 0) * 100}%"></div><div class="nm" style="left:${(pa.agent_share_baseline || 0) * 100}%" data-tip="${enc(L("normal ", "normal ") + P(pa.agent_share_baseline, 0, false))}"></div></div><b class="r">${P(pa.agent_share, 0, false)}</b></div>
    <div class="row"><span>${L("Client net flow", "Kunden-Nettofluss")}</span><div class="trk"><div class="b barx ${imb < 0 ? "neg" : ""}" style="${imb < 0 ? "right:50%" : "left:50%"};width:${Math.min(50, Math.abs(imb || 0) * 50)}%"></div><div class="nm" style="left:calc(${50 + (ib || 0) * 50}% - 1px)" data-tip="${enc(L("normal ", "normal ") + P(ib, 0))}"></div></div><b class="r">${P(imb, 0)}</b></div>
    <div class="row"><span>${L("Proprietary share", "Anteil Eigenhandel")}</span><div class="trk" style="height:12px"><div class="b barx" style="left:0;top:0;width:${(pa.prop_share || 0) * 100}%;background:var(--sky)"></div></div><b class="r">${P(pa.prop_share, 0, false)}</b></div>
    <div class="row"><span>${L("Market maker share", "Anteil Market Maker")}</span><div class="trk" style="height:12px"><div class="b barx" style="left:0;top:0;width:${(pa.mm_share || 0) * 100}%;background:var(--graphite)"></div></div><b class="r">${P(pa.mm_share, 0, false)}</b></div></div>
    <p class="sec-note">${L(`Client orders were net ${imb < 0 ? "sellers" : "buyers"}: ${EUR(Math.abs(pa.agent_aggr_net_eur))} more ${imb < 0 ? "sold" : "bought"} aggressively. Grey tick: normal.`, `Kundenorders waren per Saldo ${imb < 0 ? "Verkäufer" : "Käufer"}: ${EUR(Math.abs(pa.agent_aggr_net_eur))} mehr aggressiv ${imb < 0 ? "verkauft" : "gekauft"}. Grauer Strich: normal.`)}</p>`;
  const FL = {flow_censored: L("participant flows held back by Xetra (fewer than 7 trades)", "Teilnehmerflüsse von Xetra zurückgehalten (unter 7 Trades)"), flow_multi_day: L("participant flows cover several days", "Teilnehmerflüsse über mehrere Tage"), possible_corp_action: L("possible corporate action (split, rights issue): check before comparing", "mögliche Kapitalmaßnahme: vor Vergleich prüfen"), short_baseline: L("fewer than 20 days of history before the event", "weniger als 20 Tage Historie vor dem Ereignis"), comparison_failed: L("no comparison group", "keine Vergleichsgruppe")};
  const flags = (c.flags || []).length ? `<span>${L("Note", "Hinweis")}: ${c.flags.map(f => esc(FL[f] || f)).join("; ")}</span>` : "";
  return `<article class="card rv in" id="thecard">
    <div class="card-head"><div><div class="ttl">${L("Impact card", "Impact Card")}</div><div class="id">${esc(id)}</div></div><div class="timing">${timing}</div></div>
    <div class="card-title"><div><span class="tag">${esc(e.type)}</span><h2 style="margin-top:8px">${esc(notable ? L("Unusual trading day", "Auffälliger Handelstag") : e.title)}</h2>
      <div class="src"><span>${ver}</span>${e.source_url ? `<a href="${esc(e.source_url)}" target="_blank" rel="noopener">${L("Source", "Quelle")} ↗</a>` : ""}</div></div>
      <a class="pill pill--sm" href="${exportURL(c.isin, e.reaction_day, e.event_id)}" download>${L("Export IR report (PDF)", "IR-Report exportieren (PDF)")} ↓</a></div>
    <div class="card-sec card-top">
      <div><div class="big-cap">${L("Stock-specific move (abnormal return)", "Titelspezifische Bewegung (abnormale Rendite)")}</div>
        <div class="big" style="color:${col}"><span class="count" data-to="${p.abn_ret}">${P(p.abn_ret)}</span></div>
        <p class="big-sub">${esc(nice(U(c.isin)))} <b>${P(p.ret)}</b> · ${c.index} ${L("peers", "Peers")} <b>${P(p.peer_ret)}</b> · ${isN(p.abn_ret_z) ? `<span data-tip="${enc(L("How many times the share's normal daily stock-specific move", "Vielfaches der normalen täglichen titelspezifischen Bewegung"))}">${nf(Math.abs(p.abn_ret_z), 1)}× ${L("its normal daily move", "die normale Tagesbewegung")}</span>` : ""} · ${L("day 0 to +5", "Tag 0 bis +5")} <b>${P(p.car_0_5)}</b></p></div>
      ${cmpBlock}</div>
    <div class="card-sec" style="padding-top:0;padding-bottom:0">${inst}</div>
    <div class="card-sec"><div class="sec-head" style="margin-bottom:10px"><h3 class="h3">${L("The day, minute by minute", "Der Tag, Minute für Minute")}</h3>
      <div class="legend"><span><i></i>${L("price vs prev. close", "Kurs vs. Vortag")}</span><span><i class="b" style="background:var(--bar)"></i>${L("turnover (5 min)", "Umsatz (5 Min.)")}</span><span><i class="b" style="background:var(--navy)"></i>${L("auctions", "Auktionen")}</span><span><i class="b" style="background:var(--sky-soft)"></i>${L("first 15 min", "erste 15 Min.")}</span></div></div>
      <div class="chart" id="ichart">${d.bars ? intraChart(d) : `<p class="empty">${L("No 1-minute bars for this share yet. The daily figures above are complete.", "Für diese Aktie gibt es noch keine 1-Minuten-Balken. Die Tageswerte oben sind vollständig.")}</p>`}</div></div>
    <div class="card-sec cols" style="gap:48px"><div><h3 class="h3">${L("Who traded", "Wer gehandelt hat")}</h3>${flows}</div><div><h3 class="h3">${L("Aftershocks", "Nachwirkung")}</h3>${afterChart(d)}</div></div>
    <div class="card-sec" style="font-size:12.5px;color:var(--mute);display:flex;gap:18px;flex-wrap:wrap;justify-content:space-between"><span>${L(`Normal = median of ${c.baseline.days_used} trading days ending a week before the event (${esc(c.baseline.window)}). Abnormal return = return minus the median return of the other ${c.index} members. Prices = closing auction.`, `Normal = Median aus ${c.baseline.days_used} Handelstagen bis eine Woche vor dem Ereignis (${esc(c.baseline.window)}). Abnormale Rendite = Rendite minus Medianrendite der übrigen ${c.index}-Werte. Kurse = Schlussauktion.`)}</span>${flags}</div>
  </article>
  <section class="ai-box rv in" id="aibox">${aiBoxHTML(keyOf(S.sel))}</section>`;
}
function intraChart(d) {
  const c = d.card, b = d.bars, pc = d.prev_close, W = 880, ml = 52, mr = 92, mt = 38, PH = 220, GAP = 26, VH = 76, H = mt + PH + GAP + VH + 30;
  const T0 = -4, T1 = 522, xm = m => ml + (m - T0) / (T1 - T0) * (W - ml - mr);
  const pts = b.t.map((t, i) => ({m: minOf(t), t, c: b.close[i] / pc - 1, lo: b.low[i] / pc - 1, eur: b.eur[i], au: b.auction[i]})).filter(p => isN(p.c));
  const cont = pts.filter(p => p.m >= 0 && p.m < 510 && !(p.au && p.m <= 5));
  const auct = pts.filter(p => p.au);
  const vals = pts.map(p => p.c).concat(pts.map(p => p.lo), [0, c.price.ret]);
  const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo) * .1 + .004, y0 = lo - pad, y1 = hi + pad, y = v => mt + (y1 - v) / (y1 - y0) * PH;
  const span = (y1 - y0) * 100, step = span > 24 ? .05 : span > 10 ? .02 : span > 4 ? .01 : .005;
  let g = "";
  for (let v = Math.ceil(y0 / step) * step; v <= y1; v += step) { const z = Math.abs(v) < 1e-9; g += `<line x1="${ml}" x2="${W - mr + 8}" y1="${f1(y(v))}" y2="${f1(y(v))}" class="${z ? "zero" : "gl"}"/><text x="${ml - 8}" y="${f1(y(v) + 4)}" class="ax" text-anchor="end">${P(v, step < .01 ? 1 : 0)}</text>`; }
  g += `<text x="${W - mr + 12}" y="${f1(y(0) + 4)}" class="ax">${L("prev. close", "Vortag")} ${PX(pc)}</text>`;
  const vy = mt + PH + GAP + VH;
  [[0, "09:00"], [120, "11:00"], [240, "13:00"], [360, "15:00"], [510, "17:30"]].forEach(([m, t]) => g += `<text x="${f1(xm(m))}" y="${vy + 18}" class="ax" text-anchor="${m === 0 ? "start" : "middle"}">${t}</text>`);
  const buckets = new Map(); cont.forEach(p => { const k = Math.floor(p.m / 5) * 5; buckets.set(k, (buckets.get(k) || 0) + p.eur); });
  const bmax = Math.max(...buckets.values(), 1), bw = xm(5) - xm(0) - 1.2;
  let vol = ""; [...buckets.entries()].forEach(([m, e], i) => { const h = e / bmax * VH * .92; vol += `<rect class="bar" style="--i:${i * 3}" x="${f1(xm(m) + .6)}" y="${f1(vy - h)}" width="${f1(bw)}" height="${f1(h)}" fill="${m < 15 ? "var(--sky)" : "var(--bar)"}"/>`; });
  let au = ""; auct.forEach((p, k) => { const full = p.eur > bmax, h = Math.min(VH, p.eur / bmax * VH * .92); au += `<g class="ann" style="--i:${3 + k}" data-tip="${enc(`<span class="t">${L("Auction", "Auktion")} ${p.t}</span><br>${EUR(p.eur)}`)}"><rect x="${f1(xm(p.m) - bw)}" y="${f1(vy - h)}" width="${f1(bw * 2)}" height="${f1(h)}" fill="var(--navy)"/>${full ? `<path d="M${f1(xm(p.m) - bw - 2)},${f1(vy - VH * .55)} l${f1(bw * 2 + 4)},-6 M${f1(xm(p.m) - bw - 2)},${f1(vy - VH * .55 + 5)} l${f1(bw * 2 + 4)},-6" stroke="#fff" stroke-width="2"/>` : ""}</g>`; });
  const path = cont.map((p, i) => `${i ? "L" : "M"}${f1(xm(p.m))},${f1(y(p.c))}`).join("");
  const neg = c.price.ret < 0, col = neg ? "var(--down)" : "var(--up)";
  const close = auct.filter(p => p.m >= 510).pop(), endM = close ? close.m : 515, endV = c.price.ret;
  const intr = c.intraday || {}, on = intr.onset || {};
  let ann = "";
  if (cont.length) ann += `<g class="ann" style="--i:0"><circle cx="${f1(xm(cont[0].m))}" cy="${f1(y(c.price.gap_open))}" r="4.5" fill="#fff" stroke="var(--navy)" stroke-width="2"/><text x="${f1(xm(cont[0].m) + 10)}" y="${f1(y(c.price.gap_open) + (neg ? -12 : 20))}" class="axb" paint-order="stroke" stroke="#fff" stroke-width="4">${L("Open", "Eröffnung")} ${P(c.price.gap_open)}</text></g>`;
  if (on.time) { const m = minOf(on.time); if (m >= 0 && m <= 515) ann += `<g class="ann" style="--i:1"><line x1="${f1(xm(m))}" x2="${f1(xm(m))}" y1="${mt - 14}" y2="${vy}" stroke="var(--sky)" stroke-width="1.5" stroke-dasharray="4 3"/><text x="${f1(xm(m) + 7)}" y="${mt - 4}" class="axb" fill="var(--sky)">${L("Market starts pricing it", "Markt preist ein ab")} ${on.time}</text></g>`; }
  const evT = (d.event_row || {}).time_local; if (evT) { const m = minOf(evT); if (m > 0 && m < 510) ann += `<g class="ann" style="--i:1"><line x1="${f1(xm(m))}" x2="${f1(xm(m))}" y1="${mt - 14}" y2="${vy}" stroke="var(--navy)" stroke-width="1.5"/><text x="${f1(xm(m) - 7)}" y="${mt + 12}" class="axb" fill="var(--navy)" text-anchor="end">${L("Announcement", "Meldung")} ${evT}</text></g>`; }
  (on.volatility_interruptions || []).forEach((t, k) => { const m = minOf(t); if (m < 0 || m > 515) return; ann += `<g class="ann" style="--i:${2 + k * .3}" data-tip="${enc(`<span class="t">${L("Volatility interruption", "Volatilitätsunterbrechung")}</span><br>${t}`)}"><path d="M${f1(xm(m))},${mt + PH} l4,-8 h-8z" fill="var(--down)"/></g>`; });
  if (intr.time_of_low && isN(intr.intraday_low)) { const m = minOf(intr.time_of_low), lv = intr.intraday_low / pc - 1, right = xm(m) > W * .6; ann += `<g class="ann" style="--i:2"><circle cx="${f1(xm(m))}" cy="${f1(y(lv))}" r="4.5" fill="#fff" stroke="${col}" stroke-width="2"/><text x="${f1(right ? xm(m) - 9 : xm(m) + 9)}" y="${f1(y(lv) + 20)}" class="axb" text-anchor="${right ? "end" : "start"}" paint-order="stroke" stroke="#fff" stroke-width="4">${L("Low", "Tief")} ${intr.time_of_low} · ${PX(intr.intraday_low)}</text></g>`; }
  if (isN(intr.volume_share_first_15min)) ann += `<g class="ann" style="--i:3"><text x="${f1(xm(15) + 6)}" y="${vy - VH + 12}" class="ax" fill="var(--sky)">${L("first 15 min", "erste 15 Min.")}: <tspan font-weight="700">${P(intr.volume_share_first_15min, 0, false)}</tspan> ${L("of turnover", "des Umsatzes")}</text></g>`;
  if (close) ann += `<g class="ann" style="--i:4"><text x="${f1(xm(close.m) - bw * 1.6)}" y="${vy - VH - 6}" class="axb" text-anchor="end">${L("Closing auction", "Schlussauktion")} ${EUR((c.auctions && c.auctions.close_auction_eur != null) ? c.auctions.close_auction_eur : close.eur)}</text></g>`;
  ann += `<g class="ann" style="--i:5"><line x1="${f1(xm(cont.length ? cont[cont.length - 1].m : 509))}" y1="${f1(y(cont.length ? cont[cont.length - 1].c : endV))}" x2="${f1(xm(endM))}" y2="${f1(y(endV))}" stroke="var(--navy)" stroke-dasharray="3 3"/><circle cx="${f1(xm(endM))}" cy="${f1(y(endV))}" r="5" fill="${col}"/><text x="${f1(xm(endM) + 12)}" y="${f1(y(endV) + 7)}" font-size="21" font-weight="700" fill="${col}">${P(endV)}</text><text x="${f1(xm(endM) + 12)}" y="${f1(y(endV) + 23)}" class="ax">${L("close", "Schluss")} ${PX(d.close)}</text></g>`;
  S._intra = {pts: cont, xm, y, W, ml, mr, T0, T1, pc};
  return `<svg viewBox="0 0 ${W} ${H}" id="isvg" role="img" aria-label="${L("Intraday price and turnover", "Intraday-Kurs und Umsatz")}">
    <rect x="${f1(xm(0))}" y="${mt}" width="${f1(xm(15) - xm(0))}" height="${PH + GAP + VH}" fill="var(--sky-wash)"/>${g}
    <line x1="${ml}" x2="${W - mr + 8}" y1="${vy}" y2="${vy}" stroke="var(--ink)"/>${vol}${au}
    <path d="${path}" fill="none" stroke="var(--navy)" stroke-width="1.8" stroke-linejoin="round" class="draw" pathLength="1"/>${ann}
    <g class="xh" id="ixh"><line y1="${mt}" y2="${vy}" stroke="var(--ink)"/><circle r="4" fill="var(--navy)"/></g>
    <rect class="hit" id="ihit" x="${xm(0)}" y="${mt}" width="${f1(xm(510) - xm(0))}" height="${PH}"/></svg>`;
}
function afterChart(d) {
  const a = d.aftershocks || [], W = 480, H = 170, n = a.length; if (!n) return "";
  const mx = Math.max(...a.map(x => x.vol_ratio || 0), 1.5), bw = W / n, y = v => H - Math.sqrt(Math.max(0, v) / mx) * H;
  const l = d.card.liquidity;
  const bars = a.map((x, i) => `<rect class="bar" style="--i:${i * 10}" x="${f1(i * bw + 2)}" y="${f1(y(x.vol_ratio || 0))}" width="${f1(bw - 4)}" height="${f1(H - y(x.vol_ratio || 0))}" fill="${x.t === 0 ? "var(--navy)" : (x.vol_ratio || 0) > 1.2 ? "var(--sky)" : "var(--bar)"}" data-tip="${enc(`<span class="t">${x.t === 0 ? L("Reaction day", "Reaktionstag") : (x.t > 0 ? "+" : "") + x.t} · ${dS(x.date)}</span><br>${L("Turnover", "Umsatz")} ${X(x.vol_ratio)} · ${L("trading cost", "Handelskosten")} ${X(x.xlm_ratio)}<br>${L("abnormal", "abnormal")} ${P(x.abn_ret)}`)}"/>`).join("");
  const firstNormal = a.find(x => x.t > 0 && (x.vol_ratio || 0) <= 1.2);
  const t0 = a.findIndex(x => x.t === 0);
  return `<p style="margin:4px 0 10px;font-size:15px">${firstNormal ? L(`Turnover was back within 1.2× normal after <b>${firstNormal.t} ${firstNormal.t === 1 ? "day" : "days"}</b>`, `Umsatz nach <b>${firstNormal.t} ${firstNormal.t === 1 ? "Tag" : "Tagen"}</b> wieder unter 1,2× normal`) : L("Turnover stayed above 1.2× normal for the whole window", "Umsatz blieb im ganzen Fenster über 1,2× normal")}${isN(l.days_to_normal) ? L(`; trading cost after <b>${l.days_to_normal}</b>.`, `; Handelskosten nach <b>${l.days_to_normal}</b>.`) : "."}</p>
  <div class="chart"><svg viewBox="0 0 ${W} ${H + 22}">${bars}<line x1="0" x2="${W}" y1="${f1(y(1.2))}" y2="${f1(y(1.2))}" class="zero"/><text x="${W}" y="${f1(y(1.2) - 5)}" class="ax" text-anchor="end">1.2× ${L("normal", "normal")}</text><line x1="0" x2="${W}" y1="${H}" y2="${H}" stroke="var(--ink)"/>
  ${a.map((x, i) => x.t % 5 === 0 ? `<text x="${f1(i * bw + bw / 2)}" y="${H + 16}" class="ax" text-anchor="middle">${x.t === 0 ? L("day 0", "Tag 0") : (x.t > 0 ? "+" : "") + x.t}</text>` : "").join("")}</svg></div>`;
}

/* ---------- AI summary (on the card) ---------- */
function aiBoxHTML(k) {
  const lang = S.aiLang || S.lang, r = S.ai[k + "|" + lang], live = r ? r.source === "llm" : S.status && S.status.llm;
  const chk = r ? numbersCheck(r.text, S.cards[k] && S.cards[k].card) : null;
  return `<div class="head"><h2 class="h2">${L("AI summary", "KI-Zusammenfassung")}</h2>
    <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap"><span class="badge ${live ? "on" : ""}"><i></i>${live ? L(`Written by ${esc((r && r.model) || S.status.model || "the language model")}`, `Geschrieben von ${esc((r && r.model) || S.status.model || "dem Sprachmodell")}`) : r && r.rejected && r.rejected.length ? L("Template text (the model's draft had figures not in the card)", "Vorlagentext (Entwurf des Modells hatte Zahlen, die nicht in der Karte stehen)") : L("Template text (no language model connected)", "Vorlagentext (kein Sprachmodell verbunden)")}</span>${seg("ailang", [["en", "EN"], ["de", "DE"]], lang)}</div></div>
    <p class="ai-text ${r ? "" : "wait"}" id="aitext">${r ? esc(r.text) : L("Writing the summary from the card…", "Die Zusammenfassung wird aus der Karte geschrieben…") + '<span class="caret"></span>'}</p>
    <div class="ai-foot"><span class="check ${chk && chk.bad ? "warn" : ""}" id="aichk">${chk ? checkHTML(chk) : ""}</span>
      <span style="display:flex;gap:18px;flex-wrap:wrap"><button class="link" data-act="regen">${L("Regenerate", "Neu schreiben")}</button><button class="link" data-act="copy">${L("Copy", "Kopieren")}</button><button class="link" data-act="toreport">${L("Put in report", "In den Report")} ${ARR}</button></span></div>`;
}
const checkHTML = c => `<svg width="18" height="18" viewBox="0 0 20 20"><circle cx="10" cy="10" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/>${c.bad ? '<path d="M10 5v6M10 14v1" stroke="currentColor" stroke-width="2"/>' : '<path d="M6 10.5l2.6 2.6L14 7.6" fill="none" stroke="currentColor" stroke-width="2"/>'}</svg>` +
  (c.bad ? L(`${c.bad} of ${c.total} figures not found in the card: ${c.miss.slice(0, 3).join(", ")}`, `${c.bad} von ${c.total} Zahlen nicht in der Karte: ${c.miss.slice(0, 3).join(", ")}`) : L(`All ${c.total} figures match the impact card`, `Alle ${c.total} Zahlen stimmen mit der Impact Card überein`));
/* every number in the AI text must exist in the card JSON (rounded); dates and clock times must match exactly */
function numbersCheck(text, card) {
  if (!text || !card) return null;
  const nums = [], strs = new Set(), miss = [];
  (function walk(o) { if (o === null || o === undefined) return; if (typeof o === "number") { [o, o * 100, o / 1e3, o / 1e6, o / 1e9].forEach(v => nums.push(v, Math.abs(v))); nums.push(Math.floor(Math.abs(o) * 100)); } else if (typeof o === "string") strs.add(o); else if (typeof o === "object") Object.values(o).forEach(walk); })(card);
  // same rules as the server check (ai/checks.py): EUR k/m/bn, and "#3 of 215" = the group plus this event
  if (card.comparison && Number.isInteger(card.comparison.n)) nums.push(card.comparison.n + 1);
  const allStr = [...strs].join(" ");
  let t = text.replace(/\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b/g, (m, d, mo, y) => { const iso = `${y}-${mo.padStart(2, "0")}-${d.padStart(2, "0")}`; if (!allStr.includes(iso)) miss.push(m); return " "; });  // German dates
  t = t.replace(/\b\d{4}-\d{2}-\d{2}\b/g, m => { strs.has(m) || allStr.includes(m) ? 0 : miss.push(m); return " "; });
  t = t.replace(/\b\d{1,2}:\d{2}\b/g, m => { if (!allStr.includes(m)) miss.push(m); return " "; });
  const toks = t.match(/[−-]?\d+(?:[.,]\d+)?/g) || [];
  let total = 0;
  toks.forEach(tok => { const v = Math.abs(parseFloat(tok.replace("−", "-").replace(",", "."))); if (!isFinite(v)) return; if (v === 25 || v === 2026) return; total++;
    const dec = (tok.split(/[.,]/)[1] || "").length, tol = dec ? .5 * 10 ** -dec + 1e-9 : .5 + 1e-9;
    if (!nums.some(n => Math.abs(Math.abs(n) - v) <= tol)) miss.push(tok); });
  total += (text.match(/\b\d{1,2}:\d{2}\b/g) || []).length + (text.match(/\b\d{4}-\d{2}-\d{2}\b/g) || []).length;
  return {total, bad: miss.length, miss};
}
async function runAI(k, lang, force = false) {
  const id = k + "|" + lang;
  if (S.ai[id] && !force) { updateAIBox(k); return; }
  const [isin, day, ev] = k.split("|");
  updateAIBox(k, true);
  try {
    const r = await post("/api/narrate", {isin, day, event_id: ev || null, lang});
    S.ai[id] = r;
    if (keyOf(S.sel || {}) === k && S.page === "card") streamAI(k, r.text);
  } catch (e) { const el = $("#aitext"); if (el) el.textContent = L("The summary could not be generated: ", "Zusammenfassung fehlgeschlagen: ") + e.message; }
}
function updateAIBox(k, waiting = false) {
  const box = $("#aibox"); if (!box || keyOf(S.sel || {}) !== k) return;
  if (waiting) { const t = $("#aitext"); t.classList.add("wait"); t.innerHTML = L("Writing the summary from the card…", "Die Zusammenfassung wird aus der Karte geschrieben…") + '<span class="caret"></span>'; $("#aichk").innerHTML = ""; return; }
  box.innerHTML = aiBoxHTML(k); segThumb();
}
let streamTok = 0;
function streamAI(k, text) {
  const el = $("#aitext"); if (!el) return; const tok = ++streamTok; el.classList.remove("wait");
  const w = text.split(" "); let i = 0;
  (function step() { if (tok !== streamTok || !document.body.contains(el)) return; el.innerHTML = esc(w.slice(0, ++i).join(" ")) + (i < w.length ? '<span class="caret"></span>' : "");
    if (i < w.length) setTimeout(step, reduced ? 0 : 18 + Math.random() * 30); else updateAIBox(k); })();
}

/* ============================== 3 compare ============================== */
function pCompare() {
  const c = S.cmp;
  if (!c.type) { const cur = S.sel && S.cards[keyOf(S.sel)]; c.type = cur && cur.card.comparison ? cur.card.comparison.group_type : "NOTABLE_DAY"; }
  const types = (c.data && c.data.types) || ["NOTABLE_DAY", "FY", "Q1", "H1", "Q3", "ADHOC", "DIVIDEND_EX", "AGM", "GUIDANCE", "INDEX", "MA"];
  return `<section class="sec wrap rv" style="padding-top:44px">
    <div class="filters">${L("Show", "Zeige")} <select data-cmp="type" aria-label="type">${types.map(t => `<option value="${t}" ${t === c.type ? "selected" : ""}>${TYPE(t)}</option>`).join("")}</select>
      ${L("in", "in")} <select data-cmp="index" aria-label="index">${[["ALL", L("DAX, MDAX and SDAX", "DAX, MDAX und SDAX")], ["DAX", "DAX"], ["MDAX", "MDAX"], ["SDAX", "SDAX"]].map(([v, t]) => `<option value="${v}" ${v === c.index ? "selected" : ""}>${t}</option>`).join("")}</select> ${L("in 2026", "2026")}</div>
    <div id="cmpbody">${c.data ? cmpBody() : `<div class="skel" style="min-height:420px"></div>`}</div></section>`;
}
async function loadCompare() {
  const c = S.cmp, want = `${c.type}|${c.index}`;
  if (c.data && c.key === want) return;
  try { const d = await api(`/api/compare?type=${c.type}${c.index !== "ALL" ? "&index=" + c.index : ""}`); c.data = d; c.key = want; }
  catch (e) { $("#cmpbody") && ($("#cmpbody").innerHTML = `<p class="empty">${esc(e.message)}</p>`); return; }
  if (S.page !== "compare") return; const b = $("#cmpbody"); b.innerHTML = cmpBody(); after(b);
}
function cmpBody() {
  const rows = (S.cmp.data.rows || []).filter(r => isN(r.abn_ret));
  if (!rows.length) return `<p class="empty">${L("No events of this type in this index yet. The research team adds them to events/events.csv.", "Noch keine Ereignisse dieses Typs in diesem Index. Das Research-Team ergänzt sie in events/events.csv.")}</p>`;
  const sorted = [...rows].sort((a, b) => Math.abs(b.abn_ret) - Math.abs(a.abn_ret));
  const me = r => r.isin === S.isin && S.sel && String(r.reaction_day).slice(0, 10) === S.sel.day;
  const mine = sorted.findIndex(me), mineAny = sorted.filter(r => r.isin === S.isin).length;
  const u = U(S.isin);
  const verdict = mine >= 0 ? L(`${esc(nice(u))} on ${dS(S.sel.day)} ranks <b>#${mine + 1} of ${sorted.length}</b> by stock-specific move.`, `${esc(nice(u))} am ${dS(S.sel.day)} liegt auf <b>Rang ${mine + 1} von ${sorted.length}</b> nach titelspezifischer Bewegung.`)
    : L(`${sorted.length} events. ${esc(nice(u))} has ${mineAny} of them${mineAny ? ", marked in blue" : ""}.`, `${sorted.length} Ereignisse. ${esc(nice(u))} hat davon ${mineAny}${mineAny ? ", blau markiert" : ""}.`);
  const nm = r => `${esc(nice(U(r.isin) || r))} · ${dS(r.reaction_day)}`;
  return `<p class="verdict">${verdict}</p><div class="cols-21"><div><div class="chart" id="scatter">${scatter(rows, me)}</div>
    <p class="sec-note">${L("x: turnover vs normal (log scale), y: stock-specific move. Click a dot to open its card.", "x: Umsatz vs. normal (log), y: titelspezifische Bewegung. Punkt anklicken öffnet die Karte.")}</p></div>
    <div><table class="tbl"><thead><tr><th>#</th><th>${L("Event", "Ereignis")}</th><th class="r">${L("Abnormal", "Abnormal")}</th><th class="r">${L("Turnover", "Umsatz")}</th></tr></thead><tbody>
    ${sorted.slice(0, 12).map((r, i) => `<tr class="go ${me(r) ? "me" : ""}" data-open="${r.isin}|${String(r.reaction_day).slice(0, 10)}|${esc(r.event_id || "")}"><td class="m">${i + 1}</td><td>${nm(r)}</td><td class="r"><b>${P(r.abn_ret)}</b></td><td class="r">${X(r.vol_ratio)}</td></tr>`).join("")}</tbody></table>
    <p class="sec-note">${L("Medians", "Mediane")}: ${L("move", "Bewegung")} ${P(median(rows.map(r => Math.abs(r.abn_ret))), 1, false)} · ${L("turnover", "Umsatz")} ${X(median(rows.map(r => r.vol_ratio)))} · ${L("trading cost", "Handelskosten")} ${X(median(rows.map(r => r.xlm_ratio)))}</p></div></div>`;
}
function scatter(rows, me) {
  const W = 720, H = 430, ml = 54, mr = 18, mt = 16, mb = 40;
  const vs = rows.map(r => r.vol_ratio).filter(v => isN(v) && v > 0), lx0 = Math.log(Math.max(.4, Math.min(...vs) * .9)), lx1 = Math.log(Math.max(...vs) * 1.1);
  const as = rows.map(r => r.abn_ret), y0 = Math.min(-.02, ...as) * 1.08, y1 = Math.max(.02, ...as) * 1.08;
  const x = v => ml + Math.max(0, Math.min(1, (Math.log(Math.max(v, 1e-3)) - lx0) / (lx1 - lx0))) * (W - ml - mr), y = v => mt + (y1 - v) / (y1 - y0) * (H - mt - mb);
  let g = ""; const st = (y1 - y0) > .3 ? .1 : (y1 - y0) > .12 ? .05 : .02;
  for (let v = Math.ceil(y0 / st) * st; v <= y1; v += st) g += `<line x1="${ml}" x2="${W - mr}" y1="${f1(y(v))}" y2="${f1(y(v))}" class="${Math.abs(v) < 1e-9 ? "zero" : "gl"}"/><text x="${ml - 8}" y="${f1(y(v) + 4)}" class="ax" text-anchor="end">${P(v, 0)}</text>`;
  [.5, 1, 2, 5, 10, 20, 50].filter(v => Math.log(v) > lx0 && Math.log(v) < lx1).forEach(v => g += `<line x1="${f1(x(v))}" x2="${f1(x(v))}" y1="${mt}" y2="${H - mb}" class="gl"/><text x="${f1(x(v))}" y="${H - mb + 18}" class="ax" text-anchor="middle">${X(v, v < 1 ? 1 : 0)}</text>`);
  const tip = r => enc(`<span class="t">${esc(nice(U(r.isin) || r))} · ${dL(r.reaction_day)}</span><br>${esc(r.type)} · ${esc(r.index)}<br>${L("abnormal", "abnormal")} ${P(r.abn_ret)} · ${X(r.vol_ratio)} ${L("turnover", "Umsatz")}${r.title ? "<br><span class='m'>" + esc(String(r.title).slice(0, 90)) + "</span>" : ""}`);
  const ord = [...rows].sort((a, b) => (a.isin === S.isin) - (b.isin === S.isin) || me(a) - me(b));
  const dots = ord.map(r => { if (!isN(r.vol_ratio)) return ""; const cx = f1(x(r.vol_ratio)), cy = f1(y(r.abn_ret)), on = `data-open="${r.isin}|${String(r.reaction_day).slice(0, 10)}|${esc(r.event_id || "")}" data-tip="${tip(r)}" style="cursor:pointer"`;
    if (me(r)) return `<circle cx="${cx}" cy="${cy}" r="16" fill="none" stroke="var(--sky)" stroke-width="1.5"/><circle cx="${cx}" cy="${cy}" r="7" fill="var(--navy)" stroke="#fff" stroke-width="2" ${on}/><text x="${+cx - 22}" y="${+cy + 4}" class="axb" fill="var(--navy)" text-anchor="end" paint-order="stroke" stroke="#fff" stroke-width="4">${esc(r.ticker)} ${dS(r.reaction_day)}</text>`;
    if (r.isin === S.isin) return `<circle cx="${cx}" cy="${cy}" r="5.5" fill="#fff" stroke="var(--navy)" stroke-width="2" ${on}/>`;
    return `<circle cx="${cx}" cy="${cy}" r="${rows.length > 400 ? 3 : 4}" fill="var(--graphite)" fill-opacity=".45" ${on}/>`; }).join("");
  return `<svg viewBox="0 0 ${W} ${H}">${g}<g class="ann" style="--i:-4">${dots}</g></svg>`;
}

/* ============================== 4 report: IR snapshot (IV, VIII) ============================== */
function repOptions() {
  const o = [];
  S.iss.events.forEach(e => o.push([`${String(e.reaction_day).slice(0, 10)}|${e.event_id}`, `${dS(e.reaction_day)} · ${e.type} · ${String(e.title).slice(0, 40)}`]));
  const evd = new Set(S.iss.events.map(e => String(e.reaction_day).slice(0, 10)));
  S.iss.anomalies.filter(a => !evd.has(a.peak_date)).forEach(a => o.push([`${a.peak_date}|`, `${dS(a.peak_date)} · ${L("unusual day", "auffälliger Tag")} ${P(a.peak_abn_ret)}`]));
  return o.sort((a, b) => b[0].localeCompare(a[0]));
}
function pReport() {
  const r = S.rep; if (!r.key) { const ds = S.sel || defaultSel(); r.key = `${ds.day}|${ds.event_id || ""}`; }
  const box = (k, t) => `<label><input type="checkbox" data-rep="${k}" ${r[k] ? "checked" : ""}> ${t}</label>`;
  return `<section class="wrap print-me"><div class="rep">
    <div class="rep-side rv"><div><div class="lbl">${L("Sections", "Abschnitte")}</div>
      ${box("a", L("Trading profile (60 days)", "Handelsprofil (60 Tage)"))}${box("peers", L("Peer benchmark", "Peer-Vergleich"))}${box("liq", L("Liquidity verdict", "Liquiditätsbewertung"))}${box("anom", L("Unusual days", "Auffällige Tage"))}${box("card", L("Impact card", "Impact Card"))}${box("ai", L("AI summary of the card", "KI-Zusammenfassung der Karte"))}</div>
      <div><div class="lbl">${L("Event for the impact card", "Ereignis für die Impact Card")}</div><select data-rep="key">${repOptions().map(([v, t]) => `<option value="${esc(v)}" ${v === r.key ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></div>
      <div><div class="lbl">${L("Language", "Sprache")}</div>${seg("replang", [["en", "EN"], ["de", "DE"]], S.lang)}</div>
      <div><button class="pill" data-act="print">${L("Download PDF", "PDF herunterladen")} ${ARR}</button><p class="sec-note">${L("A4 layout. Choose “Save as PDF” in the print dialog.", "A4-Layout. Im Druckdialog „Als PDF sichern“ wählen.")}</p></div></div>
    <div class="rep-view rv" style="--d:.1s"><div class="sheet" id="sheet">${sheetHTML()}</div></div></div></section>`;
}
function sheetHTML() {
  const r = S.rep, u = U(S.isin), iss = S.iss, k = iss.kpis, lt = iss.liquidity, [day, ev] = (r.key || "|").split("|");
  const ck = `${S.isin}|${day}|${ev || ""}`, d = S.cards[ck], ai = S.ai[ck + "|" + S.lang];
  const prices = iss.series.price.filter(isN);
  let h = `<div class="sh-top"><div><div class="k">${L("IR snapshot", "IR-Snapshot")} · ${u.ticker} · ${u.isin} · ${u.index}</div><h3>${esc(nice(u))}</h3></div><div class="k" style="text-align:right">Issuer Intelligence Hub<br>${L("Xetra data as of the close on", "Xetra-Daten bis Handelsschluss")} ${dL(iss.meta.last_date)}</div></div>`;
  if (r.a) h += `<section><h4>${L("Normal state, last 60 trading days", "Normalzustand, letzte 60 Handelstage")}</h4><table><tr><th></th><th class="r">${u.ticker}</th><th class="r">${u.index} ${L("median", "Median")}</th></tr>
    <tr><td>${L("Turnover per day", "Umsatz pro Tag")}</td><td class="r"><b>${EUR(k.median_turnover_eur.stock)}</b></td><td class="r">${EUR(k.median_turnover_eur.index_median)}</td></tr>
    <tr><td>${L("Trading cost €25k (XLM)", "Handelskosten 25 T€ (XLM)")}</td><td class="r"><b>${BPS(k.median_xlm_25k_bps.stock)}</b></td><td class="r">${BPS(k.median_xlm_25k_bps.index_median)}</td></tr>
    <tr><td>${L("Auction share", "Auktionsanteil")}</td><td class="r"><b>${P(k.median_auction_share.stock, 0, false)}</b></td><td class="r">${P(k.median_auction_share.index_median, 0, false)}</td></tr>
    <tr><td>${L("Client (agent) share", "Anteil Kundenorders")}</td><td class="r"><b>${P(k.median_agent_share.stock, 0, false)}</b></td><td class="r">${P(k.median_agent_share.index_median, 0, false)}</td></tr>
    <tr><td>${L("Performance since 2 Jan", "Performance seit 2. Jan.")}</td><td class="r"><b>${P(prices[prices.length - 1] / prices[0] - 1)}</b></td><td class="r"></td></tr></table></section>`;
  if (r.peers) { const p = iss.peers, g = p.groups.filter(x => x.values && x.n); h += `<section><h4>${L("Peer benchmark", "Peer-Vergleich")}</h4><table><tr><th></th><th class="r">${u.ticker}</th>${g.map(x => `<th class="r">${x.key === "index" ? u.index : x.key === "size" ? L("Similar size", "Ähnl. Größe") : esc(x.label)}</th>`).join("")}</tr>
    ${[["turnover_eur", L("Turnover", "Umsatz"), EUR], ["xlm_25k", "XLM 25k", BPS], ["volatility", L("Volatility", "Volatilität"), v => P(v, 0, false)]].map(([kk, t, f]) => `<tr><td>${t}</td><td class="r"><b>${f(p.stock[kk])}</b></td>${g.map(x => `<td class="r">${f(x.values[kk])}</td>`).join("")}</tr>`).join("")}</table></section>`; }
  if (r.liq) h += `<section><h4>${L("Liquidity", "Liquidität")}</h4><p style="margin:0">${L(`Trading cost ${P(lt.xlm_25k_change_pct, 0)} and turnover ${P(lt.turnover_change_pct, 0)} (last 60 vs previous 60 trading days; ${u.index}: ${P(lt.index_xlm_25k_change_pct, 0)} / ${P(lt.index_turnover_change_pct, 0)}). Xetra liquidity category (estimate): ${k.liquidity_check.category_estimate}.`, `Handelskosten ${P(lt.xlm_25k_change_pct, 0)} und Umsatz ${P(lt.turnover_change_pct, 0)} (letzte 60 vs. vorherige 60 Handelstage; ${u.index}: ${P(lt.index_xlm_25k_change_pct, 0)} / ${P(lt.index_turnover_change_pct, 0)}). Xetra-Liquiditätskategorie (Schätzung): ${k.liquidity_check.category_estimate}.`)}</p></section>`;
  if (r.anom && iss.anomalies.length) h += `<section><h4>${L("Unusual days", "Auffällige Tage")}</h4><table><tr><th>${L("Date", "Datum")}</th><th class="r">${L("Abnormal", "Abnormal")}</th><th class="r">${L("Turnover", "Umsatz")}</th><th>${L("Calendar", "Kalender")}</th></tr>${iss.anomalies.slice(0, 6).map(a => `<tr><td>${dS(a.peak_date)}</td><td class="r">${P(a.peak_abn_ret)}</td><td class="r">${X(a.max_vol_ratio)}</td><td>${a.event ? esc(a.event.type) : L("cause open", "Ursache offen")}</td></tr>`).join("")}</table></section>`;
  if (r.card) {
    if (!d) h += `<section><h4>${L("Impact card", "Impact Card")}</h4><p class="m">${L("Loading…", "Wird geladen…")}</p></section>`;
    else { const c = d.card; h += `<section><h4>${L("Impact card", "Impact Card")} · ${dL(c.event.reaction_day)} · ${esc(c.event.type)}</h4>${c.event.type !== "NOTABLE_DAY" ? `<p style="margin:0 0 6px">${esc(c.event.title)}</p>` : ""}<table>
      ${[[L("Share return", "Rendite"), P(c.price.ret)], [L("Peers", "Peers"), P(c.price.peer_ret)], [L("Stock-specific move", "Titelspezifische Bewegung"), P(c.price.abn_ret)], [L("Turnover vs normal", "Umsatz vs. normal"), X(c.volume.ratio)], [L("Trading cost vs normal", "Handelskosten vs. normal"), X(c.liquidity.ratio)],
         [L("Opening auction vs normal", "Eröffnungsauktion vs. normal"), X(c.auctions.open_auction_ratio)], [L("Closing auction", "Schlussauktion"), `${EUR(c.auctions.close_auction_eur)} (${X(c.auctions.close_auction_ratio)})`], [L("Client net flow", "Kunden-Nettofluss"), P(c.participants.agent_aggr_imbalance, 0)]].map(([a, b]) => `<tr><td>${a}</td><td class="r"><b>${b}</b></td></tr>`).join("")}</table>
      ${d.bars ? `<div style="margin-top:8px">${sparkIntra(d)}</div>` : ""}</section>`; }
  }
  if (r.ai) h += `<section><h4>${L("Summary", "Zusammenfassung")}</h4><p style="margin:0;font-size:13px;line-height:1.55">${ai ? esc(ai.text) : `<span class="m">${L("Writing…", "Wird geschrieben…")}</span>`}</p></section>`;
  h += `<div class="foot">${L("Source: Deutsche Börse Xetra data (OHLC, flow dynamics, XLM, on-book trades), events/events.csv. Figures computed by the engine; text generated from them and checked. Peers = equal-weighted index members. Causes are not in the data. Not investment advice.", "Quelle: Deutsche Börse Xetra-Daten (OHLC, Flow Dynamics, XLM, On-Book-Trades), events/events.csv. Zahlen von der Engine berechnet; Text daraus generiert und geprüft. Peers = gleichgewichtete Indexmitglieder. Ursachen sind nicht in den Daten. Keine Anlageberatung.")}</div>`;
  return h;
}
function sparkIntra(d) {
  const b = d.bars, pc = d.prev_close, pts = b.t.map((t, i) => [minOf(t), b.close[i] / pc - 1]).filter(p => p[0] >= 0 && p[0] < 510 && isN(p[1]));
  const lo = Math.min(0, ...pts.map(p => p[1])), hi = Math.max(0, ...pts.map(p => p[1])), y = v => 4 + (hi - v) / (hi - lo || 1) * 72, x = m => m / 515 * 600;
  return `<svg viewBox="0 0 600 80" style="width:100%;height:auto"><line x1="0" x2="600" y1="${f1(y(0))}" y2="${f1(y(0))}" stroke="#bdbdbd" stroke-dasharray="3 3"/><path d="${pts.map((p, i) => `${i ? "L" : "M"}${f1(x(p[0]))},${f1(y(p[1]))}`).join("")}" fill="none" stroke="#000099" stroke-width="1.4"/><text x="0" y="78" font-size="9" fill="#6f6f6f">09:00</text><text x="600" y="78" font-size="9" fill="#6f6f6f" text-anchor="end">17:35</text></svg>`;
}
async function loadReport() {
  const [day, ev] = (S.rep.key || "|").split("|"); if (!day) return;
  const ck = `${S.isin}|${day}|${ev || ""}`;
  if (!S.cards[ck]) { try { S.cards[ck] = await api(cardURL(S.isin, day, ev)); } catch (e) { return; } }
  if (!S.ai[ck + "|" + S.lang]) { try { S.ai[ck + "|" + S.lang] = await post("/api/narrate", {isin: S.isin, day, event_id: ev || null, lang: S.lang}); } catch (e) { /* keep placeholder */ } }
  if (S.page === "report") $("#sheet") && ($("#sheet").innerHTML = sheetHTML());
}

/* ============================== 5 ideas ============================== */
const ILL = [
  `<svg viewBox="0 0 210 116"><g stroke="#bdbdbd">${[20, 38, 56, 74, 92].map(y => `<line x1="20" x2="190" y1="${y}" y2="${y}"/>`).join("")}</g><line x1="20" x2="190" y1="65" y2="65" stroke="#000099" stroke-dasharray="4 3"/><text x="190" y="60" font-size="9" fill="#000099" text-anchor="end">SDAX cut-off</text><path class="hl" pathLength="1" d="M20 40 C60 42 80 50 110 58 S160 80 190 88" fill="none" stroke="#0099ff" stroke-width="2.5"/><circle cx="190" cy="88" r="4" fill="#0099ff"/></svg>`,
  `<svg viewBox="0 0 210 116"><line x1="20" x2="190" y1="58" y2="58" stroke="#bdbdbd" stroke-width="4"/><line x1="130" x2="130" y1="42" y2="74" stroke="#181813" stroke-width="1.5"/><text x="130" y="36" font-size="9" fill="#404040" text-anchor="middle">100 bps</text><path class="hl" pathLength="1" d="M20 58 H112" stroke="#000099" stroke-width="4"/><circle cx="112" cy="58" r="7" fill="#fff" stroke="#000099" stroke-width="2.5"/></svg>`,
  `<svg viewBox="0 0 210 116"><line x1="20" x2="190" y1="96" y2="96" stroke="#181813"/>${[10, 40, 70, 28, 18, 14, 12, 16, 20, 26, 48, 8].map((v, i) => `<rect x="${22 + i * 14}" y="${96 - v}" width="9" height="${v}" fill="${i === 2 ? "#000099" : "#cfd3da"}"/>`).join("")}<path class="hl" pathLength="1" d="M54 18 V96" stroke="#0099ff" stroke-width="1.5" stroke-dasharray="3 3"/></svg>`,
  `<svg viewBox="0 0 210 116"><line x1="20" x2="190" y1="96" y2="96" stroke="#181813"/>${Array.from({length: 22}, (_, i) => { const v = i < 14 ? 8 + ((i * 7) % 5) * 2 : i < 17 ? 30 + (i - 14) * 12 : 62 - (i - 17) * 6; return `<rect x="${22 + i * 7.6}" y="${96 - v}" width="5" height="${v}" fill="${i >= 14 && i < 17 ? "#0099ff" : "#cfd3da"}"/>`; }).join("")}<path class="hl" pathLength="1" d="M152 14 V96" stroke="#000099" stroke-width="1.5"/><text x="148" y="16" font-size="9" fill="#000099" text-anchor="end">news</text></svg>`,
  `<svg viewBox="0 0 210 116">${[0, 1, 2, 3, 4].map(i => `<rect x="${30 + i * 32}" y="30" width="24" height="66" fill="#cfd3da"/><rect x="${30 + i * 32}" y="${96 - [12, 18, 9, 22, 15][i]}" width="24" height="${[12, 18, 9, 22, 15][i]}" fill="#000099"/>`).join("")}<line x1="20" x2="190" y1="96" y2="96" stroke="#181813"/></svg>`,
  `<svg viewBox="0 0 210 116"><line x1="105" x2="105" y1="10" y2="106" stroke="#bdbdbd"/><line x1="20" x2="190" y1="58" y2="58" stroke="#bdbdbd"/>${[[40, 90], [60, 78], [80, 70], [95, 66], [120, 52], [140, 44], [160, 36], [70, 50], [150, 70], [175, 28]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="3.5" fill="#8c9198" fill-opacity=".6"/>`).join("")}<path class="hl" pathLength="1" d="M30 98 L185 24" stroke="#0099ff" stroke-width="2"/></svg>`];
function pIdeas() {
  const I = [
    [L("Index watch", "Index-Frühwarnung"), L("Gerresheimer left the SDAX on 9 April and its XLM coverage ended with it. Track the share's rank against the index rules every day and warn months ahead.", "Gerresheimer schied am 9. April aus dem SDAX aus, damit endete auch die XLM-Abdeckung. Den Rang täglich gegen die Indexregeln verfolgen und Monate vorher warnen."), L("daily index lists, turnover", "tägliche Indexlisten, Umsatz"), L("free-float market cap, official rank lists", "Free-Float-Marktkapitalisierung, Ranglisten")],
    [L("Liquidity category monitor", "Liquiditätskategorie-Monitor"), L("Small caps such as Heidelberger Druck sit close to the Designated Sponsor thresholds. Track the rolling 4-month position against both rules.", "Small Caps wie Heidelberger Druck liegen nah an den Designated-Sponsor-Schwellen. Die rollierende 4-Monats-Position gegen beide Regeln verfolgen."), L("XLM, turnover", "XLM, Umsatz"), L("official category list", "offizielle Kategorieliste")],
    [L("Announcement planner", "Veröffentlichungsplaner"), L("Which publication time gives the cleanest reaction? Compare reactions by release time across all events of the same type.", "Welche Veröffentlichungszeit sorgt für die sauberste Reaktion? Reaktionen nach Uhrzeit über gleichartige Ereignisse vergleichen."), L("1-minute bars, event times", "1-Minuten-Balken, Ereigniszeiten"), L("more events with exact times", "mehr Ereignisse mit genauer Uhrzeit")],
    [L("Before-the-news monitor", "Vor-der-Nachricht-Monitor"), L("Unusual volume or one-sided client flow in the days before an announcement is a question IR wants to ask first.", "Auffälliger Umsatz oder einseitiger Kundenfluss vor einer Meldung ist eine Frage, die IR zuerst stellen will."), L("flows, 1-minute bars", "Flows, 1-Minuten-Balken"), L("ad hoc and news timestamps", "Zeitstempel von Ad-hoc-Meldungen")],
    [L("Derivatives positioning", "Derivate-Positionierung"), L("Eurex open interest by participant (long/short) on single-stock options and futures shows how the market positioned before an event.", "Eurex Open Interest nach Teilnehmer (long/short) auf Einzelaktienoptionen und -futures zeigt die Positionierung vor einem Ereignis."), L("Eurex open interest in the excerpt, usable for large caps", "Eurex Open Interest im Auszug, nutzbar für Large Caps"), L("the participant split is censored for >90 % of small-cap series (e.g. 2 of 75 EVD series): uncensored data", "die Teilnehmer-Aufteilung ist bei >90 % der Small-Cap-Serien zensiert (z. B. 2 von 75 EVD-Serien): unzensierte Daten")],
    [L("Surprise vs consensus", "Überraschung vs. Konsens"), L("Put results-day reactions next to the earnings surprise so the board sees whether the market punished the number or the guidance.", "Reaktionen am Ergebnistag neben die Gewinnüberraschung stellen: Bestrafte der Markt die Zahl oder den Ausblick?"), L("abnormal return per event", "abnormale Rendite je Ereignis"), L("consensus estimates", "Konsensschätzungen")]];
  return `<section class="sec wrap"><div class="sec-head"><h2 class="h2">${L("Ideas for the Issuer Services Hub", "Ideen für den Issuer Services Hub")}</h2><p class="sec-note">${L("Have = already in the Xetra/Eurex excerpt. Need = data we would add.", "Hat = bereits im Xetra/Eurex-Auszug. Fehlt = zusätzliche Daten.")}</p></div>
  <div class="tiles">${I.map((t, i) => `<article class="tile rv" style="--d:${(i % 3) * .08}s"><div class="ill">${ILL[i]}</div><div class="body"><h3>${t[0]}</h3><p>${t[1]}</p><div class="data"><div><b>${L("Have", "Hat")}</b><span>${t[2]}</span></div><div class="need"><b>${L("Need", "Fehlt")}</b><span>${t[3]}</span></div></div></div></article>`).join("")}</div></section>`;
}

/* ============================== own event calendar (VI: ingest a corporate event calendar) ============================== */
const UEV_KEY = "iih.userEvents";
function userEvents(isin) { try { return (JSON.parse(localStorage.getItem(UEV_KEY) || "{}")[isin]) || []; } catch (e) { return S._uev && S._uev[isin] || []; } }
function saveUserEvents(isin, list) { S._uev = S._uev || {}; S._uev[isin] = list; try { const all = JSON.parse(localStorage.getItem(UEV_KEY) || "{}"); all[isin] = list; localStorage.setItem(UEV_KEY, JSON.stringify(all)); } catch (e) { /* private mode: keep in memory */ } }
function mergeUserEvents() { const own = userEvents(S.isin), ids = new Set(S.iss.events.map(e => e.event_id)); S.iss.events = S.iss.events.filter(e => !e.user).concat(own.filter(e => !ids.has(e.event_id))); }
function cardURL(isin, day, ev) {
  let u = `/api/card?isin=${isin}&day=${day}${ev ? `&event_id=${enc(ev)}` : ""}`;
  const own = ev && String(ev).startsWith("USR_") && userEvents(isin).find(e => e.event_id === ev);
  if (own) u += `&date=${own.date}&time=${enc(own.time_local || "")}&type=${enc(own.type)}&title=${enc(own.title)}`;
  return u;
}
// one-click IR report (PDF) for this card: same event parameters as the card itself
function exportURL(isin, day, ev) { return cardURL(isin, day, ev).replace("/api/card?", "/api/export?") + `&lang=${S.lang}`; }
const EVTYPES = ["FY", "Q1", "H1", "Q3", "ADHOC", "GUIDANCE", "DIVIDEND_EX", "AGM", "CMD", "MA", "OTHER"];
function evForm() {
  return `<form class="ev-form" id="evform"><div class="r2"><input id="ev-d" type="date" min="${S.iss.meta.first_date}" max="${S.iss.meta.last_date}" required aria-label="${L("Date", "Datum")}"><input id="ev-t" type="time" aria-label="${L("Time (CET)", "Uhrzeit (MEZ)")}"></div>
    <select id="ev-y" aria-label="${L("Type", "Typ")}">${EVTYPES.map(t => `<option value="${t}">${TYPE(t)}</option>`).join("")}</select>
    <input id="ev-n" placeholder="${L("Title, e.g. Q3 trading statement", "Titel, z. B. Q3-Mitteilung")}" maxlength="160">
    <button class="pill pill--sm" type="submit">${L("Build impact card", "Impact Card erstellen")} ${ARR}</button>
    <p class="m">${L("Time decides the reaction day: after the 17:35 closing auction it is the next trading day. CSV import: date,time,type,title. ICS from Outlook or Google also works.", "Die Uhrzeit bestimmt den Reaktionstag: nach der Schlussauktion um 17:35 ist es der nächste Handelstag. CSV-Import: date,time,type,title. ICS aus Outlook oder Google geht auch.")}</p></form>`;
}
const guessType = t => { t = String(t).toLowerCase(); return /hauptversammlung|agm|annual general/.test(t) ? "AGM" : /dividend|ex-tag/.test(t) ? "DIVIDEND_EX" : /\bq1\b|first quarter|1\. quartal/.test(t) ? "Q1" : /\bh1\b|half|halbjahr/.test(t) ? "H1" : /\bq3\b|third quarter|9m|nine months|9 monate/.test(t) ? "Q3" : /annual|full.year|geschäftsjahr|fy\b|jahresergebnis/.test(t) ? "FY" : /ad.hoc/.test(t) ? "ADHOC" : /guidance|prognose|outlook/.test(t) ? "GUIDANCE" : /capital markets day|kapitalmarkttag|cmd\b/.test(t) ? "CMD" : "OTHER"; };
function parseCalendar(text) {
  const out = [];
  if (/BEGIN:VEVENT/.test(text)) {
    text.replace(/\r?\n[ \t]/g, "").split("BEGIN:VEVENT").slice(1).forEach(b => {
      const st = (b.match(/DTSTART[^:]*:(\d{8})(?:T(\d{2})(\d{2})\d{0,2}(Z)?)?/) || []), sum = ((b.match(/SUMMARY[^:]*:(.*)/) || [])[1] || "").trim();
      if (!st[1]) return; let date = `${st[1].slice(0, 4)}-${st[1].slice(4, 6)}-${st[1].slice(6, 8)}`, time = st[2] ? `${st[2]}:${st[3]}` : "";
      if (st[4] && time) { const d = new Date(`${date}T${time}:00Z`), f = new Intl.DateTimeFormat("sv-SE", {timeZone: "Europe/Berlin", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"}).format(d).split(" "); date = f[0]; time = f[1]; }
      out.push({date, time, type: guessType(sum), title: sum.replace(/\\,/g, ",")});
    });
    return out;
  }
  const lines = text.split(/\r?\n/).filter(l => l.trim()), sep = (lines[0] || "").includes(";") ? ";" : ",";
  const head = lines[0].toLowerCase().split(sep).map(h => h.trim().replace(/"/g, "")), has = head.includes("date") || head.includes("datum");
  const ix = k => head.findIndex(h => k.includes(h));
  const iD = has ? ix(["date", "datum"]) : 0, iT = has ? ix(["time", "zeit", "uhrzeit"]) : 1, iY = has ? ix(["type", "typ"]) : 2, iN = has ? ix(["title", "titel", "event", "name"]) : 3;
  lines.slice(has ? 1 : 0).forEach(l => { const c = l.split(sep).map(x => x.trim().replace(/^"|"$/g, "")); let d = c[iD] || ""; const m = d.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/); if (m) d = `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`; if (!/^\d{4}-\d{2}-\d{2}/.test(d)) return;
    const title = iN >= 0 ? c[iN] || "" : ""; out.push({date: d.slice(0, 10), time: iT >= 0 ? c[iT] || "" : "", type: (iY >= 0 && EVTYPES.includes((c[iY] || "").toUpperCase())) ? c[iY].toUpperCase() : guessType(title), title}); });
  return out;
}
async function importCalendar(file) {
  const evs = parseCalendar(await file.text());
  if (!evs.length) { toast(L("No events found in this file", "Keine Ereignisse in der Datei gefunden")); return; }
  addEvents(evs, true);
}
async function addEvents(evs, bulk = false) {
  try {
    const r = await post("/api/calendar", {isin: S.isin, events: evs});
    const ok = r.events.filter(e => e.reaction_day), old = userEvents(S.isin).filter(e => !ok.some(n => n.event_id === e.event_id));
    saveUserEvents(S.isin, old.concat(ok)); mergeUserEvents(); S.addEv = false;
    const inRange = ok.length, skipped = r.events.length - ok.length;
    toast(bulk ? L(`${inRange} events matched to trading days${skipped ? `, ${skipped} after the data` : ""}`, `${inRange} Ereignisse Handelstagen zugeordnet${skipped ? `, ${skipped} nach Datenende` : ""}`) : L("Event added", "Ereignis hinzugefügt"));
    if (ok.length) openCard(ok[ok.length - 1].reaction_day, ok[ok.length - 1].event_id); else render();
  } catch (e) { toast(e.message); }
}

/* ============================== IR analyst (agent dock, on every page) ============================== */
const TOOLL = {find_company: ["Company search", "Unternehmenssuche"], company_overview: ["Trading profile", "Handelsprofil"], peer_benchmark: ["Peer benchmark", "Peer-Vergleich"], trading_cost_curve: ["Cost by order size", "Kosten nach Ordergröße"], unusual_days: ["Unusual days", "Auffällige Tage"], event_calendar: ["Event calendar", "Ereigniskalender"], impact_card: ["Impact card", "Impact Card"], compare_events: ["Event comparison", "Ereignisvergleich"], show: ["View", "Ansicht"]};
const stepL = st => { const t = TOOLL[st.tool] ? TOOLL[st.tool][de() ? 1 : 0] : st.tool, a = st.args || {}; return t + (a.day ? " " + dS(a.day) : "") + (a.by ? " · " + a.by : "") + (a.event_type ? " · " + TYPE(a.event_type) : "") + (a.query ? ` “${a.query}”` : ""); };
const actL = a => a.view === "card" ? `${L("Open impact card", "Impact Card öffnen")}${a.day ? " · " + dS(a.day) : ""}` : a.view === "compare" ? `${L("Compare", "Vergleichen")}${a.event_type ? ": " + TYPE(a.event_type) : ""}` : a.view === "report" ? L("Open IR snapshot", "IR-Snapshot öffnen") : L("Open dashboard", "Dashboard öffnen");
function doAction(a) {
  if (window.innerWidth < 1200) dockToggle(false);
  if (a.isin && a.isin !== S.isin && a.view !== "card") { openIsin(a.isin, {fromGate: false, then: () => { S.page = a.view; }}); return; }
  if (a.view === "card" && a.day) { openCard(a.day, a.event_id || null, a.isin || S.isin); return; }
  if (a.view === "compare") { if (a.event_type) S.cmp.type = a.event_type; S.cmp.index = a.index || "ALL"; S.cmp.data = null; if (S.page === "compare") vt(() => render()); else go("compare"); return; }
  if (a.view === "report") { if (a.day) { S.rep.key = `${a.day}|${a.event_id || ""}`; S.rep.card = S.rep.ai = true; } go("report"); return; }
  go("dashboard");
}
function dockCtx() { const c = {page: S.page}; if (S.page === "card" && S.sel) { c.day = S.sel.day; c.event_id = S.sel.event_id; } if (S.page === "report" && S.rep.key) { const [d, e] = S.rep.key.split("|"); c.day = d; c.event_id = e || null; } if (S.page === "compare") { c.event_type = S.cmp.type; c.index = S.cmp.index; } return c; }
function dockSugg() {
  const q = {
    card: [L("Explain this card in two sentences", "Erklären Sie diese Karte in zwei Sätzen"), L("How does this rank against similar events?", "Wie ordnet sich das gegenüber ähnlichen Ereignissen ein?"), L("Put this card in a report", "Diese Karte in einen Report")],
    compare: [L("Where do we rank among these events?", "Auf welchem Rang liegen wir bei diesen Ereignissen?"), L("How did the market react to our results?", "Wie hat der Markt auf unsere Ergebnisse reagiert?")],
    report: [L("Summarise our liquidity for the board", "Fassen Sie unsere Liquidität für den Vorstand zusammen"), L("What were our biggest moves this year?", "Was waren unsere größten Bewegungen dieses Jahr?")]
  }[S.page] || [L("Has our liquidity improved?", "Hat sich unsere Liquidität verbessert?"), L("How do our spreads compare with our sector?", "Wie sind unsere Spreads im Sektorvergleich?"), L("What were our biggest moves this year?", "Was waren unsere größten Bewegungen dieses Jahr?"), L("How large an order can the book absorb?", "Wie große Orders nimmt das Orderbuch auf?")];
  return q;
}
function dockMsg(m) {
  if (m.role === "user") return `<div class="dm q"><span class="who">${L("You", "Sie")}</span><p>${esc(m.content)}</p></div>`;
  const chk = m.check, bad = chk && chk.unsupported && chk.unsupported.length;
  const src = m.source === "llm" ? esc(m.model || "LLM") : L("template", "Vorlage");
  return `<div class="dm a"><span class="who">${L("Analyst", "Analyst")} · ${src}</span>
    ${m.steps && m.steps.length ? `<ol class="steps">${m.steps.filter(s => s.tool !== "show").map(s => `<li>${esc(stepL(s))}</li>`).join("")}</ol>` : ""}
    <p>${esc(m.content)}</p>
    ${m.actions && m.actions.length ? `<div class="acts">${m.actions.map(a => `<button class="pill pill--sm" data-do="${enc(JSON.stringify(a))}">${esc(actL(a))} ${ARR}</button>`).join("")}</div>` : ""}
    ${chk && chk.total ? `<div class="chk ${bad ? "warn" : ""}">${bad ? L(`${chk.unsupported.length} figure(s) not found in the engine output: ${chk.unsupported.slice(0, 3).join(", ")}`, `${chk.unsupported.length} Zahl(en) nicht in den Engine-Ergebnissen: ${chk.unsupported.slice(0, 3).join(", ")}`) : L(`✓ Every figure traced to engine output`, `✓ Jede Zahl aus den Engine-Ergebnissen`)}</div>` : ""}</div>`;
}
function dockRender() {
  const d = $("#dock"); if (!d || !S.iss) return;
  d.classList.toggle("on", S.dock); d.classList.remove("hidden");
  const u = U(S.isin), c = dockCtx(), live = S.status && S.status.llm;
  const where = c.day ? `${NAV[S.page] ? nav(S.page) : ""} · ${dS(c.day)}` : (NAV[S.page] ? nav(S.page) : "");
  $("#dock-fab").innerHTML = `<svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><polyline points="2,12 6,12 8,5 11,15 13,9 18,9" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg><span>${L("Ask the IR analyst", "IR-Analyst fragen")}</span><kbd>A</kbd>`;
  $("#dock-head").innerHTML = `<div><b>${L("IR analyst", "IR-Analyst")}</b><small><i class="${live ? "on" : ""}"></i>${live ? esc(S.status.model) + L(" · tools over the engine", " · Werkzeuge über die Engine") : L("template mode · add the JAIF key to .env", "Vorlagenmodus · JAIF-Schlüssel in .env")}</small></div>
    <div class="dh-r">${S.chat.length ? `<button data-act="dockclear" class="x" title="${L("New conversation", "Neues Gespräch")}">${L("New", "Neu")}</button>` : ""}<button data-act="dock" class="x" aria-label="${L("Close", "Schließen")}">✕</button></div>`;
  $("#dock-ctx").innerHTML = `<span>${L("Looking at", "Kontext")}</span> <b>${esc(nice(u))}</b> · ${esc(where)}`;
  const log = $("#dock-log");
  log.innerHTML = S.chat.length ? S.chat.map(dockMsg).join("") + (S.busy ? `<div class="dm a busy"><span class="who">${L("Analyst", "Analyst")}</span><p><span class="caret"></span> ${L("reading the engine output…", "liest die Engine-Ergebnisse…")}</p></div>` : "")
    : `<div class="intro"><p>${L(`I answer questions about ${esc(nice(u))} with figures from the Xetra engine, and I can open any card, comparison or report for you.`, `Ich beantworte Fragen zu ${esc(nice(u))} mit Zahlen aus der Xetra-Engine und öffne jede Karte, jeden Vergleich oder Report für Sie.`)}</p><p class="m">${L("I say what the data shows, not why. Causes come only from the verified event calendar. No investment advice.", "Ich sage, was die Daten zeigen, nicht warum. Ursachen nur aus dem geprüften Ereigniskalender. Keine Anlageberatung.")}</p></div>`;
  $("#dock-sugg").innerHTML = dockSugg().map(q => `<button data-q="${esc(q)}">${esc(q)}</button>`).join("");
  $("#dockq").placeholder = L("Ask about liquidity, a day, peers, results…", "Fragen zu Liquidität, einem Tag, Peers, Ergebnissen…");
  $("#dockf button").disabled = S.busy;
  log.scrollTop = log.scrollHeight;
}
function dockToggle(on) { S.dock = on === undefined ? !S.dock : on; dockRender(); if (S.dock) setTimeout(() => $("#dockq") && $("#dockq").focus(), 220); }
async function dockAsk(q) {
  if (S.busy) return; if (!S.dock) S.dock = true;
  const history = S.chat.map(m => ({role: m.role, content: m.content}));
  S.chat.push({role: "user", content: q}); S.busy = true; dockRender();
  try {
    const r = await post("/api/agent", {isin: S.isin, question: q, history, context: dockCtx(), lang: S.lang});
    S.chat.push({role: "assistant", content: r.text, source: r.source, model: r.model, steps: r.steps, actions: r.actions, check: r.check});
  } catch (e) { S.chat.push({role: "assistant", content: L("The analyst could not answer: ", "Der Analyst konnte nicht antworten: ") + e.message, source: "error"}); }
  S.busy = false; dockRender();
}

/* ============================== render + interactions ============================== */
const PAGE = {dashboard: pDashboard, card: pCard, compare: pCompare, report: pReport, ideas: pIdeas};
let io;
function render() {
  chrome();
  $("#app").innerHTML = band() + `<div class="content">${PAGE[S.page]()}</div>`;
  after($("#app")); setHash(); dockRender(); requestAnimationFrame(placeInd); document.fonts && document.fonts.ready.then(() => { placeInd(); segThumb(); });
  if (S.page === "card") loadCard();
  if (S.page === "compare") loadCompare();
  if (S.page === "report") loadReport();
}
function after(root) {
  io = io || new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { en.target.classList.add("in"); counts(en.target); io.unobserve(en.target); } }), {threshold: .1, rootMargin: "0px 0px -5% 0px"});
  $$(".rv:not(.in), .chart, .tile, .card, .flows, .mini, .pct-row, .ruler", root).forEach(el => io.observe(el));
  if (root.classList && (root.classList.contains("rv") || root.id === "cardslot")) $$(".chart, .card, .flows, .mini, .pct-row", root).forEach(el => io.observe(el));
  bindTime(); bindIntra(); segThumb();
}
function counts(root) {
  $$(".count", root).forEach(el => { if (el.dataset.done) return; el.dataset.done = 1; const to = +el.dataset.to; if (!isN(to) || reduced) return; const t0 = performance.now(), D = 1300;
    (function tick(t) { const k = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - k, 4); el.textContent = P(to * e); if (k < 1) requestAnimationFrame(tick); else el.textContent = P(to); })(t0); });
}
function go(p) { if (p === S.page) { window.scrollTo({top: 0, behavior: "smooth"}); return; } streamTok++; vt(() => { S.page = p; render(); window.scrollTo(0, 0); }); }
function openCard(day, event_id, isin = S.isin) {
  const run = () => { S.sel = {day, event_id: event_id || null}; vt(() => { S.page = "card"; render(); if (S.page === "card") window.scrollTo(0, 0); }); };
  if (isin !== S.isin) { openIsin(isin, {fromGate: false, then: () => { S.sel = {day, event_id: event_id || null}; S.page = "card"; }}); toast(L(`Switched to ${nice(U(isin))}`, `Gewechselt zu ${nice(U(isin))}`)); return; }
  if (S.page === "card") { S.sel = {day, event_id: event_id || null}; render(); return; }
  run();
}

/* tooltips */
const tip = $("#tip");
function showTip(html, x, y) { tip.innerHTML = html; tip.classList.add("on"); const w = tip.offsetWidth, h = tip.offsetHeight; tip.style.left = Math.min(innerWidth - w - 12, x + 14) + "px"; tip.style.top = Math.max(8, y - h - 12) + "px"; }
const hideTip = () => tip.classList.remove("on");
document.addEventListener("mousemove", ev => { const t = ev.target.closest && ev.target.closest("[data-tip]"); if (t) showTip(decodeURIComponent(t.dataset.tip), ev.clientX, ev.clientY); });
document.addEventListener("mouseout", ev => { if (ev.target.closest && ev.target.closest("[data-tip]")) hideTip(); });
const svgX = (svg, ev) => { const r = svg.getBoundingClientRect(); return (ev.clientX - r.left) / r.width * svg.viewBox.baseVal.width; };
function bindTime() {
  const svg = $("#tsvg"); if (!svg) return; const s = S.iss.series, n = s.date.length, W = 1160, ml = 60, mr = 14, cw = (W - ml - mr) / n, hit = $("#thit"), xh = $("#txh");
  const evd = new Map(S.iss.events.map(e => [String(e.reaction_day).slice(0, 10), e])), an = new Map(S.iss.anomalies.map(a => [a.peak_date, a]));
  const at = ev => Math.max(0, Math.min(n - 1, Math.floor((svgX(svg, ev) - ml) / cw)));
  const val = i => ({turnover: `${EUR(s.turnover_eur[i])} · ${S.iss.meta.index} ${EUR(s.index_turnover_eur[i])}`, xlm: `${BPS(s.xlm_25k[i])} · ${S.iss.meta.index} ${BPS(s.index_xlm_25k[i])}`, auction: `${P(s.auction_share[i], 0, false)} · ${S.iss.meta.index} ${P(s.index_auction_share[i], 0, false)}`,
    who: `MM ${P(s.mm_share[i], 0, false)} · Agent ${P(s.agent_share[i], 0, false)} · Prop ${P(s.prop_share[i], 0, false)}`, price: `${PX(s.price[i])} · ${P(s.ret[i])}`}[S.metric]);
  hit.addEventListener("mousemove", ev => { const i = at(ev), d = s.date[i], e = evd.get(d), a = an.get(d); xh.setAttribute("transform", `translate(${ml + (i + .5) * cw},0)`); xh.classList.add("on"); hit.style.cursor = e || a ? "pointer" : "crosshair";
    showTip(`<span class="t">${dL(d)}</span><br>${val(i)}<br>${L("abnormal", "abnormal")} ${P(s.abn_ret[i])} · ${X(s.vol_ratio[i])} ${L("normal turnover", "normaler Umsatz")}${e ? `<br><b>${esc(e.type)}</b> ${esc(String(e.title).slice(0, 70))}` : ""}${a && !e ? `<br><b>${esc(reasonL(a.reason))}</b>` : ""}${e || a ? `<br><span class="m">${L("Click for the impact card", "Klick für die Impact Card")}</span>` : ""}`, ev.clientX, ev.clientY); });
  hit.addEventListener("mouseleave", () => { xh.classList.remove("on"); hideTip(); });
  hit.addEventListener("click", ev => { const d = s.date[at(ev)], e = evd.get(d), a = an.get(d); if (e) openCard(d, e.event_id); else if (a) openCard(d, null); });
}
function bindIntra() {
  const svg = $("#isvg"); if (!svg || !S._intra) return; const I = S._intra, hit = $("#ihit"), xh = $("#ixh");
  hit.addEventListener("mousemove", ev => { const xv = svgX(svg, ev); let best = I.pts[0], bd = 1e9; for (const p of I.pts) { const dd = Math.abs(I.xm(p.m) - xv); if (dd < bd) { bd = dd; best = p; } }
    xh.querySelector("line").setAttribute("x1", I.xm(best.m)); xh.querySelector("line").setAttribute("x2", I.xm(best.m)); const c = xh.querySelector("circle"); c.setAttribute("cx", I.xm(best.m)); c.setAttribute("cy", I.y(best.c)); xh.classList.add("on");
    showTip(`<span class="t">${best.t}</span><br>${PX(I.pc * (1 + best.c))} · <b>${P(best.c)}</b><br>${L("turnover this minute", "Umsatz in dieser Minute")} ${EUR(best.eur)}`, ev.clientX, ev.clientY); });
  hit.addEventListener("mouseleave", () => { xh.classList.remove("on"); hideTip(); });
}

/* company switcher (replaces the old search button) */
const CO = {sel: 0, list: []};
function coSugg() { const q = $("#co-in").value; CO.list = search(q, 8); CO.sel = 0; $("#co-sugg").innerHTML = CO.list.map((u, i) => suggRow(u, i, CO.sel)).join(""); }
function coToggle(on) { const pop = $("#co-pop"), b = $("[data-act=co]"); if (!pop) return; pop.classList.toggle("on", on); b.setAttribute("aria-expanded", on); if (on) { $("#co-in").value = ""; coSugg(); setTimeout(() => $("#co-in").focus(), 50); } }

document.addEventListener("click", ev => {
  const t = ev.target.closest("[data-go],[data-card],[data-act],[data-q],[data-open],[data-isin],[data-pick],[data-do]");
  if (!ev.target.closest(".co")) coToggle(false);
  if (!ev.target.closest(".g-form")) $("#g-sugg").classList.remove("on");
  if (!t) return;
  if (t.tagName === "A") ev.preventDefault();
  if (t.dataset.pick) { $("#g-in").value = U(t.dataset.pick).isin; anatomy($("#g-in").value); openIsin(t.dataset.pick); return; }
  if (t.dataset.isin) { if (t.closest("#g-sugg")) { const u = U(t.dataset.isin); $("#g-in").value = u.isin; $("#g-sugg").classList.remove("on"); anatomy(u.isin); openIsin(u.isin); } else { coToggle(false); if (t.dataset.isin !== S.isin) openIsin(t.dataset.isin, {fromGate: false}); } return; }
  if (t.dataset.go) { go(t.dataset.go); return; }
  if (t.dataset.card) { openCard(t.dataset.card, t.dataset.ev || null); return; }
  if (t.dataset.open) { const [isin, day, ev2] = t.dataset.open.split("|"); openCard(day, ev2 || null, isin); return; }
  if (t.dataset.q) { dockAsk(t.dataset.q); return; }
  if (t.dataset.do) { doAction(JSON.parse(decodeURIComponent(t.dataset.do))); return; }
  const a = t.dataset.act;
  if (a === "lang") { S.lang = t.dataset.v; S.aiLang = null; if ($("#ws").classList.contains("hidden")) gateText(); else vt(() => render()); }
  else if (a === "co") { ev.stopPropagation(); coToggle(!$("#co-pop").classList.contains("on")); }
  else if (a === "gate") { coToggle(false); backToGate(); }
  else if (a === "metric") { S.metric = t.dataset.v; $$("[data-act=metric]").forEach(b => b.setAttribute("aria-pressed", b === t)); segThumb(); const c = $("#tchart"); c.classList.remove("in"); c.innerHTML = timeChart(); requestAnimationFrame(() => c.classList.add("in")); bindTime(); }
  else if (a === "ailang") { S.aiLang = t.dataset.v; $$("[data-act=ailang]").forEach(b => b.setAttribute("aria-pressed", b === t)); segThumb(); runAI(keyOf(S.sel), S.aiLang); }
  else if (a === "regen") { runAI(keyOf(S.sel), S.aiLang || S.lang, true); }
  else if (a === "copy") { const tx = $("#aitext").innerText; navigator.clipboard?.writeText(tx).then(() => toast(L("Copied", "Kopiert")), () => toast(L("Copy not allowed here", "Kopieren hier nicht erlaubt"))); }
  else if (a === "toreport") { S.rep.key = `${S.sel.day}|${S.sel.event_id || ""}`; S.rep.card = S.rep.ai = true; go("report"); }
  else if (a === "cmpthis") { S.cmp.type = t.dataset.type; S.cmp.index = ["DAX", "MDAX", "SDAX"].includes(t.dataset.index) ? t.dataset.index : "ALL"; S.cmp.data = null; go("compare"); }
  else if (a === "replang") { S.lang = t.dataset.v; vt(() => render()); }
  else if (a === "print") { window.print(); }
  else if (a === "dock") { dockToggle(); }
  else if (a === "dockclear") { S.chat = []; dockRender(); }
  else if (a === "addev") { S.addEv = !S.addEv; render(); }
});
document.addEventListener("change", ev => {
  if (ev.target.id === "evfile" && ev.target.files[0]) { importCalendar(ev.target.files[0]); ev.target.value = ""; return; }
  const c = ev.target.dataset.cmp, r = ev.target.dataset.rep;
  if (c) { S.cmp[c] = ev.target.value; S.cmp.data = null; $("#cmpbody").innerHTML = `<div class="skel" style="min-height:420px"></div>`; loadCompare(); }
  if (r) { if (r === "key") { S.rep.key = ev.target.value; $("#sheet").innerHTML = sheetHTML(); loadReport(); } else { S.rep[r] = ev.target.checked; $("#sheet").innerHTML = sheetHTML(); } }
});
document.addEventListener("submit", ev => {
  ev.preventDefault();
  if (ev.target.id === "dockf") { const q = $("#dockq").value.trim(); if (q && !S.busy) { $("#dockq").value = ""; dockAsk(q); } }
  if (ev.target.id === "evform") { addEvents([{date: $("#ev-d").value, time: $("#ev-t").value, type: $("#ev-y").value, title: $("#ev-n").value}]); }
  if (ev.target.id === "g-form") { const u = resolveGate(); if (u) { $("#g-in").value = u.isin; anatomy(u.isin); $("#g-sugg").classList.remove("on"); openIsin(u.isin); } else $("#g-err").textContent = L("No DAX, MDAX or SDAX share found for this input.", "Keine DAX-, MDAX- oder SDAX-Aktie für diese Eingabe gefunden."); }
});
document.addEventListener("input", ev => {
  if (ev.target.id === "g-in") { G.sel = 0; $("#g-err").textContent = ""; gateSugg(); }
  if (ev.target.id === "co-in") coSugg();
});
document.addEventListener("keydown", ev => {
  const nav = (st, list, el, fill) => { if (ev.key === "ArrowDown") { st.sel = Math.min(list.length - 1, st.sel + 1); } else if (ev.key === "ArrowUp") { st.sel = Math.max(0, st.sel - 1); } else return false; ev.preventDefault(); el.innerHTML = list.map((u, i) => suggRow(u, i, st.sel)).join(""); fill && fill(); return true; };
  if (ev.target.id === "g-in") { nav(G, G.list, $("#g-sugg"), () => anatomy($("#g-in").value)); if (ev.key === "Escape") $("#g-sugg").classList.remove("on"); return; }
  if (ev.target.id === "co-in") { if (!nav(CO, CO.list, $("#co-sugg")) && ev.key === "Enter") { ev.preventDefault(); const u = CO.list[CO.sel]; if (u) { coToggle(false); if (u.isin !== S.isin) openIsin(u.isin, {fromGate: false}); } } if (ev.key === "Escape") coToggle(false); return; }
  if (ev.target.closest && ev.target.closest("input,select,textarea")) return;
  if ($("#ws").classList.contains("hidden") || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  if (ev.key >= "1" && ev.key <= "5") go(PAGES[+ev.key - 1]);
  if (ev.key === "a" || ev.key === "A") { ev.preventDefault(); dockToggle(true); }
  if (ev.key === "Escape" && S.dock) dockToggle(false);
});
$("#g-in").addEventListener("focus", () => { if ($("#g-in").value.trim()) $("#g-sugg").classList.add("on"); });
addEventListener("scroll", () => document.body.classList.toggle("scrolled", scrollY > 30), {passive: true});
addEventListener("resize", () => { placeInd(); segThumb(); });
setInterval(() => { const c = $("#clock"); if (c) c.textContent = new Intl.DateTimeFormat("de-DE", {timeZone: "Europe/Berlin", hour: "2-digit", minute: "2-digit", second: "2-digit"}).format(new Date()) + (de() ? " MEZ" : " CET"); }, 1000);

addEventListener("hashchange", () => {
  const m = location.hash.match(/^#\/([A-Z]{2}[A-Z0-9]{10})\/(\w+)(?:\/(\d{4}-\d{2}-\d{2}))?(?:\/(.+))?/);
  if (!m || !U(m[1]) || !S.iss) return;
  if (m[2] === "ask") { dockToggle(true); return; }
  if (m[1] !== S.isin) { openIsin(m[1], {fromGate: false, then: () => { S.page = PAGES.includes(m[2]) ? m[2] : "dashboard"; }}); return; }
  if (m[3] && m[2] === "card") { const sel = {day: m[3], event_id: m[4] ? decodeURIComponent(m[4]) : null}; if (!S.sel || keyOf(sel) !== keyOf(S.sel) || S.page !== "card") openCard(sel.day, sel.event_id); return; }
  if (PAGES.includes(m[2]) && m[2] !== S.page) go(m[2]);
});

/* boot */
(async function boot() {
  gateBg(); gateText();
  try {
    const [uni, st] = await Promise.all([api("/api/universe"), api("/api/status")]);
    S.uni = uni; S.status = st; gateText(); gateTape();
  } catch (e) { $("#g-err").textContent = L("The data server is not running. Start it with: python web/server.py", "Der Datenserver läuft nicht. Start: python web/server.py"); return; }
  const m = location.hash.match(/^#\/([A-Z]{2}[A-Z0-9]{10})\/(\w+)(?:\/(\d{4}-\d{2}-\d{2}))?(?:\/(.+))?/);
  if (m && U(m[1])) { if (PAGES.includes(m[2])) S.page = m[2]; if (m[2] === "ask") S.dock = true; if (m[3]) S.sel = {day: m[3], event_id: m[4] ? decodeURIComponent(m[4]) : null}; const sel = S.sel; await openIsin(m[1], {fromGate: false, then: () => { S.sel = sel; }}); }
  else setTimeout(() => $("#g-in").focus(), 900);
})();
