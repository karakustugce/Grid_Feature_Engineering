"""Build the panel from real files and run the feature-family ablation.

    python scripts/fetch_market_data.py
    python scripts/run_real.py --events data/processed/events.csv --scheduled data/scheduled_events.csv

events.csv is the n8n export (one row per news item; needs available_at_utc,
title, source, source_domain; optional text_raw, sentiment, event_type).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gfe.panel import build_panel, FEATURE_GROUPS_ORDER  # noqa: E402
from gfe.modeling import run_ablation  # noqa: E402
from gfe.report import write_report  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="data/raw/market")
    ap.add_argument("--events", default=None)
    ap.add_argument("--scheduled", default="data/scheduled_events.csv")
    ap.add_argument("--no-mlp", action="store_true")
    ap.add_argument("--all-history", action="store_true",
                    help="keep sessions before news collection started (news columns are 0 there)")
    a = ap.parse_args()

    m = Path(a.market)
    read = lambda f: pd.read_csv(f, index_col="date", parse_dates=True)  # noqa: E731
    px = read(m / "aapl.csv")[["open", "high", "low", "close", "volume"]]
    ctx = {f.stem: read(f)["close"] for f in m.glob("*.csv") if f.stem != "aapl"}
    events = pd.read_csv(a.events) if a.events else None
    sched = pd.read_csv(a.scheduled) if a.scheduled and Path(a.scheduled).exists() else None
    if sched is not None:
        sched = sched[sched["verified"].astype(str).str.lower() == "true"]

    panel, groups, text_info = build_panel(px, ctx=ctx, events=events, scheduled=sched,
                                           news_period_only=not a.all_history)
    order = [g for g in FEATURE_GROUPS_ORDER if g in groups]
    res, dev, test = run_ablation(panel, groups, order, use_mlp=not a.no_mlp)

    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    panel.to_csv(out / "panel.csv")
    res.to_csv(out / "ablation.csv", index=False)
    (out / "feature_groups.json").write_text(json.dumps(groups, indent=1))
    if text_info:
        (out / "text_terms.json").write_text(json.dumps(text_info, indent=1, default=str))
    note = ""
    if events is not None and len(panel.dropna(subset=["y_logret"])) < 120:
        note = (f"Only {len(dev) + len(test)} sessions have news so far, so these scores are very noisy. "
                "Treat them as a pipeline check until the collector has months of history.")
    rp = write_report(res, dev, test, groups, text_info, out / "report.html", data_note=note)
    print(f"report: {rp}")
    print(f"dev {dev.index[0].date()}..{dev.index[-1].date()} ({len(dev)})  test {test.index[0].date()}..{test.index[-1].date()} ({len(test)})")
    print(res.round(4).to_string(index=False))

