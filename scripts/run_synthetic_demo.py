"""End-to-end mechanics test on SYNTHETIC data.

This is not a result about Apple. It plants a known news effect in fake
prices and checks that the pipeline (windows -> text matrix -> 80/20 split ->
ridge / small MLP) can recover it without leaking the future.

    python scripts/run_synthetic_demo.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gfe.calendar_features import sessions, cutoff_utc  # noqa: E402
from gfe.panel import build_panel, FEATURE_GROUPS_ORDER  # noqa: E402
from gfe.modeling import run_ablation  # noqa: E402
from gfe.report import write_report  # noqa: E402

rng = np.random.default_rng(7)
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)

s = sessions("2018-01-02", "2026-09-30")[:-1]
s = s[s <= "2026-09-30"]
n = len(s)

POS = ["record iphone demand beats estimates", "services revenue growth strong", "analyst upgrade price target raised",
       "new product launch event announced", "buyback expanded dividend increase"]
NEG = ["antitrust lawsuit filed regulators", "supply chain disruption factory shutdown", "tariff on china imports raised",
       "analyst downgrade weak demand", "app store fine european commission"]
NEU = ["apple executive interview conference", "apple stores holiday hours", "iphone case accessories review",
       "apple tv show premiere date", "developer beta released"]

events, effect = [], np.zeros(n)
for i, sess in enumerate(s[:-1]):
    c_prev = cutoff_utc(s[i - 1]) if i else cutoff_utc(sess) - pd.Timedelta(hours=24)
    c_now = cutoff_utc(sess)
    k = rng.poisson(6)
    for _ in range(k):
        kind = rng.choice(["pos", "neg", "neu"], p=[0.15, 0.15, 0.70])
        txt = rng.choice({"pos": POS, "neg": NEG, "neu": NEU}[kind])
        t = c_prev + (c_now - c_prev) * rng.uniform(0.01, 1.0)
        events.append({"available_at_utc": t, "title": f"Apple {txt}", "source": "gdelt",
                       "source_domain": f"site{rng.integers(40)}.com"})
        effect[i] += {"pos": 0.004, "neg": -0.005, "neu": 0.0}[kind]
ev = pd.DataFrame(events)

# Planted calendar effect: target sessions after a weekend are a bit riskier/negative.
gap = np.append((s[1:] - s[:-1]).days, 1)
r_next = 0.0004 + effect - 0.0008 * (gap > 1) + rng.standard_t(4, n) * 0.011
close = 150 * np.exp(np.cumsum(np.concatenate([[0], r_next[:-1]])))
px = pd.DataFrame(index=s)
px["close"] = close
px["open"] = close * np.exp(rng.normal(0, 0.004, n))
px["high"] = np.maximum(px["open"], px["close"]) * np.exp(np.abs(rng.normal(0, 0.006, n)))
px["low"] = np.minimum(px["open"], px["close"]) * np.exp(-np.abs(rng.normal(0, 0.006, n)))
px["volume"] = rng.lognormal(18, 0.3, n)

panel, groups, text_info = build_panel(px, events=ev, n_text_components=16)
res, dev, test = run_ablation(panel, groups, [g for g in FEATURE_GROUPS_ORDER if g in groups])
pd.set_option("display.width", 160)
print(f"rows={len(panel)} dev={len(dev)} ({dev.index[0].date()}..{dev.index[-1].date()}) "
      f"test={len(test)} ({test.index[0].date()}..{test.index[-1].date()})")
print(f"text matrix fitted on items up to {text_info['fitted_until']} ({text_info['n_train_items']} items)")
print(res[["model", "n_features", "mae_usd", "mae_vs_persistence_pct", "dir_acc"]].round(4).to_string(index=False))
res.to_csv(OUT / "synthetic_ablation.csv", index=False)
print("report:", write_report(res, dev, test, groups, text_info, OUT / "synthetic_report.html",
                              title="Synthetic data (pipeline check)",
                              data_note="Synthetic prices with a planted news effect; not a result about Apple."))
(OUT / "synthetic_text_terms.json").write_text(json.dumps(text_info["top_terms"], indent=1))
