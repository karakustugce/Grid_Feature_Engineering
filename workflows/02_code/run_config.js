// One item describing this run. Every normalized row carries these fields.
const now = new Date();
return [{
  json: {
    ingestion_run_id: `n8n-${$execution.id}-${now.toISOString().slice(0, 19).replace(/[-:T]/g, '')}`,
    query_version: 'aapl-v2-2026-10-24',
    first_seen_at_utc: now.toISOString(),
    lookback_days: 3,
  },
}];
