"""Download collected news from Supabase into data/raw/events.csv.

    python scripts/export_events.py

Reads the public read-only view public.aapl_events_export (rejected rows are
already excluded). Uses the publishable key, which can read but never write.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
import requests

URL = os.environ.get("SUPABASE_URL", "https://zrqquefqdzdqnflirowm.supabase.co")
KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_4993_ZaGw10laI3qei1STQ_AZl4XH-N")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw/events.csv")
    ap.add_argument("--live-only", action="store_true", help="drop backfilled rows (availability not observed live)")
    a = ap.parse_args()

    rows, page = [], 1000
    while True:
        r = requests.get(f"{URL}/rest/v1/aapl_events_export",
                         params={"select": "*", "order": "available_at_utc.asc", "offset": len(rows), "limit": page},
                         headers={"apikey": KEY}, timeout=60)
        r.raise_for_status()
        batch = r.json()
        rows += batch
        if len(batch) < page:
            break

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("No events yet. Run the collector first.")
    if a.live_only:
        df = df[df["availability_basis"] == "observed"]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    by = df.groupby("source").size().to_dict()
    print(f"{len(df)} events -> {out}  ({df['available_at_utc'].min()[:16]} .. {df['available_at_utc'].max()[:16]})  {by}")
    print(f"labeled by agent: {df['sentiment'].notna().mean():.0%}   backfilled: {(df['availability_basis'] != 'observed').mean():.0%}")
