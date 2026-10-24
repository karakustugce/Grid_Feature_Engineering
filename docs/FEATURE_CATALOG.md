# Feature catalog: X variables and their economic logic

Rule for every column: **can I know this value at 4:15 p.m. New York time on session t?** If not, it cannot be an X variable. Tomorrow's gold price fails the test; today's gold return passes. The date of a launch event passes only after Apple has sent the invitations.

The target is `y_logret = log(close[t+1] / close[t])`. The predicted close is `close[t] × exp(ŷ)`. Prices are non-stationary: with an 80/20 split, test prices sit above anything seen in training, so a model trained on price levels extrapolates badly. Returns are close to stationary. We still score in dollars (MAE).

Code lives in `src/gfe/`. Each group enters the model one at a time (`run_ablation`), and a group stays only if it lowers validation MAE versus the previous step.

## 1. Calendar (`calendar_features.py`) — always known in advance

| Column | Economic mechanism | Literature / note |
|---|---|---|
| `tgt_dow_mon … tgt_dow_fri` | Monday/weekend effect: negative news is often released after Friday's close; Friday positioning before the weekend | French (1980), Gibbons & Hess (1981). The effect has weakened since the 1990s; test it, don't assume it |
| `gap_calendar_days`, `gap_is_weekend_or_holiday`, `gap_is_long_weekend` | Information accumulates while trading is closed; inventory risk over the gap. This is the testable form of "conflicts often start on weekends" — we cannot know a war will start, but we know the market will be closed for 2–3 days | Holding a position over a closed market is riskier, which should show in variance more than in the mean |
| `tgt_first/last_session_of_week` | Holiday weeks shift which weekday opens/closes the week | Uses the real exchange calendar |
| `tgt_first/last_session_of_month`, `tgt_session_in_month`, `tgt_sessions_left_in_month`, `tgt_turn_of_month` | Salary, pension and fund inflows cluster around month turns | Ariel (1987), Lakonishok & Smidt (1988) |
| `tgt_dom_sin/cos`, `tgt_month_sin/cos` | Day-of-month and month seasonality, encoded as a circle so day 31 sits next to day 1. Replaces "same day as last month" with a smooth version the model can use | |
| `tgt_is_september` | Product cycle: iPhone launch and pre-order season | A hypothesis. "Buy the rumor, sell the news" means the sign can be negative on event day |
| `tgt_quarter_end_window` | Window dressing: managers buy recent winners before quarter-end reports | Large caps like AAPL are a typical target |
| `tgt_january_first_week` | Tax-loss selling reversal, new-year allocations | Mostly a small-cap effect; expect it to be weak for AAPL |
| `tgt_is_monthly_opex`, `tgt_is_quad_witching` | Option expiry: dealer hedging and pinning near large open-interest strikes; quad witching adds index futures | AAPL has one of the largest single-stock options markets |
| `tgt_is_pre_holiday`, `tgt_is_post_holiday`, `tgt_is_early_close` | Pre-holiday optimism, thin liquidity on half days | Ariel (1990) |

## 2. Scheduled events (`add_scheduled_events`) — known only after announcement

Source file: `data/scheduled_events.csv` with `event_time_utc`, `announced_at_utc`, `timing` (`bmo` before open, `amc` after close, `intraday`), and `verified`. Only `verified=true` rows are used. Before `announced_at_utc` the event is invisible (value 60 = "nothing scheduled").

| Column pattern | Mechanism |
|---|---|
| `days_to_earnings`, `tgt_is_earnings_reaction`, `earnings_within_5d` | Uncertainty builds before results, then resolves. Apple reports after the close, so the reaction is the *next* session — exactly our target |
| `days_to_apple_event`, `tgt_is_apple_event_reaction` | September (iPhone), June (WWDC), occasional spring events |
| Add next: `fomc`, `cpi`, `jobs_report`, `tariff_deadline`, `court_ruling` | Discount-rate shocks hit long-duration tech stocks hardest; Apple's China exposure makes trade deadlines material. The Fed and BLS publish these calendars months ahead |

## 3. Own price (`market_features.own_price_features`)

| Column | Mechanism |
|---|---|
| `aapl_ret_1/5/20` | Short-term reversal (liquidity providers) vs. medium-term momentum (slow information diffusion) |
| `aapl_vol_5/20`, `aapl_vol_ratio` | Volatility clustering: calm follows calm, storms follow storms (ARCH/GARCH) |
| `aapl_overnight_gap` | News that arrived while closed, already priced at the open |
| `aapl_intraday_ret`, `aapl_range`, `aapl_close_loc` | Where the day closed in its range shows buying vs. selling pressure into the close |
| `aapl_volume_z` | Abnormal attention; volume spikes often accompany information events |
| `aapl_dist_ma20/50`, `aapl_dist_52w_high` | Anchoring: investors under-react near the 52-week high (George & Hwang, 2004) |

## 4. Market and cross-asset context (`context_features`, `relative_features`)

Values are the latest close observed by the cutoff, forward-filled on days an asset did not trade.

| Series | Why it matters for Apple |
|---|---|
| SPY, QQQ, XLK returns | Systematic risk; AAPL is ~7% of the S&P 500, so part of its move *is* the market |
| `beta_spy_60`, `idio_ret_spy` | Separates the Apple-specific move from the market move. News should explain the idiosyncratic part |
| VIX level / change | Risk appetite; high VIX widens next-day dispersion |
| US 10Y, 3M yields | Discount rate. Apple's value rests on long-dated cash flows, so higher yields lower its present value |
| DXY, USD/CNY | Roughly 60% of revenue is outside the US; a stronger dollar shrinks translated revenue. China is both a market and the assembly base |
| Gold (today, not tomorrow) | Safe-haven demand; risk-off rotation away from equities |
| Oil | Input and transport costs; inflation expectations |
| TSM, SOXX | Supplier and semiconductor cycle; TSMC makes Apple's chips |

## 5. News counts (`text_features.aggregate_windows`)

The news window for session t is (cutoff t−1, cutoff t]. Weekend windows run ~72 hours, so `news_window_hours` is a feature and counts are also expressed per hour.

| Column | Mechanism |
|---|---|
| `news_n_items`, `news_n_stories`, `news_n_sources` | Attention. Stories = deduplicated clusters; a wire story syndicated 40 times is one story |
| `news_abnormal_flow` | Surprise: today's story rate versus the trailing 20 sessions. Markets react to *unexpected* information |
| `news_closed_market_share` | News that arrives after the close is not yet in the price |
| `news_n_sec_edgar`, `news_n_apple_newsroom` | Primary disclosures (8-K, press releases) carry more information than commentary |
| `news_sent_mean`, `news_sent_neg_share`, `news_sent_x_flow` | Tone labels from the review agent. Negative words carry more signal than positive ones (Tetlock 2007; Loughran & McDonald 2011) |
| `news_evt_*` | Event type: earnings, product, supply chain, regulation/legal, macro/trade, management |

## 6. Text matrix (`text_features.TextMatrix`)

1. Each item becomes `title + body`.
2. TF-IDF with unigrams and bigrams (`"supply chain"`, `"price target"` stay one concept), sublinear term frequency, English stop words.
3. Truncated SVD (latent semantic analysis) compresses ~20k columns to `k` dense dimensions (default 32). The model sees `txt_svd_00 … txt_svd_31`.
4. One vector per story (duplicates removed), mean-pooled per news window. A window with no news gets zeros plus `news_has_any = 0`.
5. **Vocabulary and SVD are fitted only on items whose window falls inside the development 80%.** Test-period words cannot shape the matrix.
6. `TextMatrix.top_terms()` prints the words behind each dimension so every latent X variable can be named and interpreted economically.

Upgrade path, one step at a time, each compared by validation MAE: financial sentiment dictionary (Loughran-McDonald) → FinBERT sentiment → sentence embeddings (e.g. all-MiniLM-L6, 384 dims, reduced by PCA on training data).

## 7. Personal decision diary

See `docs/DECISION_DIARY.md`. The diary's job is to generate hypotheses about mechanisms, which then become market-level X variables (for example, "I postponed a purchase because prices rose" → consumer sentiment or retail sales surprise). The raw diary rows are not model inputs: one person, one week, ~5 rows per day cannot be aligned with 2,000+ trading sessions.
