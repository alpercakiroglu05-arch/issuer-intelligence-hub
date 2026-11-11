#!/usr/bin/env python3
"""
build_sectors.py - builds events/sectors.csv from Deutsche Boerse's "Listed companies" spreadsheet.

Source (Issuer Services, Listed Companies Frankfurt Stock Exchange):
    https://www.cashmarket.deutsche-boerse.com/cash-en/Data-Tech/statistics/listed-companies
    file: see DB_LISTED_URL below. The xlsx itself is NOT committed.

For every ISIN in data/universe.csv:
    sector  one of 11 groups mapped from the Deutsche Boerse Prime Standard sector (see GROUP);
            Financial Services with subsector "Real Estate" -> Real Estate
    ISINs that changed in 2026 take the sector of the ISIN the file lists today (SAME_COMPANY).
    ISINs not in the file stay blank (no guessing); they fall back to the index in engine.compare.

Usage:
    python3 ingest/build_sectors.py <path-or-url-to-Listed-companies.xlsx> [out.csv]
    python3 ingest/build_sectors.py https://www.cashmarket.deutsche-boerse.com/.../Listed-companies.xlsx
Needs only the standard library + pandas (no openpyxl).
"""
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_DIR, SECTORS_CSV  # noqa: E402

DB_LISTED_URL = ("https://www.cashmarket.deutsche-boerse.com/resource/blob/67858/"
                 "c0cedb209ed3143463ce6675b641225b/data/Listed-companies.xlsx")

# Deutsche Boerse Prime Standard sector -> our 11 groups (docs/C2_ENGINE.md)
GROUP = {
    "Automobile": "Automotive",
    "Banks": "Financials", "Financial Services": "Financials", "Insurance": "Financials",
    "Pharma & Healthcare": "Healthcare",
    "Software": "Technology", "Technology": "Technology",
    "Media": "Media & Telecom", "Telecommunication": "Media & Telecom",
    "Consumer": "Consumer", "Food & Beverages": "Consumer", "Retail": "Consumer",
    "Industrial": "Industrials", "Construction": "Industrials",
    "Chemicals": "Materials", "Basic Resources": "Materials",
    "Transportation & Logistics": "Transport & Logistics",
    "Utilities": "Utilities",
}
# Same company, ISIN changed: our (old) ISIN -> the ISIN in the Deutsche Boerse file
SAME_COMPANY = {
    "DE0005785604": "DE000FRE5EN2",  # FRE Fresenius
    "NL0015002CX3": "NL0015002SN0",  # QIA Qiagen
    "DE000A2YNT30": "DE000A41YHG1",  # ACT Alzchem (our ACT0 is the new ISIN)
    "SE0018538068": "IE000ZVY0237",  # VRV Verve Group (re-domiciled, same trading symbol)
}
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
_COLS = ["isin", "symbol", "company", "sector", "subsector", "country", "exchange", "index"]


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _sheets(xlsx: Path) -> dict[str, list[list[str]]]:
    """All sheets of an xlsx as lists of string rows (standard library only)."""
    z = zipfile.ZipFile(xlsx)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
    target = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    out = {}
    for sh in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", _NS):
        path = "xl/" + target[sh.get(f"{{{_NS['r']}}}id")].lstrip("/").removeprefix("xl/")
        rows = []
        for row in ET.fromstring(z.read(path)).iter(f"{{{_NS['m']}}}row"):
            vals = {}
            for c in row.findall("m:c", _NS):
                v, t = c.find("m:v", _NS), c.get("t")
                if t == "s" and v is not None:
                    vals[_col(c.get("r"))] = shared[int(v.text)]
                elif t == "inlineStr":
                    vals[_col(c.get("r"))] = "".join(x.text or "" for x in c.iter(f"{{{_NS['m']}}}t"))
                else:
                    vals[_col(c.get("r"))] = v.text if v is not None else ""
            if vals:
                rows.append([vals.get(k, "") for k in range(max(vals) + 1)])
        out[sh.get("name")] = rows
    return out


def read_listed(src: str) -> pd.DataFrame:
    """Listed companies (all segments) from a local path or a URL: isin, symbol, company, sector, subsector, ..."""
    if src.startswith(("http://", "https://")):
        tmp = Path(tempfile.mkdtemp()) / "Listed-companies.xlsx"
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            tmp.write_bytes(r.read())
        src = str(tmp)
    frames = []
    for name, rows in _sheets(Path(src)).items():
        head = next((i for i, r in enumerate(rows) if r and r[0].strip() == "ISIN"), None)
        if head is None:  # cover sheet
            continue
        df = pd.DataFrame([(r + [""] * 8)[:8] for r in rows[head + 1:]], columns=_COLS)
        df = df[df["isin"].str.strip().str.len() == 12].assign(segment=name)
        frames.append(df)
    db = pd.concat(frames, ignore_index=True)
    for c in _COLS:
        db[c] = db[c].str.strip()
    db["sector"] = db["sector"].replace({"Financial services": "Financial Services", "Basic resources": "Basic Resources"})
    return db.drop_duplicates("isin")


def build(listed: pd.DataFrame, universe: pd.DataFrame, source_url: str = DB_LISTED_URL) -> pd.DataFrame:
    """One row per universe ISIN: ticker, isin, name, sector (11 groups or blank), source_url."""
    db = listed.copy()
    db["group"] = db["sector"].map(GROUP)
    db.loc[(db["sector"] == "Financial Services") & (db["subsector"] == "Real Estate"), "group"] = "Real Estate"
    unknown = db.loc[db["isin"].isin(universe["isin"]) & db["group"].isna(), "sector"].unique()
    if len(unknown):
        raise ValueError(f"Deutsche Boerse sector(s) without a group mapping: {list(unknown)}")
    group = db.set_index("isin")["group"]
    out = universe[["ticker", "isin", "name"]].copy()
    out["name"] = out["name"].str.strip()
    lookup = out["isin"].map(lambda i: SAME_COMPANY.get(i, i))
    out["sector"] = lookup.map(group)
    out["source_url"] = out["sector"].notna().map({True: source_url, False: None})
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else SECTORS_CSV
    url = src if src.startswith(("http://", "https://")) else DB_LISTED_URL
    out = build(read_listed(src), pd.read_csv(DATA_DIR / "universe.csv"), url)
    out.to_csv(out_path, index=False)
    print(f"{out['sector'].notna().sum()} of {len(out)} ISINs with a sector -> {out_path}")
    print(out["sector"].value_counts().to_string())
    blank = out[out["sector"].isna()]
    if len(blank):
        print("not in the Deutsche Boerse file (left blank):\n" + blank[["ticker", "isin", "name"]].to_string(index=False))
