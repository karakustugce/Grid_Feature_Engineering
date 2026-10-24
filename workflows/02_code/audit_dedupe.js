// Deterministic gate: canonical URL, relevance rule, keys, in-batch duplicate clusters.
// Raw rows are never dropped here; they are flagged so the agent and storage can decide.

function fnv1a(s) {           // tiny stable hash (built-in crypto is often disabled in n8n Code)
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(16).padStart(8, '0');
}

function canonical(u) {
  try {
    const x = new URL(u);
    x.hash = '';
    [...x.searchParams.keys()].forEach(k => { if (/^(utm_|fbclid|gclid|mc_|ref$|cmpid)/i.test(k)) x.searchParams.delete(k); });
    return (x.hostname.replace(/^www\./, '').toLowerCase() + x.pathname.replace(/\/$/, '') + (x.search || ''));
  } catch (e) { return null; }
}

function titleKey(t) {
  return String(t || '').replace(/\s[-|–]\s[^-|–]{2,60}$/, '').toLowerCase()
    .replace(/[^a-z0-9 ]/g, ' ').split(/\s+/).filter(w => w.length > 2).sort().join(' ');
}

const STRONG = /\b(AAPL|Apple Inc|Tim Cook|Cupertino|iPhone|iPad|MacBook|Vision Pro|App Store|AirPods|Apple Watch|Apple Intelligence|iOS \d+|Apple Pay|Apple TV\+|Apple Music|Siri)\b/i;
const APPLE = /\bApple('s)?\b/;
const FRUIT = /\b(apple (pie|cider|juice|orchard|tree|picking|recipe|crumble|sauce|vinegar)|big apple|orchard|harvest)\b/i;

const rows = $input.all().map(i => i.json).filter(r => r.source && !r._error);  // empty items come from branches with no data
const errors = $input.all().map(i => i.json).filter(r => r._error);
const seenKey = new Map(), seenCluster = new Map();

const out = rows.map(r => {
  const text = `${r.title} ${r.text_raw || ''}`;
  let relevance = 'reject';
  if (r.source === 'sec_edgar' || r.source === 'apple_newsroom') relevance = 'primary';
  else if (STRONG.test(text)) relevance = 'strong';
  else if (APPLE.test(text) && !FRUIT.test(text)) relevance = 'weak';   // agent decides

  const canonical_url = r.url ? canonical(r.url) : null;
  const idempotency_key = r.source_record_id
    ? `${r.source}:${fnv1a(String(r.source_record_id))}`
    : `${r.source}:url:${fnv1a(canonical_url || r.title)}`;
  const content_hash = fnv1a(titleKey(r.title));

  const dup_key = seenKey.has(idempotency_key);
  seenKey.set(idempotency_key, true);
  const cluster_first = seenCluster.get(content_hash);
  if (!cluster_first) seenCluster.set(content_hash, idempotency_key);

  const issues = [];
  if (!r.published_at_utc) issues.push('missing_published_at');
  if (r.published_at_utc && new Date(r.published_at_utc) > new Date(r.first_seen_at_utc)) issues.push('published_in_future');
  if (!r.url) issues.push('missing_url');
  if (!r.title) issues.push('missing_title');

  return {
    json: {
      ...r,
      canonical_url,
      idempotency_key,
      content_hash,
      dedup_cluster: content_hash,
      is_duplicate_key: dup_key,
      is_repeat_story: Boolean(cluster_first),
      relevance_rule: relevance,
      needs_agent_review: relevance === 'weak' || issues.length > 0,
      audit_issues: issues.join(','),
    },
  };
});

return out.concat(errors.map(e => ({ json: { ...e, audit_issues: 'source_failed' } })));
