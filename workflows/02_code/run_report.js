// One summary item per run: what each source returned and how much was usable.
const rows = $input.all().map(i => i.json);
const RUN = $('Run Config').first().json;
const by = {};
for (const r of rows) {
  if (!r.source) continue;
  const s = r.source || 'unknown';
  by[s] = by[s] || { returned: 0, primary: 0, strong: 0, weak: 0, reject: 0, repeat_story: 0, issues: 0, failed: null };
  if (r._error) { by[s].failed = r._error; continue; }
  by[s].returned++;
  by[s][r.relevance_rule]++;
  if (r.is_repeat_story) by[s].repeat_story++;
  if (r.audit_issues) by[s].issues++;
}
return [{ json: { ingestion_run_id: RUN.ingestion_run_id, query_version: RUN.query_version,
  started_at_utc: RUN.first_seen_at_utc, finished_at_utc: new Date().toISOString(), sources: by } }];
