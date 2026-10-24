"""Turn collected news into the numeric X matrix: one row per forecast cutoff.

    python scripts/build_news_matrix.py                  # all sessions with news
    python scripts/build_news_matrix.py --components 16  # smaller text matrix

Output:
  data/processed/news_matrix.csv   session × [counts, tone, event types, txt_svd_00..k]
  data/processed/news_terms.json   the words behind each txt_svd dimension

The vocabulary and SVD are fitted on the first 80% of sessions only, the same
split the model uses, so test-period words never shape the matrix.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gfe.calendar_features import build_calendar_features  # noqa: E402
from gfe.text_features import TextMatrix, aggregate_windows, assign_windows  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="data/raw/events.csv")
    ap.add_argument("--components", type=int, default=32)
    ap.add_argument("--test-frac", type=float, default=0.20)
    a = ap.parse_args()

    ev = pd.read_csv(a.events)
    ev["available_at_utc"] = pd.to_datetime(ev["available_at_utc"], utc=True, format="ISO8601")
    start = (ev["available_at_utc"].min() - pd.Timedelta(days=1)).tz_convert("America/New_York").strftime("%Y-%m-%d")
    now = pd.Timestamp.now(tz="UTC")
    end = (now + pd.Timedelta(days=7)).tz_convert("America/New_York").strftime("%Y-%m-%d")
    cal = build_calendar_features(start, end)
    cutoffs = cal["cutoff_utc"][cal["cutoff_utc"] <= now]   # news after the last passed cutoff waits for the next one

    w = assign_windows(ev, cutoffs)
    counts = aggregate_windows(w, cutoffs)
    sessions = counts.index[counts["news_n_items"].cumsum() > 0]      # from the first session with news
    counts = counts.loc[sessions]

    dev_end = sessions[max(int(np.floor(len(sessions) * (1 - a.test_frac))) - 1, 0)]
    train_items = w[w["session"] <= dev_end]
    k = min(a.components, max(2, len(train_items) // 10))
    tm = TextMatrix(n_components=k, min_df=2 if len(train_items) < 500 else 3).fit(train_items)
    txt = tm.transform_windows(w, sessions)

    X = counts.join(txt)
    X.insert(0, "cutoff_utc", cutoffs.loc[sessions])
    out = ROOT / "data/processed"
    out.mkdir(parents=True, exist_ok=True)
    X.to_csv(out / "news_matrix.csv")
    (out / "news_terms.json").write_text(json.dumps(tm.top_terms(), indent=1))

    print(f"news matrix: {X.shape[0]} sessions × {X.shape[1] - 1} columns  ({sessions[0].date()} .. {sessions[-1].date()})")
    print(f"text vocabulary fitted on {len(train_items)} items up to {dev_end.date()}  ({k} dimensions)")
    for name, words in list(tm.top_terms(6).items())[:6]:
        print(f"  {name}: {', '.join(words)}")
    if X.shape[0] < 60:
        print(f"\nnote: only {X.shape[0]} sessions of news so far. Run the collector backfill for more history "
              "before reading anything into model results.")
