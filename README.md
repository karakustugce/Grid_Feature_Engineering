# Apple news-driven stock forecasting

This repository develops an empirical forecasting study from the news-based stock simulation built for Tuğçe's Stanford Code in Place project.

## Research question

At a fixed cutoff after a US trading session, can information available by that cutoff improve a forecast of Apple's (AAPL) next regular-session closing price?

The target is the next trading session, not the next calendar date. A Friday forecast therefore targets Monday's close, or the next exchange session after a holiday. Each input must have an availability timestamp so the backtest cannot see later information.

This is a learning and research project, not an investment recommendation or a promise of profitable trading.

## Method

- Keep raw source records and provenance, including publication time and first-observed time.
- Begin with a persistence baseline: forecast the next close as the latest known close.
- Add economically motivated feature groups one at a time.
- Split dates in order: earliest 80% for development, latest 20% for final testing. Do not shuffle.
- Report mean absolute error (MAE) in dollars and compare each model with the baseline.
- Fit preprocessing, text vocabularies, and feature selection on training data only.

## Project stages

1. Research design: define the forecast cutoff, data contract, target, leakage rules, and evaluation.
2. News collection: build and inspect one n8n source branch at a time.
3. Market and calendar data: collect Apple prices, exchange sessions, and time-stamped market context.
4. Feature matrix: aggregate only information available at each cutoff.
5. Baseline and evaluation: use chronological validation and reserve the final 20% for testing.
6. Incremental models: start interpretable and add complexity only when validation supports it.

No single feed can guarantee every public story or post about Apple. We will document source coverage and access limits. Initial candidates are GDELT for broad news, Apple Newsroom and SEC EDGAR for primary disclosures, and X API for social posts when an authorized token is available. The first importable source pilot is [the GDELT n8n workflow](workflows/01_gdelt_apple_news_pilot.json); see [its run instructions](workflows/README.md) and [the research design](docs/RESEARCH_DESIGN.md).

## Code layout

| Path | What it does |
|---|---|
| `src/gfe/calendar_features.py` | Exchange-calendar X variables and scheduled events (earnings, launches) gated by announcement time |
| `src/gfe/market_features.py` | AAPL price features, cross-asset context (SPY, QQQ, VIX, gold, dollar, yields), target |
| `src/gfe/text_features.py` | News windows between cutoffs, attention/tone aggregates, TF-IDF → SVD text matrix fitted on training items only |
| `src/gfe/modeling.py` | Chronological 80/20 split, persistence baseline, walk-forward ridge, small MLP with early stopping |
| `src/gfe/panel.py` | Joins everything into one row per cutoff session |
| `scripts/run_synthetic_demo.py` | Mechanics check on synthetic data with a planted news effect |
| `scripts/fetch_market_data.py`, `scripts/run_real.py` | Real-data pull and feature-family ablation |
| `tests/test_leakage.py` | Holiday/early-close targets, cutoff windows, announcement gating, split order |
| `docs/FEATURE_CATALOG.md` | Every X variable with its economic mechanism |
| `workflows/02_multisource_normalize.json` | n8n: GDELT + Google News + Apple Newsroom + SEC → normalize → audit/dedupe |

```bash
pip install -r requirements.txt
pytest -q
python scripts/run_synthetic_demo.py              # pipeline check -> outputs/synthetic_report.html

python scripts/export_events.py                   # news from Supabase -> data/raw/events.csv
python scripts/build_news_matrix.py               # -> data/processed/news_matrix.csv (one row per cutoff)
python scripts/fetch_market_data.py --start 2015-01-01
python scripts/run_real.py --events data/raw/events.csv
open outputs/report.html                          # the run report
```

`run_real.py` keeps only sessions from the first day with collected news (before that every news column would be 0). Use `--all-history` to keep the full price history for price/calendar/market baselines.
