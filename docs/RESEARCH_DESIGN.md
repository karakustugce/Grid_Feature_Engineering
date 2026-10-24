# Research design: Apple news and feature engineering

## 1. Forecast definition

**Question:** At the end of session t, do market, calendar, company-news, and social-media signals available by the cutoff improve the forecast of Apple's next regular-session closing price?

- **Instrument:** Apple Inc. common stock, ticker AAPL, US listing.
- **Initial cutoff:** 4:15 p.m. America/New_York on each scheduled US trading session, after the regular 4:00 p.m. close. Record the corresponding UTC timestamp on every row. The exchange calendar determines actual sessions and early closes.
- **Target session:** the next open US trading session. A Friday forecast can target Monday's close, so the horizon can exceed 24 clock hours.
- **Target:** next-session regular close on a split-adjusted price scale. Record the provider and adjustment convention.
- **Primary score:** dollar MAE, the mean absolute difference between predicted and actual close. Also report persistence-baseline error and directional accuracy.
- **Baseline:** predicted next close equals the latest close known at the cutoff.

A separate exact 24-hour target can be studied later. The first definition uses the next exchange session so weekends and holidays are explicit.

## 2. Availability and leakage

Every raw event should retain:

| Field | Meaning |
|---|---|
| source | Provider or platform |
| source_record_id | Stable item or post ID, when available |
| published_at_utc | Source-reported publication time |
| first_seen_at_utc | Time our collector first observed the item |
| available_at_utc | Earliest time the model may use it: the later of publication and first observation |
| ingestion_run_id | n8n execution or batch identifier |
| query_version | Search query or rule version |
| url and canonical_url | Original and normalized link, when available |
| title and text_raw | Original captured text; never replace it with an AI rewrite |
| raw_payload | Source fields needed to reproduce normalization |
| language | Source language or detected language, with method noted |

At cutoff c_t, a news item is eligible only if available_at_utc is no later than c_t. Historical sources often provide publication time but not when a post was first observed. Such backfills cannot fully reproduce what a live system knew; label that limitation instead of claiming a leakage-free replay.

For social engagement, retain both the metric and its observation time. Likes, reposts, and views measured after the cutoff are future information. Preserve duplicate records in raw storage, then assign a deduplication cluster so the feature builder can avoid counting the same story more than once.

Keep secrets in n8n credentials or environment variables. Never commit API tokens, raw collected data, or model outputs to this repository. Use a durable data store for those artifacts.

## 3. Source coverage

“Every Apple-related story” cannot be guaranteed by one feed. Treat the result as a documented multi-source coverage set. Record source, query, requested interval, pagination cursor, returned count, and run time.

| Source | Role | Constraint |
|---|---|---|
| GDELT DOC 2.0 | Broad online-news discovery, including monitored non-English coverage | The DOC API describes a rolling three-month window. Article-list mode returns at most 250 results, and RSS output provides titles and URLs rather than guaranteed full article text. It cannot prove exhaustive global coverage. Use overlapping windows and deduplication; obtain full text later from permitted publisher/provider sources. |
| Apple Newsroom | Primary product, leadership, and company announcements | Company-authored announcements only, not general coverage. |
| SEC EDGAR | Official filings and material disclosures | Use Apple's CIK and retain filing type and time. Public submissions APIs do not require an API key; follow SEC fair-access guidance. Filings are a distinct event source, not ordinary news. |
| X API | Public posts mentioning Apple, AAPL, selected products, or accounts | Recent Search covers the last seven days. Full-archive search has different access requirements. Use an authorized app/token; do not assume the API exposes every post. |
| Other social platforms | Additional public discussion where useful | Add each as a separate connector after confirming its supported API, permissions, and coverage. |

## 4. n8n collection flow

Keep source collection separate from daily feature generation and model training.

1. **Manual source pilot:** run one branch over a bounded time window. Start with GDELT so we can inspect the response format and false positives before configuring X credentials.
2. **Normalize and audit:** map source fields into the raw-event contract. Flag missing times, malformed URLs, ambiguous Apple matches, and duplicate IDs.
3. **Persist and deduplicate:** write to a durable event store. Prefer an idempotency key of source plus source_record_id, falling back to canonical URL and content hash. The storage backend remains an implementation choice; GitHub commits and n8n execution history are not the news database.
4. **Add primary sources:** add Apple Newsroom and SEC as separate branches, then inspect coverage and deduplication.
5. **Add X:** configure an X developer app, test the query and pagination, review API access and limits, then schedule recurring collection.
6. **Schedule:** after the manual pilot works, use n8n Schedule Trigger. Set workflow timezone explicitly to America/New_York, test daylight-saving changes, and publish the workflow. Keep news collection running outside market hours so weekend and after-hours events are captured.
7. **Review gate:** use deterministic checks for required fields, timestamp order, pagination completion, and duplicates. An AI agent may add structured labels for company relevance, event type, tone, and uncertainty. Store its model and prompt version. It must leave raw text unchanged and must not invent missing values. Keep uncertain items for review.

For each n8n run, record start/end time, source, query version, requested interval, page/cursor count, response count, retry/error status, and new versus duplicate records. The first importable workflow is at [workflows/01_gdelt_apple_news_pilot.json](../workflows/01_gdelt_apple_news_pilot.json). It is a manual GDELT pilot. Inspect its actual output before extending it or selecting a persistent storage backend.

## 5. Daily feature row

Create one row for each forecast cutoff. An initial feature matrix might contain:

- Price: latest close, 1/5/20-session returns, rolling volatility, volume change, overnight gap, and intraday range.
- Market and sector: latest available SPY, QQQ, or XLK returns; volatility and interest-rate indicators with source timestamps.
- Other assets and macro: latest gold, USD, yield, or released macro value available at the cutoff. Tomorrow's gold price is unknown; today's observed value or a lagged return is eligible. Use macro release/availability dates, not only the period a statistic describes.
- Calendar: next-session weekday, first/last trading session of a week or month, session number in month, market-holiday gap, and hours since the previous close. Use actual exchange sessions.
- Known Apple events: earnings, product launches, and regulatory dates only when publicly scheduled by the cutoff. September launches are a hypothesis to test, not a guaranteed positive-return feature.
- News and posts: counts by source/topic, unique-source count, publication delay, positive/neutral/negative tone shares, product/supply-chain/earnings/regulatory labels, and source diversity. Tone is not proof that the share price should move in the same direction.
- Social engagement: volume and engagement snapshots captured no later than the cutoff. Normalize for post age where possible.
- Text representation: begin with compact, reproducible labels and aggregates. Compare TF-IDF or embeddings only after baseline data is sound. Fit text vocabulary, scaling, imputation, and feature selection on each training fold only.

Define the daily news window as the time since the previous forecast cutoff. Include its duration, especially over weekends and holidays, so a long weekend is not treated as an ordinary one-day news window.

Candidate row fields include cutoff timestamp, target session, latest AAPL close, lagged returns, market returns, calendar indicators, news counts, source diversity, sentiment shares, event labels, and target close. Each field needs a written definition, source, lookback, and cutoff rule before entering the model.

### Personal economic decision diary

For the one-week exercise, keep a separate learning diary: timestamp, decision, alternatives, budget/time/information constraints, expected marginal benefit and cost, opportunity cost, substitution options, uncertainty, and what information was available at the time. This helps explain economic mechanisms.

A single person's one-week diary is too small and specific to serve as a reliable AAPL forecasting feature by itself. Keep it out of the initial training matrix. Reconsider it only after a clear economic mechanism, repeated observations, and an appropriate aggregate or market-level proxy are available.

## 6. Training and evaluation

- Sort observations by target session. Use the earliest 80% for development and latest 20% for final testing; never shuffle dates.
- Within the first 80%, select features and hyperparameters through expanding-window or rolling time validation. Do not tune repeatedly against the final 20%.
- A model may predict the close-to-close return and reconstruct the close, or predict the close directly. Select by validation dollar MAE so the score matches the practical objective.
- Start with persistence and a small interpretable model. Add one feature family at a time and run ablations, including whether news improves on price-only and market/calendar baselines.
- Epochs apply only to neural networks. Establish data and baseline performance first; if a small neural model is later justified, use validation and early stopping. More epochs can lower training error while worsening unseen forecasts.
- Report dollar MAE, baseline comparison, sample dates, missingness, and error in high-volatility/news-event periods. Keep the final test untouched until feature and model choices are fixed.

## 7. Current milestone

Feature builders, the text matrix, the 80/20 evaluation and leakage tests are written against the raw-event contract and checked on synthetic data (`scripts/run_synthetic_demo.py`). Workflow 02 collects four sources into that contract. Next: run workflow 02 for a week, inspect the run reports, choose storage, then export `events.csv` and run `scripts/run_real.py`. No model result counts until it runs on real collected data.

## References

- [X API Search Posts](https://docs.x.com/x-api/posts/search/introduction)
- [GDELT DOC 2.0 API overview](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [n8n Schedule Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.scheduletrigger/)
- [n8n RSS Read](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.rssfeedread/)
