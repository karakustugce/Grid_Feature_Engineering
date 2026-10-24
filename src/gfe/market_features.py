"""Price and cross-asset features observable at the session-t cutoff.

All inputs are daily bars indexed by exchange session. Everything here uses
data up to and including session t, never t+1. Tomorrow's gold price is
unknown; today's gold return is known and eligible.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def own_price_features(px: pd.DataFrame, prefix: str = "aapl") -> pd.DataFrame:
    """px: columns open, high, low, close, volume (split-adjusted)."""
    c = px["close"]
    lr = np.log(c).diff()
    f = pd.DataFrame(index=px.index)
    f[f"{prefix}_close"] = c
    f[f"{prefix}_ret_1"] = lr
    f[f"{prefix}_ret_5"] = np.log(c / c.shift(5))
    f[f"{prefix}_ret_20"] = np.log(c / c.shift(20))
    # Volatility clustering: big moves follow big moves (GARCH intuition).
    f[f"{prefix}_vol_5"] = lr.rolling(5).std()
    f[f"{prefix}_vol_20"] = lr.rolling(20).std()
    f[f"{prefix}_vol_ratio"] = f[f"{prefix}_vol_5"] / f[f"{prefix}_vol_20"]
    # Overnight gap = information that arrived while the market was closed.
    f[f"{prefix}_overnight_gap"] = np.log(px["open"] / c.shift(1))
    f[f"{prefix}_intraday_ret"] = np.log(c / px["open"])
    f[f"{prefix}_range"] = np.log(px["high"] / px["low"])
    # Where the close sits inside the day's range (buying vs selling pressure).
    rng = (px["high"] - px["low"]).replace(0, np.nan)
    f[f"{prefix}_close_loc"] = (c - px["low"]) / rng
    # Attention / liquidity shock.
    lv = np.log(px["volume"].replace(0, np.nan))
    f[f"{prefix}_volume_z"] = (lv - lv.rolling(20).mean()) / lv.rolling(20).std()
    # Short-term reversal vs medium-term momentum.
    f[f"{prefix}_dist_ma20"] = np.log(c / c.rolling(20).mean())
    f[f"{prefix}_dist_ma50"] = np.log(c / c.rolling(50).mean())
    f[f"{prefix}_dist_52w_high"] = np.log(c / c.rolling(252, min_periods=60).max())
    return f


def context_features(ctx: dict[str, pd.Series], index: pd.Index) -> pd.DataFrame:
    """ctx: name -> close series (SPY, QQQ, XLK, VIX, GOLD, DXY, US10Y, OIL ...).

    Series are forward-filled onto exchange sessions (an asset that did not
    trade today keeps its last known value). Levels are kept for VIX and yields,
    returns for priced assets.
    """
    out = pd.DataFrame(index=index)
    level_like = {"vix", "us10y", "us2y", "us3m"}
    for name, s in ctx.items():
        s = s.reindex(index.union(s.index)).sort_index().ffill().reindex(index)
        key = name.lower()
        if key in level_like:
            out[f"{key}_level"] = s
            out[f"{key}_chg_1"] = s.diff()
            out[f"{key}_chg_5"] = s.diff(5)
        else:
            out[f"{key}_ret_1"] = np.log(s).diff()
            out[f"{key}_ret_5"] = np.log(s / s.shift(5))
    if {"us10y", "us2y"} <= set(ctx):
        out["curve_10y_2y"] = out["us10y_level"] - out["us2y_level"]
    if "spy_ret_1" in out:
        return out
    return out


def relative_features(own: pd.DataFrame, ctx: pd.DataFrame, prefix: str = "aapl") -> pd.DataFrame:
    """Idiosyncratic move = own return minus market; rolling beta to SPY/QQQ."""
    out = pd.DataFrame(index=own.index)
    for mkt in ["spy", "qqq", "xlk"]:
        col = f"{mkt}_ret_1"
        if col not in ctx:
            continue
        r, m = own[f"{prefix}_ret_1"], ctx[col]
        beta = r.rolling(60).cov(m) / m.rolling(60).var()
        out[f"beta_{mkt}_60"] = beta
        out[f"idio_ret_{mkt}"] = r - beta * m
    return out


def target(px: pd.DataFrame) -> pd.DataFrame:
    """Next-session log return and close. Row t holds information about t+1."""
    c = px["close"]
    return pd.DataFrame({"y_logret": np.log(c.shift(-1) / c), "y_close": c.shift(-1)}, index=px.index)
