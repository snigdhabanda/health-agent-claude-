-- gold_daily_v2: one row per local calendar day, fixing two bugs in v1's gold_daily_metrics.
--
-- 1. v1 dates cycles with DATE(cycle_start_ts) on a UTC timestamp. Evenings in UTC-4 roll into
--    the next UTC day, so 68 dates had two rows and some real days had none. Here a cycle is
--    dated by its start in the cycle's own timezone. On the 7 dates that still have two cycles
--    (an evening sleep plus a post-midnight one), the cycle with the longer sleep is kept.
-- 2. v1's *_7d_avg used ROWS BETWEEN 6 PRECEDING, so after the Sep 2024 - Jul 2025 gap a
--    "7-day" average reached back 11 months. Here the window is 7 calendar days, and
--    days_in_7d says how many of them have data.
--
-- Sleep columns come from the same cycle (WHOOP records each cycle's main sleep with it).

CREATE OR REPLACE VIEW workspace.whoop_data.gold_daily_v2 AS
WITH local AS (
  SELECT *,
    to_date(from_utc_timestamp(cycle_start_ts,
      CASE WHEN cycle_timezone = 'UTCZ' THEN '+00:00' ELSE substr(cycle_timezone, 4) END)) AS day
  FROM workspace.whoop_data.silver_recovery
),
ranked AS (
  SELECT *,
    count(*) OVER (PARTITION BY day) AS cycles_on_day,
    row_number() OVER (PARTITION BY day ORDER BY asleep_hours DESC NULLS LAST, cycle_start_ts) AS rn
  FROM local
),
daily AS (
  SELECT * EXCEPT (rn, cycle_date) FROM ranked WHERE rn = 1
)
SELECT
  day,
  recovery_score_pct, hrv_ms, resting_hr_bpm, day_strain AS strain,
  skin_temp_celsius, blood_oxygen_pct, respiratory_rate_rpm,
  energy_burned_cal, max_hr_bpm, avg_hr_bpm,
  asleep_hours AS sleep_hours, in_bed_hours, light_sleep_hours, deep_sleep_hours, rem_sleep_hours,
  awake_hours, sleep_need_hours, sleep_debt_hours,
  sleep_performance_pct, sleep_efficiency_pct, sleep_consistency_pct,
  count(recovery_score_pct) OVER w7          AS days_in_7d,
  avg(recovery_score_pct)   OVER w7          AS recovery_score_7d_avg,
  avg(hrv_ms)               OVER w7          AS hrv_7d_avg,
  avg(resting_hr_bpm)       OVER w7          AS resting_hr_7d_avg,
  avg(asleep_hours)         OVER w7          AS sleep_hours_7d_avg,
  avg(day_strain)           OVER w7          AS strain_7d_avg,
  cycles_on_day,
  cycle_start_ts, cycle_end_ts, cycle_timezone
FROM daily
WINDOW w7 AS (ORDER BY day RANGE BETWEEN INTERVAL 6 DAYS PRECEDING AND CURRENT ROW)
