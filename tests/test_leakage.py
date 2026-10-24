"""Guards against the two failure modes that make backtests look too good:
using information after the cutoff, and fitting anything on the test period."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gfe.calendar_features import build_calendar_features, add_scheduled_events  # noqa: E402
from gfe.text_features import assign_windows  # noqa: E402
from gfe.modeling import chrono_split  # noqa: E402


def test_target_is_next_exchange_session():
    cal = build_calendar_features("2026-11-20", "2026-11-30")
    # Thanksgiving 2026-11-26 is closed: Wednesday's target is Friday (early close).
    assert cal.loc["2026-11-25", "target_session"] == pd.Timestamp("2026-11-27")
    assert cal.loc["2026-11-25", "gap_calendar_days"] == 2
    assert cal.loc["2026-11-25", "tgt_is_early_close"] == 1
    # Friday -> Monday is a weekend gap.
    assert cal.loc["2026-11-20", "gap_calendar_days"] == 3
    assert cal.loc["2026-11-20", "tgt_dow_mon"] == 1


def test_cutoff_respects_early_close():
    cal = build_calendar_features("2026-11-27", "2026-11-27")
    # Early close 13:00 ET = 18:00 UTC, cutoff 15 min later.
    assert cal.loc["2026-11-27", "cutoff_utc"] == pd.Timestamp("2026-11-27 18:15", tz="UTC")


def test_news_after_cutoff_moves_to_next_window():
    cal = build_calendar_features("2026-10-19", "2026-10-23")
    c = cal["cutoff_utc"]
    ev = pd.DataFrame({
        "available_at_utc": [c.iloc[0] - pd.Timedelta(minutes=1), c.iloc[0] + pd.Timedelta(minutes=1)],
        "title": ["before", "after"],
    })
    out = assign_windows(ev, c)
    assert out.loc[0, "session"] == c.index[0]
    assert out.loc[1, "session"] == c.index[1]


def test_unannounced_event_is_invisible():
    cal = build_calendar_features("2025-08-20", "2025-09-10")
    ev = pd.DataFrame([{"event_type": "apple_event", "event_time_utc": "2025-09-09T17:00:00Z",
                        "announced_at_utc": "2025-08-26T17:00:00Z", "timing": "intraday"}])
    out = add_scheduled_events(cal, ev)
    assert out.loc["2025-08-21", "days_to_apple_event"] == 60       # not announced yet
    assert out.loc["2025-08-27", "days_to_apple_event"] < 60         # announced
    assert out.loc["2025-09-08", "tgt_is_apple_event_reaction"] == 1


def test_amc_earnings_react_next_session():
    cal = build_calendar_features("2025-10-27", "2025-11-05")
    ev = pd.DataFrame([{"event_type": "earnings", "event_time_utc": "2025-10-30T20:30:00Z",
                        "announced_at_utc": "2025-10-01T12:00:00Z", "timing": "amc"}])
    out = add_scheduled_events(cal, ev)
    # Reported Thursday after the close -> the market reacts Friday -> flagged on Thursday's row.
    assert out.loc["2025-10-30", "tgt_is_earnings_reaction"] == 1
    assert out.loc["2025-10-29", "tgt_is_earnings_reaction"] == 0


def test_split_is_chronological():
    df = pd.DataFrame({"x": np.arange(100)}, index=pd.date_range("2020-01-01", periods=100))
    dev, test = chrono_split(df)
    assert dev.index.max() < test.index.min()
    assert len(test) == 20
