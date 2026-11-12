"""
Numbers check for LLM texts.  OWNER: C4 (AI); first version by C1.

Rule of the project: numbers come from code, words come from the LLM. This module enforces it:
every number in an LLM text must be derivable from the card JSON the model was given, else the caller
falls back to the template text.

    unsupported_numbers(text, payload) -> list[str]   numbers in `text` that are not in `payload`
    meaning_errors(text, card) -> list[str]           "the share fell X %" where X is not |price.ret|

"Derivable" means: the JSON value itself, ×100 (percent), ÷1e3/1e6/1e9 (EUR k/m/bn), or a group size + 1
("#3 of 215" when n = 214), rounded to the decimals written in the text. Signs are ignored ("fell 23.2 %"
for -0.232). Dates and clock times are split into their parts. German number style (21,7) is understood.
A German short date without a year ("am 29.05.", "14.7.:", also "am 14.04" without the closing dot when the
month has two digits and no unit follows) counts as a date only when the JSON has that day and month in an
ISO date; "EUR 1,628m" in a JSON string also yields 1628 (English thousands separator).
Limitation: a small integer (e.g. "12") can match some unrelated value by chance; invented figures with
decimals or large values are caught.
"""
import json
import math
import re

_DATE_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DATE_DE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_DATE_DE_SHORT = re.compile(r"(?<![\d.,])(\d{1,2})\.(\d{1,2})\.(?!\d)")  # "29.05." / "14.7.:" / "14.04.,", no year
# "am 14.04 und 03.02": no closing dot. Two-digit month only, and never before a unit, so "14.04 %" stays a number
_DATE_DE_BARE = re.compile(r"(?<![\d.,])(\d{1,2})\.(\d{2})(?![\d.,])"
                           r"(?!\s*(?:%|×|x\b|bps\b|Bp\b|Mio\b|Mrd\b|Tsd\b|EUR\b|€|Uhr\b|-?fach))")
_THOUSANDS = re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})+(?![\d,])")                       # "1,628" in "EUR 1,628m"
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_NUM = re.compile(r"(?<![\w.])[-+−]?\d+(?:[.,]\d+)?")


def _walk(x, out: list):
    if isinstance(x, bool) or x is None:
        return
    if isinstance(x, (int, float)):
        out.append(float(x))
    elif isinstance(x, dict):
        for k, v in x.items():
            out.extend(float(n) for n in re.findall(r"\d+", str(k)))  # e.g. xlm_25k_bps, first_15min
            _walk(v, out)
    elif isinstance(x, (list, tuple)):
        for v in x:
            _walk(v, out)
    elif isinstance(x, str):
        out.extend(float(n) for n in re.findall(r"\d+(?:\.\d+)?", x))
        out.extend(float(n.replace(",", "")) for n in _THOUSANDS.findall(x))


def _days_in(x, out: set):
    """(month, day) of every ISO date in the payload's strings."""
    if isinstance(x, dict):
        for v in x.values():
            _days_in(v, out)
    elif isinstance(x, (list, tuple)):
        for v in x:
            _days_in(v, out)
    elif isinstance(x, str):
        out.update((int(m), int(d)) for _, m, d in _DATE_ISO.findall(x))


def allowed_values(payload) -> list[float]:
    raw: list[float] = []
    _walk(json.loads(json.dumps(payload, default=str)), raw)
    cmp = payload.get("comparison") if isinstance(payload, dict) else None
    if isinstance(cmp, dict) and isinstance(cmp.get("n"), int):
        raw.append(cmp["n"] + 1.0)  # "#3 of 215": the group plus the event itself
    vals = set()
    for v in raw:
        for s in (v, v * 100, v / 1e3, v / 1e6, v / 1e9):
            vals.add(abs(s))
        vals.add(float(math.floor(abs(v) * 100)))  # percentiles are shown rounded down ("bigger than 93 %" for 0.939)
    return sorted(vals)


def _numbers(text: str) -> list[tuple[str, float, int]]:
    """(as written, absolute value, decimals) for every number in the text."""
    t = text.replace("−", "-").replace(" ", " ").replace("\xa0", " ")
    found: list[tuple[str, float, int]] = []
    for rx in (_DATE_ISO, _DATE_DE, _TIME):  # split dates and times into their parts first
        for m in rx.finditer(t):
            found += [(p, float(p), 0) for p in m.groups() if p]
        t = rx.sub(" ", t)
    for m in _NUM.finditer(t):
        s = m.group().lstrip("+-")
        val = s.replace(",", ".")
        dec = len(val.split(".")[1]) if "." in val else 0
        found.append((m.group(), abs(float(val)), dec))
    return found


_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])")       # "21.7" and "vs. the" do not split
_SUBJECT = re.compile(r"\b(share|stock|Aktie)\b", re.I)
_VERB = re.compile(r"\b(fell|rose|dropped|gained|verlor|stieg|fiel)\b", re.I)
_PCT = re.compile(r"[-+−]?(\d+(?:[.,]\d+)?)\s*%")


def meaning_errors(text: str, card) -> list[str]:
    """Narrow meaning check: in a sentence with share/stock/Aktie and fell/rose/... the first percentage
    after the verb is the share's own move, so it must be |price.ret| (rounded as written).
    Catches "the share fell 21.7 %" when 21.7 % is the stock-specific move. Other sentences are not checked."""
    ret = ((card or {}).get("price") or {}).get("ret") if isinstance(card, dict) else None
    if ret is None:
        return []
    errors = []
    for s in _SENTENCE.split(text.replace("\xa0", " ").replace(" ", " ")):
        verb = _VERB.search(s)
        if not (verb and _SUBJECT.search(s)):
            continue
        m = _PCT.search(s, verb.end())
        if not m:
            continue
        val = m.group(1).replace(",", ".")
        dec = len(val.split(".")[1]) if "." in val else 0
        if abs(float(val) - abs(ret) * 100) > 0.5 * 10 ** -dec + 1e-6:
            errors.append(f"{m.group().strip()} (share's own move is {abs(ret) * 100:.1f}%)")
    return errors


def unsupported_numbers(text: str, payload) -> list[str]:
    allowed = allowed_values(payload)
    days: set = set()
    _days_in(json.loads(json.dumps(payload, default=str)), days)
    t = _DATE_DE.sub(" ", _DATE_ISO.sub(" ", text))  # dates with a year are handled in _numbers anyway
    for m in _DATE_DE_SHORT.finditer(t):
        if (int(m.group(2)), int(m.group(1))) in days:  # a real date of the data, not a decimal number
            text = text.replace(m.group(0), " ", 1)
    text = _DATE_DE_BARE.sub(lambda m: " " if (int(m.group(2)), int(m.group(1))) in days else m.group(0), text)
    bad = []
    for written, x, dec in _numbers(text):
        tol = 0.5 * 10 ** -dec + 1e-6
        if not any(abs(a - x) <= tol for a in allowed):
            bad.append(written)
    return bad
