#!/usr/bin/env python3
"""
Offline snapshot of the web front end: ONE self-contained .html file to share with people who do not run the
server (teammates, mentors, the jury). It opens with a double click, no Python, no data folder.

    python web/snapshot.py                      # -> ~/Desktop/Issuer-Intelligence-Hub.html (showcase shares)
    python web/snapshot.py --tickers EVD HDD    # other shares
    python web/snapshot.py --llm                # AI texts from the language model in .env (slower), not templates

What is inside: the page (index.html + app.css + app.js inlined) and the JSON answers of every API call the demo
makes for the chosen shares: dashboard, every impact card (calendar events and unusual days), comparisons,
AI summaries (EN/DE) and the analyst's suggested questions. A small fetch() shim answers from that JSON.
Not inside: other shares, typed analyst questions and the own-calendar import (they need the live server).

The file contains processed Deutsche Boerse data: share it inside the team only, never commit it.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
sys.path.insert(0, str(ROOT))


def load_server(llm: bool):
    if not llm:
        os.environ["LLM_PROVIDER"] = "none"
    spec = importlib.util.spec_from_file_location("web_server_snapshot", WEB / "server.py")
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)
    return srv


def suggestions() -> dict:
    """The analyst's suggested questions per page, read from app.js so the keys always match the UI."""
    js = (WEB / "app.js").read_text(encoding="utf-8")
    body = js[js.index("function dockSugg()"):js.index("function dockMsg(")]
    pages = {}
    for page, block in re.findall(r"(card|compare|report):\s*\[(.*?)\]", body, flags=re.S):
        pages[page] = re.findall(r'L\("([^"]+)",\s*"([^"]+)"\)', block)
    default = body[body.index("||"):]
    pages["dashboard"] = re.findall(r'L\("([^"]+)",\s*"([^"]+)"\)', default)
    return pages


def build(tickers, llm: bool, out: Path):
    srv = load_server(llm)
    from engine import compare, data

    t0 = time.time()
    isins = [data.isin_of(t) for t in tickers]
    snap = {}
    uni = [u for u in srv.universe() if u["isin"] in isins]
    status = {**srv.clean({"stocks": len(uni), "intraday_stocks": len(uni), "llm": bool(llm and srv.llm_available()),
                           "model": srv.llm_model() if llm else None,
                           "last_date": str(data.daily()["date"].max().date())}), "offline": True}
    snap["/api/status"], snap["/api/universe"] = status, uni
    sugg = suggestions()
    types = compare.event_types()
    for t in types:
        for idx in ("ALL", "DAX", "MDAX", "SDAX"):
            snap[f"/api/compare?type={t}" + (f"&index={idx}" if idx != "ALL" else "")] = srv.compare_table(t, None if idx == "ALL" else idx)
    for isin in isins:
        iss = srv.issuer(isin)
        snap[f"/api/issuer?isin={isin}"] = iss
        sel = {(str(e["reaction_day"])[:10], e["event_id"]) for e in iss["events"] if e.get("reaction_day")}
        sel |= {(a["peak_date"], None) for a in iss["anomalies"]}
        for day, ev in sorted(sel, key=lambda x: (x[0], x[1] or "")):
            url = f"/api/card?isin={isin}&day={day}" + (f"&event_id={ev}" if ev else "")
            try:
                snap[url] = srv.card(isin, day, ev)
            except (KeyError, ValueError, IndexError) as e:
                print("  skip card", isin, day, ev, e)
                continue
            for lang in ("en", "de"):
                snap[f"narrate|{isin}|{day}|{ev or ''}|{lang}"] = srv.narrate({"isin": isin, "day": day, "event_id": ev, "lang": lang})
                for en, de in sugg.get("card", []):
                    q = en if lang == "en" else de
                    ctx = {"page": "card", "day": day, "event_id": ev}
                    snap[f"agent|{isin}|{lang}|card|{day}|{q}"] = srv.agent({"isin": isin, "question": q, "context": ctx, "lang": lang})
        for page in ("dashboard", "compare", "report"):
            for en, de in sugg.get(page, []):
                for lang, q in (("en", en), ("de", de)):
                    snap[f"agent|{isin}|{lang}|{page}||{q}"] = srv.agent({"isin": isin, "question": q, "context": {"page": page}, "lang": lang})
        print(f"  {data.ticker_of(isin)}: {sum(1 for k in snap if isin in k)} answers")

    html = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "app.css").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    payload = json.dumps(snap, default=str, allow_nan=False, separators=(",", ":")).replace("</", "<\\/")
    shim = """<script>
/* Offline copy: answers every /api call from the JSON below (built by web/snapshot.py). */
window.__SNAP = %s;
(function () {
  const S = window.__SNAP, real = window.fetch.bind(window);
  const reply = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
  window.fetch = function (url, opt = {}) {
    const u = String(url);
    if (!u.startsWith("/api/")) return real(url, opt);
    if ((opt.method || "GET") === "GET") return u in S ? reply(S[u]) : reply({error: "This share or day is not in the offline copy. Open the live site for everything."}, 404);
    const b = JSON.parse(opt.body || "{}"), c = b.context || {};
    if (u === "/api/narrate") { const k = `narrate|${b.isin}|${b.day}|${b.event_id || ""}|${b.lang}`; return k in S ? reply(S[k]) : reply({error: "not in the offline copy"}, 404); }
    if (u === "/api/agent") {
      const k = `agent|${b.isin}|${b.lang}|${c.page}|${c.page === "card" ? c.day : ""}|${b.question}`;
      if (k in S) return reply(S[k]);
      return reply({text: b.lang === "de" ? "Diese Offline-Kopie beantwortet nur die vorgeschlagenen Fragen. Freie Fragen beantwortet der Analyst auf der Live-Seite." : "This offline copy answers the suggested questions only. Ask anything on the live site.",
        source: "template", model: null, steps: [], actions: [], check: {total: 0, unsupported: []}});
    }
    return reply({error: b.lang === "de" ? "Kalenderimport braucht die Live-Seite." : "Calendar import needs the live site."}, 400);
  };
})();
</script>""" % payload
    html = html.replace('<link rel="stylesheet" href="app.css">', f"<style>\n{css}\n</style>")
    html = html.replace('<script src="app.js"></script>', shim + f"\n<script>\n{js.replace('</script', '<\\/script')}\n</script>")
    html = html.replace("<title>Issuer Intelligence Hub</title>", "<title>Issuer Intelligence Hub (offline copy)</title>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"{out}  {out.stat().st_size / 1e6:.1f} MB, {len(snap)} answers, {time.time() - t0:.0f} s")


def main():
    from config import HERO_TICKERS
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="+", default=list(HERO_TICKERS))
    ap.add_argument("--llm", action="store_true", help="AI texts from the model in .env instead of templates")
    ap.add_argument("--out", type=Path, default=Path.home() / "Desktop" / "Issuer-Intelligence-Hub.html")
    a = ap.parse_args()
    build(a.tickers, a.llm, a.out)


if __name__ == "__main__":
    main()
