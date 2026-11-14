-- Last 10 minutes of our feedback: requests, share answered by us, p95 latency of our answers.
SELECT count() AS requests,
       countIf(served_by::String = 'team') AS answered,
       quantileExactIf(0.95)(toFloat64OrZero(toString(latency_ms)), served_by::String = 'team') AS p95_ms
FROM {TEAM}.feedback
WHERE ts::DateTime64(3) > now64(3) - INTERVAL 10 MINUTE
