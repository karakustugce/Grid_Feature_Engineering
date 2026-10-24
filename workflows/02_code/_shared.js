// Shared helpers, inlined at the top of every normalizer by build_02.py.
const RUN = $('Run Config').first().json;
const nowIso = RUN.first_seen_at_utc;
const BACKFILL_HOURS = 6;

function toIso(v) {
  if (!v) return null;
  // GDELT seendate: 20261024T123000Z
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(String(v));
  const d = m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6])) : new Date(v);
  return isNaN(d) ? null : d.toISOString();
}

function availability(published, firstSeen) {
  // Live capture: available when we first saw it. Historical backfill: we did not
  // observe it live, so use publication + 15 min and label the row honestly.
  if (!published) return { available_at_utc: firstSeen, availability_basis: 'observed_no_pubdate' };
  const lagH = (new Date(firstSeen) - new Date(published)) / 36e5;
  if (lagH <= BACKFILL_HOURS) return { available_at_utc: firstSeen, availability_basis: 'observed' };
  const a = new Date(new Date(published).getTime() + 15 * 60000).toISOString();
  return { available_at_utc: a, availability_basis: 'backfill_published_plus_15m' };
}

function domainOf(u) {
  try { return new URL(u).hostname.replace(/^www\./, '').toLowerCase(); } catch (e) { return null; }
}

function row(source, rec) {
  const pub = toIso(rec.published_at_utc);
  return {
    source,
    source_record_id: rec.source_record_id || null,
    published_at_utc: pub,
    first_seen_at_utc: nowIso,
    ...availability(pub, nowIso),
    ingestion_run_id: RUN.ingestion_run_id,
    query_version: RUN.query_version,
    url: rec.url || null,
    title: rec.title || '',
    text_raw: rec.text_raw || '',
    source_domain: rec.source_domain || domainOf(rec.url),
    language: rec.language || null,
    raw_payload: JSON.stringify(rec.raw || {}).slice(0, 4000),
  };
}

function failed(source, items) {
  // Branch nodes use "continue on error": surface the failure as a row for the run report.
  const e = items.find(i => i.json && i.json.error);
  return e ? [{ json: { source, _error: String(e.json.error.message || e.json.error) } }] : null;
}
