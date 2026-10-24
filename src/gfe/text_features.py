"""Turn time-stamped news/posts into cutoff-aligned X variables.

Two layers:
1. Structured aggregates per news window (counts, source diversity, abnormal
   attention, closed-market share, agent labels if present). Interpretable.
2. A text matrix: TF-IDF -> TruncatedSVD (LSA) vectors per item, averaged per
   window. The vocabulary and SVD are fitted on training-period items only.

News window for cutoff c_t is (c_{t-1}, c_t]. Weekend/holiday windows are
longer, so window length is a feature of its own.
"""
from __future__ import annotations

import hashlib
import re

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

NY = "America/New_York"


def assign_windows(events: pd.DataFrame, cutoffs: pd.Series) -> pd.DataFrame:
    """Attach each event to the first cutoff at or after its available_at_utc.

    cutoffs: Series indexed by session with tz-aware UTC cutoff timestamps.
    Events available after the last cutoff are dropped (future for this panel).
    """
    ev = events.copy()
    ev["available_at_utc"] = pd.to_datetime(ev["available_at_utc"], utc=True)
    c = pd.to_datetime(cutoffs, utc=True).sort_values()
    cvals = pd.DatetimeIndex(c.array)
    if cvals.tz is None:
        cvals = cvals.tz_localize("UTC")
    pos = cvals.searchsorted(pd.DatetimeIndex(ev["available_at_utc"]), side="left")
    keep = pos < len(c)
    ev = ev.loc[keep].copy()
    ev["session"] = c.index[pos[keep]]
    ev["cutoff_utc"] = cvals[pos[keep]]
    assert (ev["available_at_utc"] <= ev["cutoff_utc"]).all(), "leakage: event after its cutoff"
    return ev


def dedup_cluster(ev: pd.DataFrame) -> pd.Series:
    """Cheap story cluster: normalized title hash. Replace with embedding clusters later."""
    def norm(t: str) -> str:
        t = re.sub(r"\s[-|–]\s[^-|–]{2,40}$", "", str(t))  # strip " - Publisher"
        t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
        return " ".join(sorted(set(t.split())))
    return ev["title"].fillna("").map(lambda t: hashlib.md5(norm(t).encode()).hexdigest()[:12])


def aggregate_windows(ev: pd.DataFrame, cutoffs: pd.Series) -> pd.DataFrame:
    idx = cutoffs.index
    out = pd.DataFrame(index=idx)
    c = pd.to_datetime(cutoffs, utc=True)
    out["news_window_hours"] = c.diff().dt.total_seconds().div(3600).fillna(24.0)

    if "cluster" not in ev:
        ev = ev.assign(cluster=dedup_cluster(ev))
    g = ev.groupby("session")
    out["news_n_items"] = g.size().reindex(idx, fill_value=0)
    out["news_n_stories"] = g["cluster"].nunique().reindex(idx, fill_value=0)
    out["news_n_sources"] = g["source_domain"].nunique().reindex(idx, fill_value=0) if "source_domain" in ev else 0
    out["news_log_items"] = np.log1p(out["news_n_items"])
    out["news_stories_per_hour"] = out["news_n_stories"] / out["news_window_hours"]
    # Abnormal attention: today's story flow versus the trailing month.
    base = out["news_stories_per_hour"].shift(1).rolling(20, min_periods=5).mean()
    out["news_abnormal_flow"] = np.log1p(out["news_stories_per_hour"]) - np.log1p(base)
    out["news_has_any"] = (out["news_n_items"] > 0).astype(int)

    # Share of stories that arrived while the exchange was closed.
    local = ev["available_at_utc"].dt.tz_convert(NY)
    mins = local.dt.hour * 60 + local.dt.minute
    closed = (mins < 570) | (mins >= 960) | (local.dt.weekday >= 5)
    out["news_closed_market_share"] = closed.groupby(ev["session"]).mean().reindex(idx).fillna(0)

    # Primary sources are a different kind of signal than press coverage.
    if "source" in ev:
        for src in ["sec_edgar", "apple_newsroom"]:
            out[f"news_n_{src}"] = (ev["source"] == src).groupby(ev["session"]).sum().reindex(idx, fill_value=0)

    # Labels written by the n8n review agent (optional columns).
    if "sentiment" in ev:  # expected in [-1, 1]
        s = ev.groupby("session")["sentiment"]
        out["news_sent_mean"] = s.mean().reindex(idx).fillna(0)
        out["news_sent_neg_share"] = (ev["sentiment"] < -0.2).groupby(ev["session"]).mean().reindex(idx).fillna(0)
        out["news_sent_x_flow"] = out["news_sent_mean"] * np.log1p(out["news_n_stories"])
    if "event_type" in ev:
        for et in ["earnings", "product", "supply_chain", "regulation_legal", "macro_trade", "management"]:
            out[f"news_evt_{et}"] = (ev["event_type"] == et).groupby(ev["session"]).sum().reindex(idx, fill_value=0)
    return out


class TextMatrix:
    """TF-IDF -> SVD document vectors, mean-pooled per news window.

    Fit only on items whose cutoff falls inside the training period.
    """

    def __init__(self, n_components: int = 32, min_df: int = 3, max_features: int = 20000, seed: int = 0):
        self.vec = TfidfVectorizer(ngram_range=(1, 2), min_df=min_df, max_df=0.9, sublinear_tf=True,
                                   stop_words="english", max_features=max_features)
        self.svd = TruncatedSVD(n_components=n_components, random_state=seed)
        self.k = n_components

    @staticmethod
    def _text(ev: pd.DataFrame) -> pd.Series:
        body = ev["text_raw"] if "text_raw" in ev else ""
        return (ev["title"].fillna("") + ". " + pd.Series(body, index=ev.index).fillna("")).str.slice(0, 5000)

    def fit(self, ev_train: pd.DataFrame) -> "TextMatrix":
        X = self.vec.fit_transform(self._text(ev_train))
        k = min(self.k, X.shape[1] - 1, X.shape[0] - 1)
        if k < self.k:
            self.svd = TruncatedSVD(n_components=max(k, 1), random_state=0)
            self.k = max(k, 1)
        self.svd.fit(X)
        return self

    def transform_windows(self, ev: pd.DataFrame, index: pd.Index) -> pd.DataFrame:
        cols = [f"txt_svd_{i:02d}" for i in range(self.k)]
        if ev.empty:
            return pd.DataFrame(0.0, index=index, columns=cols)
        if "cluster" not in ev:
            ev = ev.assign(cluster=dedup_cluster(ev))
        one_per_story = ev.sort_values("available_at_utc").drop_duplicates(["session", "cluster"])
        Z = self.svd.transform(self.vec.transform(self._text(one_per_story)))
        Z = pd.DataFrame(Z, index=one_per_story.index, columns=cols)
        Z["session"] = one_per_story["session"].values
        pooled = Z.groupby("session")[cols].mean()
        return pooled.reindex(index).fillna(0.0)

    def top_terms(self, n: int = 8) -> dict[str, list[str]]:
        """What each latent dimension means; use this to name and audit them."""
        terms = np.array(self.vec.get_feature_names_out())
        return {f"txt_svd_{i:02d}": list(terms[np.argsort(-comp)[:n]]) for i, comp in enumerate(self.svd.components_)}
