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

No single feed can guarantee every public story or post about Apple. We will document source coverage and access limits. Initial candidates are GDELT for broad news, Apple Newsroom and SEC EDGAR for primary disclosures, and X API for social posts when an authorized token is available. See [the research design](docs/RESEARCH_DESIGN.md) for details.
