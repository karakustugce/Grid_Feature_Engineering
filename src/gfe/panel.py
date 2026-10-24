"""Assemble one row per cutoff session from all feature families."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .calendar_features import build_calendar_features, add_scheduled_events
from .market_features import own_price_features, context_features, relative_features, target
from .text_features import assign_windows, aggregate_windows, TextMatrix

FEATURE_GROUPS_ORDER = ["price", "calendar", "scheduled", "market", "news_counts", "news_text"]


def build_panel(px: pd.DataFrame, ctx: dict[str, pd.Series] | None = None,
                events: pd.DataFrame | None = None, scheduled: pd.DataFrame | None = None,
                n_text_components: int = 32, test_frac: float = 0.20,
                news_period_only: bool = True):
    px = px.sort_index()
    start, end = px.index.min().strftime("%Y-%m-%d"), px.index.max().strftime("%Y-%m-%d")
    cal = build_calendar_features(start, end)
    cal = cal.loc[cal.index.intersection(px.index)]
    groups: dict[str, list[str]] = {}

    own = own_price_features(px).reindex(cal.index)
    groups["price"] = list(own.columns.drop("aapl_close"))
    cal_cols = [c for c in cal.columns if c not in ("target_session", "cutoff_utc")]
    groups["calendar"] = cal_cols
    parts = [cal, own]

    if scheduled is not None and len(scheduled):
        sch = add_scheduled_events(cal[["target_session", "cutoff_utc"]], scheduled)
        sch = sch.drop(columns=["target_session", "cutoff_utc"])
        groups["scheduled"] = list(sch.columns)
        parts.append(sch)

    if ctx:
        cx = context_features(ctx, cal.index)
        rel = relative_features(own, cx)
        groups["market"] = list(cx.columns) + list(rel.columns)
        parts += [cx, rel]

    panel = pd.concat(parts, axis=1)
    panel = panel.join(target(px).reindex(cal.index))
    # Sanity: the target must be the close of the session the calendar says is next.
    nxt_close = px["close"].reindex(pd.DatetimeIndex(panel["target_session"])).values
    ok = ~np.isnan(nxt_close)
    assert np.allclose(nxt_close[ok], panel["y_close"].values[ok], equal_nan=True), "target misaligned"

    text_info = {}
    if events is not None and len(events):
        ev = assign_windows(events, panel["cutoff_utc"])
        counts = aggregate_windows(ev, panel["cutoff_utc"])
        groups["news_counts"] = list(counts.columns)
        panel = panel.join(counts)
        if news_period_only:
            # Before collection started every news column is 0, which the model would read as
            # "no news". Keep only sessions from the first one that has collected news.
            first = panel.index[panel["news_n_items"].fillna(0).cumsum() > 0]
            if len(first):
                panel = panel.loc[first[0]:]
        # Text matrix: fit vocabulary + SVD on development-period items ONLY.
        usable = panel.dropna(subset=["y_logret"])
        dev_end = usable.index[int(np.floor(len(usable) * (1 - test_frac))) - 1]
        ev_train = ev[ev["session"] <= dev_end]
        if len(ev_train) >= 50:
            tm = TextMatrix(n_components=n_text_components).fit(ev_train)
            txt = tm.transform_windows(ev, panel.index)
            groups["news_text"] = list(txt.columns)
            panel = panel.join(txt)
            text_info = {"fitted_until": str(dev_end.date()), "n_train_items": len(ev_train), "top_terms": tm.top_terms()}
    return panel, groups, text_info
