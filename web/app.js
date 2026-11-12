/* Issuer Intelligence Hub, web front end (C3).  web/index.html + app.css + app.js, served at / by web/server.py.
   Numbers come from /api/* (the engine), words from the model (/api/narrate, /api/agent) or the template fallback.
   Periods (1M / 3M / YTD / 1Y) come from engine.market via /api/dashboard; a period the data does not cover is
   disabled with the reason, never replaced by another one. Light theme by default (index.html sets it before paint). */
"use strict";

/* ============================== helpers ============================== */
const $ = s => document.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const S = {lang: "en", uni: [], st: null, isin: null, iss: null, route: "overview", day: null, ev: null, metric: "price", tab: "summary",
  period: "ytd", dash: {}, dashNow: null,
  cards: {}, briefs: {}, ai: {}, tested: {}, cmp: {type: null, index: null, data: null, key: null}, chat: [], busy: false,
  rep: {perf: true, profile: true, peers: true, liq: true, anom: true, card: true, words: true, key: null}, cal: null, addOpen: false};
const de = () => S.lang === "de", L = (en, d) => de() ? d : en;
const NA = "–", isN = v => typeof v === "number" && !Number.isNaN(v) && v !== null;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const nf = (v, d = 1) => new Intl.NumberFormat(de() ? "de-DE" : "en-GB", {minimumFractionDigits: d, maximumFractionDigits: d}).format(Math.abs(v));
function pct(v, d = 1, sign = true) { if (!isN(v)) return NA; const r = Math.round(v * 100 * 10 ** d); return (r < 0 ? "−" : sign && r > 0 ? "+" : "") + nf(v * 100, d) + (de() ? " %" : "%"); }
const X = (v, d = 1) => isN(v) ? nf(v, d) + "×" : NA;
const BPS = (v, d = 1) => isN(v) ? nf(v, d) + (de() ? " Bp." : " bps") : NA;
function EUR(v, d = 1) {
  if (!isN(v)) return NA; const a = Math.abs(v); let n = v, u = "";
  if (a >= 1e9) { n = v / 1e9; u = de() ? " Mrd. €" : "bn"; } else if (a >= 1e6) { n = v / 1e6; u = de() ? " Mio. €" : "m"; } else if (a >= 1e3) { n = v / 1e3; u = de() ? " Tsd. €" : "k"; d = 0; } else { u = de() ? " €" : ""; d = 0; }
  return (n < 0 ? "−" : "") + (de() ? nf(n, d) + u : "€" + nf(n, d) + u);
}
const PX = v => isN(v) ? (de() ? nf(v, 2) + " €" : "€" + nf(v, 2)) : NA;
const MS = [["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."]];
const ML = [["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]];
const dS = s => { if (!s) return NA; const [, m, d] = String(s).slice(0, 10).split("-").map(Number); return de() ? `${d}. ${MS[1][m - 1]}` : `${d} ${MS[0][m - 1]}`; };
const dL = s => { if (!s) return NA; const [, m, d] = String(s).slice(0, 10).split("-").map(Number); return de() ? `${d}. ${ML[1][m - 1]}` : `${d} ${ML[0][m - 1]}`; };
const dY = s => { if (!s) return NA; return dL(s) + " " + String(s).slice(0, 4); };
const day10 = s => String(s || "").slice(0, 10);
const enc = encodeURIComponent;
const roll = (a, w) => a.map((_, i) => median(a.slice(Math.max(0, i - w + 1), i + 1)));   /* rolling median, missing days skipped */
const median = a => { const b = a.filter(isN).sort((x, y) => x - y); return b.length ? b[Math.floor(b.length / 2)] : null; };
const CHEV = `<svg class="chev" width="9" height="14" viewBox="0 0 9 14" aria-hidden="true"><path d="M1.5 1.5L7 7l-5.5 5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const BACK = `<svg width="10" height="16" viewBox="0 0 10 16" aria-hidden="true"><path d="M8 2L2 8l6 6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const SPARK = `<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l2.2 6.3L20.5 10l-6.3 2.2L12 18.5l-2.2-6.3L3.5 10l6.3-1.7z" fill="currentColor"/></svg>`;
function toast(t) { const el = $("#toast"); el.textContent = t; el.classList.add("on"); clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("on"), 2600); }
function progress(on) { const p = $("#progress"); clearTimeout(p._t); if (on) p._t = setTimeout(() => p.classList.add("on"), 150); else p.classList.remove("on"); }
async function api(path, opt) { const r = await fetch(path, opt); const j = await r.json().catch(() => ({error: r.statusText})); if (!r.ok) throw new Error(j.error || r.status); return j; }
const post = (p, b) => api(p, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(b)});

/* readable company names from exchange short names */
const NAMES = {EVD: "CTS Eventim", EVT: "Evotec", HDD: "Heidelberger Druck", GXI: "Gerresheimer", SAP: "SAP", ENR: "Siemens Energy", RHM: "Rheinmetall", DB1: "Deutsche Börse", DBK: "Deutsche Bank", MUV2: "Munich Re", ALV: "Allianz", SIE: "Siemens", IFX: "Infineon", DTE: "Deutsche Telekom", BAS: "BASF", BAYN: "Bayer", BMW: "BMW", MBG: "Mercedes-Benz Group", VOW3: "Volkswagen", ADS: "adidas", AIR: "Airbus", DHL: "DHL Group", EOAN: "E.ON", RWE: "RWE", MRK: "Merck", HEN3: "Henkel", BEI: "Beiersdorf", ZAL: "Zalando", VNA: "Vonovia", CBK: "Commerzbank", HNR1: "Hannover Rück", MTX: "MTU Aero Engines", SHL: "Siemens Healthineers", FRE: "Fresenius", FME: "Fresenius Medical Care", CON: "Continental", DTG: "Daimler Truck", QIA: "Qiagen", SY1: "Symrise", HEI: "Heidelberg Materials", BNR: "Brenntag", G1A: "GEA Group", G24: "Scout24", HOT: "Hochtief", PUM: "Puma"};
const DROP = new Set(["O.N.", "O.N", "ON", "INH", "INH.", "NA", "NA.", "VNA", "NAM.", "NAM", "EO", "SP.ADR", "VZO", "ST", "ST.", "+", "-", "CO.", "KGAA", "SE", "AG", "&"]);
function nice(u) {
  if (!u) return ""; if (NAMES[u.ticker]) return NAMES[u.ticker]; if (u.display) return u.display;   /* data.display_name from the server */
  const w = String(u.name || u.ticker).replace(/\.?(INH|O\.N|NAM|VNA)\.?(?=\s|$)/gi, "").replace(/\s+/g, " ").split(" ").filter(t => t && !DROP.has(t.toUpperCase()) && !/\d/.test(t));
  return w.map(t => t.length <= 3 ? t : t.charAt(0) + t.slice(1).toLowerCase()).join(" ").replace(/\.$/, "") || u.ticker;
}
const U = isin => S.uni.find(u => u.isin === isin);
/* "hIP_1.0-Mistral/Mistral-Medium-3.5-128B" -> "Mistral AI": the maker, not the gateway's model id */
function modelName(id) {
  const m = String(id || "");
  return /mistral/i.test(m) ? "Mistral AI" : /claude|anthropic/i.test(m) ? "Claude" : /gpt|openai/i.test(m) ? "OpenAI"
    : /llama/i.test(m) ? "Meta Llama" : /gemini/i.test(m) ? "Google Gemini" : /glm/i.test(m) ? "GLM" : (m.split("/").pop() || "AI");
}
const TYPE = t => ({NOTABLE_DAY: L("Unusual days", "Auffällige Tage"), FY: L("Full-year results", "Jahresergebnisse"), Q1: L("Q1 results", "Q1-Ergebnisse"), H1: L("Half-year results", "Halbjahresergebnisse"), Q3: L("Q3 results", "Q3-Ergebnisse"),
  DIVIDEND_EX: L("Ex-dividend days", "Ex-Dividenden-Tage"), AGM: L("AGMs", "Hauptversammlungen"), ADHOC: L("Ad hoc releases", "Ad-hoc-Meldungen"), GUIDANCE: L("Guidance changes", "Prognoseänderungen"), MA: L("M&A news", "M&A-Nachrichten"), INDEX: L("Index changes", "Indexänderungen"), CMD: L("Capital markets days", "Kapitalmarkttage"), OTHER: L("Other", "Sonstiges")}[t] || t);
const TAG = t => ({ADHOC: "Ad hoc", DIVIDEND_EX: L("Dividend", "Dividende"), GUIDANCE: L("Guidance", "Prognose"), INDEX: "Index", MA: "M&A", OTHER: L("Other", "Sonstiges")}[t] || t);
const TIMING = t => ({pre_open: L("before the open", "vor Handelsbeginn"), intraday: L("during trading", "während des Handels"), post_close: L("after the close", "nach Handelsschluss")}[t] || "");
const CTX = c => !c ? "" : String(c).split(/,\s*/).map(k => ({index_event: L("index change", "Indexänderung"), index_change: L("index membership change", "Indexwechsel"), quarterly_expiry: L("quarterly expiry", "großer Verfall"), monthly_expiry: L("monthly expiry", "Monatsverfall"), month_end_review: L("index review date", "Index-Review-Tag"), market_wide_volume: L("market-wide volume", "marktweiter Umsatz")}[k] || k)).join(", ");
const keyOf = (isin, day, ev) => `${isin}|${day}|${ev || ""}`;

/* ============================== own calendar (stored in this browser) ============================== */
const UEV = "iih.userEvents";   /* same key as the previous UI, so dates added there stay */
function userEvents(isin) { try { return (JSON.parse(localStorage.getItem(UEV) || "{}")[isin]) || []; } catch (e) { return (S._uev || {})[isin] || []; } }
function saveUserEvents(isin, list) { S._uev = S._uev || {}; S._uev[isin] = list; try { const a = JSON.parse(localStorage.getItem(UEV) || "{}"); a[isin] = list; localStorage.setItem(UEV, JSON.stringify(a)); return true; } catch (e) { return false; } }
function mergeUserEvents() { const own = userEvents(S.isin).map(e => ({...e, user: true})), ids = new Set(S.iss.events.map(e => e.event_id)); S.iss.events = S.iss.events.filter(e => !e.user).concat(own.filter(e => !ids.has(e.event_id))); }
function cardURL(isin, day, ev, path = "/api/card") {
  let u = `${path}?isin=${isin}&day=${day}${ev ? `&event_id=${enc(ev)}` : ""}`;
  const own = ev && String(ev).startsWith("USR_") && userEvents(isin).find(e => e.event_id === ev);
  if (own) u += `&date=${own.date}&time=${enc(own.time_local || "")}&type=${enc(own.type)}&title=${enc(own.title)}`;
  return u;
}

/* ============================== data model ============================== */
/* one timeline: calendar entries and unusual days, figures from the same "normal" as the impact card */
function timeline() {
  const s = S.iss.series, di = new Map(s.date.map((d, i) => [d, i])), out = new Map();
  S.iss.anomalies.forEach(a => out.set(a.peak_date, {day: a.peak_date, ev: a.event ? a.event.event_id : null, type: a.event ? a.event.type : null, title: a.event ? a.event.title : L("Unusual trading day", "Auffälliger Handelstag"),
    sub: a.event ? "" : (a.context ? CTX(a.context) : L("No calendar entry · cause open", "Kein Kalendereintrag · Ursache offen")), abn: a.peak_abn_ret, vol: a.peak_vol_ratio, unusual: true, sev: a.severity, verified: a.event && a.event.verified === "1"}));
  S.iss.events.forEach(e => { const d = day10(e.reaction_day); if (!di.has(d)) return; const i = di.get(d), prev = out.get(d);
    out.set(d, {day: d, ev: e.event_id, type: e.type, title: e.title, sub: e.user ? L("Your calendar", "Ihr Kalender") : "", abn: prev ? prev.abn : s.abn_ret[i], vol: prev ? prev.vol : s.vol_ratio[i], unusual: !!prev, sev: prev ? prev.sev : 0, verified: String(e.verified) === "1", user: e.user}); });
  return [...out.values()].sort((a, b) => b.day.localeCompare(a.day));
}
const leadDay = () => timeline().filter(r => r.unusual).sort((a, b) => b.sev - a.sev)[0];

async function loadIssuer(isin) {
  progress(true);
  try {
    const iss = await api(`/api/issuer?isin=${isin}`);
    if (S.isin !== isin) { S.chat = []; S.rep.key = null; S.cal = null; S.addOpen = false; S.cmp = {type: null, index: null, data: null, key: null}; }
    S.dashNow = await loadDash(isin, S.period);
    S.isin = isin; S.iss = iss; mergeUserEvents();
    try { localStorage.setItem("iih.isin", isin); } catch (e) { /* ignore */ }
  } finally { progress(false); }
}
/* period data (engine.market): price vs index peers, period medians with ranks, effective dates */
function loadDash(isin, period) {
  const k = `${isin}|${period}`;
  if (!S.dash[k]) S.dash[k] = api(`/api/dashboard?isin=${isin}&period=${period}`).catch(e => { delete S.dash[k]; throw e; });
  return S.dash[k];
}
const PERIODS = () => (S.st && S.st.periods) || [];
const periodOf = k => PERIODS().find(p => p.key === k) || {key: k, label: k.toUpperCase(), available: true};
async function setPeriod(k) {
  const p = periodOf(k); if (!p.available) return;
  progress(true);
  try { S.dashNow = await loadDash(S.isin, k); S.period = k; try { localStorage.setItem("iih.period", k); } catch (e) { /* ignore */ } render(true); }
  catch (e) { toast(e.message); } finally { progress(false); }
}
const PP = v => !isN(v) ? NA : (v < 0 ? "−" : v > 0 ? "+" : "") + nf(v * 100, 1) + (de() ? " Pp." : " pp");
function inPeriod(day) { const d = S.dashNow; return !d || (day >= d.from && day <= d.to); }

async function loadCard(isin, day, ev) {
  const k = keyOf(isin, day, ev);
  if (!S.cards[k]) S.cards[k] = api(cardURL(isin, day, ev)).catch(e => ({error: e.message})).then(d => { (S.done = S.done || {})[k] = d; return d; });
  if (!S.briefs[k]) S.briefs[k] = api(cardURL(isin, day, ev, "/api/evidence")).catch(e => ({error: e.message}));
  return Promise.all([S.cards[k], S.briefs[k]]);
}
async function loadAI(isin, day, ev, lang, fresh = false) {
  const k = keyOf(isin, day, ev) + "|" + lang;
  if (!S.ai[k] || fresh) S.ai[k] = post("/api/narrate", {isin, day, event_id: ev || null, lang, fresh}).catch(e => ({error: e.message}));
  return S.ai[k];
}

/* ============================== router with transitions ============================== */
const ROUTES = ["overview", "events", "event", "compare", "report", "ideas"];
const TABS = () => [["overview", L("Overview", "Überblick")], ["events", L("Events", "Ereignisse")], ["compare", L("Compare", "Vergleich")], ["report", L("Report", "Report")], ["ideas", L("Ideas", "Ideen")]];
function hashFor() { return `#/${S.isin}/${S.route}${S.route === "event" ? `/${S.day}${S.ev ? "/" + enc(S.ev) : ""}` : ""}`; }
function go(route, {day = null, ev = null, dir = "", morph = null} = {}) {
  const run = () => { S.route = route; if (route === "event") { S.day = day; S.ev = ev; S.tab = "summary"; } render(); scrollTo(0, 0); history.pushState(null, "", hashFor()); };
  if (!document.startViewTransition || reduced || document.hidden) { run(); const v = $(".view"); v && v.classList.add("enter"); return; }
  document.documentElement.dataset.dir = dir;
  if (morph) morph.style.viewTransitionName = "hero";
  const t = document.startViewTransition(run);
  setTimeout(() => t.skipTransition && t.skipTransition(), 1400);
  t.finished.catch(() => {}).finally(() => { document.documentElement.dataset.dir = ""; $$("[style*=view-transition-name]").forEach(el => { if (!el.classList.contains("keep-vt")) el.style.viewTransitionName = ""; }); });
}
async function openEvent(isin, day, ev, morph = null) {
  if (isin !== S.isin) { await loadIssuer(isin); toast(L(`Switched to ${nice(U(isin))}`, `Gewechselt zu ${nice(U(isin))}`)); }
  loadCard(isin, day, ev); go("event", {day, ev, dir: "push", morph});
}
async function switchCompany(isin, route = "overview") {
  if (!U(isin)) return;
  try { await loadIssuer(isin); go(route); } catch (e) { toast(L("Could not load: ", "Laden fehlgeschlagen: ") + e.message); }
}
function render(stat = false) {
  document.documentElement.lang = S.lang;
  const u = U(S.isin);
  $("#tabs").innerHTML = TABS().map(([k, t]) => `<button data-go="${k}" ${S.route === k || (k === "events" && S.route === "event") ? 'aria-current="page"' : ""}>${t}</button>`).join("");
  $("#co").innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="M16.5 16.5L21 21" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg><span>${L("Shares", "Aktien")}</span>`;
  $("#co").setAttribute("aria-label", L("Search shares", "Aktien suchen"));
  $$(".lang button").forEach(b => b.setAttribute("aria-pressed", b.dataset.lang === S.lang));
  $(".ask-btn span").textContent = L("Ask", "Fragen");
  $("#foot").innerHTML = (S.st.offline ? L("<b>Offline copy</b> of the showcase companies: saved answers, no free questions and no calendar import. ", "<b>Offline-Kopie</b> der Beispielunternehmen: gespeicherte Antworten, keine freien Fragen und kein Kalenderimport. ") : "") + L(`Xetra data to the close on ${dY(S.st.last_date)} · ${S.uni.length} DAX, MDAX and SDAX shares · minute data for ${S.st.intraday_stocks} · ${S.st.llm ? "AI connected" : "AI in template mode"}. Numbers come from the engine; words from the model, with every figure checked. Causes come only from the verified calendar. Concept prototype, not an official Deutsche Börse product. Not investment advice.`,
    `Xetra-Daten bis Handelsschluss ${dY(S.st.last_date)} · ${S.uni.length} DAX-, MDAX- und SDAX-Aktien · Minutendaten für ${S.st.intraday_stocks} · ${S.st.llm ? "KI verbunden" : "KI im Vorlagenmodus"}. Zahlen aus der Engine; Texte vom Modell, jede Zahl geprüft. Ursachen nur aus dem geprüften Kalender. Konzept-Prototyp, kein offizielles Produkt der Deutschen Börse. Keine Anlageberatung.`);
  $("#main").innerHTML = `<div class="view ${stat ? "static" : ""}">${({overview: vOverview, events: vEvents, event: vEvent, compare: vCompare, report: vReport, ideas: vIdeas})[S.route]()}</div>`;
  after();
  if (S.route === "event") fillEvent();
  if (S.route === "compare") fillCompare();
  if (S.route === "report") fillReport();
  if ($("#sheet").classList.contains("on")) drawChat();
}
let io;
function after() {
  io = io || new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); countUp(e.target); io.unobserve(e.target); } }), {threshold: .12});
  $$(".rv, .chart, [data-count]", $("#main")).forEach(el => io.observe(el));
  $$(".seg").forEach(placeThumb);
  bindChart();
}
function countUp(root) {
  [root, ...$$("[data-count]", root)].filter(el => el.dataset && el.dataset.count && !el.dataset.done).forEach(el => {
    el.dataset.done = 1; const to = +el.dataset.count; if (reduced) { el.textContent = pct(to); return; }
    const t0 = performance.now(), D = 1100; (function tick(t) { const k = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - k, 3); el.textContent = pct(to * e); if (k < 1) requestAnimationFrame(tick); })(t0);
  });
}
const seg = (name, opts, cur) => `<div class="seg" data-seg="${name}"><span class="thumb"></span>${opts.map(([v, t]) => `<button data-segv="${v}" aria-pressed="${v === cur}">${t}</button>`).join("")}</div>`;
function placeThumb(g) { const b = g.querySelector("[aria-pressed=true]"), th = g.querySelector(".thumb"); if (b && th) { th.style.left = b.offsetLeft + "px"; th.style.width = b.offsetWidth + "px"; } }

/* ============================== charts ============================== */
let CH = null;
/* the issuer series cut to the selected period, starting at the close the period return starts from */
function win() {
  const d = S.dashNow, dates = S.iss.series.date;
  if (!d) return {i0: 0, i1: dates.length - 1};
  const i0 = dates.indexOf(d.versus_market.price.start_close), i1 = dates.indexOf(d.to);
  return {i0: i0 < 0 ? 0 : i0, i1: i1 < 0 ? dates.length - 1 : i1};
}
function seriesFor(metric) {
  const s = S.iss.series, {i0, i1} = win(), sl = a => a.slice(i0, i1 + 1), dates = sl(s.date);
  if (metric === "turnover") return {dates, vals: sl(s.turnover_eur), ref: sl(s.index_turnover_eur), fmt: v => EUR(v), ax: v => EUR(v, 0), color: "var(--accent)"};
  if (metric === "xlm") return {dates, vals: sl(s.xlm_25k), ref: sl(s.index_xlm_25k), fmt: v => BPS(v), ax: v => BPS(v, 0), color: "var(--accent)"};
  if (metric === "auction") return {dates, vals: sl(roll(s.auction_share, 10)), ref: sl(roll(s.index_auction_share, 10)), fmt: v => pct(v, 1, false), ax: v => pct(v, 0, false), color: "var(--accent)"};
  /* index line: the start price compounded with the equal-weighted move of the other index members (peer_ret),
     the same "index" as the period return and the impact card's abnormal return */
  const vals = sl(s.price), pr = sl(s.peer_ret || []), p0 = vals.find(isN); let c = p0;
  const ref = vals.map((_, i) => i === 0 ? p0 : (c *= 1 + (isN(pr[i]) ? pr[i] : 0)));
  return {dates, vals, ref, fmt: PX, ax: v => (de() ? "" : "€") + nf(v, 0) + (de() ? " €" : ""), color: "var(--text)"};
}
function lineChart(metric) {
  const {dates, vals, ref, fmt, ax, color} = seriesFor(metric), W = 1040, H = 300, ml = 8, mr = 70, mt = 16, mb = 26, n = vals.length;
  if (vals.filter(isN).length < 2) return `<p class="muted" style="padding:40px 0">${L("Not enough data in this period.", "Zu wenige Daten in diesem Zeitraum.")}</p>`;
  const all = vals.concat(ref).filter(isN), lo0 = Math.min(...all), hi0 = Math.max(...all), pad = (hi0 - lo0) * .08 || Math.abs(hi0) * .05 || 1, lo = metric === "price" ? lo0 - pad : Math.max(0, lo0 - pad), hi = hi0 + pad;
  const x = i => ml + i / Math.max(1, n - 1) * (W - ml - mr), y = v => mt + (hi - v) / (hi - lo) * (H - mt - mb);
  const path = a => { let d = "", pen = false; a.forEach((v, i) => { if (!isN(v)) { pen = false; return; } d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`; pen = true; }); return d; };
  const d = path(vals), first = vals.findIndex(isN), last = vals.length - 1 - [...vals].reverse().findIndex(isN);
  let g = ""; for (let k = 0; k <= 3; k++) { const v = lo + (hi - lo) * k / 3; g += `<line class="gl" x1="${ml}" x2="${W - mr}" y1="${y(v)}" y2="${y(v)}"/><text class="ax" x="${W - mr + 8}" y="${y(v) + 4}">${ax(v)}</text>`; }
  const step = n > 90 ? "m" : "w";
  let pm = ""; dates.forEach((dd, i) => { const m = step === "m" ? dd.slice(5, 7) : dd; if (step === "m" ? (m !== pm && i) : (i && i % 5 === 0)) g += `<text class="ax" x="${x(i)}" y="${H - 6}" text-anchor="middle">${step === "m" ? MS[de() ? 1 : 0][+m - 1] : dS(dd)}</text>`; pm = m; });
  const di = new Map(dates.map((dd, i) => [dd, i]));
  const mk = timeline().filter(r => inPeriod(r.day)).map(r => { const i = di.get(r.day); if (i === undefined || !isN(vals[i])) return ""; return `<g class="mk" data-open="${r.day}|${esc(r.ev || "")}" data-tip="${esc(`${dS(r.day)} · ${r.type ? TAG(r.type) : L("Unusual day", "Auffälliger Tag")} · ${L("stock-specific", "titelspezifisch")} ${pct(r.abn)}`)}"><circle cx="${x(i)}" cy="${y(vals[i])}" r="5" fill="${(r.abn || 0) < 0 ? "var(--down)" : "var(--up)"}" stroke="var(--surface)" stroke-width="2.5"/></g>`; }).join("");
  CH = {vals, ref, dates, fmt, x, y, n, W, ml, mr, metric};
  return `<svg viewBox="0 0 ${W} ${H}" id="c" role="img" aria-label="${esc(chartTitle())}"><defs><linearGradient id="cg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".14"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    ${g}<path d="${path(ref)}" fill="none" stroke="var(--text3)" stroke-width="1.3" stroke-dasharray="3 3" opacity=".8"/>
    <path class="area" d="${d}L${x(last)},${H - mb}L${x(first)},${H - mb}Z" fill="url(#cg)"/><path class="ln" d="${d}" stroke="${color}" pathLength="1"/>
    <g class="xh"><line y1="${mt}" y2="${H - mb}" stroke="var(--text3)" stroke-dasharray="2 3"/><circle r="5" fill="${color}" stroke="var(--surface)" stroke-width="2.5"/></g>
    <rect class="hit" x="${ml}" y="${mt}" width="${W - ml - mr}" height="${H - mt - mb - 10}" fill="transparent"/>${mk}</svg>`;
}
function chartTitle() { return {auction: L("Auction share of turnover (opening, intraday and closing), 10-day median", "Auktionsanteil am Umsatz (Eröffnung, untertägig, Schluss), 10-Tage-Median"), price: L("Share price, closing auction", "Aktienkurs, Schlussauktion"), turnover: L("Turnover per day", "Umsatz pro Tag"), xlm: L("Trading cost of a €25k round trip (XLM)", "Handelskosten für 25 T€ hin und zurück (XLM)")}[S.metric]; }
function chartLabel() {
  const idx = S.iss.meta.index;
  return `${chartTitle()} · <span style="color:var(--text3)">${S.metric === "price" ? L(`dashed: ${idx} peers, equal-weighted, from the same start`, `gestrichelt: ${idx}-Werte, gleichgewichtet, gleicher Start`) : L(`dashed: ${idx} median`, `gestrichelt: ${idx}-Median`)} · ${L("dots: events", "Punkte: Ereignisse")}</span>`;
}
function bindChart() {
  const svg = $("#main svg#c"); if (!svg || !CH) return; const hit = svg.querySelector(".hit"), xh = svg.querySelector(".xh"), read = $("#read"), {vals, ref, dates, fmt, x, y, n, W, ml, mr, metric} = CH;
  hit.addEventListener("pointermove", ev => { const r = svg.getBoundingClientRect(), px = (ev.clientX - r.left) / r.width * W, i = Math.max(0, Math.min(n - 1, Math.round((px - ml) / (W - ml - mr) * (n - 1))));
    if (!isN(vals[i])) return; xh.querySelector("line").setAttribute("x1", x(i)); xh.querySelector("line").setAttribute("x2", x(i)); xh.querySelector("circle").setAttribute("cx", x(i)); xh.querySelector("circle").setAttribute("cy", y(vals[i])); xh.classList.add("on");
    const idx = S.iss.meta.index;
    read.innerHTML = `<b>${fmt(vals[i])}</b> · ${dY(dates[i])} · ` + (metric === "price"
      ? `${L("since start", "seit Start")} ${pct(vals[i] / vals[0] - 1)} (${idx} ${pct(ref[i] / ref[0] - 1)})`
      : `${idx} ${L("median", "Median")} ${fmt(ref[i])}`); });
  /* auction share: the 10-day median is drawn; the readout says so */
  hit.addEventListener("pointerleave", () => { xh.classList.remove("on"); read.innerHTML = chartLabel(); });
}
const minOf = t => { const [h, m] = t.split(":").map(Number); return (h - 9) * 60 + m; };
function intraChart(d) {
  const c = d.card, b = d.bars, pc = d.prev_close, W = 1040, H = 340, ml = 8, mr = 86, mt = 34, VH = 54, mb = 30;
  const xm = m => ml + (m + 4) / 526 * (W - ml - mr);
  const pts = b.t.map((t, i) => ({m: minOf(t), t, c: b.close[i] / pc - 1, lo: b.low[i] / pc - 1, eur: b.eur[i], au: b.auction[i]})).filter(p => isN(p.c));
  const cont = pts.filter(p => p.m >= 0 && p.m < 510 && !(p.au && p.m <= 5));
  const vals = pts.map(p => p.c).concat(pts.map(p => p.lo), [0, c.price.ret]), lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo) * .1 + .004, y0 = lo - pad, y1 = hi + pad;
  const PH = H - mt - mb - VH - 12, y = v => mt + (y1 - v) / (y1 - y0) * PH, vy = H - mb;
  const span = (y1 - y0) * 100, step = span > 24 ? .05 : span > 10 ? .02 : span > 4 ? .01 : .005;
  let g = ""; for (let v = Math.ceil(y0 / step) * step; v <= y1; v += step) g += `<line class="gl" x1="${ml}" x2="${W - mr}" y1="${y(v)}" y2="${y(v)}" ${Math.abs(v) < 1e-9 ? 'stroke-dasharray="3 3"' : ""}/><text class="ax" x="${W - mr + 8}" y="${y(v) + 4}">${pct(v, step < .01 ? 1 : 0)}</text>`;
  [[0, "09:00"], [120, "11:00"], [240, "13:00"], [360, "15:00"], [510, "17:30"]].forEach(([m, t]) => g += `<text class="ax" x="${xm(m)}" y="${H - 8}" text-anchor="${m ? "middle" : "start"}">${t}</text>`);
  const bk = new Map(); cont.forEach(p => { const k = Math.floor(p.m / 5) * 5; bk.set(k, (bk.get(k) || 0) + p.eur); });
  const bmax = Math.max(...bk.values(), 1), bw = xm(5) - xm(0) - 1.4;
  const vol = [...bk.entries()].map(([m, e]) => { const h = e / bmax * VH; return `<rect x="${xm(m)}" y="${vy - h}" width="${bw}" height="${h}" rx="1.5" fill="${m < 15 ? "var(--accent)" : "var(--fill2)"}"/>`; }).join("");
  const au = pts.filter(p => p.au).map(p => { const h = Math.min(VH, p.eur / bmax * VH); return `<rect x="${xm(p.m) - bw}" y="${vy - h}" width="${bw * 2}" height="${h}" rx="1.5" fill="var(--text)" data-tip="${esc(L("Auction", "Auktion") + " " + p.t + " · " + EUR(p.eur))}"/>`; }).join("");
  const path = cont.map((p, i) => `${i ? "L" : "M"}${xm(p.m).toFixed(1)},${y(p.c).toFixed(1)}`).join(""), col = c.price.ret < 0 ? "var(--down)" : "var(--up)";
  const intr = c.intraday || {}, on = intr.onset || {};
  const ann = (m, v, t, side = 1, colr = col) => `<g><line x1="${xm(m)}" x2="${xm(m)}" y1="${mt - 10}" y2="${vy}" stroke="var(--text3)" stroke-dasharray="2 3"/>${isN(v) ? `<circle cx="${xm(m)}" cy="${y(v)}" r="5" fill="var(--surface)" stroke="${colr}" stroke-width="2.5"/>` : ""}<text x="${xm(m) + 8 * side}" y="${mt - 14}" font-size="12" font-weight="600" fill="var(--text)" text-anchor="${side > 0 ? "start" : "end"}">${t}</text></g>`;
  let a = "";
  if (on.time && minOf(on.time) >= 0 && minOf(on.time) <= 515) { const p = cont.find(q => q.m >= minOf(on.time)); a += ann(minOf(on.time), p ? p.c : null, L("Reaction detected ", "Reaktion erkannt ") + on.time, 1, "var(--accent)"); }
  const evT = (d.event_row || {}).time_local, sameDay = d.event_row && day10(d.event_row.date) === day10(c.event.reaction_day);
  if (evT && sameDay && minOf(evT) > 0 && minOf(evT) < 510) a += ann(minOf(evT), null, L("Announcement ", "Meldung ") + evT, -1);
  if (intr.time_of_low && isN(intr.intraday_low)) { const m = minOf(intr.time_of_low); if (m >= 0 && m <= 515) a += ann(m, intr.intraday_low / pc - 1, L("Low ", "Tief ") + intr.time_of_low, m > 300 ? -1 : 1); }
  (on.volatility_interruptions || []).forEach(t => { const m = minOf(t); if (m >= 0 && m <= 515) a += `<path d="M${xm(m)},${y0 > -1 ? y(y0) : vy} l4,-8 h-8z" fill="var(--down)" data-tip="${esc(L("Volatility interruption ", "Volatilitätsunterbrechung ") + t)}"/>`; });
  a += `<circle cx="${xm(515)}" cy="${y(c.price.ret)}" r="6" fill="${col}"/><text x="${xm(515) + 10}" y="${y(c.price.ret) + 5}" font-size="15" font-weight="700" fill="${col}">${pct(c.price.ret)}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}"><defs><linearGradient id="ig" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${col}" stop-opacity="0"/><stop offset="1" stop-color="${col}" stop-opacity=".12"/></linearGradient></defs>
    <rect x="${xm(0)}" y="${mt}" width="${xm(15) - xm(0)}" height="${vy - mt}" fill="var(--fill)"/>${g}${vol}${au}
    <path class="area" d="${path}L${xm(cont.length ? cont[cont.length - 1].m : 509)},${y(0)}L${xm(cont.length ? cont[0].m : 0)},${y(0)}Z" fill="url(#ig)"/><path class="ln" d="${path}" stroke="${col}" pathLength="1"/>${a}</svg>`;
}
function scatter(rows, me) {
  const W = 1040, H = 380, ml = 48, mr = 24, mt = 20, mb = 32;
  const vs = rows.map(r => r.vol_ratio).filter(v => isN(v) && v > 0);
  let lx0 = Math.log(Math.max(.4, Math.min(...vs) * .9)), lx1 = Math.log(Math.max(...vs) * 1.1);
  if (!(lx1 - lx0 > .2)) { lx0 -= .7; lx1 += .7; }   /* one or two events: give the axis room instead of dividing by zero */
  const as = rows.map(r => r.abn_ret), y0 = Math.min(-.02, ...as) * 1.12, y1 = Math.max(.02, ...as) * 1.12;
  const x = v => ml + Math.max(0, Math.min(1, (Math.log(Math.max(v, 1e-3)) - lx0) / (lx1 - lx0))) * (W - ml - mr), y = v => mt + (y1 - v) / (y1 - y0) * (H - mt - mb);
  let g = ""; const st = (y1 - y0) > .3 ? .1 : (y1 - y0) > .12 ? .05 : .02;
  for (let v = Math.ceil(y0 / st) * st; v <= y1; v += st) g += `<line class="gl" x1="${ml}" x2="${W - mr}" y1="${y(v)}" y2="${y(v)}" ${Math.abs(v) < 1e-9 ? 'stroke-dasharray="3 3"' : ""}/><text class="ax" x="${ml - 6}" y="${y(v) + 4}" text-anchor="end">${pct(v, 0)}</text>`;
  [.5, 1, 2, 5, 10, 20, 50].filter(v => Math.log(v) > lx0 && Math.log(v) < lx1).forEach(v => g += `<line class="gl" x1="${x(v)}" x2="${x(v)}" y1="${mt}" y2="${H - mb}" opacity=".5"/><text class="ax" x="${x(v)}" y="${H - 8}" text-anchor="middle">${X(v, v < 1 ? 1 : 0)}</text>`);
  const tip = r => esc(`${nice(U(r.isin) || r)} · ${dS(r.reaction_day)}${r.type !== "NOTABLE_DAY" && r.title ? " · " + String(r.title).slice(0, 60) : ""} · ${L("stock-specific", "titelspezifisch")} ${pct(r.abn_ret)} · ${X(r.vol_ratio)} ${L("turnover", "Umsatz")}`);
  const at = r => `data-xopen="${r.isin}|${day10(r.reaction_day)}|${esc(rowEv(r))}" data-tip="${tip(r)}" style="cursor:pointer"`;
  const others = rows.filter(r => r.isin !== S.isin && isN(r.vol_ratio)), mine = rows.filter(r => r.isin === S.isin && isN(r.vol_ratio));
  let h = others.map(r => `<circle cx="${x(r.vol_ratio).toFixed(1)}" cy="${y(r.abn_ret).toFixed(1)}" r="${rows.length > 400 ? 3 : 4}" fill="var(--text3)" opacity=".38" ${at(r)}/>`).join("");
  /* the selected company: accent, larger, outlined; the open day also gets a ring and a label (non-colour cues) */
  mine.sort((a, b) => me(a) - me(b)).forEach(r => { const cx = x(r.vol_ratio), cy = y(r.abn_ret);
    if (me(r)) { const right = cx > W * .72; h += `<circle cx="${cx}" cy="${cy}" r="17" fill="none" stroke="var(--accent)" stroke-width="1.5" opacity=".55"/><circle cx="${cx}" cy="${cy}" r="8" fill="var(--accent)" stroke="var(--surface)" stroke-width="2.5" ${at(r)}/><text x="${right ? cx - 24 : cx + 24}" y="${cy + 5}" font-size="13" font-weight="600" fill="var(--accent)" text-anchor="${right ? "end" : "start"}" paint-order="stroke" stroke="var(--surface)" stroke-width="4">${esc(r.ticker)} · ${dS(r.reaction_day)}</text>`; }
    else h += `<circle cx="${cx}" cy="${cy}" r="6" fill="var(--surface)" stroke="var(--accent)" stroke-width="2.5" ${at(r)}/>`; });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(L("Events by turnover vs normal and stock-specific move", "Ereignisse nach Umsatz vs. normal und titelspezifischer Bewegung"))}">${g}${h}</svg>`;
}
const rowEv = r => r.event_id && !String(r.event_id).includes("NOTABLE_DAY") ? r.event_id : "";

/* ============================== views ============================== */
function periodSeg() {
  return `<div class="seg" data-seg="period" role="group" aria-label="${L("Period", "Zeitraum")}"><span class="thumb"></span>${PERIODS().filter(p => p.available).map(p => `<button data-segv="${p.key}" aria-pressed="${p.key === S.period}">${p.label}</button>`).join("")}</div>`;
}
function periodNote() {
  const d = S.dashNow, p = periodOf(S.period), pr = d.versus_market.price;
  const bits = [L(`${p.label}: ${dS(pr.start_close)} close to ${dY(d.to)} close, ${d.days} trading days`, `${p.label}: Schluss ${dS(pr.start_close)} bis Schluss ${dY(d.to)}, ${d.days} Handelstage`)];
  if (p.note) bits.push(L("the 31 Dec 2025 close is not in the data, so the 2 Jan move is not included", "der Schlusskurs vom 31.12.2025 fehlt in den Daten, die Bewegung vom 2. Jan. ist nicht enthalten"));
  bits.push(L("closing-auction prices, not adjusted for dividends", "Schlussauktionskurse, nicht um Dividenden bereinigt") + (pr.ex_dividend_days && pr.ex_dividend_days.length ? L(` (ex-dividend ${pr.ex_dividend_days.map(dS).join(", ")})`, ` (Ex-Dividende ${pr.ex_dividend_days.map(dS).join(", ")})`) : ""));
  return bits.join(" · ");
}
function vOverview() {
  const u = U(S.isin), d = S.dashNow, vm = d.versus_market, pr = vm.price, to = vm.turnover_eur, xl = vm.xlm_25k, k = S.iss.kpis, lt = S.iss.liquidity, idx = vm.index, lc = k.liquidity_check, p = periodOf(S.period);
  const vw = {improved: L("improved", "verbessert"), worsened: L("worsened", "verschlechtert"), mixed: L("mixed", "gemischt"), stable: L("stable", "stabil")}[lt.verdict] || L("open", "offen");
  const rel = isN(pr.stock) && isN(pr.index) ? pr.stock - pr.index : null;
  const lead = timeline().filter(r => r.unusual && inPeriod(r.day)).sort((a, b) => b.sev - a.sev)[0];
  const unusual = timeline().filter(r => r.unusual && inPeriod(r.day));
  return `<section class="wrap hero">
    <div class="eyebrow rv">${idx}<span class="dot">·</span>${u.isin}${d.sector ? `<span class="dot">·</span>${esc(d.sector)}` : ""}</div>
    <h1 class="h-hero rv" style="--d:.05s">${esc(nice(u))}</h1>
    <p class="lede rv" style="--d:.1s">${L(`<b>${pct(pr.stock)}</b> over ${p.label}, against <b>${pct(pr.index)}</b> for the ${idx} peers: <b>${PP(rel)}</b>, rank ${pr.rank} of ${pr.of} by return. Median turnover <b>${EUR(to.stock)} a day</b> (${idx} median ${EUR(to.index)}), trading cost <b>${BPS(xl.stock)}</b> for a €25k round trip (${idx} ${BPS(xl.index)}).`,
      `<b>${pct(pr.stock)}</b> im Zeitraum ${p.label}, gegenüber <b>${pct(pr.index)}</b> für die ${idx}-Werte: <b>${PP(rel)}</b>, Rang ${pr.rank} von ${pr.of} nach Rendite. Medianumsatz <b>${EUR(to.stock)} pro Tag</b> (${idx}-Median ${EUR(to.index)}), Handelskosten <b>${BPS(xl.stock)}</b> für 25 T€ hin und zurück (${idx} ${BPS(xl.index)}).`)}</p>
    <div class="price rv" style="--d:.15s"><span class="p num">${PX(pr.close_end)}</span><span class="pill ${(pr.stock || 0) < 0 ? "dn" : "up"}" title="${esc(L("Price return over the period", "Kursrendite im Zeitraum"))}">${pct(pr.stock)} · ${p.label}</span><span class="muted" style="font-size:14px">${L("Closing auction", "Schlussauktion")} · ${dY(d.to)}</span>
      <span style="margin-left:auto;display:flex;gap:10px;align-items:center;flex-wrap:wrap">${periodSeg()}${S.st.offline ? `<button class="btn ghost sm" data-go="report">${L("IR report (print to PDF)", "IR-Report (als PDF drucken)")}</button>` : `<a class="btn ghost sm" href="/api/export?isin=${u.isin}&lang=${S.lang}" download>${L("Export IR report", "IR-Report exportieren")}</a>`}</span></div>
    <p class="note rv" style="--d:.15s;margin-top:8px">${periodNote()}</p>
    <div class="card chart-card rv" style="--d:.2s"><div class="chart-top"><div class="chart-read" id="read">${chartLabel()}</div>${seg("metric", [["price", L("Price", "Kurs")], ["turnover", L("Turnover", "Umsatz")], ["xlm", L("Trading cost", "Handelskosten")], ["auction", L("Auctions", "Auktionen")]], S.metric)}</div>
      <div class="chart" id="chart">${lineChart(S.metric)}</div>
      <p class="note">${L("Trading cost = Xetra Liquidity Measure (XLM): the round-trip cost of a €25k order including price impact, in basis points. It is not the quoted bid-ask spread.", "Handelskosten = Xetra Liquidity Measure (XLM): Kosten für Kauf und Verkauf von 25 T€ inklusive Preiseinfluss, in Basispunkten. Nicht der quotierte Geld-Brief-Spread.")}</p></div>
  </section>
  <section class="wrap sec"><div class="grid g4">
    ${tile(L(`Turnover per day · ${p.label} median`, `Umsatz pro Tag · Median ${p.label}`), EUR(to.stock), L(`${idx} median ${EUR(to.index)} · rank ${to.rank} of ${to.of}`, `${idx}-Median ${EUR(to.index)} · Rang ${to.rank} von ${to.of}`), [[L("You", "Sie"), to.stock, 1], [idx, to.index]], 0)}
    ${tile(L(`Trading cost €25k · ${p.label} median`, `Handelskosten 25 T€ · Median ${p.label}`), BPS(xl.stock), L(`${idx} median ${BPS(xl.index)} · rank ${xl.rank} of ${xl.of} (1 = cheapest)`, `${idx}-Median ${BPS(xl.index)} · Rang ${xl.rank} von ${xl.of} (1 = günstigste)`), [[L("You", "Sie"), xl.stock, 1], [idx, xl.index]], .06)}
    ${tile(L("Liquidity trend · last 60 vs previous 60 days", "Liquiditätstrend · letzte 60 vs. vorherige 60 Tage"), vw.charAt(0).toUpperCase() + vw.slice(1), L(`Trading cost ${pct(lt.xlm_25k_change_pct, 0)}, turnover ${pct(lt.turnover_change_pct, 0)}`, `Handelskosten ${pct(lt.xlm_25k_change_pct, 0)}, Umsatz ${pct(lt.turnover_change_pct, 0)}`), null, .12)}
    ${tile(L("Xetra liquidity category (estimate)", "Xetra-Liquiditätskategorie (Schätzung)"), lc.category_estimate || L("n/a", "k. A."), lc.category_estimate ? `${lc.category_estimate === "A" ? L("No Designated Sponsor needed", "Kein Designated Sponsor nötig") : L("Designated Sponsor needed", "Designated Sponsor nötig")} · ${L("4-month daily average", "4-Monats-Tagesdurchschnitt")}: ${BPS(lc.avg_xlm_25k_bps_4m ?? lc.median_xlm_25k_bps_4m, 0)}, ${EUR(lc.avg_turnover_eur_4m)}` : L("No XLM in the last four months (only DAX, MDAX and SDAX members have it), so no estimate.", "Kein XLM in den letzten vier Monaten (nur DAX-, MDAX- und SDAX-Werte haben es), daher keine Schätzung."), null, .18)}
  </div></section>
  <section class="wrap sec"><div class="grid g2">${whoTrades(p)}${costCurve()}</div></section>
  ${lead ? `<section class="wrap sec"><div class="card feature rv">
    <div><div class="cap">${L(`Most unusual day · ${p.label}`, `Auffälligster Tag · ${p.label}`)}</div><h2 class="h-sec" style="margin-top:10px">${dY(lead.day)}</h2>
      <p>${lead.type ? esc(lead.title) : esc(lead.sub)}. ${L(`Stock-specific move (return minus the ${idx} peers), on ${X(lead.vol)} normal turnover.`, `Titelspezifische Bewegung (Rendite minus ${idx}-Werte), bei ${X(lead.vol)} normalem Umsatz.`)}</p>
      <button class="btn" data-open="${lead.day}|${esc(lead.ev || "")}" data-morph="#leadnum">${L("Open impact card", "Impact Card öffnen")} ${CHEV}</button></div>
    <div style="text-align:right"><span class="big ${lead.abn < 0 ? "dn" : "up"} num" id="leadnum" data-count="${lead.abn}">${pct(lead.abn)}</span></div></div></section>` : ""}
  <section class="wrap sec"><div class="sec-head"><h2 class="h-sec rv">${L("Peers", "Peers")}</h2></div><div class="card rv">${peersTable()}</div>
    <p class="note">${L("Medians of the last 60 trading days (fixed window, independent of the period above). Similar size = the 10 shares closest in median turnover: a proxy, because market capitalisation is not in the Xetra data.", "Mediane der letzten 60 Handelstage (festes Fenster, unabhängig vom Zeitraum oben). Ähnliche Größe = die 10 Aktien mit dem nächsten Medianumsatz: ein Ersatzmaß, da die Marktkapitalisierung nicht in den Xetra-Daten ist.")}</p></section>
  <section class="wrap sec"><div class="sec-head"><h2 class="h-sec rv">${L(`Unusual days · ${p.label}`, `Auffällige Tage · ${p.label}`)}</h2><button class="link rv" data-go="events">${L("All events", "Alle Ereignisse")} ${CHEV}</button></div>${unusual.length ? rows(unusual.slice(0, 6)) : `<div class="card lead-empty">${L(`No unusual days in ${p.label} (${dS(d.from)} – ${dS(d.to)}).`, `Keine auffälligen Tage im Zeitraum ${p.label} (${dS(d.from)} – ${dS(d.to)}).`)}</div>`}</section>`;
}
/* who trades: participant shares of one-sided turnover over the period (Xetra flow dynamics), medians of the days */
function whoTrades(p) {
  const s = S.iss.series, {i0, i1} = win(), sl = a => a.slice(i0 + (S.dashNow && S.dashNow.versus_market.price.start_close !== S.dashNow.from ? 1 : 0), i1 + 1);
  const R = [[L("Client orders (agent)", "Kundenorders (Agent)"), median(sl(s.agent_share)), "var(--text)"], [L("Proprietary trading", "Eigenhandel"), median(sl(s.prop_share)), "var(--accent)"], [L("Market makers", "Market Maker"), median(sl(s.mm_share)), "var(--text3)"]];
  const any = R.some(r => isN(r[1]));
  return `<div class="card rv"><span class="cap">${L(`Who trades · ${p.label} median`, `Wer handelt · Median ${p.label}`)}</span>
    ${any ? R.map(([t, v, c]) => `<div class="flow plain"><span>${t}</span><div class="trk"><i style="left:0;width:${(v || 0) * 100}%;background:${c}"></i></div><b class="num">${pct(v, 0, false)}</b></div>`).join("") : `<p class="muted">${L("No participant flows in this period.", "Keine Teilnehmerflüsse in diesem Zeitraum.")}</p>`}
    <p class="note">${L("Share of one-sided turnover by participant type (Xetra flow dynamics). Exchange data shows types, not investor names; days Xetra withholds (fewer than 7 trades) are left out.", "Anteil am einseitigen Umsatz nach Teilnehmertyp (Xetra Flow Dynamics). Börsendaten zeigen Typen, keine Investorennamen; von Xetra zurückgehaltene Tage (unter 7 Trades) fehlen.")}</p></div>`;
}
/* trading cost by order size (engine/xlm.py): the share vs its index peers, last 60 trading days */
function costCurve() {
  const c = S.iss.cost_curve; if (!c || !c.rows || !c.rows.length) return `<div class="card rv"><span class="cap">${L("Trading cost by order size", "Handelskosten nach Ordergröße")}</span><p class="muted">${L("No XLM for this share (only DAX, MDAX and SDAX members have it).", "Kein XLM für diese Aktie (nur DAX-, MDAX- und SDAX-Werte haben es).")}</p></div>`;
  const rows = c.rows.filter(r => (isN(r.stock_bps) && r.stock_fill >= .5) || isN(r.peer_bps)), sm = c.summary || {};
  const W = 520, H = 220, ml = 40, mr = 14, mt = 12, mb = 28, xs = rows.map(r => Math.log10(r.notional_eur)), x0 = Math.min(...xs), x1 = Math.max(...xs);
  const vals = rows.flatMap(r => [r.stock_fill >= .5 ? r.stock_bps : null, r.peer_bps]).filter(v => isN(v) && v > 0), l0 = Math.log10(Math.min(...vals) * .8), l1 = Math.log10(Math.max(...vals) * 1.25);
  const x = v => ml + (Math.log10(v) - x0) / (x1 - x0 || 1) * (W - ml - mr), y = v => mt + (1 - (Math.log10(v) - l0) / (l1 - l0 || 1)) * (H - mt - mb);
  let g = ""; [5, 10, 20, 50, 100, 200, 500, 1000].filter(v => Math.log10(v) >= l0 && Math.log10(v) <= l1).forEach(v => { g += `<line class="gl" x1="${ml}" x2="${W - mr}" y1="${y(v)}" y2="${y(v)}"/><text class="ax" x="${ml - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`; });
  rows.forEach((r, i) => { if (i % 2 === 0 || i === rows.length - 1) g += `<text class="ax" x="${x(r.notional_eur)}" y="${H - 8}" text-anchor="middle">${esc(r.label)}</text>`; });
  const ln = (k, col, dash) => { const pts = rows.filter(r => isN(r[k + "_bps"]) && (k === "peer" || r.stock_fill >= .5)); return `<path d="${pts.map((r, i) => `${i ? "L" : "M"}${x(r.notional_eur).toFixed(1)},${y(r[k + "_bps"]).toFixed(1)}`).join("")}" fill="none" stroke="${col}" stroke-width="${dash ? 1.5 : 2.2}" ${dash ? 'stroke-dasharray="3 3"' : ""}/>` + pts.map(r => `<circle cx="${x(r.notional_eur)}" cy="${y(r[k + "_bps"])}" r="${dash ? 2.5 : 3.5}" fill="${col}" data-tip="${esc(`${r.label} ${L("order", "Order")} · ${k === "stock" ? S.iss.meta.ticker : L("peers", "Peers")} ${BPS(r[k + "_bps"], 0)}`)}"/>`).join(""); };
  return `<div class="card rv"><span class="cap">${L("Trading cost by order size · last 60 days", "Handelskosten nach Ordergröße · letzte 60 Tage")}</span>
    <div class="chart in" style="margin-top:8px"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(L("Trading cost by order size", "Handelskosten nach Ordergröße"))}">${g}${ln("peer", "var(--text3)", true)}${ln("stock", "var(--accent)")}</svg></div>
    <p class="note">${L(`bps, log scale. Solid: ${esc(nice(U(S.isin)))}; dashed: ${S.iss.meta.index} peers. A €100k order costs ${BPS(sm.cost_100k_bps, 0)} (peers ${BPS(sm.peer_cost_100k_bps, 0)}); the book absorbs up to ${esc(sm.largest_absorbed_label || NA)} on most days. Sizes the book could not absorb on most days are left out.`, `Bp., log. Skala. Durchgezogen: ${esc(nice(U(S.isin)))}; gestrichelt: ${S.iss.meta.index}-Peers. Eine 100-T€-Order kostet ${BPS(sm.cost_100k_bps, 0)} (Peers ${BPS(sm.peer_cost_100k_bps, 0)}); das Buch nimmt meist bis ${esc(sm.largest_absorbed_label || NA)} auf. Größen, die das Buch meist nicht aufnehmen konnte, fehlen.`)}</p></div>`;
}
function tile(cap, v, s, bars, d) {
  const mx = bars ? Math.max(...bars.map(b => b[1])) : 1;
  return `<div class="card tile rv" style="--d:${d}s"><span class="cap">${cap}</span><div class="v num">${v}</div><div class="s">${s}</div>${bars ? `<div class="cmpbar">${bars.map(([l, w, me]) => `<div><span>${l}</span><i class="${me ? "me" : ""}" style="--w:${(w / mx).toFixed(3)}"></i></div>`).join("")}</div>` : ""}</div>`;
}
function peersTable() {
  const p = S.iss.peers, g = p.groups.filter(x => x.values && x.n > 0), lab = x => x.key === "index" ? S.iss.meta.index : x.key === "size" ? L("Similar size", "Ähnliche Größe") : esc(x.name);
  const R = [["turnover_eur", L("Turnover per day", "Umsatz pro Tag"), v => EUR(v)], ["xlm_25k", L("Cost to trade €25k", "Kosten 25 T€"), v => BPS(v)], ["auction_share", L("Auction share", "Auktionsanteil"), v => pct(v, 0, false)], ["agent_share", L("Client orders", "Kundenorders"), v => pct(v, 0, false)], ["volatility", L("Volatility", "Volatilität"), v => pct(v, 0, false)]];
  return `<div style="overflow-x:auto"><table class="tbl"><thead><tr><th></th><th>${S.iss.meta.ticker}</th>${g.map(x => `<th>${lab(x)} <span style="font-weight:400">(${x.n})</span></th>`).join("")}</tr></thead>
    <tbody>${R.map(([k, t, f]) => `<tr><td>${t}</td><td class="me">${f(p.stock[k])}</td>${g.map(x => `<td class="muted">${f(x.values[k])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function rows(list) {
  if (!list.length) return `<div class="card lead-empty">${L("No unusual days in this period.", "Keine auffälligen Tage in diesem Zeitraum.")}</div>`;
  return `<div class="list rv">${list.map(r => `<button class="row" data-open="${r.day}|${esc(r.ev || "")}" data-morph=".a">
    <span class="d">${dS(r.day)}</span><span class="t">${r.type ? `<span class="tag">${esc(TAG(r.type))}</span>` : ""}${esc(r.title)}${r.sub ? `<small>${esc(r.sub)}</small>` : ""}</span>
    <span class="a ${(r.abn || 0) < 0 ? "dn" : "up"} num">${pct(r.abn)}</span><span class="xr num">${X(r.vol)}</span>${CHEV}</button>`).join("")}</div>`;
}
function vEvents() {
  const off = S.st.offline;
  return `<section class="wrap hero"><div class="eyebrow rv">${esc(nice(U(S.isin)))}</div><h1 class="h-hero rv" style="--d:.05s">${L("Events", "Ereignisse")}</h1>
    <p class="lede rv" style="--d:.1s">${L("Every announcement and every unusual trading day, measured against the share's own normal and its peers. Choose one to see its impact card.", "Jede Meldung und jeder auffällige Handelstag, gemessen am eigenen Normalzustand und an den Peers. Wählen Sie einen Tag für seine Impact Card.")}</p>
    ${off ? "" : `<div class="rv" style="--d:.15s;margin-top:22px;display:flex;gap:10px;flex-wrap:wrap"><button class="btn ghost sm" data-act="add">${L("Add a date", "Datum hinzufügen")}</button><label class="btn ghost sm" style="cursor:pointer">${L("Import calendar (CSV, ICS)", "Kalender importieren (CSV, ICS)")}<input type="file" id="calfile" accept=".csv,.ics,.txt" hidden></label></div>`}
    ${S.addOpen ? addForm() : ""}${calPreview()}</section>
  <section class="wrap" style="margin-top:40px">${rows(timeline())}<p class="note">${L("Stock-specific move · turnover vs normal (median of trading days t−65 to t−6)", "Titelspezifische Bewegung · Umsatz vs. normal (Median der Handelstage t−65 bis t−6)")}</p></section>`;
}
const EVTYPES = ["FY", "Q1", "H1", "Q3", "ADHOC", "GUIDANCE", "DIVIDEND_EX", "AGM", "CMD", "MA", "OTHER"];
function addForm() {
  const m = S.iss.meta;
  return `<div class="card" style="margin-top:20px"><b>${L("Add a date", "Datum hinzufügen")}</b><p class="note" style="margin-top:4px">${L("The time decides the reaction day: after the 17:35 closing auction it is the next trading day.", "Die Uhrzeit bestimmt den Reaktionstag: nach der Schlussauktion um 17:35 ist es der nächste Handelstag.")}</p>
    <form class="form" id="addf"><input type="date" id="f-d" min="${m.first_date}" max="${m.last_date}" required aria-label="${L("Date", "Datum")}"><input type="time" id="f-t" aria-label="${L("Time", "Uhrzeit")}">
    <select class="sel" id="f-y" aria-label="${L("Type", "Typ")}">${EVTYPES.map(t => `<option value="${t}">${TYPE(t)}</option>`).join("")}</select><input type="text" id="f-n" maxlength="160" placeholder="${L("Title, e.g. Q3 trading statement", "Titel, z. B. Q3-Mitteilung")}"><button class="btn sm">${L("Build impact card", "Impact Card erstellen")}</button></form></div>`;
}
function calPreview() {
  const c = S.cal; if (!c) return "";
  if (c.error) return `<div class="card prev" style="margin-top:20px"><b>${esc(c.file)}</b><p class="dn">${esc(c.error)}</p><button class="btn ghost sm" data-act="calx">${L("Close", "Schließen")}</button></div>`;
  const ok = c.rows.filter(r => r.status === "matched"), ST = st => ({matched: L("matched", "zugeordnet"), before_data: L("before the data", "vor Datenbeginn"), after_data: L("after the data", "nach Datenende"), invalid: L("skipped", "übersprungen")}[st] || st);
  return `<div class="card prev" style="margin-top:20px"><b>${L("Preview", "Vorschau")} · ${esc(c.file)}</b><p class="note" style="margin-top:4px">${L(`${ok.length} of ${c.rows.length} entries match a trading day. Nothing is saved until you confirm.`, `${ok.length} von ${c.rows.length} Einträgen passen zu einem Handelstag. Gespeichert wird erst nach Bestätigung.`)}</p>
    <ol>${c.rows.map(r => `<li><span class="st ${r.status === "matched" ? "matched" : "other"}">${ST(r.status)}</span><span><b>${/^\d{4}-\d{2}-\d{2}$/.test(r.date || "") ? dY(r.date) : esc(r.date || "?")}${r.time_local || r.time ? " " + esc(r.time_local || r.time) : ""}</b> ${esc(String(r.title || "").slice(0, 70))}${r.status === "matched" ? `<br><small class="muted">→ ${L("reaction", "Reaktion")} ${dS(r.reaction_day)} · ${esc(r.rule || "")}${r.note ? " · " + esc(r.note) : ""}</small>` : r.note ? `<br><small class="muted">${esc(r.note)}</small>` : ""}</span></li>`).join("")}</ol>
    <div style="display:flex;gap:10px">${ok.length ? `<button class="btn sm" data-act="calok">${L(`Add ${ok.length} events`, `${ok.length} Ereignisse hinzufügen`)}</button>` : ""}<button class="btn ghost sm" data-act="calx">${L("Cancel", "Abbrechen")}</button></div></div>`;
}

/* ---------- impact card ---------- */
function vEvent() {
  const r = timeline().find(x => x.day === S.day && (x.ev || "") === (S.ev || "")) || timeline().find(x => x.day === S.day) || {day: S.day, abn: null, vol: null, title: L("Trading day", "Handelstag")};
  return `<section class="wrap ic-hero"><button class="back" data-go="events" data-dir="pop">${BACK} ${L("Events", "Ereignisse")}</button>
    <div class="eyebrow" style="margin-top:22px" id="ic-eye">${dY(S.day)}</div>
    <h1 class="h-sec" style="margin-top:8px;max-width:24em" id="ic-title">${esc(r.type ? r.title : L("Unusual trading day", "Auffälliger Handelstag"))}</h1>
    <div class="src" id="ic-src"></div>
    <div class="ic-num"><span class="big ${(r.abn || 0) < 0 ? "dn" : "up"} num" style="view-transition-name:hero" id="ic-big">${pct(r.abn)}</span><div class="ctx" id="ic-ctx">${L("Stock-specific move", "Titelspezifische Bewegung")}<br>${X(r.vol)} ${L("normal turnover", "normaler Umsatz")}</div></div>
    <div class="card summary rv" id="ic-sum"><div class="ai">${SPARK}</div><div><div class="wait" style="padding:4px 0"><span class="spin"></span>${L("Building the impact card from Xetra data…", "Impact Card wird aus Xetra-Daten berechnet…")}</div></div></div>
    <div class="ic-tabs">${seg("tab", [["summary", L("At a glance", "Überblick")], ["day", L("The day", "Der Tag")], ["who", L("Who traded", "Wer handelte")], ["evidence", L("Evidence", "Belege")]], S.tab)}</div>
    <div class="panel" id="panel"><div class="skel" style="height:220px"></div></div>
    <div class="ic-acts no-print" id="ic-acts"></div></section>`;
}
async function fillEvent() {
  const isin = S.isin, day = S.day, ev = S.ev, k = keyOf(isin, day, ev);
  const [d, b] = await loadCard(isin, day, ev);
  if (S.route !== "event" || keyOf(S.isin, S.day, S.ev) !== k) return;
  if (d.error) { $("#ic-sum").innerHTML = `<div class="ai">!</div><div><p>${L("The card could not be built: ", "Die Karte konnte nicht berechnet werden: ")}${esc(d.error)}</p></div>`; $("#panel").innerHTML = ""; return; }
  const c = d.card, e = c.event, notable = e.type === "NOTABLE_DAY", row = d.event_row || {}, [dt, tm] = (e.datetime_local || "").split(" ");
  $("#ic-eye").innerHTML = notable ? L(`Detected from trading on ${dY(e.reaction_day)}`, `Aus dem Handel erkannt am ${dY(e.reaction_day)}`)
    : `${L("Published", "Veröffentlicht")} ${dS(dt)}${tm ? " · " + tm : ""}${e.timing ? " · " + TIMING(e.timing) : ""}<span class="dot">·</span>${L("Reaction", "Reaktion")} ${dS(e.reaction_day)}`;
  $("#ic-title").textContent = notable ? L("Unusual trading day", "Auffälliger Handelstag") : e.title;
  $("#ic-src").innerHTML = notable ? `<span>${L("No calendar entry. The cause is not in the data and has not been verified.", "Kein Kalendereintrag. Die Ursache steht nicht in den Daten und ist nicht geprüft.")}</span>`
    : String(e.event_id || "").startsWith("USR_") ? `<span>${L("From your own calendar, not checked against a source", "Aus Ihrem eigenen Kalender, nicht mit einer Quelle geprüft")}</span>`
    : `<span>${String(row.verified) === "1" ? "✓ " + L("Date and time verified against the source", "Datum und Uhrzeit mit der Quelle geprüft") : L("Source not yet verified", "Quelle noch nicht geprüft")}</span>${e.source_url ? `<a href="${esc(e.source_url)}" target="_blank" rel="noopener">${L("Source", "Quelle")} ↗</a>` : ""}`;
  const big = $("#ic-big"); big.textContent = pct(c.price.abn_ret); big.className = `big ${c.price.abn_ret < 0 ? "dn" : "up"} num`;
  $("#ic-ctx").innerHTML = `${L("Stock-specific move", "Titelspezifische Bewegung")}<br>${esc(nice(U(isin)))} <b>${pct(c.price.ret)}</b> · ${c.index} ${L("peers", "Peers")} <b>${pct(c.price.peer_ret)}</b>${isN(c.price.car_0_5) ? `<br>${L("Day 0 to +5", "Tag 0 bis +5")} <b>${pct(c.price.car_0_5)}</b>` : ""}`;
  $("#ic-acts").innerHTML = `${S.st.offline ? `<button class="btn" data-act="toreport">${L("IR report (print to PDF)", "IR-Report (als PDF drucken)")}</button>` : `<a class="btn" href="${cardURL(isin, day, ev, "/api/export")}&lang=${S.lang}" download>${L("Export IR report (PDF)", "IR-Report exportieren (PDF)")}</a>`}<button class="btn ghost" data-act="toreport">${L("Add to report", "In den Report")}</button>${c.comparison ? `<button class="btn ghost" data-act="cmpthis" data-type="${esc(c.comparison.group_type)}" data-index="${esc(c.comparison.group_index)}">${L("Compare with similar days", "Mit ähnlichen Tagen vergleichen")}</button>` : ""}`;
  $("#panel").innerHTML = panel(d, b);
  fillSummary();
}
async function fillSummary(fresh = false) {
  const isin = S.isin, day = S.day, ev = S.ev, k = keyOf(isin, day, ev), lang = S.lang;
  const box = () => S.route === "event" && keyOf(S.isin, S.day, S.ev) === k && $("#ic-sum");
  if (box()) $("#ic-sum").innerHTML = `<div class="ai">${SPARK}</div><div><div class="wait" style="padding:4px 0"><span class="spin"></span>${fresh ? L("Asking the model again…", "Das Modell wird neu gefragt…") : L("Writing the summary from the card…", "Die Zusammenfassung wird aus der Karte geschrieben…")}</div></div>`;
  const [r, [d]] = await Promise.all([loadAI(isin, day, ev, lang, fresh), loadCard(isin, day, ev)]);
  if (!box()) return;
  if (r.error) { $("#ic-sum").innerHTML = `<div class="ai">!</div><div><p>${L("The summary could not be generated: ", "Zusammenfassung fehlgeschlagen: ")}${esc(r.error)}</p></div>`; return; }
  const chk = numbersCheck(r.text, d.card), live = r.source === "llm";
  const who = live ? (r.cached ? L(`Saved answer from ${modelName(r.model)}`, `Gespeicherte Antwort von ${modelName(r.model)}`) : L(`Written by ${modelName(r.model)}`, `Geschrieben von ${modelName(r.model)}`)) : r.rejected && r.rejected.length ? L("Template text: the model's draft had figures not in the card", "Vorlagentext: Entwurf des Modells hatte Zahlen, die nicht in der Karte stehen") : L("Template text, no language model connected", "Vorlagentext, kein Sprachmodell verbunden");
  $("#ic-sum").innerHTML = `<div class="ai">${SPARK}</div><div><p>${esc(r.text)}</p><div class="meta">${chk ? (chk.bad ? `<span class="dn">${L(`${chk.bad} of ${chk.total} figures not found in the card`, `${chk.bad} von ${chk.total} Zahlen nicht in der Karte`)}</span>` : `<span class="ok">✓ ${L(`All ${chk.total} figures match the card`, `Alle ${chk.total} Zahlen stimmen mit der Karte überein`)}</span>`) : ""}<span>${esc(who)}</span>
    ${S.st.llm && !S.st.offline ? `<button class="link" data-act="regen">${L("Ask the model again", "Modell neu fragen")}</button>` : ""}<button class="link" data-act="ask-card">${L("Ask about this day", "Zu diesem Tag fragen")} ${CHEV}</button></div></div>`;
}
function panel(d, b) {
  const c = d.card, v = c.volume, l = c.liquidity, a = c.auctions || {}, pa = c.participants, cm = c.comparison;
  if (S.tab === "summary") {
    const T = [[L("Turnover", "Umsatz"), X(v.ratio), `${EUR(v.turnover_eur)} ${L("vs", "vs.")} ${EUR(v.baseline_eur)} ${L("normal", "normal")}`],
      [L("Trading cost", "Handelskosten"), X(l.ratio), `${BPS(l.xlm_25k_bps)} ${L("vs", "vs.")} ${BPS(l.xlm_25k_baseline_bps)}${isN(l.days_to_normal) ? ` · ${L("normal after", "normal nach")} ${l.days_to_normal} ${l.days_to_normal === 1 ? L("day", "Tag") : L("days", "Tagen")}` : ""}`],
      [L("Opening auction", "Eröffnungsauktion"), X(a.open_auction_ratio), `${EUR(a.open_auction_eur)} · ${L("price", "Kurs")} ${pct(a.open_auction_move)}`],
      [L("Closing auction", "Schlussauktion"), X(a.close_auction_ratio), `${EUR(a.close_auction_eur)} · ${pct(a.close_auction_move)} ${L("vs last trade", "vs. letztem Handel")}`]];
    const rk = cm ? (Number.isInteger(cm.rank_of) ? cm.rank_of : cm.n + 1) : null, w = cm ? cm.abs_abn_ret_pctile : 0;
    return `<div class="grid g4">${T.map(([kk, vv, ss], i) => `<div class="card tile rv in" style="--d:${i * .05}s"><span class="cap">${kk}</span><div class="v num">${vv}</div><div class="s">${ss}</div></div>`).join("")}</div>
      ${cm ? `<div class="card" style="margin-top:16px"><div class="rank"><div class="of num">#${cm.rank_abs_abn_ret}<small> ${L("of", "von")} ${rk}</small></div>
      <div class="meter in"><div class="cap" style="margin-bottom:10px">${L(`Bigger than ${Math.round(w * 100)}% of ${cm.group_type === "NOTABLE_DAY" ? "unusual days" : TYPE(cm.group_type)} (${cm.group_index})`, `Größer als ${Math.round(w * 100)} % der ${cm.group_type === "NOTABLE_DAY" ? "auffälligen Tage" : TYPE(cm.group_type)} (${cm.group_index})`)}</div><div class="trk"><i style="--w:${w}"></i></div><div class="lb"><span>${L("smallest", "kleinste")}</span><span>${L("largest", "größte")}</span></div></div></div>
      ${cm.group_type !== c.event.type && c.event.type !== "NOTABLE_DAY" ? `<p class="note">${L(`Fewer than 5 ${TYPE(c.event.type)} with data, so this ranks among unusual trading days: a broader group, not like-for-like.`, `Weniger als 5 ${TYPE(c.event.type)} mit Daten, daher Einordnung unter auffälligen Handelstagen: eine breitere Gruppe.`)}</p>` : ""}</div>` : ""}`;
  }
  if (S.tab === "day") {
    const af = d.aftershocks || [], mx = Math.max(...af.map(x => x.vol_ratio || 0), 1.5), fn = af.find(x => x.t > 0 && (x.vol_ratio || 0) <= 1.2);
    return `<div class="card"><div class="chart-top"><div class="chart-read"><b>${L("Minute by minute", "Minute für Minute")}</b> · ${L("price vs previous close; bars: turnover per 5 min, auctions dark; shaded: first 15 minutes", "Kurs vs. Vortag; Balken: Umsatz je 5 Min., Auktionen dunkel; schattiert: erste 15 Minuten")}</div></div>
      <div class="chart in">${d.bars ? intraChart(d) : `<p class="muted">${L("No minute data for this share. The daily figures are complete.", "Für diese Aktie gibt es keine Minutendaten. Die Tageswerte sind vollständig.")}</p>`}</div>
      <p class="note">${L("The reaction time is inferred from trades (price beyond 2σ and turnover 3× normal for the time of day); it is not the publication time.", "Der Reaktionszeitpunkt ist aus den Trades abgeleitet (Kurs jenseits 2σ, Umsatz 3× normal für die Tageszeit), nicht die Veröffentlichungszeit.")}</p></div>
      ${af.length ? `<div class="card" style="margin-top:16px"><b>${L("Aftershocks", "Nachwirkung")}</b><p class="muted" style="margin:4px 0 0;font-size:15px">${fn ? L(`Turnover was back within 1.2× normal after ${fn.t} ${fn.t === 1 ? "day" : "days"}.`, `Umsatz nach ${fn.t} ${fn.t === 1 ? "Tag" : "Tagen"} wieder unter 1,2× normal.`) : L("Turnover stayed above 1.2× normal for the whole window.", "Umsatz blieb im ganzen Fenster über 1,2× normal.")}</p>
        <div class="aft">${af.map(x => `<i class="${x.t === 0 ? "z" : (x.vol_ratio || 0) > 1.2 ? "h" : ""}" style="height:${Math.max(2, Math.sqrt((x.vol_ratio || 0) / mx) * 100)}%" data-tip="${esc(`${x.t === 0 ? L("Reaction day", "Reaktionstag") : (x.t > 0 ? "+" : "") + x.t} · ${dS(x.date)} · ${X(x.vol_ratio)}`)}"></i>`).join("")}</div>
        <div class="meter"><div class="lb"><span>${L("day", "Tag")} ${af[0].t}</span><span style="color:var(--accent)">${L("blue: reaction day", "blau: Reaktionstag")}</span><span>${L("day", "Tag")} +${af[af.length - 1].t}</span></div></div></div>` : ""}`;
  }
  if (S.tab === "who") {
    const fl = (t, val, base, f, diverge) => { const w = diverge ? Math.min(50, Math.abs(val || 0) * 50) : (val || 0) * 100;
      return `<div class="flow"><span>${t}</span><div class="trk"><i style="${diverge ? (val < 0 ? `right:50%;width:${w}%;background:var(--down)` : `left:50%;width:${w}%;background:var(--up)`) : `left:0;width:${w}%;background:var(--text)`}"></i>${isN(base) ? `<em style="position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--accent);left:${diverge ? 50 + base * 50 : base * 100}%"></em>` : ""}</div><b class="num">${f(val)}</b></div>`; };
    const imb = pa.agent_aggr_imbalance;
    return `<div class="card">${fl(L("Client orders, net", "Kundenorders, netto"), imb, pa.agent_aggr_imbalance_baseline, x => pct(x, 0), true)}${fl(L("Client share", "Anteil Kunden"), pa.agent_share, pa.agent_share_baseline, x => pct(x, 0, false))}${fl(L("Proprietary", "Eigenhandel"), pa.prop_share, null, x => pct(x, 0, false))}${fl(L("Market makers", "Market Maker"), pa.mm_share, null, x => pct(x, 0, false))}
      <p class="lede" style="font-size:17px;margin-top:18px">${L(`Client orders were net ${imb < 0 ? "sellers" : "buyers"}: ${EUR(Math.abs(pa.agent_aggr_net_eur))} more ${imb < 0 ? "sold" : "bought"} aggressively.`, `Kundenorders waren per Saldo ${imb < 0 ? "Verkäufer" : "Käufer"}: ${EUR(Math.abs(pa.agent_aggr_net_eur))} mehr aggressiv ${imb < 0 ? "verkauft" : "gekauft"}.`)}</p>
      <p class="note">${L("Blue tick: normal. Xetra shows participant types (clients, market makers, proprietary), not investor names.", "Blauer Strich: normal. Xetra zeigt Teilnehmertypen (Kunden, Market Maker, Eigenhandel), keine Investorennamen.")}</p></div>`;
  }
  if (!b || b.error) return `<div class="card"><p class="muted">${L("The evidence brief could not be built.", "Die Belege konnten nicht erstellt werden.")} ${esc(b && b.error || "")}</p></div>`;
  const br = b[S.lang] || b.en, tested = S.tested[keyOf(S.isin, S.day, S.ev)];
  const V = v => VERDICT()[v] || ["na", "?", v];
  return `<div class="card"><p class="lede" style="margin:0 0 20px;color:var(--text);font-size:19px">${esc(br.headline)}</p>
    <div class="bf">${br.sections.filter(s => s.key !== "changed").map(s => `<div><h4>${esc(s.title)}</h4><ul>${s.points.slice(0, 2).map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`).join("")}</div>
    <form class="test" id="test"><input id="testq" placeholder="${L("Test an explanation, e.g. “the whole market sold off”", "Erklärung prüfen, z. B. „der Gesamtmarkt fiel“")}" aria-label="${L("Explanation", "Erklärung")}"><button class="btn sm">${L("Check", "Prüfen")}</button></form>
    <div class="claims">${Object.entries(br.claims).map(([id, cl]) => { const [cls, ic, vt] = V(cl.verdict); return `<div class="claim ${tested && !tested.includes(id) ? "dim" : ""}" id="cl-${id}"><span class="verd ${cls}"><i>${ic}</i>${vt}</span><div><b>${esc(cl.label)}</b><p>${esc(cl.text)}</p>${cl.better && tested && tested.includes(id) ? `<div class="better"><span>${L("Say instead", "Besser so")}</span>${esc(cl.better)}</div>` : ""}</div></div>`; }).join("")}</div>
    <dl class="vlegend">${Object.entries(VERDICT()).map(([k, [cls, ic, vt, ex]]) => `<div><dt><span class="verd ${cls}"><i>${ic}</i>${vt}</span></dt><dd>${ex}</dd></div>`).join("")}</dl>
    <p class="note">${L("Fixed rules on the card's own figures (same day, same normal: median of trading days t−65 to t−6). No language model involved. Trading data shows association, never the cause.", "Feste Regeln auf den Zahlen der Karte (gleicher Tag, gleiches Normal: Median der Handelstage t−65 bis t−6). Kein Sprachmodell. Handelsdaten zeigen Zusammenhänge, nie die Ursache.")}</p></div>`;
}
/* the five statuses of engine/evidence.py, one meaning each */
const VERDICT = () => ({
  supported: ["yes", "✓", L("Consistent with the data", "Mit den Daten vereinbar"), L("The figures fit the explanation. An association, not proof.", "Die Zahlen passen zur Erklärung. Ein Zusammenhang, kein Beweis.")],
  partly: ["part", "◐", L("Partly consistent", "Teilweise vereinbar"), L("Some figures fit, others do not.", "Manche Zahlen passen, andere nicht.")],
  contradicted: ["no", "✕", L("Contradicted by the data", "Von den Daten widerlegt"), L("A measured figure speaks against it.", "Eine gemessene Zahl spricht dagegen.")],
  no_evidence: ["na", "–", L("No sign in the data", "In den Daten nicht erkennbar"), L("Nothing points to it, but the data cannot rule it out.", "Nichts deutet darauf hin, ausschließen können die Daten es aber nicht.")],
  not_testable: ["na", "?", L("Not testable with this data", "Mit diesen Daten nicht prüfbar"), L("The data does not contain what would be needed.", "Die Daten enthalten nicht, was dafür nötig wäre.")]});
const CLAIM_RX = {
  market: /\b(whole|overall|broad|general|entire) market|market[- ](sell-?off|fell|fall|drop|decline|weak|was down|rout|turmoil)|it was the market|the market|sector|industry|macro|interest rate|peers|everyone|all stocks|gesamtmarkt|marktschwäche|markt|sektor|branche|konjunktur|zinsen/i,
  announcement: /result|earning|announc|guidance|ad.?hoc|dividend|figures|numbers|outlook|quarterly|report|ergebnis|zahlen|meldung|prognose|dividende|ausblick|quartal|bericht/i,
  thin: /thin|illiquid|low (volume|liquidity|turnover)|lack of liquidity|few trades|dünn|geringe[rn]? (umsatz|liquidität)|wenig umsatz|mangelnde liquidität/i,
  technical: /rebalanc|index (inclusion|deletion|change|review|fund|trade)|expir|witching|msci|stoxx|ftse|verfall|indexänderung|indexaufnahme|indexstreichung|indexfonds|option|future|derivat/i,
  investors: /fund|institution|hedge|short|investor|retail|block (sale|trade)|placement|fonds|leerverk|anleger|privat|institutionell|platzierung/i,
  overreaction: /overreact|over-react|recover|bounce|revers|rebound|übertr|erhol|gegenbewegung|korrektur/i,
  leak: /leak|before the (news|announcement|release)|insider|front.?run|in advance|ahead of the|vorab|vor der (meldung|nachricht|veröffentlichung)|durchgestochen/i};
/* every number in the AI text must exist in the card JSON (rounded); dates and clock times must match exactly (same rules as ai/checks.py) */
function numbersCheck(text, card) {
  if (!text || !card) return null; const nums = [], strs = new Set(), miss = [];
  (function walk(o) { if (o === null || o === undefined) return; if (typeof o === "number") { [o, o * 100, o / 1e3, o / 1e6, o / 1e9].forEach(v => nums.push(v, Math.abs(v))); nums.push(Math.floor(Math.abs(o) * 100)); } else if (typeof o === "string") strs.add(o); else if (typeof o === "object") Object.values(o).forEach(walk); })(card);
  if (card.comparison && Number.isInteger(card.comparison.n)) nums.push(card.comparison.n + 1);
  const allStr = [...strs].join(" ");
  let t = text.replace(/\b(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})\b/g, (m, d, mo, y) => { if (!allStr.includes(`${y}-${mo.padStart(2, "0")}-${d.padStart(2, "0")}`)) miss.push(m); return " "; });
  t = t.replace(/\b\d{4}-\d{2}-\d{2}\b/g, m => { if (!allStr.includes(m)) miss.push(m); return " "; });
  t = t.replace(/\b\d{1,2}:\d{2}\b/g, m => { if (!allStr.includes(m)) miss.push(m); return " "; });
  const toks = t.match(/[−-]?\d+(?:[.,]\d+)?/g) || []; let total = 0;
  toks.forEach(tok => { const v = Math.abs(parseFloat(tok.replace("−", "-").replace(",", "."))); if (!isFinite(v) || v === 25 || v === 2026) return; total++;
    const dec = (tok.split(/[.,]/)[1] || "").length, tol = dec ? .5 * 10 ** -dec + 1e-9 : .5 + 1e-9; if (!nums.some(n => Math.abs(Math.abs(n) - v) <= tol)) miss.push(tok); });
  total += (text.match(/\b\d{1,2}:\d{2}\b/g) || []).length + (text.match(/\b\d{4}-\d{2}-\d{2}\b/g) || []).length;
  return {total, bad: miss.length, miss};
}

/* ---------- compare ---------- */
const IDXL = i => i === "ALL" ? L("All indices (DAX + MDAX + SDAX)", "Alle Indizes (DAX + MDAX + SDAX)") : i;
function vCompare() {
  const c = S.cmp, u = U(S.isin);
  if (!c.type) { const cur = S.day && (S.done || {})[keyOf(S.isin, S.day, S.ev)]; c.type = "NOTABLE_DAY"; c.index = ["DAX", "MDAX", "SDAX"].includes(u.index) ? u.index : "ALL";
    if (cur && cur.card && cur.card.comparison) { c.type = cur.card.comparison.group_type; c.index = ["DAX", "MDAX", "SDAX"].includes(cur.card.comparison.group_index) ? cur.card.comparison.group_index : "ALL"; } }
  const dd = c.data, types = (dd && dd.types) || [c.type], tc = (dd && dd.type_counts) || {}, cnt = (dd && dd.counts) || {};
  return `<section class="wrap hero"><div class="eyebrow rv">${L("Compare", "Vergleich")}</div><h1 class="h-hero rv" style="--d:.05s" id="cmp-h">${L("Same kind of day.", "Gleiche Art von Tag.")}</h1>
    <p class="lede rv" style="--d:.1s" id="cmp-lede">${L("Every event of the same type in 2026, measured with the impact card's definitions: stock-specific move against the index peers, turnover against the share's own normal.", "Alle Ereignisse desselben Typs 2026, gemessen wie in der Impact Card: titelspezifische Bewegung gegen die Indexwerte, Umsatz gegen das eigene Normalniveau.")}</p>
    <div class="rv" style="--d:.15s;margin-top:24px;display:flex;gap:10px;flex-wrap:wrap"><select class="sel" data-cmp="type" aria-label="${L("Event type", "Ereignistyp")}">${types.map(t => `<option value="${t}" ${t === c.type ? "selected" : ""}>${TYPE(t)}${isN(tc[t]) ? ` (${tc[t]})` : ""}</option>`).join("")}</select>
      <select class="sel" data-cmp="index" aria-label="Index">${["ALL", "DAX", "MDAX", "SDAX"].map(v => `<option value="${v}" ${v === c.index ? "selected" : ""}>${IDXL(v)}${isN(cnt[v]) ? ` (${cnt[v]})` : ""}</option>`).join("")}</select></div>
    <div id="cmpbody" style="margin-top:22px"><div class="skel" style="height:420px"></div></div></section>`;
}
async function fillCompare() {
  const c = S.cmp, want = `${c.type}|${c.index}`;
  if (!c.data || c.key !== want) { try { c.data = await api(`/api/compare?type=${c.type}${c.index !== "ALL" ? "&index=" + c.index : ""}`); c.key = want; } catch (e) { $("#cmpbody") && ($("#cmpbody").innerHTML = `<div class="card lead-empty">${L("The comparison could not be loaded: ", "Der Vergleich konnte nicht geladen werden: ")}${esc(e.message)}</div>`); return; } }
  if (S.route !== "compare" || c.key !== `${S.cmp.type}|${S.cmp.index}`) return;
  /* refresh the two menus with the counts that came with the answer (how many events each choice holds) */
  const tc = c.data.type_counts || {}, cnt = c.data.counts || {};
  const ts = $("[data-cmp=type]"); if (ts) ts.innerHTML = c.data.types.map(t => `<option value="${t}" ${t === c.type ? "selected" : ""}>${TYPE(t)} (${tc[t] ?? 0})</option>`).join("");
  const is = $("[data-cmp=index]"); if (is) is.innerHTML = ["ALL", "DAX", "MDAX", "SDAX"].map(v => `<option value="${v}" ${v === c.index ? "selected" : ""}>${IDXL(v)} (${cnt[v] ?? 0})</option>`).join("");
  const rows = (c.data.rows || []).filter(r => isN(r.abn_ret)), u = U(S.isin), where = c.index === "ALL" ? L("DAX, MDAX and SDAX", "DAX, MDAX und SDAX") : c.index;
  if (!rows.length) {
    const alt = ["ALL", "DAX", "MDAX", "SDAX"].filter(v => v !== c.index && (cnt[v] || 0) > 0);
    $("#cmp-h").textContent = L("No events here yet.", "Hier noch keine Ereignisse.");
    $("#cmp-lede").textContent = L(`The researched calendar has no ${TYPE(c.type).toLowerCase()} in ${where} for 2026. Nothing is estimated in their place.`, `Der recherchierte Kalender enthält 2026 keine ${TYPE(c.type)} in ${where}. Es wird nichts ersatzweise geschätzt.`);
    $("#cmpbody").innerHTML = `<div class="card lead-empty">${alt.length ? `${L("Available:", "Verfügbar:")} ${alt.map(v => `<button class="btn ghost sm" data-act="cmpidx" data-index="${v}" style="margin:4px 6px 0 0">${IDXL(v)} · ${cnt[v]}</button>`).join("")}` : L("No events of this type in any index.", "Keine Ereignisse dieses Typs in einem Index.")}</div>`;
    return;
  }
  const sorted = [...rows].sort((a, b) => Math.abs(b.abn_ret) - Math.abs(a.abn_ret)), me = r => r.isin === S.isin && S.day && day10(r.reaction_day) === S.day, mine = sorted.findIndex(me), own = sorted.filter(r => r.isin === S.isin).length;
  $("#cmp-h").textContent = mine >= 0 ? `#${mine + 1} ${L("of", "von")} ${sorted.length}.` : L(`${sorted.length} event${sorted.length === 1 ? "" : "s"}.`, `${sorted.length} Ereignis${sorted.length === 1 ? "" : "se"}.`);
  $("#cmp-lede").textContent = mine >= 0 ? L(`${nice(u)} on ${dS(S.day)} ranks #${mine + 1} by size of the stock-specific move among ${TYPE(c.type).toLowerCase()} in ${where}, Jan–Oct 2026.`, `${nice(u)} am ${dS(S.day)} liegt auf Rang ${mine + 1} nach Größe der titelspezifischen Bewegung unter ${TYPE(c.type)} in ${where}, Jan.–Okt. 2026.`)
    : L(`${TYPE(c.type)} in ${where}, Jan–Oct 2026. ${nice(u)} has ${own} of them${own ? ", marked in the accent colour" : ""}. Open one of your own days to see its rank.`, `${TYPE(c.type)} in ${where}, Jan.–Okt. 2026. ${nice(u)} hat davon ${own}${own ? ", in der Akzentfarbe markiert" : ""}. Öffnen Sie einen eigenen Tag, um seinen Rang zu sehen.`);
  const thin = rows.length < 10 ? `<p class="note">${L(`Only ${rows.length} researched event${rows.length === 1 ? "" : "s"} of this type here: read them as examples, not as a benchmark.`, `Nur ${rows.length} recherchierte${rows.length === 1 ? "s Ereignis" : " Ereignisse"} dieses Typs: als Beispiele lesen, nicht als Benchmark.`)}</p>` : "";
  $("#cmpbody").innerHTML = `<div class="card"><div class="chart-top"><div class="chart-read">${L("Turnover vs normal → (log scale) · stock-specific move ↑", "Umsatz vs. normal → (log. Skala) · titelspezifische Bewegung ↑")}</div>
      <div class="legend-k"><span><i class="k-me"></i>${L("open day", "geöffneter Tag")}</span><span><i class="k-own"></i>${esc(nice(u))}</span><span><i class="k-oth"></i>${L("other companies", "andere Unternehmen")}</span></div></div>
    <div class="chart in">${scatter(rows, me)}</div>${thin}</div>
    <div class="card" style="margin-top:16px"><table class="tbl"><thead><tr><th>#</th><th style="text-align:left">${L("Event", "Ereignis")}</th><th>${L("Stock-specific", "Titelspezifisch")}</th><th>${L("Turnover vs normal", "Umsatz vs. normal")}</th><th>${L("Trading cost vs normal", "Handelskosten vs. normal")}</th></tr></thead><tbody>
    ${sorted.slice(0, 12).map((r, i) => `<tr class="go ${r.isin === S.isin ? "mine" : ""}" data-xopen="${r.isin}|${day10(r.reaction_day)}|${esc(rowEv(r))}"><td class="muted">${i + 1}</td><td style="text-align:left" class="${r.isin === S.isin ? "me" : ""}">${esc(nice(U(r.isin) || r))} · ${dS(r.reaction_day)}</td><td class="${r.abn_ret < 0 ? "dn" : "up"}">${pct(r.abn_ret)}</td><td>${X(r.vol_ratio)}</td><td>${X(r.xlm_ratio)}</td></tr>`).join("")}</tbody></table>
    <p class="note">${L("Medians", "Mediane")}: ${pct(median(rows.map(r => Math.abs(r.abn_ret))), 1, false)} ${L("stock-specific move (absolute)", "titelspezifische Bewegung (absolut)")} · ${X(median(rows.map(r => r.vol_ratio)))} ${L("turnover", "Umsatz")} · ${X(median(rows.map(r => r.xlm_ratio)))} ${L("trading cost", "Handelskosten")}</p></div>`;
}

/* ---------- report ---------- */
function repOptions() { return timeline().map(r => [`${r.day}|${r.ev || ""}`, `${dS(r.day)} · ${r.type ? TAG(r.type) : L("unusual day", "auffälliger Tag")} · ${pct(r.abn)}`]); }
function vReport() {
  const r = S.rep; if (r.key === null) { const ld = S.day ? `${S.day}|${S.ev || ""}` : (leadDay() ? `${leadDay().day}|${leadDay().ev || ""}` : ""); r.key = ld; }
  const noCard = !r.key, p = periodOf(S.period);
  const ck = (k, t, dis) => `<label class="ck"><input type="checkbox" data-rep="${k}" ${r[k] && !dis ? "checked" : ""} ${dis ? "disabled" : ""}><span>${t}</span></label>`;
  return `<section class="wrap hero"><div class="eyebrow rv no-print">${L("Report", "Report")}</div><h1 class="h-hero rv no-print" style="--d:.05s">${L("IR snapshot.", "IR-Snapshot.")}</h1><p class="lede rv no-print" style="--d:.1s">${L("One page for the board, in English or German. Choose what goes in; the page on the right is exactly what is saved.", "Eine Seite für den Vorstand, auf Deutsch oder Englisch. Wählen Sie die Inhalte; die Seite rechts ist genau das, was gespeichert wird.")}</p>
    <div class="rep"><div class="opts rv"><fieldset class="cks"><legend class="cap">${L("Include", "Enthalten")}</legend>
      ${ck("perf", L(`Share price · ${p.label}`, `Aktienkurs · ${p.label}`))}${ck("profile", L("Trading profile (60 days)", "Handelsprofil (60 Tage)"))}${ck("peers", L("Peers", "Peers"))}${ck("liq", L("Liquidity", "Liquidität"))}${ck("anom", L(`Unusual days · ${p.label}`, `Auffällige Tage · ${p.label}`))}${ck("card", L("Impact card", "Impact Card"), noCard)}${ck("words", L("Summary in plain words", "Zusammenfassung"), noCard)}</fieldset>
      <label class="cap" for="repkey" style="display:block;margin-top:16px">${L("Impact card for", "Impact Card für")}</label>
      <select class="sel" id="repkey" data-rep="key" style="margin-top:6px;width:100%"><option value="">${L("No impact card", "Keine Impact Card")}</option>${repOptions().map(([v, t]) => `<option value="${esc(v)}" ${v === r.key ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>
      <button class="btn" data-act="print" style="margin-top:16px;justify-content:center;width:100%">${L("Save as PDF", "Als PDF sichern")}</button><p class="note">${L("Prints exactly this page with the sections you chose. Choose “Save as PDF” in the print dialog.", "Druckt genau diese Seite mit den gewählten Abschnitten. Im Druckdialog „Als PDF sichern“ wählen.")}</p></div>
    <div class="doc rv" style="--d:.1s" id="doc">${docHTML()}</div></div></section>`;
}
function docHTML() {
  const r = S.rep, u = U(S.isin), iss = S.iss, k = iss.kpis, lt = iss.liquidity, [day, ev] = (r.key || "|").split("|"), ck = keyOf(S.isin, day, ev), dn = S.dashNow, per = periodOf(S.period);
  const d = S._resolved && S._resolved[ck], ai = S._resolvedAI && S._resolvedAI[ck + "|" + S.lang], br = S._resolvedB && S._resolvedB[ck];
  const kv = list => `<div class="kv">${list.map(([a, b]) => `<span>${a}</span><span>${b}</span>`).join("")}</div>`, blk = (key, h) => `<div class="sec-block ${r[key] ? "" : "off"}" data-blk="${key}">${h}</div>`;
  const p = iss.peers, g = p.groups.filter(x => x.values && x.n);
  let h = `<div style="font-size:11px;color:#86868b">${L("IR SNAPSHOT", "IR-SNAPSHOT")} · ${u.ticker} · ${u.isin} · ${u.index} · ${L("Xetra data to", "Xetra-Daten bis")} ${dY(iss.meta.last_date)}</div><h2>${esc(nice(u))}</h2>`;
  if (br && !br.error) { const b = br[S.lang] || br.en; h += blk("card", `<div style="border-left:3px solid #0071e3;padding:2px 0 2px 12px;margin-bottom:6px"><b>${L("Main finding", "Kernaussage")}</b><br>${esc(b.headline)}</div>`); }
  if (dn) { const vm = dn.versus_market, pr = vm.price;
    h += blk("perf", `<h4>${L(`Share price · ${per.label} (${dS(pr.start_close)} close to ${dY(dn.to)} close)`, `Aktienkurs · ${per.label} (Schluss ${dS(pr.start_close)} bis Schluss ${dY(dn.to)})`)}</h4>${kv([[L("Share", "Aktie"), `${pct(pr.stock)} (${PX(pr.close_start)} → ${PX(pr.close_end)})`], [L(`${vm.index} peers, equal-weighted`, `${vm.index}-Werte, gleichgewichtet`), pct(pr.index)], [L("Difference", "Differenz"), PP(isN(pr.stock) && isN(pr.index) ? pr.stock - pr.index : null)], [L("Rank by return", "Rang nach Rendite"), `${pr.rank} / ${pr.of}`], [L("Median turnover · trading cost €25k", "Medianumsatz · Handelskosten 25 T€"), `${EUR(vm.turnover_eur.stock)} · ${BPS(vm.xlm_25k.stock)}`]])}<p style="margin:6px 0 0;color:#86868b;font-size:11px">${L("Closing-auction prices, not adjusted for dividends.", "Schlussauktionskurse, nicht um Dividenden bereinigt.")}${per.note ? " " + L("The 31 Dec 2025 close is not in the data.", "Der Schlusskurs vom 31.12.2025 fehlt in den Daten.") : ""}</p>`); }
  h += blk("profile", `<h4>${L("Trading profile · last 60 trading days", "Handelsprofil · letzte 60 Handelstage")}</h4>${kv([[L("Turnover per day", "Umsatz pro Tag"), `${EUR(k.median_turnover_eur.stock)} (${u.index} ${EUR(k.median_turnover_eur.index_median)})`], [L("Cost to trade €25k", "Kosten 25 T€"), `${BPS(k.median_xlm_25k_bps.stock)} (${u.index} ${BPS(k.median_xlm_25k_bps.index_median)})`], [L("Auction share", "Auktionsanteil"), pct(k.median_auction_share.stock, 0, false)], [L("Client orders", "Kundenorders"), pct(k.median_agent_share.stock, 0, false)]])}`);
  h += blk("peers", `<h4>${L("Peers", "Peers")}</h4>${kv(g.map(x => [`${x.key === "index" ? u.index : x.key === "size" ? L("Similar size", "Ähnliche Größe") : esc(x.name)} (${x.n})`, `${EUR(x.values.turnover_eur)} · ${BPS(x.values.xlm_25k)}`]))}`);
  h += blk("liq", `<h4>${L("Liquidity", "Liquidität")}</h4><p style="margin:0">${L(`Trading cost ${pct(lt.xlm_25k_change_pct, 0)} and turnover ${pct(lt.turnover_change_pct, 0)}, last 60 vs previous 60 trading days. Xetra liquidity category (estimate): ${k.liquidity_check.category_estimate || "n/a (no XLM)"}.`, `Handelskosten ${pct(lt.xlm_25k_change_pct, 0)} und Umsatz ${pct(lt.turnover_change_pct, 0)}, letzte 60 vs. vorherige 60 Handelstage. Xetra-Liquiditätskategorie (Schätzung): ${k.liquidity_check.category_estimate || "k. A. (kein XLM)"}.`)}</p>`);
  const an = timeline().filter(x => x.unusual && inPeriod(x.day));
  h += blk("anom", `<h4>${L(`Unusual days · ${per.label}`, `Auffällige Tage · ${per.label}`)}</h4>${an.length ? "" : `<p style="margin:0;color:#86868b">${L("None in this period.", "Keine in diesem Zeitraum.")}</p>`}${kv(an.slice(0, 6).map(x => [`${dS(x.day)} · ${x.type ? TAG(x.type) : L("cause open", "Ursache offen")}`, `${pct(x.abn)} · ${X(x.vol)}`]))}`);
  if (day) {
    if (!d) h += blk("card", `<h4>${L("Impact card", "Impact Card")}</h4><p style="margin:0;color:#86868b">${L("Loading…", "Wird geladen…")}</p>`);
    else if (!d.error) { const c = d.card; h += blk("card", `<h4>${L("Impact card", "Impact Card")} · ${dY(c.event.reaction_day)} · ${esc(c.event.type)}</h4>${c.event.type !== "NOTABLE_DAY" ? `<p style="margin:0 0 6px">${esc(c.event.title)}</p>` : ""}${kv([[L("Share", "Aktie"), pct(c.price.ret)], [L("Peers", "Peers"), pct(c.price.peer_ret)], [L("Stock-specific move", "Titelspezifische Bewegung"), pct(c.price.abn_ret)], [L("Turnover vs normal", "Umsatz vs. normal"), X(c.volume.ratio)], [L("Trading cost vs normal", "Handelskosten vs. normal"), X(c.liquidity.ratio)], [L("Closing auction", "Schlussauktion"), `${EUR(c.auctions.close_auction_eur)} (${X(c.auctions.close_auction_ratio)})`]])}`);
      if (br && !br.error) { const b = br[S.lang] || br.en, sec = key => (b.sections.find(x => x.key === key) || {points: []}).points; h += blk("card", `<h4>${L("What the data cannot tell", "Was die Daten nicht sagen")}</h4><p style="margin:0">${esc(sec("unknown")[0] || "")}</p><h4>${L("Next step", "Nächster Schritt")}</h4><p style="margin:0">${esc(sec("next")[0] || "")}</p>`); } }
    h += blk("words", `<h4>${L("In plain words", "In einfachen Worten")}</h4><p style="margin:0">${ai && !ai.error ? esc(ai.text) : ai && ai.error ? `<span style="color:#86868b">${L("The summary could not be generated.", "Die Zusammenfassung konnte nicht erstellt werden.")}</span>` : `<span style="color:#86868b">${L("Writing…", "Wird geschrieben…")}</span>`}</p>${ai && !ai.error ? `<p style="margin:4px 0 0;color:#86868b;font-size:10px">${ai.source === "llm" ? L("Written by the language model from the card; every figure checked against it.", "Vom Sprachmodell aus der Karte geschrieben; jede Zahl dagegen geprüft.") : L("Template text from the card's figures.", "Vorlagentext aus den Zahlen der Karte.")}</p>` : ""}`);
  }
  return h + `<p style="font-size:10px;color:#86868b;margin-top:28px;border-top:1px solid #e8e8ed;padding-top:8px">${L("Source: Deutsche Börse Xetra data (OHLC, flow dynamics, XLM, on-book trades) and the researched event calendar. Figures computed by the engine; text generated from them and checked. Causes are not in the data. Not investment advice.", "Quelle: Deutsche Börse Xetra-Daten (OHLC, Flow Dynamics, XLM, On-Book-Trades) und der recherchierte Ereigniskalender. Zahlen von der Engine; Text daraus generiert und geprüft. Ursachen sind nicht in den Daten. Keine Anlageberatung.")}</p>`;
}
async function fillReport() {
  const [day, ev] = (S.rep.key || "|").split("|"); if (!day) return; const isin = S.isin, ck = keyOf(isin, day, ev);
  if (!S.rep.card && !S.rep.words) return;   /* nothing of the card is in the report: no card request */
  S._resolved = S._resolved || {}; S._resolvedB = S._resolvedB || {}; S._resolvedAI = S._resolvedAI || {};
  const [d, b] = await loadCard(isin, day, ev); S._resolved[ck] = d; S._resolvedB[ck] = b;
  if (S.route === "report" && $("#doc")) $("#doc").innerHTML = docHTML();
  S._resolvedAI[ck + "|" + S.lang] = await loadAI(isin, day, ev, S.lang);
  if (S.route === "report" && $("#doc")) $("#doc").innerHTML = docHTML();
}

/* ============================== ideas ============================== */
function vIdeas() {
  const I = [
    [L("Index watch", "Index-Frühwarnung"), L("Gerresheimer left the SDAX on 9 April and its XLM coverage ended with it. Track the share's rank against the index rules every day and warn months ahead.", "Gerresheimer schied am 9. April aus dem SDAX aus, damit endete auch die XLM-Abdeckung. Den Rang täglich gegen die Indexregeln verfolgen und Monate vorher warnen."), L("daily index lists, turnover", "tägliche Indexlisten, Umsatz"), L("free-float market cap, official rank lists", "Free-Float-Marktkapitalisierung, Ranglisten")],
    [L("Liquidity category monitor", "Liquiditätskategorie-Monitor"), L("Small caps such as Heidelberger Druck sit close to the Designated Sponsor thresholds. Track the rolling 4-month position against both rules.", "Small Caps wie Heidelberger Druck liegen nah an den Designated-Sponsor-Schwellen. Die rollierende 4-Monats-Position gegen beide Regeln verfolgen."), L("XLM, turnover", "XLM, Umsatz"), L("official category list", "offizielle Kategorieliste")],
    [L("Announcement planner", "Veröffentlichungsplaner"), L("Which publication time gives the cleanest reaction? Compare reactions by release time across all events of the same type.", "Welche Veröffentlichungszeit sorgt für die sauberste Reaktion? Reaktionen nach Uhrzeit über gleichartige Ereignisse vergleichen."), L("1-minute bars, event times", "1-Minuten-Balken, Ereigniszeiten"), L("more events with exact times", "mehr Ereignisse mit genauer Uhrzeit")],
    [L("Before-the-news monitor", "Vor-der-Nachricht-Monitor"), L("Unusual volume or one-sided client flow in the days before an announcement is a question IR wants to ask first.", "Auffälliger Umsatz oder einseitiger Kundenfluss vor einer Meldung ist eine Frage, die IR zuerst stellen will."), L("flows, 1-minute bars", "Flows, 1-Minuten-Balken"), L("ad hoc and news timestamps", "Zeitstempel von Ad-hoc-Meldungen")],
    [L("Derivatives positioning", "Derivate-Positionierung"), L("Eurex open interest by participant (long/short) on single-stock options and futures shows how the market positioned before an event.", "Eurex Open Interest nach Teilnehmer (long/short) auf Einzelaktienoptionen und -futures zeigt die Positionierung vor einem Ereignis."), L("Eurex open interest in the excerpt, usable for large caps", "Eurex Open Interest im Auszug, nutzbar für Large Caps"), L("the participant split is censored for >90 % of small-cap series: uncensored data", "die Teilnehmer-Aufteilung ist bei >90 % der Small-Cap-Serien zensiert: unzensierte Daten")],
    [L("Surprise vs consensus", "Überraschung vs. Konsens"), L("Put results-day reactions next to the earnings surprise so the board sees whether the market punished the number or the guidance.", "Reaktionen am Ergebnistag neben die Gewinnüberraschung stellen: Bestrafte der Markt die Zahl oder den Ausblick?"), L("stock-specific move per event", "titelspezifische Bewegung je Ereignis"), L("consensus estimates", "Konsensschätzungen")]];
  return `<section class="wrap hero"><div class="eyebrow rv">${L("Ideas", "Ideen")}</div><h1 class="h-hero rv" style="--d:.05s">${L("What IR needs next.", "Was IR als Nächstes braucht.")}</h1>
    <p class="lede rv" style="--d:.1s">${L("Ideas for the Issuer Services Hub built on the same data, and the data each one still needs.", "Ideen für den Issuer Services Hub auf derselben Datenbasis, und welche Daten jeweils noch fehlen.")}</p></section>
  <section class="wrap" style="margin-top:36px"><div class="grid g3">${I.map((t, i) => `<div class="card rv" style="--d:${(i % 3) * .05}s"><h3 style="margin:0 0 8px;font:600 21px/1.2 var(--display);letter-spacing:-.02em">${t[0]}</h3><p class="muted" style="margin:0 0 16px;font-size:15px">${t[1]}</p>
    <div class="note" style="border-top:1px solid var(--sep);padding-top:10px"><b style="color:var(--text2)">${L("Have", "Hat")}:</b> ${t[2]}<br><b style="color:var(--accent)">${L("Need", "Fehlt")}:</b> ${t[3]}</div></div>`).join("")}</div></section>`;
}

/* ============================== IR analyst (POST /api/agent) ============================== */
const TOOLL = () => ({find_company: L("Company search", "Unternehmenssuche"), company_overview: L("Trading profile", "Handelsprofil"), share_performance: L("Share performance", "Kursentwicklung"), peer_benchmark: L("Peers", "Peers"), trading_cost_curve: L("Cost by order size", "Kosten nach Ordergröße"), unusual_days: L("Unusual days", "Auffällige Tage"), event_calendar: L("Calendar", "Kalender"), impact_card: "Impact card", compare_events: L("Comparison", "Vergleich"), check_explanation: L("Explanation check", "Erklärungsprüfung")});
function sugg() {
  if (S.route === "event") return [L("Was this the market, or company-specific?", "War das der Markt oder unternehmensspezifisch?"), L("Explain this card in two sentences", "Erklären Sie diese Karte in zwei Sätzen"), L("How does this rank against similar events?", "Wie ordnet sich das gegenüber ähnlichen Ereignissen ein?")];
  if (S.route === "compare") return [L("Where do we rank among these events?", "Auf welchem Rang liegen wir bei diesen Ereignissen?"), L("How did the market react to our results?", "Wie hat der Markt auf unsere Ergebnisse reagiert?")];
  return [L("Has our liquidity improved?", "Hat sich unsere Liquidität verbessert?"), L("How do our spreads compare with our sector?", "Wie sind unsere Spreads im Sektorvergleich?"), L("What were our biggest moves this year?", "Was waren unsere größten Bewegungen dieses Jahr?"), L("How large an order can the book absorb?", "Wie große Orders nimmt das Orderbuch auf?")];
}
function ctx() { const c = {page: {overview: "dashboard", events: "card", event: "card", compare: "compare", report: "report", ideas: "dashboard"}[S.route]};
  if (S.dashNow) { c.period = S.period; c.from = S.dashNow.versus_market.price.start_close; c.to = S.dashNow.to; } if (S.route === "event") { c.day = S.day; c.event_id = S.ev; } if (S.route === "compare") { c.event_type = S.cmp.type; c.index = S.cmp.index; } return c; }
function sheet(on) { $("#sheet").classList.toggle("on", on); $("#scrim").classList.toggle("on", on); $("#sheet").setAttribute("aria-hidden", !on); if (on) { drawChat(); setTimeout(() => $("#q").focus(), 350); } }
const actL = a => a.view === "card" ? `${L("Open impact card", "Impact Card öffnen")}${a.day ? " · " + dS(a.day) : ""}` : a.view === "compare" ? `${L("Compare", "Vergleichen")}${a.event_type ? ": " + TYPE(a.event_type) : ""}` : a.view === "report" ? L("Open report", "Report öffnen") : L("Open overview", "Überblick öffnen");
function drawChat() {
  const u = U(S.isin);
  $("#shtitle").textContent = L("IR Analyst", "IR-Analyst");
  $("#shctx").innerHTML = S.st.llm ? `<span class="mdl" title="${esc(S.st.model)}"><i>${SPARK}</i>${modelName(S.st.model)}</span>`
    : `<span class="mdl off"><i>${SPARK}</i>${L("Fixed-rule answers, no model connected", "Antworten nach festen Regeln, kein Modell")}</span>`;
  $("#log").innerHTML = (S.chat.length ? "" : `<div class="msg ai">${L(`Ask me about ${esc(nice(u))}: liquidity, a day, peers or results. I answer with figures from the Xetra engine and can open any page for you. I say what the data shows, not why.`, `Fragen Sie mich zu ${esc(nice(u))}: Liquidität, ein Tag, Peers oder Ergebnisse. Ich antworte mit Zahlen aus der Xetra-Engine und öffne jede Seite. Ich sage, was die Daten zeigen, nicht warum.`)}</div>`) +
    S.chat.map(m => m.typing ? `<div class="msg ai"><span class="typing" style="padding:4px 0"><i></i><i></i><i></i></span> <span class="muted" style="font-size:13px">${L("reading the engine output…", "liest die Engine-Ergebnisse…")}</span></div>` : m.me ? `<div class="msg me">${esc(m.t)}</div>` : msgAI(m)).join("");
  $("#sugg").innerHTML = sugg().map(q => `<button data-q="${esc(q)}">${esc(q)}</button>`).join("");
  $("#q").placeholder = L("Ask about liquidity, a day, peers…", "Fragen zu Liquidität, einem Tag, Peers…"); $("#q").disabled = !!S.st.offline;
  $("#log").scrollTop = 1e6;
}
function msgAI(m) {
  const chk = m.check, bad = chk && chk.unsupported && chk.unsupported.length;
  const src = m.source === "llm" ? esc(modelName(m.model)) + (m.cached ? L(" · saved answer", " · gespeicherte Antwort") : "") : m.source === "error" ? L("error", "Fehler") : L("fixed rules, no model", "feste Regeln, kein Modell") + (m.note ? L(" (model answer not used)", " (Modellantwort nicht verwendet)") : "");
  return `<div class="msg ai">${m.steps && m.steps.length ? `<div class="steps">${m.steps.filter(s => s.tool !== "show").map(s => `<span>${esc(TOOLL()[s.tool] || s.tool)}${s.args && s.args.day ? " " + dS(s.args.day) : ""}</span>`).join("")}</div>` : ""}<div style="white-space:pre-line">${esc(m.t)}</div>
    ${m.actions && m.actions.length ? `<div class="acts">${m.actions.map(a => `<button class="btn sm" data-do="${esc(JSON.stringify(a))}">${esc(actL(a))}</button>`).join("")}</div>` : ""}
    <span class="src2 ${bad ? "warn" : ""}">${chk && chk.total ? (bad ? L(`${chk.unsupported.length} figure(s) not in the engine output`, `${chk.unsupported.length} Zahl(en) nicht in den Engine-Ergebnissen`) : L(`✓ all ${chk.total} figures from the engine`, `✓ alle ${chk.total} Zahlen aus der Engine`)) + " · " : ""}${src}</span></div>`;
}
async function ask(q) {
  if (S.busy) return; S.busy = true;
  const history = S.chat.filter(m => !m.typing).map(m => ({role: m.me ? "user" : "assistant", content: m.t}));
  S.chat.push({me: true, t: q}, {typing: true}); drawChat();
  try { const r = await post("/api/agent", {isin: S.isin, question: q, history, context: ctx(), lang: S.lang}); S.chat.pop(); S.chat.push({t: r.text, source: r.source, model: r.model, steps: r.steps, actions: r.actions, check: r.check, cached: r.cached, note: r.note}); }
  catch (e) { S.chat.pop(); S.chat.push({t: L("The analyst could not answer: ", "Der Analyst konnte nicht antworten: ") + e.message, source: "error"}); }
  S.busy = false; drawChat();
}
function doAction(a) {
  if (innerWidth < 1200) sheet(false);
  if (a.view === "card" && a.day) { openEvent(a.isin || S.isin, a.day, a.event_id || null); return; }
  if (a.isin && a.isin !== S.isin) { switchCompany(a.isin, a.view === "compare" ? "compare" : a.view === "report" ? "report" : "overview"); return; }
  if (a.view === "compare") { if (a.event_type) S.cmp.type = a.event_type; S.cmp.index = a.index || "ALL"; S.cmp.data = null; go("compare"); return; }
  if (a.view === "report") { if (a.day) S.rep.key = `${a.day}|${a.event_id || ""}`; go("report"); return; }
  go("overview");
}

/* ============================== spotlight palette ============================== */
const PL = {sel: 0, items: []};
function pal(on) { $("#pal").classList.toggle("on", on); $("#scrim").classList.toggle("on", on || $("#sheet").classList.contains("on")); if (on) { $("#palq").value = ""; PL.sel = 0; palList(); setTimeout(() => $("#palq").focus(), 50); } }
function palList() {
  const q = $("#palq").value.trim().toLowerCase();
  const sc = u => { const n = nice(u).toLowerCase(), t = u.ticker.toLowerCase(), i = u.isin.toLowerCase(); if (!q) return u.isin === S.isin ? 200 : u.hero ? 100 : 0; if (i === q || t === q) return 100; if (t.startsWith(q)) return 70; if (n.startsWith(q)) return 60; if (n.includes(q) || u.name.toLowerCase().includes(q)) return 40; if (i.includes(q)) return 30; return 0; };
  const cos = S.uni.map(u => [sc(u), u]).filter(x => x[0] > 0).sort((a, b) => b[0] - a[0] || b[1].avg_turnover_eur - a[1].avg_turnover_eur).slice(0, 7).map(x => ({k: "co", u: x[1]}));
  const ld = leadDay();
  const acts = [ld && [L("Open the most unusual day", "Auffälligsten Tag öffnen"), "lead"], [L("Ask the IR analyst", "IR-Analyst fragen"), "ask"], [L("Export IR report (PDF)", "IR-Report exportieren (PDF)"), "pdf"], [L("Compare events", "Ereignisse vergleichen"), "go:compare"], [de() ? "Switch to English" : "Auf Deutsch umschalten", "lang"], [document.documentElement.dataset.theme === "dark" ? L("Light mode", "Heller Modus") : L("Dark mode", "Dunkler Modus"), "theme"]].filter(Boolean).filter(([t]) => !q || t.toLowerCase().includes(q)).map(([t, a]) => ({k: "act", t, a}));
  PL.items = [...cos, ...acts]; PL.sel = Math.min(PL.sel, Math.max(0, PL.items.length - 1));
  let h = "", i = 0;
  if (cos.length) h += `<li class="grp" role="presentation">${L("Companies", "Unternehmen")} · ${S.uni.length}</li>` + cos.map(c => `<li role="option" data-pi="${i}" aria-selected="${i++ === PL.sel}"><span class="ic">${c.u.ticker}</span><span>${esc(nice(c.u))}<small>${c.u.index} · ${c.u.isin}${c.u.isin === S.isin ? " · " + L("open now", "geöffnet") : c.u.hero ? " · " + L("full calendar", "voller Kalender") : ""}</small></span></li>`).join("");
  if (acts.length) h += `<li class="grp" role="presentation">${L("Actions", "Aktionen")}</li>` + acts.map(a => `<li role="option" data-pi="${i}" aria-selected="${i++ === PL.sel}"><span class="ic">↵</span><span>${a.t}</span></li>`).join("");
  $("#pall").innerHTML = h || `<li class="grp">${L("No DAX, MDAX or SDAX share matches.", "Keine passende DAX-, MDAX- oder SDAX-Aktie.")}</li>`;
  const sel = $("#pall [aria-selected=true]"); sel && sel.scrollIntoView({block: "nearest"});
}
function palRun(it) {
  pal(false); if (!it) return;
  if (it.k === "co") { if (it.u.isin !== S.isin) switchCompany(it.u.isin); return; }
  if (it.a === "lead") { const ld = leadDay(); if (ld) openEvent(S.isin, ld.day, ld.ev); }
  else if (it.a.startsWith("go:")) go(it.a.slice(3)); else if (it.a === "ask") sheet(true);
  else if (it.a === "pdf") { if (S.st.offline) go("report"); else location.href = `/api/export?isin=${S.isin}&lang=${S.lang}`; }
  else if (it.a === "lang") setLang(de() ? "en" : "de");
  else if (it.a === "theme") setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
}
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("iih.theme", t); } catch (e) { /* ignore: the choice then lasts for this page only */ }
  themeBtn();
  if (S.iss) render(true);
}
function themeBtn() {
  const dark = document.documentElement.dataset.theme === "dark", b = $("#theme");
  if (!b) return;
  b.setAttribute("aria-label", dark ? L("Switch to light mode", "Zum hellen Modus wechseln") : L("Switch to dark mode", "Zum dunklen Modus wechseln"));
  b.title = b.getAttribute("aria-label");
  b.innerHTML = dark ? `<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5" fill="currentColor"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></g></svg>`
    : `<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" fill="currentColor"/></svg>`;
}
function setLang(l) { S.lang = l; try { localStorage.setItem("iih.lang", l); } catch (e) { /* ignore */ } render(true); }

/* ============================== calendar import (CSV / ICS) ============================== */
const guessType = t => { t = String(t).toLowerCase(); return /hauptversammlung|agm|annual general/.test(t) ? "AGM" : /dividend|ex-tag/.test(t) ? "DIVIDEND_EX" : /\bq1\b|first quarter|1\. quartal/.test(t) ? "Q1" : /\bh1\b|half|halbjahr/.test(t) ? "H1" : /\bq3\b|third quarter|9m|nine months|9 monate/.test(t) ? "Q3" : /annual|full.year|geschäftsjahr|fy\b|jahresergebnis/.test(t) ? "FY" : /ad.hoc/.test(t) ? "ADHOC" : /guidance|prognose|outlook/.test(t) ? "GUIDANCE" : /capital markets day|kapitalmarkttag|cmd\b/.test(t) ? "CMD" : "OTHER"; };
function csvRows(text) {
  const first = text.split(/\r?\n/)[0] || "", sep = [";", "\t", ","].sort((a, b) => first.split(b).length - first.split(a).length)[0];
  const out = []; let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) { const ch = text[i];
    if (q) { if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (ch === '"') q = false; else cell += ch; }
    else if (ch === '"') q = true; else if (ch === sep) { row.push(cell.trim()); cell = ""; }
    else if (ch === "\n" || ch === "\r") { if (ch === "\r" && text[i + 1] === "\n") i++; row.push(cell.trim()); cell = ""; if (row.some(c => c)) out.push(row); row = []; } else cell += ch; }
  row.push(cell.trim()); if (row.some(c => c)) out.push(row); return out;
}
function zoneToBerlin(date, time, tz) {
  const fmt = (z, ms) => Object.fromEntries(new Intl.DateTimeFormat("en-GB", {timeZone: z, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"}).formatToParts(new Date(ms)).map(x => [x.type, x.value]));
  const want = Date.UTC(+date.slice(0, 4), +date.slice(5, 7) - 1, +date.slice(8, 10), +time.slice(0, 2), +time.slice(3, 5)); let ms = want;
  for (let k = 0; k < 2; k++) { const p = fmt(tz, ms); ms += want - Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute); }
  const b = fmt("Europe/Berlin", ms); return [`${b.year}-${b.month}-${b.day}`, `${b.hour}:${b.minute}`];
}
function parseCalendar(text) {
  const out = [];
  if (/BEGIN:VEVENT/.test(text)) {
    text.replace(/\r?\n[ \t]/g, "").split("BEGIN:VEVENT").slice(1).forEach(b => {
      const line = b.match(/^DTSTART([^:\r\n]*):([^\r\n]+)/m) || [], sum = ((b.match(/^SUMMARY[^:]*:(.*)$/m) || [])[1] || "").trim().replace(/\\,/g, ",").replace(/\\;/g, ";").replace(/\\n/gi, " ");
      const v = (line[2] || "").trim(), m = v.match(/^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})\d{0,2}(Z)?)?$/);
      if (!m) { out.push({date: "", time: "", type: guessType(sum), title: sum, issue: L("no readable DTSTART", "kein lesbares DTSTART")}); return; }
      let date = `${m[1]}-${m[2]}-${m[3]}`, time = m[4] ? `${m[4]}:${m[5]}` : "", note = ""; const tz = ((line[1] || "").match(/TZID=([^;:]+)/) || [])[1];
      try { if (time && m[6]) [date, time] = zoneToBerlin(date, time, "UTC"); else if (time && tz && tz !== "Europe/Berlin") { [date, time] = zoneToBerlin(date, time, tz.replace(/"/g, "")); note = L(`converted from ${tz}`, `umgerechnet aus ${tz}`); } else if (time && !tz) note = L("no time zone: read as Berlin time", "keine Zeitzone: als Berliner Zeit gelesen"); }
      catch (e) { note = L(`unknown time zone ${tz}: read as Berlin time`, `unbekannte Zeitzone ${tz}: als Berliner Zeit gelesen`); }
      out.push({date, time, type: guessType(sum), title: sum, note}); });
    return out;
  }
  const rs = csvRows(text); if (!rs.length) return out;
  const head = rs[0].map(h => h.toLowerCase()), has = head.some(h => ["date", "datum"].includes(h)), ix = ks => head.findIndex(h => ks.includes(h));
  const iD = has ? ix(["date", "datum"]) : 0, iT = has ? ix(["time", "zeit", "uhrzeit"]) : 1, iY = has ? ix(["type", "typ", "art"]) : 2, iN = has ? ix(["title", "titel", "event", "name", "ereignis", "beschreibung"]) : 3;
  rs.slice(has ? 1 : 0).forEach(c => {
    let d = c[iD] || ""; const g = d.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/); if (g) d = `${g[3]}-${g[2].padStart(2, "0")}-${g[1].padStart(2, "0")}`;
    const title = iN >= 0 ? c[iN] || "" : "", ty = iY >= 0 ? (c[iY] || "").toUpperCase() : ""; let time = iT >= 0 ? (c[iT] || "").replace(".", ":") : ""; if (/^\d:\d\d$/.test(time)) time = "0" + time;
    const row = {date: d.slice(0, 10), time: /^\d\d:\d\d/.test(time) ? time.slice(0, 5) : "", type: EVTYPES.includes(ty) ? ty : guessType(title), title};
    if (!/^\d{4}-\d{2}-\d{2}$/.test(row.date) || isNaN(Date.parse(row.date))) row.issue = L(`date “${c[iD] || ""}” not readable: use YYYY-MM-DD or DD.MM.YYYY`, `Datum „${c[iD] || ""}“ nicht lesbar: JJJJ-MM-TT oder TT.MM.JJJJ`);
    else if (time && !row.time) row.note = L(`time “${time}” ignored`, `Uhrzeit „${time}“ ignoriert`);
    out.push(row); });
  return out;
}
async function importCalendar(file) {
  let evs; try { evs = parseCalendar(await file.text()); } catch (e) { evs = []; }
  if (!evs.length) { S.cal = {file: file.name, error: L("No events found. Expected a CSV with date,time,type,title (header optional) or an .ics calendar.", "Keine Ereignisse gefunden. Erwartet: CSV mit date,time,type,title (Kopfzeile optional) oder eine .ics-Datei."), rows: []}; render(true); return; }
  const ok = evs.filter(e => !e.issue); let matched = [];
  if (ok.length) { try { matched = (await post("/api/calendar", {isin: S.isin, events: ok})).events; } catch (e) { S.cal = {file: file.name, error: L("Matching failed: ", "Zuordnung fehlgeschlagen: ") + e.message, rows: []}; render(true); return; } }
  let k = 0; S.cal = {file: file.name, rows: evs.map(e => e.issue ? {...e, status: "invalid", note: e.issue} : {...matched[k++], note: [e.note, matched[k - 1] && matched[k - 1].note].filter(Boolean).join("; ")})}; S.addOpen = false; render(true);
}
function commitEvents(ok) {
  const saved = saveUserEvents(S.isin, userEvents(S.isin).filter(e => !ok.some(n => n.event_id === e.event_id)).concat(ok));
  mergeUserEvents(); S.cal = null; S.addOpen = false;
  toast(L(`${ok.length} event(s) added${saved ? "" : " for this session only"}`, `${ok.length} Ereignis(se) hinzugefügt${saved ? "" : " nur für diese Sitzung"}`));
  if (ok.length) { const e = ok[ok.length - 1]; openEvent(S.isin, e.reaction_day, e.event_id); } else render(true);
}

/* ============================== events ============================== */
document.addEventListener("click", ev => {
  if (ev.target.closest("#theme")) { setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"); return; }
  const t = ev.target.closest("[data-go],[data-open],[data-xopen],[data-act],[data-segv],[data-q],[data-do],[data-pi],[data-lang]"); if (!t || t.disabled) return;
  if (t.tagName === "A" && !t.hasAttribute("download") && !t.target) ev.preventDefault();
  if (t.dataset.lang) { setLang(t.dataset.lang); return; }
  if (t.dataset.pi !== undefined) { palRun(PL.items[+t.dataset.pi]); return; }
  if (t.dataset.go) { go(t.dataset.go, {dir: t.dataset.dir || ""}); return; }
  if (t.dataset.open) { const [day, e] = t.dataset.open.split("|"), m = t.dataset.morph ? (t.dataset.morph.startsWith(".") ? t.querySelector(t.dataset.morph) : $(t.dataset.morph)) : null; openEvent(S.isin, day, e || null, m); return; }
  if (t.dataset.xopen) { const [isin, day, e] = t.dataset.xopen.split("|"); openEvent(isin, day, e || null); return; }
  if (t.dataset.q) { ask(t.dataset.q); return; }
  if (t.dataset.do) { doAction(JSON.parse(t.dataset.do)); return; }
  if (t.dataset.segv) { const g = t.closest(".seg"), name = g.dataset.seg, v = t.dataset.segv;
    $$("button", g).forEach(b => b.setAttribute("aria-pressed", b === t)); placeThumb(g);
    if (name === "period") { setPeriod(v); return; }
    if (name === "metric") { S.metric = v; const c = $("#chart"); c.classList.remove("in"); c.innerHTML = lineChart(v); $("#read").innerHTML = chartLabel(); requestAnimationFrame(() => requestAnimationFrame(() => c.classList.add("in"))); bindChart(); }
    if (name === "tab") { S.tab = v; const k = keyOf(S.isin, S.day, S.ev); Promise.all([S.cards[k], S.briefs[k]]).then(([d, b]) => { if (!d || d.error || keyOf(S.isin, S.day, S.ev) !== k) return; const p = $("#panel"); p.innerHTML = panel(d, b); p.classList.remove("swap"); void p.offsetWidth; p.classList.add("swap"); }); }
    return; }
  const a = t.dataset.act;
  if (a === "ask") sheet(true); else if (a === "close") { sheet(false); pal(false); } else if (a === "pal") pal(true);
  else if (a === "ask-card") { sheet(true); if (!S.chat.length) ask(sugg()[0]); }
  else if (a === "regen") fillSummary(true);
  else if (a === "toreport") { S.rep.key = `${S.day}|${S.ev || ""}`; go("report"); }
  else if (a === "cmpidx") { S.cmp.index = t.dataset.index; $("#cmpbody").innerHTML = `<div class="skel" style="height:420px"></div>`; fillCompare(); }
  else if (a === "cmpthis") { S.cmp.type = t.dataset.type; S.cmp.index = ["DAX", "MDAX", "SDAX"].includes(t.dataset.index) ? t.dataset.index : "ALL"; S.cmp.data = null; go("compare"); }
  else if (a === "print") print();
  else if (a === "add") { S.addOpen = !S.addOpen; S.cal = null; render(true); }
  else if (a === "calok") commitEvents(S.cal.rows.filter(r => r.status === "matched"));
  else if (a === "calx") { S.cal = null; render(true); }
});
document.addEventListener("change", ev => {
  const el = ev.target;
  if (el.id === "calfile" && el.files[0]) { importCalendar(el.files[0]); el.value = ""; return; }
  if (el.dataset.cmp) { S.cmp[el.dataset.cmp] = el.value; $("#cmpbody").innerHTML = `<div class="skel" style="height:420px"></div>`; fillCompare(); return; }
  const k = el.dataset.rep; if (!k) return;
  if (k === "key") { S.rep.key = el.value; render(true); return; }
  S.rep[k] = el.checked; $$(`[data-blk=${k}]`).forEach(b => b.classList.toggle("off", !el.checked));
  if (el.checked && (k === "card" || k === "words")) fillReport();
});
document.addEventListener("submit", async ev => {
  ev.preventDefault(); const f = ev.target;
  if (f.id === "compose") { const q = $("#q").value.trim(); if (q && !S.busy) { $("#q").value = ""; ask(q); } }
  if (f.id === "test") { const q = $("#testq").value, k = keyOf(S.isin, S.day, S.ev), ids = Object.keys(CLAIM_RX).filter(i => CLAIM_RX[i].test(q));
    if (!ids.length) { toast(L("No check matches. Try “market”, “thin trading”, “funds sold” or “overreaction”.", "Keine Prüfung passt. Versuchen Sie „Markt“, „dünner Handel“, „Fonds“ oder „Übertreibung“.")); return; }
    S.tested[k] = ids; const [d, b] = await Promise.all([S.cards[k], S.briefs[k]]); $("#panel").innerHTML = panel(d, b);
    const el = $("#cl-" + ids[0]); el.scrollIntoView({behavior: reduced ? "auto" : "smooth", block: "center"}); ids.forEach(i => $("#cl-" + i).classList.add("hl")); }
  if (f.id === "addf") {
    try { const r = await post("/api/calendar", {isin: S.isin, events: [{date: $("#f-d").value, time: $("#f-t").value, type: $("#f-y").value, title: $("#f-n").value}]}), e = r.events[0];
      if (!e || e.status !== "matched") { toast(e ? (e.note || e.status) : L("Not added", "Nicht hinzugefügt")); return; } commitEvents([e]); } catch (err) { toast(err.message); } }
});
document.addEventListener("input", ev => { if (ev.target.id === "palq") { PL.sel = 0; palList(); } });
document.addEventListener("keydown", ev => {
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") { ev.preventDefault(); pal(!$("#pal").classList.contains("on")); return; }
  if ($("#pal").classList.contains("on")) {
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") { ev.preventDefault(); PL.sel = Math.max(0, Math.min(PL.items.length - 1, PL.sel + (ev.key === "ArrowDown" ? 1 : -1))); palList(); }
    else if (ev.key === "Enter") { ev.preventDefault(); palRun(PL.items[PL.sel]); } else if (ev.key === "Escape") pal(false); return; }
  if (ev.key === "Escape") { sheet(false); return; }
  if (ev.target.closest("input,select,textarea")) return;
  if ((ev.key === "a" || ev.key === "A") && !ev.metaKey && !ev.ctrlKey) { ev.preventDefault(); sheet(true); }
});
document.addEventListener("pointerover", ev => { const t = ev.target.closest && ev.target.closest("[data-tip]"), tip = $("#tip"); if (!t) { tip.classList.remove("on"); return; } tip.textContent = t.dataset.tip; tip.classList.add("on"); const r = t.getBoundingClientRect(); tip.style.left = Math.max(8, Math.min(innerWidth - tip.offsetWidth - 10, r.left + r.width / 2 - tip.offsetWidth / 2)) + "px"; tip.style.top = Math.max(8, r.top - tip.offsetHeight - 10) + "px"; });
addEventListener("resize", () => $$(".seg").forEach(placeThumb));
function parseHash() { const m = location.hash.match(/^#\/([A-Z]{2}[A-Z0-9]{10})\/(\w+)(?:\/(\d{4}-\d{2}-\d{2}))?(?:\/(.+))?/); return m && U(m[1]) && ROUTES.includes(m[2]) ? {isin: m[1], route: m[2], day: m[3] || null, ev: m[4] ? decodeURIComponent(m[4]) : null} : null; }
addEventListener("popstate", async () => { const h = parseHash(); if (!h || !S.iss) return;
  if (h.isin !== S.isin) await loadIssuer(h.isin);
  if (h.route === "event" && h.day) { loadCard(h.isin, h.day, h.ev); S.day = h.day; S.ev = h.ev; }
  const run = () => { S.route = h.route; render(); };
  if (document.startViewTransition && !reduced) { document.documentElement.dataset.dir = "pop"; document.startViewTransition(run).finished.catch(() => {}).finally(() => document.documentElement.dataset.dir = ""); } else run(); });

/* ============================== launch ============================== */
(async function boot() {
  try { const l = localStorage.getItem("iih.lang"); if (l === "de" || l === "en") S.lang = l; const pp = localStorage.getItem("iih.period"); if (pp) S.period = pp; } catch (e) { /* ignore */ }
  themeBtn();
  $("#spmsg").textContent = L("Reading Xetra data…", "Xetra-Daten werden gelesen…");
  try { const [uni, st] = await Promise.all([api("/api/universe"), api("/api/status")]); S.uni = uni; S.st = st; if (!periodOf(S.period).available || !PERIODS().some(p => p.key === S.period)) S.period = "ytd"; }
  catch (e) { $("#spmsg").textContent = L("The data server is not running. Start it with: python web/server.py", "Der Datenserver läuft nicht. Start: python web/server.py"); return; }
  const h = parseHash(); let isin = h ? h.isin : null;
  if (!isin) { try { const l = localStorage.getItem("iih.isin"); if (l && U(l)) isin = l; } catch (e) { /* ignore */ } }
  if (!isin) isin = (S.uni.find(u => u.ticker === "EVD") || S.uni.find(u => u.hero) || S.uni[0]).isin;
  $("#spmsg").textContent = L(`Computing ${nice(U(isin))}: trading profile, peers and unusual days`, `${nice(U(isin))}: Handelsprofil, Peers und auffällige Tage werden berechnet`);
  try { await loadIssuer(isin); } catch (e) { $("#spmsg").textContent = L("Could not load: ", "Laden fehlgeschlagen: ") + e.message; return; }
  if (h) { S.route = h.route; if (h.route === "event") { S.day = h.day || (leadDay() || {}).day; S.ev = h.ev; loadCard(isin, S.day, S.ev); } }
  render(); history.replaceState(null, "", hashFor());
  setTimeout(() => $("#splash").classList.add("done"), reduced ? 0 : 350);
})();
