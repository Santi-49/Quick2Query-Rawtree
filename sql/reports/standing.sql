-- Newest leaderboard refresh: one row per team, with baseline and reference.
SELECT team_id::String AS team_id, conversion::Float64 AS conv, on_time::Float64 AS on_time_pct, ts::String AS ts
FROM {TEAM}.scratch
WHERE kind::String = 'leaderboard' AND dynamicType(conversion) != 'None'
  AND ts::String = (SELECT max(ts::String) FROM {TEAM}.scratch WHERE kind::String = 'leaderboard')
