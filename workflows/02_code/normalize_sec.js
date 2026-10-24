const items = $input.all();
const f = failed('sec_edgar', items); if (f) return f;
const r = items[0].json.filings && items[0].json.filings.recent;
if (!r) return [];
const since = new Date(Date.now() - 30 * 864e5);   // filings are rare; look back 30 days
const out = [];
for (let k = 0; k < r.accessionNumber.length; k++) {
  const accepted = r.acceptanceDateTime[k];
  if (new Date(accepted) < since) continue;
  const acc = r.accessionNumber[k];
  const url = `https://www.sec.gov/Archives/edgar/data/320193/${acc.replace(/-/g, '')}/${r.primaryDocument[k]}`;
  out.push({
    json: row('sec_edgar', {
      source_record_id: acc,
      published_at_utc: accepted,           // EDGAR acceptance time = when the market could see it
      url,
      title: `Apple ${r.form[k]}: ${r.primaryDocDescription[k] || r.form[k]}`,
      source_domain: 'sec.gov',
      language: 'en',
      raw: { form: r.form[k], filingDate: r.filingDate[k], items: r.items ? r.items[k] : null },
    }),
  });
}
return out;
