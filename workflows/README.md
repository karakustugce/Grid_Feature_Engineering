# n8n workflow pilots

## 01: GDELT Apple news pilot

Import [01_gdelt_apple_news_pilot.json](01_gdelt_apple_news_pilot.json) into n8n using the workflow menu's **Import from File** option, then click **Execute workflow**.

This manual pilot asks GDELT DOC 2.0 for one week of broad Apple-related article results, sorted newest first, with a maximum of 250 items. It needs no API credential. Inspect the RSS output for titles, links, publication dates, source coverage, and false Apple/fruit matches.

This is a candidate-news list, not a complete Apple news archive. The GDELT RSS response provides article titles and URLs; it does not guarantee full article text. Retrieving publisher text requires a later source-by-source access and rights decision.

The pilot intentionally does not schedule runs, write to a database, or ask an AI agent to label stories. After inspecting its actual output, add timestamp normalization and deterministic relevance/deduplication checks; then add the review agent and persistent storage.
