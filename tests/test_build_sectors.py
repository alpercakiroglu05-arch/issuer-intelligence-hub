"""Tests for ingest/build_sectors.py on a tiny synthetic xlsx (no network, no data/ needed)."""
import zipfile

import pandas as pd
import pytest

from ingest.build_sectors import SAME_COMPANY, build, read_listed

HEADER = ["ISIN", "Trading Symbol", "Company", "Sector", "Subsector", "Country", "Instrument Exchange", "Index"]


def _xlsx(path, sheets: dict[str, list[list[str]]]):
    """Write a minimal xlsx with inline strings, like the Deutsche Boerse file (cover + data sheets)."""
    def cell(ref, v):
        v = v.replace("&", "&amp;")
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{v}</t></is></c>'
    with zipfile.ZipFile(path, "w") as z:
        names = list(sheets)
        z.writestr("xl/workbook.xml",
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{n}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, n in enumerate(names))
                   + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i + 1}" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(len(names)))
                   + "</Relationships>")
        for i, n in enumerate(names):
            rows = "".join(f'<row r="{r + 1}">' + "".join(cell(f"{chr(65 + c)}{r + 1}", v) for c, v in enumerate(row) if v)
                           + "</row>" for r, row in enumerate(sheets[n]))
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml",
                       f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{rows}</sheetData></worksheet>')


@pytest.fixture
def listed(tmp_path):
    p = tmp_path / "Listed-companies.xlsx"
    _xlsx(p, {
        "Cover": [["", "Report: Listed Companies Frankfurt Stock Exchange"]],
        "Prime Standard": [
            ["Companies in Prime Standard"], ["Number of companies: ", "4"], HEADER,
            ["DE0000000001", "AAA", "Alpha AG ", "Industrial ", "Machinery", "Germany", "XETRA", "SDAX"],
            ["DE000VNC0014 ", "V1NC ", "Vincorion SE", "Industrial", "Advanced Industrial Equipment", "Germany", "XETRA", "SDAX"],
            ["DE0000000003", "RRR", "Realty AG", "Financial services", "Real Estate", "Germany", "XETRA", "MDAX"],
            ["DE000FRE5EN2", "FRE", "Fresenius", "Pharma & Healthcare", "Health Care", "Germany", "XETRA", "DAX"],
        ],
        "Scale": [["Companies in Scale"], HEADER,
                  ["DE0000000004", "BBB", "Bank AG", "Financial Services", "Diversified Financial", "Germany", "XETRA", "-"]],
    })
    return p


def test_read_listed_strips_cells_incl_non_breaking_space(listed):
    db = read_listed(str(listed))
    assert len(db) == 5 and set(db["segment"]) == {"Prime Standard", "Scale"}
    assert "DE000VNC0014" in set(db["isin"])                     # the cell ended with U+00A0
    assert db.loc[db["isin"] == "DE0000000001", "sector"].iloc[0] == "Industrial"
    assert db.loc[db["isin"] == "DE0000000003", "sector"].iloc[0] == "Financial Services"   # case normalised


def test_build_maps_groups_real_estate_same_company_and_blanks(listed):
    universe = pd.DataFrame({
        "ticker": ["AAA", "V1NC", "RRR", "BBB", "FRE", "FRE", "KCO"],
        "isin": ["DE0000000001", "DE000VNC0014", "DE0000000003", "DE0000000004", "DE000FRE5EN2",
                 next(k for k, v in SAME_COMPANY.items() if v == "DE000FRE5EN2"), "DE000KC01000"],
        "name": ["ALPHA AG ", "VINCORION", "REALTY", "BANK", "FRESENIUS", "FRESENIUS (old ISIN)", "KLOECKNER"],
    })
    out = build(read_listed(str(listed)), universe, "https://example.org/file.xlsx").set_index("isin")
    assert list(out.reset_index().columns) == ["isin", "ticker", "name", "sector", "source_url"]
    assert out.loc["DE0000000001", "sector"] == "Industrials" and out.loc["DE0000000001", "name"] == "ALPHA AG"
    assert out.loc["DE000VNC0014", "sector"] == "Industrials"
    assert out.loc["DE0000000003", "sector"] == "Real Estate"       # Financial Services + subsector Real Estate
    assert out.loc["DE0000000004", "sector"] == "Financials"
    assert out.loc[out["ticker"] == "FRE", "sector"].tolist() == ["Healthcare", "Healthcare"]
    assert pd.isna(out.loc["DE000KC01000", "sector"]) and pd.isna(out.loc["DE000KC01000", "source_url"])
    assert out.loc["DE0000000001", "source_url"] == "https://example.org/file.xlsx"


def test_build_fails_on_unmapped_sector(listed):
    db = read_listed(str(listed))
    db.loc[db["isin"] == "DE0000000001", "sector"] = "Space Tourism"
    universe = pd.DataFrame({"ticker": ["AAA"], "isin": ["DE0000000001"], "name": ["ALPHA"]})
    with pytest.raises(ValueError, match="Space Tourism"):
        build(db, universe)
