"""
Numbers check for LLM texts.  OWNER: C4 (AI); first version by C1.

Rule of the project: numbers come from code, words come from the LLM. This module enforces it:
every number in an LLM text must be derivable from the card JSON the model was given, else the caller
falls back to the template text.

    unsupported_numbers(text, payload) -> list[str]   numbers in `text` that are not in `payload`

"Derivable" means: the JSON value itself, ×100 (percent), ÷1e3/1e6/1e9 (EUR k/m/bn), or a group size + 1
("#3 of 215" when n = 214), rounded to the decimals written in the text. Signs are ignored ("fell 23.2 %"
for -0.232). Dates and clock times are split into their parts. German number style (21,7) is understood.
Limitation: a small integer (e.g. "12") can match some unrelated value by chance; invented figures with
decimals or large values are caught.
"""
import json
import re

_DATE_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DATE_DE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
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


def unsupported_numbers(text: str, payload) -> list[str]:
    allowed = allowed_values(payload)
    bad = []
    for written, x, dec in _numbers(text):
        tol = 0.5 * 10 ** -dec + 1e-6
        if not any(abs(a - x) <= tol for a in allowed):
            bad.append(written)
    return bad
