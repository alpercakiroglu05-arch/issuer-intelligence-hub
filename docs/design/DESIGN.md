# UI design (C3)

There are two mockups. Open either one in a browser; both work offline except for the web fonts.

| File | Look | Use it for |
|---|---|---|
| `docs/design/ui-mockup-db.html` | **Deutsche Börse family look** (recommended for the demo) | It sits inside DB's web family, so the jury sees a module of the Issuer Services Hub, not a foreign tool. |
| `docs/design/ui-mockup.html` | Market seismograph | The concept and the pitch line ("a seismograph for listed companies"). |

## Variant B: Deutsche Börse family look (`ui-mockup-db.html`)

Tokens were measured on deutsche-boerse.com (11 Nov 2026) so the module does not stand out on a DB page:

| Token | Value | Where on DB's site |
|---|---|---|
| Navy | `#000099` | section headings (uppercase, bold) |
| Sky | `#0099ff` | pill buttons with →, links, side dock |
| Body text | `#404040`, 16–17 px | everywhere |
| Tile | `#f5f5f5`, square corners | "Aktuelle Themen" tiles |
| Font | News Gothic (fallback: Archivo at 88 % width) | everywhere |
| Tables | thin grey rules, ↑ ↗ → ↘ ↓ arrows | "Marktindikatoren", "Gewinner/Verlierer" |

Small upgrades on top of the DB look:

- **Page transitions:** View Transitions API. The navy band morphs between the tall hero and the short page header, the title slides up, and the nav indicator glides to the new tab.
- **One orchestrated moment per page:** lines draw in, turnover bars rise as a wave, the abnormal return and magnitude count up, and annotations appear in order (open → onset → low → closing auction → close).
- **Header** shrinks on scroll. A live CET clock sits in the utility bar, as on DB's site.
- **Side dock** (Export / Ask / Search) mirrors DB's Tools / Folgen / Kontakt dock.
- **⌘K search** across pages, issuers and events. Keys `1`–`5` switch pages and `E` opens the export.
- **Locale-aware numbers:** EN `−23.2%`, `€25.8m`; DE `−23,2 %`, `25,8 Mio. €`. There is also a separate DE/EN switch for the board note.
- **Export dialog:** A4 IR snapshot with section toggles and DE/EN; it prints to PDF.

Colour rule: green and red are used only for returns. Everything else uses navy and sky.

## Variant A: the market seismograph (`ui-mockup.html`)
Values marked with **°** in the mockup are placeholders until the engine provides them. All other numbers are real (EVD, 27 Mar 2026, see `CLAUDE.md`).

## Concept

An announcement is a tremor in the share. The app reads it like an instrument:

| Seismology | In the app | Source |
|---|---|---|
| Magnitude | **Impact magnitude 0–10**: one number for the CFO | new, `engine/` (proposal below) |
| Epicentre | The minute the market starts reacting | C1 news-onset detection |
| Seismogram | Intraday price trace with turnover needles | `intraday_bars.parquet` |
| Aftershocks | Days until turnover and spread are back within 1.2× of normal | `impact.liquidity.days_to_normal` + same for turnover |
| Seismic year | The year in one strip: every day's turnover vs normal | `daily_features.vol_ratio` |

This gives the pitch a memorable line ("a seismograph for listed companies") and every screen a reason to look the way it does.

## Visual rules

- **Materials:** cool lab paper background; a millimetre grid appears **only behind charts**. There is no card grid. Sections are separated by rules and whitespace.
- **Ink colours have fixed meanings across every chart:**
  - ultramarine pen `#2340d8`: the company
  - graphite `#8f959b`: peers, the index and "normal"
  - red pen `#df3f27`: events, unusual days and losses
  - green `#1d7a4c`: gains only
- **Type:**
  - *Bricolage Grotesque* for headlines and big numbers
  - *Instrument Sans* for UI text
  - *Martian Mono* for axis ticks, ISINs and tool traces
- **Readings** sit on a shared baseline like instrument dials. A small dot plot shows "you vs index median" (filled dot vs hollow dot) instead of a coloured badge.
- **Motion has one orchestrated moment:** when an event reading opens, the trace draws itself, the magnitude counts up, and the red annotations appear in order. Everything else is still. `prefers-reduced-motion` turns it off.
- **Light and dark** are both defined through CSS variables.
- **Never:**
  - tinted KPI cards
  - coloured status pills everywhere
  - gradient heroes
  - emoji icons
  - red/green on anything that is not a return

## Screens and what they cover from the challenge

| Tab | Content | Challenge item |
|---|---|---|
| **1 Overview** (Part A) | Lede sentence built from the numbers · the year in one strip (click a day → its reading) · normal state readings vs index · cost to trade vs MDAX · who trades · unusual days list · Xetra liquidity category check | I volume/spread/auctions over time, II peers, III anomalies |
| **2 Event reading** (Part B) | Event line (announcements + notable days) · magnitude meter · headline + lede · seismogram with open/low/closing-auction/onset annotations · "Was it us or the market?" decomposition · readings · aftershocks · who sold · note for the CFO (DE/EN, numbers check) | V impact card, VI events matched to intraday data |
| **3 Compare** | Filter written as a sentence ("Show me notable days in the MDAX during 2026") · scatter of abnormal return × turnover, dot size = spread change · rank sentences | VII compare events of the same type |
| **4 Ask** | Suggested questions · visible tool trace · streamed answer · disclaimer | AI assistant |
| **5 Lab** | Six next ideas with the data each needs (have / need) | "What else is relevant for IR, and which data" |
| **Export snapshot** (top bar) | A4 preview, choose sections, DE/EN, download PDF | IV, VIII exportable summary |

## Small additions beyond the brief

1. **Impact magnitude.** One comparable number per event.
2. **"Was it us or the market?" bar.** Splits the move into market, peers and stock-specific parts.
3. **Aftershocks.** How long the share needed to calm down.
4. **Xetra liquidity category check.** Compares the share against the Designated Sponsor thresholds from the Being Public Guide (p. 32).
5. **Lede sentences built from the numbers.** The top of every screen reads like a sentence, not a dashboard.
6. **Cause status on every unusual day** ("cause open" / "explained"). It keeps us honest: the data never says why.
7. **Keyboard shortcuts** `1`–`5` to switch tabs.

## Engine proposals (C2), small and deterministic

```python
# Impact magnitude, 0..10. Proposal only; tune on the 174 × 213 stock-days.
M = min(10, 2.2 * log2(1 + abs(abn_ret_z)) + 1.6 * log2(max(vol_ratio, 1)) + 0.8 * log2(max(xlm_25k_ratio, 1)))

# "Was it us or the market?": daily_features already has market_ret, peer_ret, abn_ret.
parts = {"market": market_ret, "peers": peer_ret - market_ret, "stock": abn_ret}

# Aftershocks: first day after t0 where vol_ratio <= 1.2 (we already have it for the spread).
volume_days_to_normal = ...
```

## How it maps to Streamlit (`app/`)

| Mockup | Streamlit |
|---|---|
| Top navigation | `st.navigation(pages, position="top")` (Streamlit ≥ 1.46; we pin ≥ 1.50) |
| Theme | `.streamlit/config.toml`: `primaryColor="#2340d8"`, `backgroundColor="#f5f6f3"`, `secondaryBackgroundColor="#ffffff"`, `textColor="#141618"` |
| Fonts, rules, readings | `components.inject_css()` → `st.markdown("<style>…</style>", unsafe_allow_html=True)`, plus `reading(label, value, ctx)` helpers that output the mockup HTML |
| Year strip (clickable) | Plotly bars + `st.plotly_chart(fig, on_select="rerun", selection_mode="points")` → set `st.session_state["impact_day"]` → `st.switch_page` |
| Seismogram with draw-in animation | `st.components.v1.html(SEISMO_TEMPLATE.replace("__DATA__", bars_json), height=380)`: copy the `seis()` function from the mockup |
| Event line | `st.segmented_control` over events + notable days |
| Compare sentence | three `st.selectbox(..., label_visibility="collapsed")` in `st.columns` |
| Note for the CFO | `ai.narrate.narrate(card, lang)` rendered with the `.note` CSS |
| Export snapshot | existing `report.export.to_html` / `to_pdf` + `st.download_button` |
| Plotly look | one `pio.templates["iih"]` in `components.py`: transparent background, grid `#e4e6e2`, colorway pen/graphite/red, font Instrument Sans |

## Suggested order before the 11:00 freeze

1. `components.py`: theme, CSS, colours, `reading()` helper (no conflicts with C2/C4)
2. Impact card page → event reading layout + seismogram component
3. Overview: year strip with click-through, readings, liquidity check
4. Compare: sentence filter + scatter (empty state until `engine/compare.py` lands)
5. Lab tab (static), export dialog polish
