# H-view-age · the age of the last view and the span of the views
- **status**: rejected. Neither the age of the last view nor the span of the views changes what the session predicts, live or in history.
- **owner**: agent
- **claim**: an old last view (or a long session) predicts less: the re-shown last view and products of its subcategory convert less as the view ages.
- **test**: `sql/hypotheses/H-view-age.sql`, run 14 Nov 16:20 UTC. Age = request ts − ts of the last recent view; span = last view ts − first view ts. Live: all feedback, every strategy pooled (cells compared within an age bucket). Impressions weighted 1/log2(slot+1); ctr_w, conv_w per 100 weighted impressions; click× = ctr_w over "other category" in the same bucket.

## 1 · Live, by age of the last view
| shown product | <30 s: clicks / ctr_w / conv_w / click× | 30 s–2 min | 2–10 min |
|---|---|---|---|
| the last view | 51 / 1.57 / 0.86 / 3.4 | 44 / 1.46 / 0.90 / 2.9 | 9 / 1.91 / 0.85 / 4.5 † |
| same subcategory | 132 / 1.39 / 0.51 / 3.0 | 109 / 1.25 / 0.48 / 2.5 | 22 / 1.56 / 0.57 / 3.7 |
| same category | 297 / 1.26 / 0.49 / 2.8 | 247 / 1.16 / 0.39 / 2.3 | 41 / 1.16 / 0.54 / 2.7 |
| other | 380 / 0.46 / 0.13 / 1 | 385 / 0.51 / 0.14 / 1 | 53 / 0.43 / 0.12 / 1 |

## 2 · History (product and category pages), by age of the last view
| shown product | <30 s: clicks / ctr_w / conv_w | 30 s–2 min | 2–10 min |
|---|---|---|---|
| the last view | 1,672 / 6.58 / 4.56 | 1,461 / 6.35 / 4.09 | 249 / 6.96 / 4.64 |
| same subcategory | 7,990 / 1.38 / 0.57 | 7,394 / 1.41 / 0.59 | 1,113 / 1.35 / 0.57 |
| same category | 25,274 / 0.86 / 0.30 | 23,062 / 0.86 / 0.31 | 3,554 / 0.85 / 0.29 |

## 3 · Live, by span of the views (2+ views)
| shown product | <1 min: clicks / ctr_w | 1–5 min | >5 min |
|---|---|---|---|
| the last view | 16 / 0.90 | 16 / 0.72 | 1 / 0.79 † |
| same subcategory | 89 / 1.54 | 103 / 1.31 | 4 / 0.77 † |
| same category | 159 / 1.18 | 211 / 1.20 | 12 / 1.09 † |
| other | 235 / 0.50 | 299 / 0.45 | 24 / 0.58 |

## 4 · Distribution
| | <30 s | 30 s–2 min | 2–10 min | >10 min | median age | median span |
|---|---|---|---|---|---|---|
| live, last 3 h (25,875 requests with views) | 48.2% | 44.7% | 7.1% | 0% | 32 s | 39 s |
| history (1.6M) | 48.7% | 44.3% | 7.0% | 0% | 31 s | 40 s |

## verdict
- Age: the largest move between buckets is −15% (same subcategory click× 3.0 → 2.5 at 30 s–2 min) and it reverses at 2–10 min; history is flat within ±10% on 35,000 clicks. No age term. Views are never older than 10 min, so there is nothing stale to discount.
- Span: flat below 5 min; the >5 min cells have under 20 clicks (†) and hold 5% of impressions.
- **`Request` does not need the view timestamps.** rules4 does not use them.

## next
- None. Re-check only if the final round's sessions look different (median age, a share over 10 min).
