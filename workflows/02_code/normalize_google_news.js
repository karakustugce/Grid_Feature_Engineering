const items = $input.all();
const f = failed('google_news', items); if (f) return f;
return items.map(i => {
  const it = i.json;
  // Titles look like "Apple shares rise after ... - Reuters"; keep the publisher.
  const m = /\s-\s([^-]{2,60})$/.exec(it.title || '');
  return {
    json: row('google_news', {
      source_record_id: it.guid || it.link,
      published_at_utc: it.isoDate || it.pubDate,
      url: it.link,                        // news.google.com redirect; resolve later if needed
      title: it.title,
      text_raw: it.contentSnippet || '',
      source_domain: m ? m[1].trim().toLowerCase() : 'news.google.com',
      language: 'en',
      raw: { guid: it.guid, pubDate: it.pubDate, publisher: m ? m[1] : null },
    }),
  };
});
