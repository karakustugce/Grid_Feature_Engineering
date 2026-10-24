"""Download daily bars for AAPL and context assets into data/raw/market/.

Run locally (needs internet):  python scripts/fetch_market_data.py --start 2015-01-01
yfinance is convenient for research but unofficial; record the pull date and
re-pull before any final result. Closes are split-adjusted (auto_adjust=True).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

TICKERS = {
    "AAPL": "aapl",
    "SPY": "spy", "QQQ": "qqq", "XLK": "xlk",      # market and tech sector
    "^VIX": "vix",                                  # implied volatility (fear)
    "GC=F": "gold", "CL=F": "oil",                  # safe haven, energy cost
    "DX-Y.NYB": "dxy",                              # dollar: ~60% of Apple revenue is outside the US
    "^TNX": "us10y", "^IRX": "us3m",                # discount rate for long-duration cash flows
    "TSM": "tsm", "SOXX": "soxx",                   # supply chain / semis
    "CNY=X": "usdcny",                              # China: market + manufacturing exposure
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--out", default="data/raw/market")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pulled = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    for tk, name in TICKERS.items():
        df = yf.download(tk, start=a.start, auto_adjust=True, progress=False)
        if df.empty:
            print(f"!! {tk}: no data")
            continue
        df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
        df.index.name = "date"
        df["pulled_at_utc"] = pulled
        df.to_csv(out / f"{name}.csv")
        print(f"{tk:10s} -> {name}.csv  {df.index.min().date()}..{df.index.max().date()}  rows={len(df)}")
