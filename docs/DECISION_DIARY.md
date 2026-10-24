# One-week economic decision diary

Purpose: log real decisions, name the economic mechanism behind each, and turn the mechanism into a **market-level, time-stamped** variable that could plausibly move Apple's share price. The diary produces hypotheses; the dataset gets the proxies.

Fill `data/decision_diary.csv` (one row per decision). Write the row when you decide, not at night: hindsight changes what you think you knew.

| Column | What to write |
|---|---|
| `logged_at_local` | Date and time, Istanbul time |
| `decision` | What you chose ("took the bus instead of a taxi") |
| `alternatives` | What you gave up (opportunity cost) |
| `constraint` | Budget, time, information, habit |
| `price_signal` | Which price or cost changed your choice, if any |
| `expectation` | What you expected about the future (inflation, income, risk) |
| `mechanism` | substitution · income effect · opportunity cost · risk aversion · intertemporal choice · network effect · switching cost · signaling · loss aversion · information asymmetry |
| `apple_channel` | How the same mechanism, summed over millions of people, reaches AAPL: iPhone demand, services spending, upgrade cycle length, switching costs, China demand, discount rate |
| `market_proxy` | A public series that measures it at market scale (Michigan consumer sentiment, retail sales, CPI electronics, USD/TRY, 10Y yield, App Store revenue estimates) |
| `proxy_known_at` | When that series is published; it becomes an X variable only from that timestamp |

Example row:

| logged_at_local | decision | mechanism | apple_channel | market_proxy | proxy_known_at |
|---|---|---|---|---|---|
| 2026-10-26 13:10 | Kept my old phone another year | intertemporal choice, income effect | longer iPhone upgrade cycle | Michigan consumer sentiment; carrier upgrade rates in earnings calls | sentiment: preliminary release, 2nd Friday of the month, 10:00 ET |

At the end of the week, group rows by `mechanism`. Each mechanism that maps to a published, time-stamped `market_proxy` becomes a candidate column in `docs/FEATURE_CATALOG.md` and enters the ablation like any other group.
