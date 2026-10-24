const items = $input.all();
const f = failed('apple_newsroom', items); if (f) return f;
return items.map(i => {
  const it = i.json;
  return {
    json: row('apple_newsroom', {
      source_record_id: it.id || it.guid || it.link,
      published_at_utc: it.isoDate || it.pubDate,
      url: it.link,
      title: it.title,
      text_raw: (it.contentSnippet || it.content || '').slice(0, 5000),
      source_domain: 'apple.com',
      language: 'en',
      raw: { id: it.id || it.guid, pubDate: it.pubDate },
    }),
  };
});
