"""Central configuration. Import from here instead of hard-coding paths or constants."""
import locale
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    """Load KEY=VALUE lines from .env into os.environ (existing env vars win).
    Tolerates Windows editors/PowerShell that save the file as ANSI instead of UTF-8."""
    if not path.exists():
        return
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode(locale.getpreferredencoding(False) or "cp1252", errors="replace")
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()

# Processed, small files (parquet/csv). Shared via OneDrive/SharePoint, never committed.
DATA_DIR = Path(os.getenv("IIH_DATA_DIR", REPO_ROOT / "data"))

# Raw Deutsche Boerse excerpt (8.9 GB). Only needed to (re)run the ingest scripts.
RAW_DIR = Path(os.getenv("IIH_RAW_DIR", REPO_ROOT.parent))

EVENTS_CSV = REPO_ROOT / "events" / "events.csv"
SECTORS_CSV = REPO_ROOT / "events" / "sectors.csv"
NAMES_CSV = REPO_ROOT / "events" / "names.csv"   # readable company names for the event stocks

# Stocks we showcase (max 3 per the challenge). Proposed - team decides.
#   EVD  CTS Eventim (MDAX): 27 Mar -23% after FY results (26 Mar 17:45); priced from 09:03, closing auction 3.6x normal
#   EVT  Evotec (SDAX):      14 Jul -24%, -22% gap at the open (news before the open)
#   HDD  Heidelberger Druck (SDAX): small cap, ~EUR 1.3m/day, XLM ~90 bps -> liquidity story
#   (GXI Gerresheimer: -31% on 11 Feb, left the SDAX on 9 Apr -> no XLM data afterwards; pitch story only)
HERO_TICKERS = ["EVD", "EVT", "HDD"]
# first screen of the web UI: one example per index (DAX, MDAX, SDAX). Zalando = the DAX member with the
# largest H1 reaction among the 40 DAX stocks, which all have one calendar event and full minute data.
EXAMPLE_TICKERS = ["ZAL", "EVD", "HDD"]
DEFAULT_TICKER = "EVD"

# Event study windows (trading days, relative to the reaction day t=0)
BASELINE_DAYS = 60      # length of the "normal" window
BASELINE_GAP = 5        # skip t-5..t-1 so pre-event run-up does not pollute the baseline
CAR_DAYS = 5            # cumulative abnormal return over t0..t+5
SPREAD_NORMAL_TOL = 1.2 # spread counts as "back to normal" at <= 1.2 x baseline

# Xetra session (local Frankfurt time)
XETRA_OPEN = "09:00"
XETRA_CLOSE_AUCTION = "17:35"
TZ = "Europe/Berlin"

# Xetra Designated Sponsor thresholds (Being Public Guide, p. 32)
DS_XLM_MAX_BPS = 100       # XLM (EUR 25k order) <= 100 bps ...
DS_TURNOVER_MIN_EUR = 2.5e6  # ... and avg daily order book turnover >= EUR 2.5m -> category A
DS_LOOKBACK_DAYS = 84      # ~4 months

# Anomaly thresholds
ANOMALY_Z = 3.0

# Liquidity trend (engine/baseline.py): a change of more than +-10% in XLM or turnover counts as a move
LIQUIDITY_TREND_TOL = 0.10

# Same-type comparison (engine/compare.py): smallest group worth a percentile
COMPARE_MIN_GROUP = 5

# Peer groups (engine/compare.py peer_group): market cap is not in the data, so "size" is a
# peers: every benchmark (web, Streamlit, report, assistant) = median over the peers of each stock's median
# over the last PEER_DAYS trading days (engine.compare.peer_medians). Size = the SIZE_PEERS_N stocks with the
# closest median turnover (market cap is not in the data).
PEER_DAYS = 60
SIZE_PEERS_N = 10
# turnover cohort (terciles, kept for size_cohort()); no longer the size peer group.
SIZE_COHORT_DAYS = 60
SIZE_COHORT_LABELS = ("large", "mid", "small")   # top / middle / bottom third by turnover
MIN_PEER_GROUP = 3                               # fewer peers -> flag "small_peer_group"

# Market context of unusual days (engine/baseline.py context_frame): a day is "market-wide" when at least
# MARKET_WIDE_SHARE of all stocks trade more than MARKET_WIDE_VOL_RATIO x their normal turnover
MARKET_WIDE_VOL_RATIO = 2.0
MARKET_WIDE_SHARE = 0.25

# News onset detection (engine/onset.py): first minute where price AND volume break from normal
ONSET_PRICE_K = 2.0               # |move vs previous close| >= 2 x daily return std (baseline)
ONSET_VOLUME_K = 3.0              # cumulative turnover >= 3 x normal for the time of day
ONSET_MIN_TURNOVER_SHARE = 0.01   # ... and >= 1% of a normal day's turnover (ignores single odd prints)
ONSET_PERSIST_MIN = 5             # price still beyond the threshold 5 minutes later
ONSET_OPEN_WINDOW_MIN = 15        # break within the first 15 min of trading -> news was out before the open
