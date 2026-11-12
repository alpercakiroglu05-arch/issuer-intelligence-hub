"""
Number and date formatting for texts and reports, EN and DE.  OWNER: C4 (report); DE style by C2.

    formatters(lang) -> dict of functions (None/NaN -> "n/a"):

    | name   | EN          | DE              |
    |--------|-------------|-----------------|
    | pct    | -23.2%      | −23,2 %         |  signed, 1 decimal
    | pct0   | 63%         | 63 %            |  0 decimals
    | spct0  | -33%        | −33 %           |  signed, 0 decimals
    | pct1   | 1.5%        | 1,5 %           |  unsigned, 1 decimal
    | pctile | 99%         | 99 %            |  rounded down, so 0.995 never shows as 100%
    | x      | 8.6x        | 8,6-fach        |
    | bps    | 21 bps      | 21 bps          |
    | eur    | EUR 2.5m    | 2,5 Mio. EUR    |  k: EUR 561k | 561 Tsd. EUR
    | date   | 2026-03-27  | 27.03.2026      |  accepts str / date / Timestamp
    | dt     | 2026-03-26 17:45 | 26.03.2026 17:45 |
    | month_range | Jan – Oct 2026 | Jan.–Okt. 2026 |
    | rank(3, 215) | rank 3 of 215 (incl. this day) | Rang 3 von 215 (inkl. dieses Tages) |

DE uses the real minus sign (U+2212) and a no-break space before "%"; report.export.to_pdf maps them to
ASCII for the PDF font. ai/checks.py understands both styles.
"""
import math

import pandas as pd

MINUS = "−"
NBSP = "\xa0"
MONTHS = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
          "de": ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."]}


def _na(v) -> bool:
    return v is None or (isinstance(v, float) and v != v) or v is pd.NaT


def formatters(lang: str = "en") -> dict:
    de = lang == "de"

    def num(v: float, dec: int, sign: bool = False) -> str:
        s = f"{v:+.{dec}f}" if sign else f"{v:.{dec}f}"
        return s.replace("-", MINUS).replace(".", ",") if de else s

    def per(s: str) -> str:
        return f"{s}{NBSP}%" if de else f"{s}%"

    def pct(v): return "n/a" if _na(v) else per(num(v * 100, 1, sign=True))
    def pct0(v): return "n/a" if _na(v) else per(num(v * 100, 0))
    def spct0(v): return "n/a" if _na(v) else per(num(v * 100, 0, sign=True))
    def pct1(v): return "n/a" if _na(v) else per(num(v * 100, 1))
    def pctile(v): return "n/a" if _na(v) else per(str(math.floor(round(v * 100, 6))))
    def x(v): return "n/a" if _na(v) else (f"{num(v, 1)}-fach" if de else f"{v:.1f}x")
    def bps(v): return "n/a" if _na(v) else f"{v:.0f} bps"

    def eur(v):
        if _na(v):
            return "n/a"
        if de:
            return f"{num(v / 1e6, 1)} Mio. EUR" if v >= 1e6 else f"{num(v / 1e3, 0)} Tsd. EUR"
        return f"EUR {v / 1e6:.1f}m" if v >= 1e6 else f"EUR {v / 1e3:.0f}k"

    def date(v):
        if _na(v) or v == "":
            return "n/a"
        d = pd.Timestamp(v)
        return d.strftime("%d.%m.%Y") if de else d.strftime("%Y-%m-%d")

    def dt(v):
        """'2026-03-26 17:45' -> DE '26.03.2026 17:45'; EN keeps the string as given."""
        if _na(v) or v == "":
            return ""
        if not de:
            return str(v)
        day, _, rest = str(v).partition(" ")
        return f"{date(day)} {rest}".strip()

    def month_range(start, end):
        a, b = pd.Timestamp(start), pd.Timestamp(end)
        m = MONTHS["de" if de else "en"]
        sep = "–" if de else " – "
        return f"{m[a.month - 1]}{sep}{m[b.month - 1]} {b.year}"

    def rank(r, of):
        return (f"Rang {r} von {of} (inkl. dieses Tages)" if de else f"rank {r} of {of} (incl. this day)")

    return dict(rank=rank, pct=pct, pct0=pct0, spct0=spct0, pct1=pct1, pctile=pctile, x=x, bps=bps, eur=eur, date=date,
                dt=dt, month_range=month_range)


def group_label(cmp: dict, lang: str = "en") -> str:
    """Label of the comparison group (engine.compare.comparison_for). EN: the engine's own `group` string.
    DE: built from group_type, group_index and period_start/period_end, e.g.
    'auffälligen Handelstagen, MDAX, Jan.–Okt. 2026' (dative, follows 'Im Vergleich mit <n>')."""
    if lang != "de":
        return cmp["group"]
    what = "auffälligen Handelstagen" if cmp["group_type"] == "NOTABLE_DAY" else f"{cmp['group_type']}-Ereignissen"
    idx = "DAX, MDAX und SDAX" if cmp["group_index"] == "DAX+MDAX+SDAX" else cmp["group_index"]
    parts = [what, idx]
    if cmp.get("period_start") and cmp.get("period_end"):
        parts.append(formatters("de")["month_range"](cmp["period_start"], cmp["period_end"]))
    return ", ".join(parts)
