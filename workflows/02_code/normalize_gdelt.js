const items = $input.all();
const f = failed('gdelt', items); if (f) return f;
const arts = (items[0] && items[0].json.articles) || [];
return arts.map(a => ({
  json: row('gdelt', {
    source_record_id: a.url,
    published_at_utc: a.seendate,          // GDELT's first-seen time; the publisher time is not provided
    url: a.url,
    title: a.title,
    source_domain: a.domain,
    language: a.language,
    raw: { seendate: a.seendate, domain: a.domain, sourcecountry: a.sourcecountry, language: a.language },
  }),
}));
