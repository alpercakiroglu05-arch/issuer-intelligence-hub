/* Issuer Intelligence Hub: simple web UI.
   Every number on screen comes from the API (engine); this file only formats and draws.
   Pages: Dashboard (Part A, I-III, VI) -> Impact card (Part B, V, VI, VII) · Compare (VII) · How it works.
   Export PDF = IV / VIII. State lives in the URL (?isin=&period=&view=...), so a refresh or a shared link
   shows the same screen. */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const isN = v => typeof v === "number" && isFinite(v);

/* ---------- state + URL ---------- */
const Q = new URLSearchParams(location.search);
const S = {
  lang: Q.get("lang") === "de" ? "de" : "en", isin: Q.get("isin"), period: ["3m", "6m", "all"].includes(Q.get("period")) ? Q.get("period") : "3m",
  view: ["card", "compare", "how"].includes(Q.get("view")) ? Q.get("view") : "dash", day: Q.get("day"), ev: Q.get("ev"),
  metric: "turnover", cmp: {type: Q.get("type") || "NOTABLE_DAY", index: Q.get("index") || "ALL"},
  uni: [], status: {}, claim: null, more: false, chat: [], busy: false, addEv: false, calMsg: "",
};
const de = () => S.lang === "de";
const L = (en, d) => de() ? d : en;
function syncURL(push) {
  const q = new URLSearchParams();
  if (S.isin) q.set("isin", S.isin);
  if (S.period !== "3m") q.set("period", S.period);
  if (S.view !== "dash") q.set("view", S.view);
  if (S.view === "card" && S.day) { q.set("day", S.day); if (S.ev) q.set("ev", S.ev); }
  if (S.view === "compare") { q.set("type", S.cmp.type); q.set("index", S.cmp.index); }
  if (de()) q.set("lang", "de");
  const u = location.pathname + (q.toString() ? "?" + q : "");
  try { history[push ? "pushState" : "replaceState"](null, "", u); } catch (e) { /* offline copy opened as a file */ }
}
window.addEventListener("popstate", () => location.reload());

/* ---------- API (cached per URL) ---------- */
const CACHE = new Map();
function api(url) {
  if (!CACHE.has(url)) CACHE.set(url, fetch(url).then(async r => { const j = await r.json(); if (!r.ok) throw new Error(j.error || r.statusText); return j; }).catch(e => { CACHE.delete(url); throw e; }));
  return CACHE.get(url);
}
const post = (url, body) => fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)}).then(async r => { const j = await r.json(); if (!r.ok) throw new Error(j.error || r.statusText); return j; });

/* ---------- formatting (one place; same rules as report/fmt.py) ---------- */
const nf = (v, dec) => new Intl.NumberFormat(de() ? "de-DE" : "en-GB", {minimumFractionDigits: dec, maximumFractionDigits: dec}).format(Math.abs(v));
const sgn = (v, plus) => v < 0 ? "−" : (plus && v > 0 ? "+" : "");
const F = {
  pct: (v, dec = 1, plus = true) => !isN(v) ? "–" : sgn(v, plus) + nf(v * 100, dec) + (de() ? " %" : "%"),
  share: v => !isN(v) ? "–" : nf(v * 100, 0) + (de() ? " %" : "%"),
  x: v => !isN(v) ? "–" : de() ? nf(v, 1) + "-fach" : nf(v, 1) + "×",
  bps: v => !isN(v) ? "–" : nf(v, 1) + " bps",
  eur: v => { if (!isN(v)) return "–"; const a = Math.abs(v), [n, u] = a >= 1e9 ? [a / 1e9, L("bn", " Mrd.")] : a >= 1e6 ? [a / 1e6, L("m", " Mio.")] : [a / 1e3, L("k", " Tsd.")];
    return de() ? `${sgn(v)}${nf(n, 1)}${u} €` : `${sgn(v)}€${nf(n, 1)}${u}`; },
  px: v => !isN(v) ? "–" : (de() ? nf(v, 2) + " €" : "€" + nf(v, 2)),
  day: (d, year) => { if (!d) return "–"; const t = new Date(d + "T12:00:00"); return t.toLocaleDateString(de() ? "de-DE" : "en-GB", {day: "numeric", month: "short", ...(year ? {year: "numeric"} : {})}); },
  rank: r => r && r.rank ? L(`rank ${r.rank} of ${r.of}`, `Rang ${r.rank} von ${r.of}`) : "–",
};
const cls = v => !isN(v) || v === 0 ? "" : v < 0 ? "neg" : "pos";
const TYPES = {FY: ["Full-year results", "Jahresergebnis"], Q1: ["Q1 results", "Q1-Ergebnis"], H1: ["Half-year results", "Halbjahresergebnis"], Q3: ["Q3 results", "Q3-Ergebnis"],
  ADHOC: ["Ad hoc release", "Ad-hoc-Meldung"], GUIDANCE: ["Guidance change", "Prognoseänderung"], DIVIDEND_EX: ["Ex-dividend day", "Ex-Dividende"], AGM: ["Annual general meeting", "Hauptversammlung"],
  INDEX: ["Index change", "Indexänderung"], MA: ["Company news", "Unternehmensmeldung"], CMD: ["Capital markets day", "Kapitalmarkttag"], OTHER: ["Other news", "Sonstige Meldung"],
  UNUSUAL_DAY: ["Unusual day", "Auffälliger Tag"], NOTABLE_DAY: ["Unusual days", "Auffällige Tage"]};
const typeL = t => (TYPES[t] || [t, t])[de() ? 1 : 0];
const CTX = {index_event: ["index change", "Indexänderung"], index_change: ["index change", "Indexänderung"], quarterly_expiry: ["quarterly expiry", "großer Verfall"], monthly_expiry: ["monthly expiry", "Monatsverfall"],
  month_end_review: ["index review date", "Index-Überprüfung"], market_wide_volume: ["market-wide volume", "marktweit hoher Umsatz"]};
const ctxL = list => (list || []).map(c => (CTX[c] || [c, c])[de() ? 1 : 0]).join(" · ");
const TIMING = {post_close: ["after the close", "nach Handelsschluss"], pre_open: ["before the open", "vor Handelsbeginn"], intraday: ["during trading", "während des Handels"]};
const timingL = t => TIMING[t] ? TIMING[t][de() ? 1 : 0] : "";
const company = isin => S.uni.find(u => u.isin === isin);
const cardQS = (isin, day, ev) => { let q = `isin=${isin}&day=${day}${ev ? "&event_id=" + encodeURIComponent(ev) : ""}`; const o = ev && String(ev).startsWith("USR_") && ownEvents(isin).find(e => e.event_id === ev);
  if (o) q += `&date=${o.date}&time=${encodeURIComponent(o.time_local || "")}&type=${encodeURIComponent(o.type)}&title=${encodeURIComponent(o.title)}`; return q; };

/* ---------- own calendar (brief VI): kept in the browser, matched by the server ---------- */
const OWN = "iih.ownEvents";
function ownEvents(isin) { try { return (JSON.parse(localStorage.getItem(OWN) || "{}")[isin]) || []; } catch (e) { return []; } }
function saveOwn(isin, list) { try { const all = JSON.parse(localStorage.getItem(OWN) || "{}"); all[isin] = list; localStorage.setItem(OWN, JSON.stringify(all)); } catch (e) { /* private mode */ } }
function parseCalendar(text) {
  if (/BEGIN:VCALENDAR/i.test(text)) {
    return text.split(/BEGIN:VEVENT/i).slice(1).map(b => { const g = k => (b.match(new RegExp("^" + k + "[^:\\n]*:(.*)$", "mi")) || [])[1] || ""; const dt = g("DTSTART").trim();
      return {date: dt.slice(0, 4) + "-" + dt.slice(4, 6) + "-" + dt.slice(6, 8), time: dt.length >= 13 ? dt.slice(9, 11) + ":" + dt.slice(11, 13) : "", type: "OTHER", title: g("SUMMARY").trim()}; });
  }
  const rows = text.split(/\r?\n/).filter(l => l.trim()).map(l => l.split(/[;,](?=(?:[^"]*"[^"]*")*[^"]*$)/).map(c => c.trim().replace(/^"|"$/g, "")));
  const head = rows[0].map(h => h.toLowerCase()), has = head.includes("date"), ix = k => has ? head.indexOf(k) : ["date", "time", "type", "title"].indexOf(k);
  return rows.slice(has ? 1 : 0).map(r => ({date: r[ix("date")], time: (ix("time") >= 0 ? r[ix("time")] : "") || (ix("time_local") >= 0 ? r[ix("time_local")] : ""), type: (ix("type") >= 0 && r[ix("type")]) || "OTHER", title: (ix("title") >= 0 && r[ix("title")]) || ""}));
}
async function addOwn(events) {
  const r = await post("/api/calendar", {isin: S.isin, events});
  const ok = r.events.filter(e => e.status === "matched"), cur = ownEvents(S.isin).filter(e => !ok.some(o => o.event_id === e.event_id));
  saveOwn(S.isin, cur.concat(ok));
  S.calMsg = L(`${ok.length} of ${r.events.length} entries matched to a trading day.`, `${ok.length} von ${r.events.length} Einträgen einem Handelstag zugeordnet.`) + (r.events.length > ok.length ? " " + r.events.filter(e => e.status !== "matched").map(e => e.note).slice(0, 2).join("; ") : "");
  S.addEv = false; render();
}

/* ---------- top bar ---------- */
function topBar() {
  const c = company(S.isin), nav = [["dash", L("Dashboard", "Dashboard")], ["compare", L("Compare", "Vergleich")], ["how", L("How it works", "So funktioniert es")]];
  const exp = S.isin ? (S.view === "card" && S.day ? `/api/export?${cardQS(S.isin, S.day, S.ev)}&lang=${S.lang}` : `/api/export?isin=${S.isin}&lang=${S.lang}`) : null;
  $("#top").innerHTML = `<div class="wrap bar">
    <span class="brand">Issuer Intelligence Hub</span>
    <nav class="nav" aria-label="Main">${nav.map(([v, t]) => `<button data-go="${v}" aria-current="${(S.view === v || (v === "dash" && S.view === "card")) ? "page" : "false"}">${t}</button>`).join("")}</nav>
    <div class="picker"><input id="pick" autocomplete="off" spellcheck="false" aria-label="${L("Company", "Unternehmen")}" placeholder="${L("Search company or ticker", "Unternehmen oder Kürzel suchen")}" value="${c ? esc(c.display) + " · " + esc(c.ticker) : ""}"><ul class="sugg" id="sugg" hidden></ul></div>
    <span class="grow"></span>
    <div class="seg" role="group" aria-label="${L("Period", "Zeitraum")}">${[["3m", "3M"], ["6m", "6M"], ["all", L("All", "Alle")]].map(([v, t]) => `<button data-period="${v}" aria-pressed="${S.period === v}">${t}</button>`).join("")}</div>
    <div class="seg" role="group" aria-label="Language"><button data-lang="de" aria-pressed="${de()}">DE</button><button data-lang="en" aria-pressed="${!de()}">EN</button></div>
    <button class="btn" data-act="dock" ${S.isin ? "" : "disabled"}>${L("Ask", "Fragen")}</button>
    ${exp && !S.status.offline ? `<a class="btn primary" href="${exp}" download>${L("Export PDF", "PDF exportieren")}</a>` : `<button class="btn primary" disabled title="${S.status.offline ? L("Not in the offline copy", "Nicht in der Offline-Kopie") : ""}">${L("Export PDF", "PDF exportieren")}</button>`}
  </div>`;
  document.documentElement.lang = S.lang;
}
function suggest(q) {
  const el = $("#sugg"), t = q.trim().toLowerCase();
  const list = (t ? S.uni.filter(u => (u.display + " " + u.ticker + " " + u.isin + " " + u.name).toLowerCase().includes(t)) : S.uni).slice(0, 12);
  el.hidden = !list.length;
  el.innerHTML = list.map((u, i) => `<li role="option" data-isin="${u.isin}" aria-selected="${i === 0}" class="${u.offline_missing ? "off" : ""}"><span>${esc(u.display)} <small>${esc(u.ticker)} · ${esc(u.index)}${u.offline_missing ? " · " + L("not in the offline copy", "nicht in der Offline-Kopie") : ""}</small></span><small class="grey">${u.isin}</small></li>`).join("");
}
function choose(isin) { S.isin = isin; S.view = "dash"; S.day = S.ev = null; S.claim = null; S.chat = []; S.calMsg = ""; syncURL(true); render(); window.scrollTo(0, 0); }

/* ---------- first visit ---------- */
function firstVisit() {
  const ex = S.uni.filter(u => u.example !== null && u.example !== undefined).sort((a, b) => a.example - b.example);
  return `<div class="wrap empty"><h1>${L("How does your share trade?", "Wie handelt Ihre Aktie?")}</h1>
    <p class="sub" style="font-size:16px">${L("Pick your company. You get the normal state, the market comparison, and an impact card for every announcement.", "Wählen Sie Ihr Unternehmen. Sie sehen den Normalzustand, den Marktvergleich und eine Impact Card zu jeder Meldung.")}</p>
    <div class="chips">${ex.map(u => `<button class="chip" data-isin="${u.isin}">${esc(u.display)} · ${esc(u.index)}</button>`).join("")}</div>
    <p class="note">${L(`${S.uni.length} DAX, MDAX and SDAX shares · Xetra data to ${F.day(S.status.last_date, true)}`, `${S.uni.length} Aktien aus DAX, MDAX und SDAX · Xetra-Daten bis ${F.day(S.status.last_date, true)}`)}</p></div>`;
}

/* ---------- dashboard ---------- */
function timelineSVG(d) {
  const tl = d.timeline, n = tl.date.length, W = 1040, H = 250, ml = 56, mr = 12, mt = 26, mb = 24, pw = W - ml - mr, ph = H - mt - mb;
  const M = {turnover: ["turnover_eur", "index_turnover_eur", v => F.eur(v)], cost: ["xlm_25k", "index_xlm_25k", v => F.bps(v)], auction: ["auction_share", "index_auction_share", v => F.share(v)]}[S.metric];
  const a = tl[M[0]], b = tl[M[1]], max = Math.max(...a.filter(isN), ...b.filter(isN), 0) * 1.08 || 1;
  const x = i => ml + (i + .5) * pw / n, y = v => mt + ph - v / max * ph, bw = Math.max(1.5, pw / n * .62);
  const path = arr => arr.map((v, i) => isN(v) ? `${i && isN(arr[i - 1]) ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}` : "").join("");
  let g = [0, .5, 1].map(f => `<line x1="${ml}" x2="${W - mr}" y1="${y(max * f / 1.08)}" y2="${y(max * f / 1.08)}" stroke="#e3e6eb"/><text x="${ml - 8}" y="${y(max * f / 1.08) + 4}" text-anchor="end" font-size="11" fill="#5b6472">${f ? M[2](max * f / 1.08) : "0"}</text>`).join("");
  const step = Math.max(1, Math.round(n / 6));
  g += tl.date.map((dt, i) => i % step === 0 ? `<text x="${x(i)}" y="${H - 6}" text-anchor="middle" font-size="11" fill="#5b6472">${F.day(dt)}</text>` : "").join("");
  g += S.metric === "turnover" ? a.map((v, i) => isN(v) ? `<rect x="${(x(i) - bw / 2).toFixed(1)}" y="${y(v).toFixed(1)}" width="${bw.toFixed(1)}" height="${(mt + ph - y(v)).toFixed(1)}" fill="#c3cad5"><title>${F.day(tl.date[i], true)} · ${M[2](v)}</title></rect>` : "").join("")
    : `<path d="${path(a)}" fill="none" stroke="#1d4ed8" stroke-width="1.8"/>`;
  g += `<path d="${path(b)}" fill="none" stroke="#5b6472" stroke-width="1.2" stroke-dasharray="4 3"/>`;
  const at = new Map(tl.date.map((dt, i) => [dt, i]));
  g += d.events.concat(ownRows(d)).map(e => { const i = at.get(e.day); if (i === undefined) return ""; const X = x(i), ev = e.type !== "UNUSUAL_DAY";
    return `<g class="mk" data-card="${e.day}" data-ev="${esc(e.event_id || "")}"><title>${F.day(e.day, true)} · ${esc(typeL(e.type))}${e.title ? " · " + esc(e.title) : ""}</title><line x1="${X}" x2="${X}" y1="${mt - 8}" y2="${mt + ph}" stroke="${ev ? "#1d4ed8" : "#b4530f"}" stroke-width="1" stroke-dasharray="2 3" opacity=".6"/>${ev ? `<rect x="${X - 5}" y="${mt - 18}" width="10" height="10" fill="#1d4ed8"/>` : `<path d="M${X - 6},${mt - 8} L${X + 6},${mt - 8} L${X},${mt - 19} Z" fill="#b4530f"/>`}</g>`; }).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${L("Trading over time", "Handel im Zeitverlauf")}">${g}</svg>`;
}
const ownRows = d => ownEvents(S.isin).filter(e => e.reaction_day >= d.from && e.reaction_day <= d.to).map(e => ({day: e.reaction_day, published: e.date, time: e.time_local || null, timing: e.timing, event_id: e.event_id, type: e.type, title: e.title, own: true, context: []}));
function dashboard(d) {
  const t = d.tiles, vm = d.versus_market, idx = d.index, cc = d.cost_curve;
  const cat = d.liquidity_category === "A" ? L("Liquidity category A: no Designated Sponsor needed (estimate)", "Liquiditätskategorie A: kein Designated Sponsor nötig (Schätzung)") : L("Liquidity category B: Designated Sponsor needed (estimate)", "Liquiditätskategorie B: Designated Sponsor nötig (Schätzung)");
  const per = {"3m": L("last 3 months", "letzte 3 Monate"), "6m": L("last 6 months", "letzte 6 Monate"), all: L("since 2 Jan 2026", "seit 2. Jan. 2026")}[d.period];
  const tile = (k, v, s, c = "") => `<div class="tile"><div class="k">${k}</div><div class="v ${c}">${v}</div><div class="s">${s}</div></div>`;
  const vrow = (name, sv, iv, r) => `<tr><td>${name}</td><td class="r"><b>${sv}</b></td><td class="r">${iv}</td><td class="r">${F.rank(r)}</td></tr>`;
  const grp = Object.values(vm.groups).map(g => `<tr><td>${g.name === "10 closest by turnover" || /closest/.test(g.name) ? L(`Similar size (${g.n} closest by turnover)`, `Ähnliche Größe (${g.n} nächste nach Umsatz)`) : esc(g.name) + ` (${g.n})`}</td><td class="r">${F.eur(g.turnover_eur)}</td><td class="r">${F.bps(g.xlm_25k)}</td></tr>`).join("");
  const rows = d.events.concat(ownRows(d)).sort((a, b) => b.day.localeCompare(a.day));
  return `<div class="wrap stack">
  <section><h1>${esc(d.name)}</h1>
    <div class="meta"><span>${esc(d.ticker)} · ${esc(idx)}${d.sector ? " · " + esc(d.sector) : ""}</span><span>${cat}</span><span class="grey">${d.isin}</span></div>
    <div class="tiles">
      ${tile(L("Turnover per day", "Umsatz pro Tag"), F.eur(t.turnover_eur.stock), L(`${idx} median ${F.eur(t.turnover_eur.index)}`, `${idx}-Median ${F.eur(t.turnover_eur.index)}`))}
      ${tile(L("Trading cost, €25k order", "Handelskosten, 25-Tsd.-€-Order"), F.bps(t.xlm_25k.stock), L(`${idx} median ${F.bps(t.xlm_25k.index)}`, `${idx}-Median ${F.bps(t.xlm_25k.index)}`))}
      ${tile(L("Price", "Kurs"), F.pct(t.price.stock), L(`${idx} ${F.pct(t.price.index)}`, `${idx} ${F.pct(t.price.index)}`), cls(t.price.stock))}
      ${tile(L("Unusual days", "Auffällige Tage"), String(t.unusual_days), per)}
    </div></section>

  <section class="card"><div class="sec-h"><h2>${L("Trading over time", "Handel im Zeitverlauf")}</h2>
      <div class="seg" role="group">${[["turnover", L("Turnover", "Umsatz")], ["cost", L("Trading cost", "Handelskosten")], ["auction", L("Auction share", "Auktionsanteil")]].map(([v, x]) => `<button data-metric="${v}" aria-pressed="${S.metric === v}">${x}</button>`).join("")}</div></div>
    <div id="tchart">${timelineSVG(d)}</div>
    <p class="note">${L(`Dashed: ${idx} median. ■ announcement · ▲ unusual day: click to open the impact card.`, `Gestrichelt: ${idx}-Median. ■ Meldung · ▲ auffälliger Tag: Klick öffnet die Impact Card.`)}${S.metric === "auction" ? " " + L("Auction share: 10-day rolling median.", "Auktionsanteil: gleitender 10-Tage-Median.") : ""}${S.metric === "cost" ? " " + L("Trading cost = XLM, the round-trip cost of a €25k order in basis points.", "Handelskosten = XLM, die Kosten für Kauf und Verkauf einer 25-Tsd.-€-Order in Basispunkten.") : ""}</p></section>

  <section class="card"><div class="sec-h"><h2>${L("You vs market", "Sie und der Markt")}</h2><span class="sub">${per} · ${F.day(d.from)} – ${F.day(d.to, true)}</span></div>
    <div class="scroll"><table><thead><tr><th></th><th class="r">${esc(d.ticker)}</th><th class="r">${esc(idx)}*</th><th class="r">${L(`Rank in ${idx}`, `Rang im ${idx}`)}</th></tr></thead><tbody>
      ${vrow(L("Price performance", "Kursentwicklung"), `<span class="${cls(vm.price.stock)}">${F.pct(vm.price.stock)}</span>`, F.pct(vm.price.index), vm.price)}
      ${vrow(L("Turnover per day (median)", "Umsatz pro Tag (Median)"), F.eur(vm.turnover_eur.stock), F.eur(vm.turnover_eur.index), vm.turnover_eur)}
      ${vrow(L("Trading cost, €25k order (median)", "Handelskosten, 25-Tsd.-€-Order (Median)"), F.bps(vm.xlm_25k.stock), F.bps(vm.xlm_25k.index), vm.xlm_25k)}
    </tbody></table></div>
    <p class="note">* ${L(`Equal-weighted move or median of the other ${idx} members; not the official index level. Rank 1 = best performance, highest turnover, lowest cost.`, `Gleichgewichtete Bewegung bzw. Median der anderen ${idx}-Mitglieder; nicht der offizielle Indexstand. Rang 1 = beste Kursentwicklung, höchster Umsatz, niedrigste Kosten.`)}</p>
    <details><summary>${L("Sector, similar size and cost of larger orders", "Sektor, ähnliche Größe und Kosten größerer Orders")}</summary>
      <div class="scroll"><table style="margin-top:8px"><thead><tr><th>${L("Peer group (median)", "Vergleichsgruppe (Median)")}</th><th class="r">${L("Turnover per day", "Umsatz pro Tag")}</th><th class="r">${L("Trading cost €25k", "Handelskosten 25 Tsd. €")}</th></tr></thead><tbody>${grp}</tbody></table></div>
      ${cc ? `<p class="note">${L(`Larger orders (last 60 days): €100k costs ${F.bps(cc.cost_100k_bps)} (index peers ${F.bps(cc.peer_cost_100k_bps)}), €1m costs ${F.bps(cc.cost_1m_bps)} (${F.bps(cc.peer_cost_1m_bps)}). Largest order the book absorbs on most days: ${F.eur(cc.largest_absorbed_eur)}.`, `Größere Orders (letzte 60 Tage): 100 Tsd. € kosten ${F.bps(cc.cost_100k_bps)} (Index-Vergleich ${F.bps(cc.peer_cost_100k_bps)}), 1 Mio. € ${F.bps(cc.cost_1m_bps)} (${F.bps(cc.peer_cost_1m_bps)}). Größte Order, die das Orderbuch an den meisten Tagen aufnimmt: ${F.eur(cc.largest_absorbed_eur)}.`)}</p>` : ""}
      <p class="note">${L("Similar size uses turnover as a proxy: market capitalisation is not in the Xetra data.", "Ähnliche Größe nutzt den Umsatz als Näherung: Die Marktkapitalisierung ist nicht in den Xetra-Daten.")}</p></details></section>

  <section class="card"><div class="sec-h"><h2>${L("Big market days", "Große Markttage")}</h2><span class="sub">${L("How did your share move when the whole market moved?", "Wie bewegte sich Ihre Aktie, wenn sich der ganze Markt bewegte?")}</span></div>
    <div class="scroll"><table><thead><tr><th>${L("Day", "Tag")}</th><th class="r">${esc(idx)}*</th><th class="r">${esc(d.ticker)}</th><th class="r">${L("Difference", "Differenz")}</th><th class="r">${L("Turnover vs normal", "Umsatz vs. normal")}</th><th class="r">${L("Trading cost vs normal", "Handelskosten vs. normal")}</th><th></th></tr></thead><tbody>
    ${d.market_days.map(r => `<tr class="go" data-card="${r.date}"><td>${F.day(r.date)}${r.why === "market_wide_volume" ? ` <span class="tag">${L("market-wide volume", "marktweit hoher Umsatz")}</span>` : ""}</td><td class="r">${F.pct(r.index_ret)}</td><td class="r">${F.pct(r.ret)}</td><td class="r ${cls(r.abn_ret)}"><b>${F.pct(r.abn_ret)}</b></td><td class="r">${F.x(r.vol_ratio)}</td><td class="r">${F.x(r.xlm_ratio)}</td><td class="r"><a href="#" tabindex="-1">${L("Impact card", "Impact Card")}</a></td></tr>`).join("")}
    </tbody></table></div>
    <p class="note">${L(`The ${d.market_days.length} strongest ${idx} days of the period: largest index moves, plus days with market-wide high volume.`, `Die ${d.market_days.length} stärksten ${idx}-Tage des Zeitraums: größte Indexbewegungen sowie Tage mit marktweit hohem Umsatz.`)}</p></section>

  <section class="card"><div class="sec-h"><h2>${L("Events & unusual days", "Ereignisse & auffällige Tage")}</h2>
      ${S.status.offline ? "" : `<button class="btn small" data-act="addev">${L("Add your calendar", "Eigenen Kalender ergänzen")}</button>`}</div>
    ${S.addEv ? `<form class="form" id="evform"><input type="date" id="ev-d" required min="${d.from}" max="${d.to}" aria-label="${L("Date", "Datum")}"><input type="time" id="ev-t" aria-label="${L("Time", "Uhrzeit")}"><select id="ev-y" aria-label="${L("Type", "Typ")}">${["ADHOC", "FY", "Q1", "H1", "Q3", "GUIDANCE", "DIVIDEND_EX", "AGM", "CMD", "OTHER"].map(x => `<option value="${x}">${typeL(x)}</option>`).join("")}</select><input id="ev-n" placeholder="${L("What was announced", "Was wurde gemeldet")}" required><button class="btn primary" type="submit">${L("Add", "Hinzufügen")}</button></form>
      <p class="note">${L("Or import a file (CSV with date, time, type, title; or ICS):", "Oder Datei importieren (CSV mit date, time, type, title; oder ICS):")} <input type="file" id="ev-f" accept=".csv,.ics,text/csv,text/calendar"></p>` : ""}
    ${S.calMsg ? `<p class="note">${esc(S.calMsg)}</p>` : ""}
    <div class="scroll"><table><thead><tr><th>${L("Published", "Veröffentlicht")}</th><th>${L("What", "Was")}</th><th class="r">${L("Stock-specific move", "Titelspezifische Bewegung")}</th><th class="r">${L("Turnover vs normal", "Umsatz vs. normal")}</th><th>${L("Market context", "Marktkontext")}</th><th></th></tr></thead><tbody>
    ${rows.length ? rows.map(e => { const ev = e.type !== "UNUSUAL_DAY", next = ev && e.published && e.published !== e.day;
      return `<tr class="go" data-card="${e.day}" data-ev="${esc(e.event_id || "")}"><td style="white-space:nowrap">${F.day(ev ? e.published : e.day)}${e.time ? " · " + esc(e.time) : ""}${next ? `<div class="grey">${L("reaction", "Reaktion")} ${F.day(e.day)}</div>` : ""}</td>
        <td><span class="tag">${e.own ? L("Own · ", "Eigen · ") : ""}${esc(typeL(e.type))}</span>${e.unusual ? ` <span class="tag warn">${L("unusual", "auffällig")}</span>` : ""}<div>${ev ? esc(e.title) : `<span class="sub">${L("No announcement in the calendar; the data does not show why.", "Keine Meldung im Kalender; die Daten zeigen nicht, warum.")}</span>`}</div></td>
        <td class="r ${cls(e.abn_ret)}"><b>${e.own ? "" : F.pct(e.abn_ret)}</b></td><td class="r">${e.own ? "" : F.x(e.vol_ratio)}</td><td class="sub">${ctxL(e.context)}</td><td class="r"><a href="#" tabindex="-1">${L("Impact card", "Impact Card")}</a></td></tr>`; }).join("")
      : `<tr><td colspan="6" class="sub">${L("No announcement or unusual day in this period. Choose a longer period.", "Keine Meldung und kein auffälliger Tag in diesem Zeitraum. Längeren Zeitraum wählen.")}</td></tr>`}
    </tbody></table></div>
    <p class="note">${L("Unusual = turnover or stock-specific move far outside the share's own normal, or trading cost at twice normal. Stock-specific move = share minus the other index members.", "Auffällig = Umsatz oder titelspezifische Bewegung weit außerhalb des eigenen Normalbereichs oder doppelte Handelskosten. Titelspezifische Bewegung = Aktie minus andere Indexmitglieder.")}</p></section>
  </div>`;
}

/* ---------- impact card ---------- */
function intradaySVG(d) {
  const b = d.bars, c = d.card; if (!b || !b.ret) return `<p class="sub">${L("No minute data for this share: the card uses daily data.", "Keine Minutendaten für diese Aktie: Die Karte nutzt Tagesdaten.")}</p>`;
  const W = 1040, H = 300, ml = 52, mr = 16, mt = 18, ph = 190, vh = 52, vy = mt + ph + 14 + vh, min = t => (+t.slice(0, 2)) * 60 + (+t.slice(3)) - 540, T = 520;
  const x = t => ml + Math.max(0, Math.min(T, min(t))) / T * (W - ml - mr);
  const rs = b.ret.filter(isN), lo = Math.min(0, ...rs), hi = Math.max(0, ...rs), pad = (hi - lo) * .08 || .01, y = v => mt + (hi + pad - v) / (hi - lo + 2 * pad) * ph;
  const vmax = Math.max(...b.eur.filter(isN), 1);
  let g = `<line x1="${ml}" x2="${W - mr}" y1="${y(0)}" y2="${y(0)}" stroke="#9aa3af"/><text x="${ml - 8}" y="${y(0) + 4}" text-anchor="end" font-size="11" fill="#5b6472">0</text>`;
  [lo, hi].filter(v => Math.abs(v) > .004).forEach(v => { g += `<text x="${ml - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="#5b6472">${F.pct(v, 0)}</text>`; });
  ["09:00", "11:00", "13:00", "15:00", "17:00"].forEach(t => { g += `<text x="${x(t)}" y="${H - 4}" text-anchor="middle" font-size="11" fill="#5b6472">${t}</text>`; });
  g += b.t.map((t, i) => isN(b.eur[i]) && b.eur[i] > 0 ? `<rect x="${(x(t) - 1).toFixed(1)}" y="${(vy - b.eur[i] / vmax * vh).toFixed(1)}" width="2" height="${(b.eur[i] / vmax * vh).toFixed(1)}" fill="${b.auction[i] ? "#1d4ed8" : "#c3cad5"}"/>` : "").join("");
  let p = "", pen = false; b.t.forEach((t, i) => { if (isN(b.ret[i]) && min(t) >= 0 && min(t) <= T) { p += `${pen ? "L" : "M"}${x(t).toFixed(1)},${y(b.ret[i]).toFixed(1)}`; pen = true; } });
  g += `<path d="${p}" fill="none" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/>`;
  const on = c.intraday && c.intraday.onset && c.intraday.onset.time;
  if (on) g += `<line x1="${x(on)}" x2="${x(on)}" y1="${mt}" y2="${vy}" stroke="#b4530f" stroke-width="1.4" stroke-dasharray="4 3"/><text x="${x(on) + 8}" y="${mt + 12}" font-size="12" font-weight="600" fill="#8a3b08">${L("Reaction in trading from", "Reaktion im Handel ab")} ${on}</text>`;
  g += `<text x="${W - mr}" y="${vy - vh - 4}" text-anchor="end" font-size="11" fill="#5b6472">${L("Turnover per minute · blue = auctions", "Umsatz pro Minute · blau = Auktionen")}</text>`;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${L("Price against the previous close, minute by minute", "Kurs gegenüber dem Vortagesschluss, Minute für Minute")}">${g}</svg>`;
}
function cardView(d, ev) {
  const c = d.card, p = c.price, v = c.volume, l = c.liquidity, a = c.auctions || {}, pa = c.participants || {}, e = c.event, cm = c.comparison, rk = d.rank && d.rank[S.lang];
  const isEv = e.type !== "NOTABLE_DAY", pub = e.datetime_local;
  const tile = (k, val, s, cl = "") => `<div class="tile"><div class="k">${k}</div><div class="v ${cl}">${val}</div><div class="s">${s}</div></div>`;
  const b = ev && !ev.error ? ev[S.lang] : null;
  const first = b ? b.sections.filter(s => ["market", "trading", "unknown"].includes(s.key)).map(s => `<li><b>${esc(s.title)}:</b> ${esc(s.points[0])}</li>`).join("") : "";
  const all = b ? b.sections.map(s => `<p style="margin-top:10px"><b>${esc(s.title)}</b></p><ul style="margin:4px 0 0;padding-left:18px">${s.points.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`).join("") : "";
  const VL = {supported: L("Consistent with the data", "Mit den Daten vereinbar"), contradicted: L("Not supported by the data", "Von den Daten nicht gestützt"), partly: L("Partly", "Teilweise"), not_testable: L("The data cannot tell", "Aus den Daten nicht ablesbar")};
  const cl = b && S.claim && b.claims[S.claim];
  return `<div class="wrap stack">
  <a class="back" href="#" data-go="dash">← ${L("Dashboard", "Dashboard")} · ${esc(c.name)}</a>
  <section><div class="meta" style="margin:0 0 6px"><span class="tag">${esc(typeL(isEv ? e.type : "UNUSUAL_DAY"))}</span>
      ${isEv && pub ? `<span>${L("Published", "Veröffentlicht")} <b>${F.day(pub.slice(0, 10), true)}${pub.length > 10 ? ", " + pub.slice(11, 16) : ""}</b>${timingL(e.timing) ? " (" + timingL(e.timing) + ")" : ""}</span>` : ""}
      <span>${L("Trading day", "Handelstag")} <b>${F.day(e.reaction_day, true)}</b></span>
      ${e.source_url ? `<a href="${esc(e.source_url)}" target="_blank" rel="noopener">${L("Source", "Quelle")} ↗</a>` : ""}</div>
    <h1>${isEv ? esc(e.title) : L("Unusual trading day", "Auffälliger Handelstag")}</h1>
    <div class="tiles">
      ${tile(L("Stock-specific move", "Titelspezifische Bewegung"), F.pct(p.abn_ret), L(`share ${F.pct(p.ret)} · ${c.index} ${F.pct(p.peer_ret)}`, `Aktie ${F.pct(p.ret)} · ${c.index} ${F.pct(p.peer_ret)}`), cls(p.abn_ret))}
      ${tile(L("Turnover", "Umsatz"), F.x(v.ratio), L(`${F.eur(v.turnover_eur)} · normal ${F.eur(v.baseline_eur)}`, `${F.eur(v.turnover_eur)} · normal ${F.eur(v.baseline_eur)}`))}
      ${tile(L("Trading cost, €25k order", "Handelskosten, 25-Tsd.-€-Order"), isN(l.ratio) ? F.x(l.ratio) : "–", isN(l.xlm_25k_bps) ? `${F.bps(l.xlm_25k_bps)} · normal ${F.bps(l.xlm_25k_baseline_bps)}` : L("no XLM for this day", "kein XLM für diesen Tag"))}
      ${tile(L("How it ranks", "Einordnung"), cm && cm.rank_abs_abn_ret ? L(`${cm.rank_abs_abn_ret} of ${cm.rank_of || cm.n + 1}`, `${cm.rank_abs_abn_ret} von ${cm.rank_of || cm.n + 1}`) : "–", rk ? esc(rk.group) + L(" · this day included", " · inkl. dieses Tages") + ` · <a href="#" data-act="cmp">${L("see all", "alle ansehen")}</a>` : L("no comparison group", "keine Vergleichsgruppe"))}
    </div></section>

  <section class="card"><div class="sec-h"><h2>${L("The day, minute by minute", "Der Tag, Minute für Minute")}</h2><span class="sub">${L("price vs previous close", "Kurs gegenüber Vortagesschluss")}</span></div>${intradaySVG(d)}</section>

  <div class="two">
    <section class="card"><h2 style="margin-bottom:8px">${L("Auctions", "Auktionen")}</h2>
      <div class="kv"><span>${L("Opening auction turnover", "Umsatz Eröffnungsauktion")}</span><b>${F.eur(a.open_auction_eur)} · ${F.x(a.open_auction_ratio)}</b></div>
      <div class="kv"><span>${L("Opening price vs previous close", "Eröffnungskurs vs. Vortagesschluss")}</span><b>${F.pct(a.open_auction_move)} <span class="sub">(${L("typical", "üblich")} ±${F.pct(a.open_auction_move_baseline_abs, 1, false)})</span></b></div>
      <div class="kv"><span>${L("Closing auction turnover", "Umsatz Schlussauktion")}</span><b>${F.eur(a.close_auction_eur)} · ${F.x(a.close_auction_ratio)}</b></div>
      <div class="kv"><span>${L("Closing price vs last trade", "Schlusskurs vs. letzter Handel")}</span><b>${F.pct(a.close_auction_move)} <span class="sub">(${L("typical", "üblich")} ±${F.pct(a.close_auction_move_baseline_abs, 1, false)})</span></b></div></section>
    <section class="card"><h2 style="margin-bottom:8px">${L("Who traded", "Wer handelte")}</h2>
      <div class="kv"><span>${L("Client orders (via brokers)", "Kundenorders (über Broker)")}</span><b>${F.share(pa.agent_share)} <span class="sub">(normal ${F.share(pa.agent_share_baseline)})</span></b></div>
      <div class="kv"><span>${L("Client net flow", "Netto-Fluss der Kundenorders")}</span><b>${isN(pa.agent_aggr_net_eur) ? (pa.agent_aggr_net_eur < 0 ? L("net selling ", "Netto-Verkauf ") : L("net buying ", "Netto-Kauf ")) + F.eur(Math.abs(pa.agent_aggr_net_eur)) : "–"}</b></div>
      <div class="kv"><span>${L("Proprietary traders", "Eigenhandel")}</span><b>${F.share(pa.prop_share)}</b></div>
      <div class="kv"><span>${L("Market makers", "Market Maker")}</span><b>${F.share(pa.mm_share)}</b></div>
      <p class="note">${L("Xetra flows show these three groups only; they do not identify funds or retail investors.", "Xetra-Flüsse zeigen nur diese drei Gruppen; sie identifizieren weder Fonds noch Privatanleger.")}</p></section>
  </div>

  <section class="card"><h2 style="margin-bottom:8px">${L("Summary", "Zusammenfassung")}</h2><div id="ai"><div class="skel"></div><div class="skel" style="width:80%"></div></div></section>

  <section class="card"><h2 style="margin-bottom:8px">${L("Evidence", "Belege")}</h2>
    ${b ? `<p><b>${esc(b.headline)}</b></p><ul style="margin:8px 0 0;padding-left:18px">${first}</ul><details ${S.more ? "open" : ""}><summary>${L("Show every point", "Alle Punkte zeigen")}</summary>${all}</details>` : ev && ev.error ? `<p class="sub">${esc(ev.error)}</p>` : `<div class="skel"></div><div class="skel" style="width:70%"></div>`}</section>

  <section class="card"><div class="sec-h"><h2>${L("Test an explanation", "Eine Erklärung prüfen")}</h2><span class="sub">${L("Fixed rules on the figures above; no language model.", "Feste Regeln auf den Zahlen oben; kein Sprachmodell.")}</span></div>
    ${b ? `<div class="claims">${Object.entries(b.claims).map(([k, x]) => `<button class="chip" data-claim="${k}" aria-pressed="${S.claim === k}">${esc(x.label)}</button>`).join("")}</div>
      ${cl ? `<div class="verdict"><b class="v">${VL[cl.verdict] || cl.verdict}.</b>${esc(cl.text)}${cl.better ? `<p class="note" style="margin-top:8px"><b>${L("Wording the data supports:", "Formulierung, die die Daten stützen:")}</b> ${esc(cl.better)}</p>` : ""}</div>` : ""}` : `<div class="skel"></div>`}</section>

  <p class="note">${L(`Normal = median of the ${c.baseline.days_used} trading days ending a week before the day. The reaction time is read from trades (price beyond 2 standard deviations and turnover 3 times normal for the time of day); it is not the publication time.`, `Normal = Median der ${c.baseline.days_used} Handelstage bis eine Woche vor dem Tag. Die Reaktionszeit wird aus dem Handel gelesen (Kurs jenseits von 2 Standardabweichungen und 3-facher Umsatz für die Tageszeit); sie ist nicht die Veröffentlichungszeit.`)}</p>
  </div>`;
}
async function loadSummary(key) {
  let h;
  try { const m = await post("/api/narrate", {isin: S.isin, day: S.day, event_id: S.ev, lang: S.lang});
    h = `<p>${esc(m.text)}</p><p class="note">${m.source === "llm" ? L("Written by a language model from the card's numbers only; every figure and the share's own move were checked against the card.", "Von einem Sprachmodell nur aus den Zahlen der Karte geschrieben; jede Zahl und die Bewegung der Aktie wurden mit der Karte abgeglichen.") : L("Fixed template text (no model text is shown for this card).", "Fester Vorlagentext (für diese Karte wird kein Modelltext gezeigt).")}</p>`;
  } catch (e) { h = `<p class="sub">${L("The summary is not available right now; all figures above are complete.", "Die Zusammenfassung ist gerade nicht verfügbar; alle Zahlen oben sind vollständig.")}</p>`; }
  if (S.view === "card" && key === S.day + "|" + (S.ev || "") + "|" + S.lang && $("#ai")) $("#ai").innerHTML = h;
}
function openCard(day, ev) { S.view = "card"; S.day = day; S.ev = ev || null; S.claim = null; S.more = false; syncURL(true); render(); window.scrollTo(0, 0); }

/* ---------- compare ---------- */
function compareView(t) {
  const types = (t.types || []).filter(x => x !== "INDEX" || true), mine = t.rows.filter(r => r.isin === S.isin), top = t.rows.slice(0, 15), sel = S.day && mine.find(r => String(r.reaction_day).slice(0, 10) === S.day);
  const show = top.concat(mine.filter(r => r.rank > 15)), nm = company(S.isin);
  const W = 1040, H = 240, ml = 52, mr = 14, mt = 12, mb = 26, xs = v => ml + (Math.log(Math.max(.3, Math.min(60, v))) - Math.log(.3)) / (Math.log(60) - Math.log(.3)) * (W - ml - mr);
  const amax = Math.max(.05, ...t.rows.map(r => Math.abs(r.abn_ret || 0))), ys = v => mt + (amax - v) / (2 * amax) * (H - mt - mb);
  const dots = t.rows.filter(r => isN(r.vol_ratio) && isN(r.abn_ret)).map(r => { const me = r.isin === S.isin; return `<circle cx="${xs(r.vol_ratio).toFixed(1)}" cy="${ys(r.abn_ret).toFixed(1)}" r="${me ? 5 : 3}" fill="${me ? "#1d4ed8" : "#c3cad5"}" ${me ? "" : 'opacity=".7"'}><title>${esc(r.display)} · ${F.day(String(r.reaction_day).slice(0, 10), true)} · ${F.pct(r.abn_ret)} · ${F.x(r.vol_ratio)}</title></circle>`; });
  return `<div class="wrap stack"><section><h1>${L("Compare events", "Ereignisse vergleichen")}</h1><p class="sub">${L("Every event of the same type in 2026, measured exactly like the impact card.", "Alle Ereignisse desselben Typs 2026, gemessen genau wie die Impact Card.")}</p></section>
  <section class="card"><div class="sec-h"><div style="display:flex;gap:8px;flex-wrap:wrap"><select class="field" id="cmp-type" aria-label="${L("Event type", "Ereignistyp")}">${types.map(x => `<option value="${x}" ${x === t.type ? "selected" : ""}>${esc(typeL(x))}</option>`).join("")}</select>
      <select class="field" id="cmp-index" aria-label="Index">${["ALL", "DAX", "MDAX", "SDAX"].map(x => `<option value="${x}" ${x === t.index ? "selected" : ""}>${x === "ALL" ? L("DAX, MDAX and SDAX", "DAX, MDAX und SDAX") : x}</option>`).join("")}</select></div>
      <span class="sub">${t.n} ${L("events", "Ereignisse")}${sel ? " · " + L(`${esc(nm ? nm.display : "")} on ${F.day(S.day)}: rank ${sel.rank} of ${t.n}`, `${esc(nm ? nm.display : "")} am ${F.day(S.day)}: Rang ${sel.rank} von ${t.n}`) : ""}</span></div>
    <svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${L("Stock-specific move against turnover vs normal", "Titelspezifische Bewegung gegen Umsatz vs. normal")}"><line x1="${ml}" x2="${W - mr}" y1="${ys(0)}" y2="${ys(0)}" stroke="#9aa3af"/>
      ${[1, 3, 10, 30].map(v => `<text x="${xs(v)}" y="${H - 6}" text-anchor="middle" font-size="11" fill="#5b6472">${F.x(v)}</text>`).join("")}<text x="${ml - 8}" y="${ys(amax) + 10}" text-anchor="end" font-size="11" fill="#5b6472">${F.pct(amax, 0)}</text><text x="${ml - 8}" y="${ys(-amax)}" text-anchor="end" font-size="11" fill="#5b6472">${F.pct(-amax, 0)}</text>${dots.join("")}</svg>
    <p class="note">${L("Across: turnover vs normal (log scale). Up/down: stock-specific move. Blue: this company.", "Waagerecht: Umsatz vs. normal (logarithmisch). Senkrecht: titelspezifische Bewegung. Blau: dieses Unternehmen.")}</p>
    <div class="scroll"><table><thead><tr><th>#</th><th>${L("Company", "Unternehmen")}</th><th>${L("Trading day", "Handelstag")}</th><th class="r">${L("Stock-specific move", "Titelspezifische Bewegung")}</th><th class="r">${L("Turnover vs normal", "Umsatz vs. normal")}</th></tr></thead><tbody>
    ${show.map(r => `<tr class="go" data-open="${r.isin}|${String(r.reaction_day).slice(0, 10)}|${esc(r.event_id || "")}" ${r.isin === S.isin ? 'style="background:#f3f6fe"' : ""}><td>${r.rank}</td><td>${esc(r.display)}${r.title && t.type !== "NOTABLE_DAY" ? `<div class="sub">${esc(String(r.title).slice(0, 80))}</div>` : ""}</td><td>${F.day(String(r.reaction_day).slice(0, 10), true)}</td><td class="r ${cls(r.abn_ret)}"><b>${F.pct(r.abn_ret)}</b></td><td class="r">${F.x(r.vol_ratio)}</td></tr>`).join("")}
    </tbody></table></div><p class="note">${L("Ranked by the size of the stock-specific move. Top 15, plus this company's own events.", "Sortiert nach Größe der titelspezifischen Bewegung. Top 15 sowie die eigenen Ereignisse dieses Unternehmens.")}</p></section></div>`;
}

/* ---------- how it works ---------- */
function howView() {
  const steps = [[L("1 · Deutsche Börse trading data", "1 · Handelsdaten der Deutschen Börse"), L("Xetra prices, auctions, turnover by participant type, trading cost (XLM) and every single trade.", "Xetra-Kurse, Auktionen, Umsatz nach Teilnehmertyp, Handelskosten (XLM) und jeder einzelne Trade.")],
    [L("2 · What is normal", "2 · Was normal ist"), L("A 60-day baseline for your share, and the same figures for index, sector and similar-size peers.", "Eine 60-Tage-Basis für Ihre Aktie und dieselben Zahlen für Index, Sektor und ähnlich große Titel.")],
    [L("3 · Announcements meet trading", "3 · Meldungen treffen Handel"), L("Each announcement is matched to its trading day and to the minute trading reacted.", "Jede Meldung wird ihrem Handelstag und der Minute zugeordnet, in der der Handel reagierte.")],
    [L("4 · Impact card", "4 · Impact Card"), L("All numbers come from code. The AI only writes the text, and the text is checked against the numbers.", "Alle Zahlen kommen aus Code. Die KI schreibt nur den Text, und der Text wird mit den Zahlen abgeglichen.")]];
  const cannot = [L("Why a share moved. Causes come only from announcements with a source.", "Warum sich eine Aktie bewegte. Ursachen kommen nur aus Meldungen mit Quelle."), L("Who bought or sold. The data separates client orders, proprietary traders and market makers, nothing finer.", "Wer kaufte oder verkaufte. Die Daten trennen Kundenorders, Eigenhandel und Market Maker, nicht feiner."), L("Trading outside the Xetra order book.", "Handel außerhalb des Xetra-Orderbuchs.")];
  const ideas = [[L("Index early warning", "Index-Frühwarnung"), L("See an index exit coming months ahead.", "Einen Indexabstieg Monate vorher erkennen."), L("free-float market cap, official ranking lists", "Streubesitz-Marktkapitalisierung, offizielle Ranglisten")],
    [L("Designated Sponsor monitor", "Designated-Sponsor-Monitor"), L("Does the sponsor deliver the quote quality agreed?", "Liefert der Sponsor die vereinbarte Quotierungsqualität?"), L("quotes per Designated Sponsor", "Quotes je Designated Sponsor")],
    [L("Block trades and placements", "Blocktrades und Platzierungen"), L("What traded off the order book around an event.", "Was rund um ein Ereignis außerhalb des Orderbuchs gehandelt wurde."), L("Xetra off-book trades (TES)", "Xetra-Off-Book-Trades (TES)")],
    [L("Surprise vs consensus", "Überraschung vs. Konsens"), L("Separate the figures from the expectations.", "Die Zahlen von den Erwartungen trennen."), L("analyst consensus estimates", "Analysten-Konsensschätzungen")],
    [L("Announcement planner", "Meldungsplaner"), L("Compare reactions by publication time for the same event type.", "Reaktionen nach Veröffentlichungszeit für denselben Ereignistyp vergleichen."), L("more events with exact times", "mehr Ereignisse mit exakter Uhrzeit")],
    [L("Derivatives positioning", "Derivate-Positionierung"), L("How the market was positioned before an event.", "Wie der Markt vor einem Ereignis positioniert war."), L("uncensored Eurex open interest by participant", "unzensiertes Eurex Open Interest nach Teilnehmer")]];
  return `<div class="wrap stack"><section><h1>${L("How it works", "So funktioniert es")}</h1></section>
    <div class="steps">${steps.map(([h, p]) => `<div class="card step"><b>${h}</b>${p}</div>`).join("")}</div>
    <section class="card"><h2 style="margin-bottom:8px">${L("What the data cannot say", "Was die Daten nicht sagen können")}</h2><ul style="margin:0;padding-left:18px">${cannot.map(x => `<li>${x}</li>`).join("")}</ul></section>
    <section><h2 style="margin-bottom:10px">${L("What else IR needs, and the data it takes", "Was IR noch braucht, und welche Daten dafür nötig sind")}</h2>
      <div class="ideas">${ideas.map(([h, p, n]) => `<div class="card"><b>${h}</b><p>${p}</p><p class="note">${L("Needs: ", "Braucht: ")}${n}</p></div>`).join("")}</div></section></div>`;
}

/* ---------- assistant ---------- */
function dock() {
  const el = $("#dock"); if (el.hidden) return;
  const sug = S.view === "card" ? [L("Was this the market, or company-specific?", "War das der Markt oder unternehmensspezifisch?"), L("Explain this card in two sentences", "Erklären Sie diese Karte in zwei Sätzen"), L("How does this rank against similar events?", "Wie ordnet sich das gegenüber ähnlichen Ereignissen ein?")]
    : [L("Has our liquidity improved?", "Hat sich unsere Liquidität verbessert?"), L("How do our spreads compare with our sector?", "Wie sind unsere Spreads im Sektorvergleich?"), L("What were our biggest moves this year?", "Was waren unsere größten Bewegungen dieses Jahr?")];
  el.innerHTML = `<div class="dock-h"><span>${L("Ask about", "Fragen zu")} ${esc((company(S.isin) || {}).display || "")}</span><button class="btn small" data-act="dock">${L("Close", "Schließen")}</button></div>
    <div class="dock-b">${S.chat.length ? S.chat.map(m => m.role === "user" ? `<div class="msg q">${esc(m.content)}</div>` : `<div class="msg">${esc(m.content)}${(m.actions || []).filter(a => a.day).map(a => `<div style="margin-top:8px"><button class="btn small" data-card="${a.day}" data-ev="${esc(a.event_id || "")}">${L("Open impact card", "Impact Card öffnen")} · ${F.day(a.day)}</button></div>`).join("")}<div class="note">${m.source === "llm" ? L("Model answer; every figure checked against the engine.", "Modellantwort; jede Zahl mit der Engine abgeglichen.") : L("Fixed answer from the engine.", "Feste Antwort aus der Engine.")}</div></div>`).join("") : `<div class="chips">${sug.map(q => `<button class="chip" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div>`}
      ${S.busy ? `<div class="msg sub">${L("Working…", "Arbeitet…")}</div>` : ""}</div>
    <form class="dock-f" id="dockf"><input id="dockq" placeholder="${S.status.offline ? L("Offline copy: suggested questions only", "Offline-Kopie: nur vorgeschlagene Fragen") : L("Your question", "Ihre Frage")}" ${S.busy ? "disabled" : ""}><button class="btn primary" ${S.busy ? "disabled" : ""}>${L("Ask", "Fragen")}</button></form>`;
  const bd = $(".dock-b", el); bd.scrollTop = bd.scrollHeight;
}
async function ask(q) {
  if (S.busy || !q.trim()) return;
  const history = S.chat.map(m => ({role: m.role, content: m.content})), ctx = S.view === "card" ? {page: "card", day: S.day, event_id: S.ev} : {page: "dashboard"};
  S.chat.push({role: "user", content: q}); S.busy = true; dock();
  try { const r = await post("/api/agent", {isin: S.isin, question: q, history, context: ctx, lang: S.lang}); S.chat.push({role: "assistant", content: r.text, source: r.source, actions: r.actions}); }
  catch (e) { S.chat.push({role: "assistant", content: L("No answer right now. The figures on the page are complete.", "Gerade keine Antwort. Die Zahlen auf der Seite sind vollständig."), source: "template"}); }
  S.busy = false; dock();
}

/* ---------- render ---------- */
let SEQ = 0, CARD = null;
async function render() {
  const seq = ++SEQ, main = $("#main");
  topBar(); dock();
  const fail = e => { if (seq === SEQ) main.innerHTML = `<div class="wrap empty"><h2>${L("This could not be loaded.", "Das konnte nicht geladen werden.")}</h2><p class="sub">${esc(e.message)}</p><p style="margin-top:14px"><button class="btn" data-go="dash">${L("Back to the dashboard", "Zurück zum Dashboard")}</button></p></div>`; };
  if (S.view === "how") { main.innerHTML = howView(); return; }
  if (!S.isin || !company(S.isin)) { S.isin = null; main.innerHTML = firstVisit(); const p = $("#pick"); if (p) p.focus(); return; }
  try {
    if (S.view === "dash") {
      const d = await api(`/api/dashboard?isin=${S.isin}&period=${S.period}`); if (seq !== SEQ) return;
      main.innerHTML = dashboard(d);
      d.events.slice(0, 4).forEach(e => { api(`/api/card?${cardQS(S.isin, e.day, e.event_id)}`).catch(() => {}); api(`/api/evidence?${cardQS(S.isin, e.day, e.event_id)}`).catch(() => {}); });  // prefetch the top rows
    } else if (S.view === "card") {
      const qs = cardQS(S.isin, S.day, S.ev), key = S.day + "|" + (S.ev || "") + "|" + S.lang, t0 = performance.now();
      const d = await api(`/api/card?${qs}`); if (seq !== SEQ) return;
      CARD = d.card; main.innerHTML = cardView(d, null); window.__cardMs = Math.round(performance.now() - t0);   // numbers first
      loadSummary(key);
      const ev = await api(`/api/evidence?${qs}`).catch(e => ({error: e.message})); if (seq !== SEQ) return;
      const ai = $("#ai") ? $("#ai").innerHTML : null; main.innerHTML = cardView(d, ev); if (ai && $("#ai")) $("#ai").innerHTML = ai;
    } else if (S.view === "compare") {
      const t = await api(`/api/compare?type=${S.cmp.type}${S.cmp.index !== "ALL" ? "&index=" + S.cmp.index : ""}`); if (seq !== SEQ) return;
      main.innerHTML = compareView(t);
    }
  } catch (e) { fail(e); }
}

/* ---------- events ---------- */
document.addEventListener("click", ev => {
  const t = ev.target.closest("[data-go],[data-isin],[data-period],[data-lang],[data-metric],[data-card],[data-claim],[data-act],[data-q],[data-open]");
  if (!ev.target.closest(".picker")) { const s = $("#sugg"); if (s) s.hidden = true; }
  if (!t) return;
  const d = t.dataset;
  if (d.go) { ev.preventDefault(); S.view = d.go; if (d.go === "compare" && !S.cmp.type) S.cmp.type = "NOTABLE_DAY"; syncURL(true); render(); window.scrollTo(0, 0); }
  else if (d.isin) choose(d.isin);
  else if (d.period) { S.period = d.period; syncURL(); render(); }
  else if (d.lang) { S.lang = d.lang; syncURL(); render(); }
  else if (d.metric) { S.metric = d.metric; render(); }
  else if (d.card) { ev.preventDefault(); openCard(d.card, d.ev); }
  else if (d.claim) { S.claim = S.claim === d.claim ? null : d.claim; S.more = !!($("details[open]")); const y = window.scrollY; render().then(() => window.scrollTo(0, y)); }
  else if (d.q) ask(d.q);
  else if (d.open) { const [isin, day, e] = d.open.split("|"); S.isin = isin; openCard(day, e); }
  else if (d.act === "dock") { $("#dock").hidden = !$("#dock").hidden; dock(); const q = $("#dockq"); if (q) q.focus(); }
  else if (d.act === "cmp") { ev.preventDefault(); const cm = (CARD || {}).comparison || {}; S.cmp.type = cm.group_type || "NOTABLE_DAY"; S.cmp.index = ["DAX", "MDAX", "SDAX"].includes(cm.group_index) ? cm.group_index : "ALL"; S.view = "compare"; syncURL(true); render(); window.scrollTo(0, 0); }
  else if (d.act === "addev") { S.addEv = !S.addEv; S.calMsg = ""; render(); }
});
document.addEventListener("input", ev => { if (ev.target.id === "pick") suggest(ev.target.value); });
document.addEventListener("focusin", ev => { if (ev.target.id === "pick") { ev.target.select(); suggest(""); } });
document.addEventListener("keydown", ev => {
  if (ev.target.id !== "pick") return;
  const items = [...document.querySelectorAll("#sugg li")], i = items.findIndex(x => x.getAttribute("aria-selected") === "true");
  if (ev.key === "ArrowDown" || ev.key === "ArrowUp") { ev.preventDefault(); const j = Math.max(0, Math.min(items.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1))); items.forEach((x, k) => x.setAttribute("aria-selected", k === j)); items[j] && items[j].scrollIntoView({block: "nearest"}); }
  else if (ev.key === "Enter" && items[i]) { ev.preventDefault(); choose(items[i].dataset.isin); }
  else if (ev.key === "Escape") { $("#sugg").hidden = true; ev.target.blur(); }
});
document.addEventListener("change", ev => {
  if (ev.target.id === "cmp-type" || ev.target.id === "cmp-index") { S.cmp.type = $("#cmp-type").value; S.cmp.index = $("#cmp-index").value; syncURL(); render(); }
  if (ev.target.id === "ev-f" && ev.target.files[0]) ev.target.files[0].text().then(tx => addOwn(parseCalendar(tx))).catch(e => { S.calMsg = e.message; render(); });
});
document.addEventListener("submit", ev => {
  ev.preventDefault();
  if (ev.target.id === "dockf") { const q = $("#dockq").value; $("#dockq").value = ""; ask(q); }
  if (ev.target.id === "evform") addOwn([{date: $("#ev-d").value, time: $("#ev-t").value, type: $("#ev-y").value, title: $("#ev-n").value}]).catch(e => { S.calMsg = e.message; render(); });
});

/* ---------- start ---------- */
(async function start() {
  try { [S.uni, S.status] = await Promise.all([api("/api/universe"), api("/api/status")]); }
  catch (e) { $("#main").innerHTML = `<div class="wrap empty"><h2>The data service is not reachable.</h2><p class="sub">${esc(e.message)}</p><p style="margin-top:14px"><button class="btn" onclick="location.reload()">Retry</button></p></div>`; return; }
  S.uni.forEach(u => { u.display = u.display || u.name; });
  render();
})();
