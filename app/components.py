"""
Shared UI pieces.  OWNER: C3 (frontend).

TODO C3:
  - visual design of the impact card (this is THE demo moment) - use the designer's sketch
  - consistent colors: stock vs peers vs normal band
"""
import _bootstrap  # noqa: F401
import pandas as pd
import streamlit as st

from config import DEFAULT_TICKER, HERO_TICKERS
from engine import data


# ---------- formatting (None/NaN -> "n/a") ----------
def _na(v) -> bool:
    return v is None or v != v


def pct(x):
    return "n/a" if _na(x) else f"{x * 100:+.1f}%"


def pct0(x):
    return "n/a" if _na(x) else f"{x * 100:.0f}%"


def times(v):
    return "n/a" if _na(v) else f"{v:.1f}x"


def bps(v):
    return "n/a" if _na(v) else f"{v:.0f} bps"


def band(v):
    """Typical absolute move, e.g. 'normal ±0.5%'."""
    return "n/a" if _na(v) else f"normal ±{v * 100:.1f}%"


def eur(v):
    if _na(v):
        return "n/a"
    return f"€{v / 1e6:.1f}m" if abs(v) >= 1e6 else f"€{v / 1e3:.0f}k"


# ---------- page setup ----------
@st.cache_data
def _universe():
    return data.universe()


def setup(title: str) -> str:
    """Call first on every page. Returns the selected ISIN (kept across pages)."""
    st.set_page_config(page_title=f"Issuer Intelligence Hub · {title}", page_icon="📈", layout="wide")
    u = _universe().copy()
    ex = ~u["member_now"].astype(bool) if "member_now" in u else pd.Series(False, index=u.index)
    u["label"] = (u["ticker"] + " · " + u["name"].str.title() + " (" + u["idx_latest"]
                  + ")" + ex.map({True: " · left index", False: ""}))
    u["order"] = (~u["ticker"].isin(HERO_TICKERS)).astype(int)
    u = u.sort_values(["order", "idx_latest", "ticker"])
    isins, labels = u["isin"].tolist(), u["label"].tolist()
    if "isin" not in st.session_state:
        st.session_state["isin"] = data.isin_of(DEFAULT_TICKER)
    k = st.sidebar.selectbox("Stock", range(len(isins)), index=isins.index(st.session_state["isin"]),
                             format_func=lambda i: labels[i])
    st.session_state["isin"] = isins[k]
    st.sidebar.caption("Data: Deutsche Börse Xetra, 2 Jan – 30 Oct 2026")
    return isins[k]


# ---------- impact card ----------
def render_card(card: dict) -> None:
    p, v, l, a, au = card["price"], card["volume"], card["liquidity"], card["participants"], card["auctions"]
    ev = card["event"]
    st.subheader(f"{card['name'].title()} · {ev['title']}")
    st.caption(f"Reaction day {ev['reaction_day']} · timing: {ev['timing']} · "
               f"baseline {card['baseline']['window']} ({card['baseline']['days_used']} days)")
    c = st.columns(5)
    c[0].metric("Stock-specific move", pct(p["abn_ret"]), f"stock {pct(p['ret'])} · peers {pct(p['peer_ret'])}",
                delta_color="off")
    c[1].metric("Turnover vs normal", times(v["ratio"]), f"{eur(v['turnover_eur'])} vs {eur(v['baseline_eur'])}",
                delta_color="off")
    c[2].metric("Trading cost XLM 25k", bps(l["xlm_25k_bps"]), f"normal {bps(l['xlm_25k_baseline_bps'])}",
                delta_color="off")
    c[3].metric("Auction share", pct0(au["auction_share"]), f"normal {pct0(au['auction_share_baseline'])}",
                delta_color="off")
    c[4].metric("Agent order imbalance", pct(a["agent_aggr_imbalance"]), "+ net buying / − net selling",
                delta_color="off")
    c2 = st.columns(5)
    c2[0].metric("Gap at open", pct(p["gap_open"]))
    c2[1].metric("Move during session", pct(p["ret_intraday"]))
    c2[2].metric("Abnormal return t0..t+5", pct(p["car_0_5"]))
    c2[3].metric("Spread back to normal after", "n/a" if l["days_to_normal"] is None else f"{l['days_to_normal']} days")
    c2[4].metric("Volume z-score", "n/a" if v["z"] is None else f"{v['z']:.1f}")
    st.markdown("**Opening and closing auction**")
    ca = st.columns(4)
    norm = lambda r, b: "n/a" if _na(r) else f"{r:.1f}x normal ({eur(b)})"  # noqa: E731
    ca[0].metric("Opening auction volume", eur(au["open_auction_eur"]),
                 norm(au["open_auction_ratio"], au["open_auction_eur_baseline"]), delta_color="off")
    ca[1].metric("Opening auction price vs prev. close", pct(au["open_auction_move"]),
                 band(au["open_auction_move_baseline_abs"]), delta_color="off")
    ca[2].metric("Closing auction volume", eur(au["close_auction_eur"]),
                 norm(au["close_auction_ratio"], au["close_auction_eur_baseline"]), delta_color="off")
    ca[3].metric("Closing auction price vs last trade", pct(au["close_auction_move"]),
                 band(au["close_auction_move_baseline_abs"]), delta_color="off")
    if _na(au["close_auction_eur"]):
        st.caption("Auction volumes need the trade-by-trade data, built so far for the hero stocks.")
    elif not _na(au["close_auction_share"]):
        st.caption(f"Closing auction = {pct0(au['close_auction_share'])} of the day's turnover "
                   f"(normal {pct0(au['close_auction_share_baseline'])}).")
    if card.get("intraday"):
        i = card["intraday"]
        o = i.get("onset") or {}
        st.markdown("**Intraday**")
        c3 = st.columns(4)
        c3[0].metric("Turnover in first 15 min", pct0(i["volume_share_first_15min"]))
        c3[1].metric("Turnover in first 60 min", pct0(i["volume_share_first_60min"]))
        c3[2].metric("Volatility interruptions", len(o.get("volatility_interruptions") or []))
        c3[3].metric("Intraday low at", i["time_of_low"] or "n/a")
        if o.get("time"):
            where = {"pre_market": "pre-market", "opening_auction": "opening auction",
                     "at_open": "right after the open", "continuous": "during the session"}[o["session"]]
            st.success(f"⏱ **The market started pricing the news at {o['time']}** ({where}): "
                       f"{pct(o['ret_at_onset'])} vs. previous close at {o['volume_ratio_at_onset']:.1f}x normal "
                       f"turnover for that time; {pct(o['ret_15min_after'])} 15 min later.")
            if o["volatility_interruptions"]:
                st.caption("Volatility interruptions (unscheduled auctions): " + ", ".join(o["volatility_interruptions"]))
            if card["event"].get("timing_source") == "inferred_from_trading":
                st.caption(f"Announcement time unknown → timing inferred from trading: **{card['event']['timing']}**.")
    if card["flags"]:
        st.warning("Data flags: " + ", ".join(card["flags"]))
