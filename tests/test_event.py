"""
Validierung der von Hand gepflegten Datei events/events.csv.

Ausführen (im Projektroot):
    pytest tests/test_events_csv.py -v

Jeder Test meldet bei einem Fehler die betroffenen Zeilen mit der Zeilennummer
aus der CSV-Datei (Zeile 1 = Kopfzeile), damit man sie direkt im Editor findet.
"""

import csv
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import pytest

EVENTS_CSV = Path(__file__).resolve().parent.parent / "events" / "events.csv"

EXPECTED_COLUMNS = ["ticker", "isin", "type", "date", "time_local", "title", "source_url", "verified"]
ALLOWED_TYPES = {"FY", "Q1", "H1", "Q3", "DIVIDEND_EX", "AGM", "ADHOC", "GUIDANCE", "MA", "CMD", "INDEX"}
DATE_MIN = date(2026, 1, 2)
DATE_MAX = date(2026, 10, 30)

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ----------------------------------------------------------------------------
# Hilfsfunktionen
# ----------------------------------------------------------------------------
def _fail(title, problems, limit=15):
    """Pytest-Fehlermeldung mit den ersten Problemzeilen."""
    lines = [f"{title} ({len(problems)} Problem(e)):"]
    lines += [f"  Zeile {n}: {msg}" for n, msg in problems[:limit]]
    if len(problems) > limit:
        lines.append(f"  ... und {len(problems) - limit} weitere")
    pytest.fail("\n".join(lines), pytrace=False)


@pytest.fixture(scope="module")
def header_and_rows():
    """Liest die CSV einmal. Rückgabe: (Spaltenliste, [(zeilennummer, dict), ...])."""
    if not EVENTS_CSV.exists():
        pytest.fail(f"Datei nicht gefunden: {EVENTS_CSV}", pytrace=False)
    # utf-8-sig: entfernt ein BOM, falls die Datei aus Excel gespeichert wurde
    with EVENTS_CSV.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        rows = []
        for row in reader:
            # fehlende Felder (zu kurze Zeile) als leere Strings behandeln
            clean = {col: (row.get(col) or "") for col in header}
            rows.append((reader.line_num, clean))
    return header, rows


def _val(row, col):
    """Wert einer Spalte, leer falls die Spalte fehlt (der Spaltentest meldet das separat)."""
    return row.get(col, "")


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------
def test_columns(header_and_rows):
    header, _ = header_and_rows
    missing = [c for c in EXPECTED_COLUMNS if c not in header]
    extra = [c for c in header if c not in EXPECTED_COLUMNS]
    dupes = sorted({c for c in header if header.count(c) > 1})
    problems = []
    if missing:
        problems.append(f"fehlende Spalten: {missing}")
    if extra:
        problems.append(f"unerwartete Spalten: {extra}")
    if dupes:
        problems.append(f"doppelte Spaltennamen: {dupes}")
    if problems:
        pytest.fail("Spalten stimmen nicht: " + "; ".join(problems) + f" (gefunden: {header})", pytrace=False)


def test_file_has_rows(header_and_rows):
    _, rows = header_and_rows
    assert rows, "events.csv enthält keine Datenzeilen"


def test_type_is_allowed(header_and_rows):
    _, rows = header_and_rows
    problems = [(n, f"type={_val(r, 'type')!r} nicht erlaubt (erlaubt: {sorted(ALLOWED_TYPES)})")
                for n, r in rows if _val(r, "type") not in ALLOWED_TYPES]
    if problems:
        _fail("Ungültige type-Werte", problems)


def test_date_is_valid_and_in_range(header_and_rows):
    _, rows = header_and_rows
    problems = []
    for n, r in rows:
        raw = _val(r, "date")
        if not DATE_RE.match(raw):
            problems.append((n, f"date={raw!r} ist nicht im Format YYYY-MM-DD"))
            continue
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            problems.append((n, f"date={raw!r} ist kein gültiges Datum"))
            continue
        if not (DATE_MIN <= d <= DATE_MAX):
            problems.append((n, f"date={raw} liegt außerhalb {DATE_MIN} bis {DATE_MAX}"))
    if problems:
        _fail("Ungültige date-Werte", problems)


def test_time_local_empty_or_hhmm(header_and_rows):
    _, rows = header_and_rows
    problems = [(n, f"time_local={_val(r, 'time_local')!r} ist weder leer noch HH:MM")
                for n, r in rows
                if _val(r, "time_local") != "" and not TIME_RE.match(_val(r, "time_local"))]
    if problems:
        _fail("Ungültige time_local-Werte", problems)


def test_source_url_not_empty_and_http(header_and_rows):
    _, rows = header_and_rows
    problems = []
    for n, r in rows:
        url = _val(r, "source_url")
        if url == "":
            problems.append((n, "source_url ist leer"))
        elif not url.startswith("http"):
            problems.append((n, f"source_url={url!r} beginnt nicht mit http"))
    if problems:
        _fail("Ungültige source_url-Werte", problems)


def test_verified_is_0_or_1(header_and_rows):
    _, rows = header_and_rows
    problems = [(n, f"verified={_val(r, 'verified')!r} ist weder 0 noch 1")
                for n, r in rows if _val(r, "verified") not in {"0", "1"}]
    if problems:
        _fail("Ungültige verified-Werte", problems)


def test_isin_has_12_characters(header_and_rows):
    _, rows = header_and_rows
    problems = [(n, f"isin={_val(r, 'isin')!r} hat {len(_val(r, 'isin'))} statt 12 Zeichen")
                for n, r in rows if len(_val(r, "isin")) != 12]
    if problems:
        _fail("Ungültige ISINs", problems)


def test_no_duplicate_ticker_type_date(header_and_rows):
    _, rows = header_and_rows
    seen = defaultdict(list)
    for n, r in rows:
        seen[(_val(r, "ticker"), _val(r, "type"), _val(r, "date"))].append(n)
    problems = []
    for (ticker, typ, d), line_numbers in seen.items():
        if len(line_numbers) > 1:
            problems.append((line_numbers[1], f"Duplikat von ticker={ticker}, type={typ}, date={d} "
                                              f"(auch in Zeile(n) {line_numbers[:1] + line_numbers[2:]})"))
    if problems:
        _fail("Doppelte Einträge", sorted(problems))gi