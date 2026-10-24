"""Calendar and scheduled-event features that are known at the forecast cutoff.

Every row is indexed by the *cutoff session* t (cutoff = 16:15 America/New_York
after session t closes). The target is the close of the next exchange session.
The exchange calendar is published in advance, so everything about session
t+1's date (weekday, holiday gap, month position, option expiry) is legitimately
known at the cutoff. Scheduled events (earnings, product launches, FOMC, CPI)
are only usable if their *announcement* happened before the cutoff.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import exchange_calendars as xcals

NY = "America/New_York"


def sessions(start: str, end: str, exchange: str = "XNYS") -> pd.DatetimeIndex:
    """Trading sessions, padded so every session in range has a next session."""
    cal = xcals.get_calendar(exchange)
    pad_end = (pd.Timestamp(end) + pd.Timedelta(days=15)).strftime("%Y-%m-%d")
    pad_end = min(pd.Timestamp(pad_end), cal.last_session).strftime("%Y-%m-%d")
    return cal.sessions_in_range(start, pad_end)


def cutoff_utc(session: pd.Timestamp, minutes_after_close: int = 15, exchange: str = "XNYS") -> pd.Timestamp:
    cal = xcals.get_calendar(exchange)
    close = cal.session_close(session)  # handles early closes, tz-aware UTC
    return close + pd.Timedelta(minutes=minutes_after_close)


def _third_friday(year: int, month: int) -> pd.Timestamp:
    first = pd.Timestamp(year=year, month=month, day=1)
    offset = (4 - first.weekday()) % 7
    return first + pd.Timedelta(days=offset + 14)


def build_calendar_features(start: str, end: str, exchange: str = "XNYS") -> pd.DataFrame:
    cal = xcals.get_calendar(exchange)
    s = sessions(start, end, exchange)
    df = pd.DataFrame(index=s[:-1])
    df.index.name = "session"
    nxt = s[1:]
    df["target_session"] = nxt
    df["cutoff_utc"] = [cutoff_utc(x, exchange=exchange) for x in df.index]

    t = pd.DatetimeIndex(df["target_session"])
    # 1. Weekday of the target session (Monday effect, Friday effect).
    for i, name in enumerate(["mon", "tue", "wed", "thu", "fri"]):
        df[f"tgt_dow_{name}"] = (t.weekday == i).astype(int)

    # 2. Closed-market gap: weekends and holidays let news and risk accumulate
    #    while nobody can trade (the "events break out on the weekend" idea).
    gap = (t - df.index).days
    df["gap_calendar_days"] = gap
    df["gap_is_weekend_or_holiday"] = (gap > 1).astype(int)
    df["gap_is_long_weekend"] = (gap > 3).astype(int)

    # 3. Week and month position of the target session.
    s_series = pd.Series(s, index=s)
    week_key = s_series.dt.isocalendar().week.astype(str) + "-" + s_series.dt.isocalendar().year.astype(str)
    month_key = s_series.dt.to_period("M")
    first_of_week = ~week_key.duplicated(keep="first")
    last_of_week = ~week_key.duplicated(keep="last")
    first_of_month = ~month_key.duplicated(keep="first")
    last_of_month = ~month_key.duplicated(keep="last")
    sess_in_month = s_series.groupby(month_key).cumcount() + 1
    sess_left = s_series.groupby(month_key).cumcount(ascending=False)

    df["tgt_first_session_of_week"] = first_of_week.loc[t].values.astype(int)
    df["tgt_last_session_of_week"] = last_of_week.loc[t].values.astype(int)
    df["tgt_first_session_of_month"] = first_of_month.loc[t].values.astype(int)
    df["tgt_last_session_of_month"] = last_of_month.loc[t].values.astype(int)
    df["tgt_session_in_month"] = sess_in_month.loc[t].values
    df["tgt_sessions_left_in_month"] = sess_left.loc[t].values
    # Turn-of-month window: last session + first three sessions (pension/salary flows).
    df["tgt_turn_of_month"] = ((df["tgt_sessions_left_in_month"] == 0) | (df["tgt_session_in_month"] <= 3)).astype(int)

    # 4. Cyclical encodings so day 31 sits next to day 1, December next to January.
    dom = t.day
    df["tgt_dom_sin"] = np.sin(2 * np.pi * dom / 31)
    df["tgt_dom_cos"] = np.cos(2 * np.pi * dom / 31)
    df["tgt_month_sin"] = np.sin(2 * np.pi * t.month / 12)
    df["tgt_month_cos"] = np.cos(2 * np.pi * t.month / 12)
    df["tgt_is_september"] = (t.month == 9).astype(int)
    # Quarter-end window dressing by fund managers.
    df["tgt_quarter_end_window"] = ((t.month % 3 == 0) & (df["tgt_sessions_left_in_month"] <= 2)).astype(int)
    df["tgt_january_first_week"] = ((t.month == 1) & (dom <= 7)).astype(int)

    # 5. Option expiry: hedging and pinning flows around the third Friday;
    #    quad witching in Mar/Jun/Sep/Dec.
    third_fridays = {(y, m): _third_friday(y, m) for y in range(t.year.min(), t.year.max() + 1) for m in range(1, 13)}
    opex = []
    for x in t:
        tf = third_fridays[(x.year, x.month)]
        # If the third Friday is a holiday, expiry moves to the prior session.
        if tf not in s:
            prior = s[s < tf]
            tf = prior[-1] if len(prior) else tf
        opex.append(x == tf)
    df["tgt_is_monthly_opex"] = np.array(opex, dtype=int)
    df["tgt_is_quad_witching"] = (df["tgt_is_monthly_opex"].astype(bool) & (t.month % 3 == 0)).astype(int)

    # 6. Holidays and early closes (pre-holiday effect, thin liquidity).
    after_target = s[2:]
    after_gap = np.append((after_target - t[: len(after_target)]).days, [np.nan] * (len(t) - len(after_target)))
    df["tgt_is_pre_holiday"] = ((after_gap > 1) & (pd.Series(t.weekday).values != 4)).astype(int)
    df["tgt_is_post_holiday"] = ((gap > 1) & (t.weekday != 0)).astype(int)
    early = set(cal.early_closes) if hasattr(cal, "early_closes") else set()
    df["tgt_is_early_close"] = [int(x in early) for x in t]

    return df.loc[: pd.Timestamp(end)]


def add_scheduled_events(cal_df: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Add distance-to-event features using only events announced by the cutoff.

    events columns: event_type, event_time_utc (when it happens),
    announced_at_utc (when the date became public), timing ('bmo','amc','intraday').
    An 'amc' (after market close) event on session t is reacted to on session t+1.
    """
    out = cal_df.copy()
    ev = events.copy()
    for col in ["event_time_utc", "announced_at_utc"]:
        ev[col] = pd.to_datetime(ev[col], utc=True)
    cal = xcals.get_calendar("XNYS")
    local_day = ev["event_time_utc"].dt.tz_convert(NY).dt.normalize().dt.tz_localize(None)
    reaction = []
    for day, timing in zip(local_day, ev["timing"]):
        sess = cal.date_to_session(day, direction="next")
        if timing == "amc" and sess == day:
            sess = cal.next_session(sess)
        reaction.append(sess)
    ev["reaction_session"] = pd.DatetimeIndex(reaction)

    for etype, grp in ev.groupby("event_type"):
        days_to, is_next = [], []
        for sess, row in out.iterrows():
            known = grp[grp["announced_at_utc"] <= row["cutoff_utc"]]
            future = known[known["reaction_session"] >= row["target_session"]]
            if future.empty:
                days_to.append(np.nan)
                is_next.append(0)
                continue
            d = (future["reaction_session"].min() - row["target_session"]).days
            days_to.append(d)
            is_next.append(int(d == 0))
        out[f"days_to_{etype}"] = np.clip(days_to, 0, 60)
        out[f"days_to_{etype}"] = out[f"days_to_{etype}"].fillna(60)  # 60 = "nothing scheduled"
        out[f"tgt_is_{etype}_reaction"] = is_next
        out[f"{etype}_within_5d"] = (out[f"days_to_{etype}"] <= 7).astype(int)
    return out
