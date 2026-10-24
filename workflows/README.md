# n8n workflow pilots

## 01: GDELT Apple news pilot

Import [01_gdelt_apple_news_pilot.json](01_gdelt_apple_news_pilot.json) into n8n using the workflow menu's **Import from File** option, then click **Execute workflow**.

This manual pilot asks GDELT DOC 2.0 for one week of broad Apple-related article results, sorted newest first, with a maximum of 250 items. It needs no API credential. Inspect the RSS output for titles, links, publication dates, source coverage, and false Apple/fruit matches.

This is a candidate-news list, not a complete Apple news archive. The GDELT RSS response provides article titles and URLs; it does not guarantee full article text. Retrieving publisher text requires a later source-by-source access and rights decision.

The pilot intentionally does not schedule runs, write to a database, or ask an AI agent to label stories. After inspecting its actual output, add timestamp normalization and deterministic relevance/deduplication checks; then add the review agent and persistent storage.

## 02: Multi-source normalize + audit

Import [02_multisource_normalize.json](02_multisource_normalize.json), then before the first run open **SEC EDGAR Submissions** and replace the `User-Agent` header with your name and email (SEC fair-access rule). Click **Execute workflow**.

```
Manual Trigger → Run Config ─┬─ GDELT DOC (JSON) ───── Normalize GDELT ────────┐
                             ├─ Google News RSS ────── Normalize Google News ──┤
                             ├─ Apple Newsroom RSS ─── Normalize Apple Newsroom┼─ Merge → Audit + Dedupe → Run Report
                             └─ SEC EDGAR Submissions ─ Normalize SEC ─────────┘
```

- **Run Config** stamps every row with `ingestion_run_id`, `query_version` and `first_seen_at_utc`.
- **Normalize*** nodes map each source into the raw-event contract in `docs/RESEARCH_DESIGN.md`. GDELT now uses JSON mode, which returns domain, language and GDELT's first-seen time (the RSS pilot did not).
- **Availability rule:** if we saw an item within 6 hours of publication, `available_at_utc = first_seen_at_utc` (`availability_basis = observed`). Older items are backfill: `available_at_utc = published + 15 min`, labeled `backfill_published_plus_15m`, so results can be checked on live-observed rows only.
- **Audit + Dedupe** adds `canonical_url` (tracking parameters stripped), `idempotency_key`, `dedup_cluster` (same story across outlets), `relevance_rule` (`primary` / `strong` / `weak` / `reject`, with a fruit filter), and `audit_issues`. Nothing is deleted; `weak` rows are flagged for the agent in workflow 03.
- **Run Report** returns one summary item: rows per source, relevance mix, repeat stories, failures.
- Every source node retries 3 times and continues on error, so one failed feed shows up in the report instead of stopping the run.

The JavaScript for each node lives in [02_code/](02_code/) so changes are reviewable in git. After editing a `.js` file, rebuild the importable JSON with `python workflows/build_02.py`.

Not in 02 yet, on purpose: storage, scheduling, X API, and the AI review agent. Next pieces, in order: persist to a table keyed on `idempotency_key` → Schedule Trigger every 30 min including weekends → X Recent Search branch (needs a bearer token in n8n credentials) → workflow 03 agent ([spec](../docs/AGENT_REVIEW_SPEC.md)).
