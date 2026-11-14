-- Logged leaderboard refreshes for us, baseline and reference: one row per (window_end, team_id).
SELECT window_end::String AS window_end,
       team_id::String AS team_id,
       any(conversion::Float64) AS conv,
       any(requests::Float64) AS reqs
FROM {TEAM}.scratch
WHERE kind::String = 'leaderboard'
  AND team_id::String IN ('{TEAM}', 'baseline', 'reference')
  AND dynamicType(conversion) != 'None'
  AND window_end::String >= '{SINCE}'
GROUP BY window_end, team_id
ORDER BY window_end, team_id
