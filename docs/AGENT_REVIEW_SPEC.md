# Workflow 03 spec: agent review and labeling

Workflow 02 is fully deterministic. Workflow 03 adds the AI step, but only where a rule cannot decide, and only as **labels next to the raw text**.

## Flow (build one node at a time)

1. **Input:** rows from workflow 02 where `relevance_rule ∈ {strong, weak, primary}` and `is_duplicate_key = false`.
2. **Router (IF node):** `primary` and `strong` → labeler; `weak` → relevance agent first; `reject` → store only.
3. **Relevance agent** (weak rows only): "Is this item materially about Apple Inc. as a company or its stock?" → `{is_apple_company: bool, confidence: 0–1}`. Below 0.7 goes to a manual review sheet.
4. **Labeler agent** (AI Agent node + Structured Output Parser), batched 20 items per call to save tokens.
5. **Validator (Code node):** rejects outputs that break the schema, invent fields, or change the title; failed rows retry once, then go to review.
6. **Store:** raw row + labels + `label_model`, `label_prompt_version`, `labeled_at_utc`.

The agent never decides what enters the training set, never rewrites text, and never fills a missing timestamp.

## Label schema

```json
{
  "idempotency_key": "string (copied, not generated)",
  "is_apple_company": true,
  "event_type": "earnings | product | supply_chain | regulation_legal | macro_trade | management | analyst | other",
  "sentiment": -1.0,
  "sentiment_basis": "short phrase quoted from the title",
  "novelty": "new_information | follow_up | opinion | recap",
  "expected_horizon": "intraday | days | quarters",
  "confidence": 0.0
}
```

`sentiment` is the expected direction for Apple's share price as written in the item, from −1 to 1. It is not a forecast; the model learns how much it matters.

## Prompt (version `label-v1`)

> You label news items for an academic dataset about Apple Inc. (ticker AAPL). For each item return one JSON object matching the schema. Use only the title and text provided. Copy `idempotency_key` exactly. If the item is not about Apple the company, set `is_apple_company` to false and `event_type` to "other". `sentiment_basis` must quote words that appear in the item. Do not guess facts that are not in the item. Return a JSON array and nothing else.

## Controls

- Store the model name and prompt version on every label; changing either starts a new label version, and old labels are kept.
- Labeling a historical backfill with today's model leaks nothing about prices, but the model may *know* how a story turned out. Mark labels made more than 24 h after `published_at_utc` as `label_is_retrospective = true` and test whether results hold on live-labeled rows only.
- Weekly audit: sample 30 labels by hand, record agreement rate.
