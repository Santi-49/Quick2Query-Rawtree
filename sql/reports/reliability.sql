-- Per 10 minutes over the last 3 hours, from our feedback: share answered by us, fallback reasons, latency.
SELECT toString(toStartOfInterval(ts::DateTime64(3), INTERVAL 10 MINUTE)) AS t,
       count() AS requests,
       countIf(served_by::String = 'team') AS answered,
       countIf(fallback_reason::String = 'missing') AS missing,
       countIf(fallback_reason::String = 'late') AS late,
       countIf(fallback_reason::String = 'invalid') AS invalid,
       quantileExactIf(0.5)(toFloat64OrZero(toString(latency_ms)), served_by::String = 'team') AS p50_ms,
       quantileExactIf(0.95)(toFloat64OrZero(toString(latency_ms)), served_by::String = 'team') AS p95_ms
FROM {TEAM}.feedback
WHERE ts::DateTime64(3) > now64(3) - INTERVAL 3 HOUR
GROUP BY t
ORDER BY t
