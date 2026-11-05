"""Download the CBN data feeds used in this project and save them, dated, to data/raw/.

The CBN feeds are undocumented JSON endpoints, so they can change without notice.
Every value comes back as text. This script saves the raw JSON exactly as received;
cleaning happens in clean.py. Raw files are never edited by hand.

If a feed fails, the script stops with an error. It never falls back to made-up data.

Run from the project root:  python src/fetch_cbn.py
"""

from datetime import date
from pathlib import Path
import json

import requests

BASE_URL = "https://www.cbn.gov.ng/api/"
FEEDS = {
    "money_market": "GetAllMoneyMarketIndicators",
    "money_credit": "GetAllMoneyAndCreditStats",
    "inflation": "GetAllInflationRates",
}

# Some servers refuse requests that don't look like they come from a web browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
}

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def fetch_feed(endpoint):
    """Download one CBN feed and return the parsed JSON (a list of records)."""
    response = requests.get(BASE_URL + endpoint, headers=HEADERS, timeout=180)
    response.raise_for_status()
    records = response.json()
    if not isinstance(records, list) or not records:
        raise ValueError(f"{endpoint} returned no records")
    return records


def fetch_all(pull_date=None):
    """Download every feed and save it as data/raw/<name>_<YYYY-MM-DD>.json."""
    pull_date = pull_date or date.today().isoformat()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    saved = {}
    for name, endpoint in FEEDS.items():
        records = fetch_feed(endpoint)
        path = RAW_DIR / f"{name}_{pull_date}.json"
        path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        saved[name] = path
        print(f"{endpoint}: {len(records)} records -> {path.name}")
    return saved


def latest_raw(name):
    """Path of the most recent raw pull for one feed (by the date in the filename)."""
    files = sorted(RAW_DIR.glob(f"{name}_*.json"))
    if not files:
        raise FileNotFoundError(f"No raw pull for '{name}' in {RAW_DIR}. Run src/fetch_cbn.py first.")
    return files[-1]


if __name__ == "__main__":
    fetch_all()
