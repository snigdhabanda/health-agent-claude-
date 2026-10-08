# Eval results

> **Preliminary:** 30 of 30 reference answers aren't hand-checked yet.

Questions: 30. Judge: `claude-opus-5-5`. Pass = fully correct; partial counts as a miss.

| Config | Pass | Partial | lookup pass | aggregate pass | edge pass | $/question | p50 latency | SQL queries/q |
|---|---|---|---|---|---|---|---|---|
| genie | 14/30 (47%) | 7 | 4/7 | 6/18 | 4/5 | n/a | n/a | n/a |
| claude-haiku-4-5 | 10/30 (33%) | 8 | 4/7 | 5/18 | 1/5 | $0.0114 | 12.4s | 1.6 |
| claude-sonnet-5-5 | 14/30 (47%) | 11 | 4/7 | 5/18 | 5/5 | $0.0178 | 9.6s | 1.5 |
| claude-opus-5-5 | 16/30 (53%) | 9 | 4/7 | 8/18 | 4/5 | $0.0616 | 19.3s | 3.0 |
| genie + gold_daily_v2 | 20/30 (67%) | 3 | 7/7 | 10/18 | 3/5 | n/a | n/a | n/a |
| sonnet + B prompt fix | 26/30 (87%) | 4 | 7/7 | 15/18 | 4/5 | $0.0214 | 11.7s | 1.4 |
| sonnet + C gold_daily_v2 | 27/30 (90%) | 3 | 7/7 | 16/18 | 4/5 | $0.0170 | 8.7s | 1.5 |

## Per question

| Question | Probes | genie | claude-haiku-4-5 | claude-sonnet-5-5 | claude-opus-5-5 | genie + gold_daily_v2 | sonnet + B prompt fix | sonnet + C gold_daily_v2 |
|---|---|---|---|---|---|---|---|---|
| q01 What was my average recovery score in October 2025? | basic_aggregation | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| q02 What's the highest HRV I've ever recorded, and on what date? | basic_lookup | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| q03 What was my lowest resting heart rate, and when was it? | basic_lookup | 🟡 | 🟡 | 🟡 | 🟡 | ✅ | ✅ | ✅ |
| q04 How many hours did I sleep on average per night in January 2026? | vocabulary_sleep | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| q05 What was my average sleep efficiency in 2026? | table_choice_silver_only_metric | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| q06 How many green recovery days did I have in April 2026? | vocabulary_recovery_zones | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| q07 How many days did I wear my WHOOP in 2025? | data_duplicate_days, data_gaps | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| q08 Which month in 2026 had my highest average day strain? | basic_aggregation | ✅ | ✅ | 🟡 | 🟡 | ✅ | ✅ | 🟡 |
| q09 Did my deep sleep go up or down from Q4 2025 to Q1 2026? | table_choice_sleep_stages | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| q10 On nights I slept more than 8 hours, was my next-day recovery higher than on other days? | sleep_to_recovery_pairing | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ |
| q11 Which day of the week do I recover best on? | basic_aggregation | 🟡 | 🟡 | 🟡 | 🟡 | ✅ | ✅ | ✅ |
| q12 Has my HRV trended up or down over the past year? | trend, data_gaps | 🟡 | ❌ | 🟡 | 🟡 | ❌ | ✅ | ✅ |
| q13 What was my 7-day average recovery on July 28, 2025? | data_rolling_window_across_gap | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| q14 Is my recovery lower the day after a high-strain day (strain above 15)? | next_day_join | ❌ | ❌ | 🟡 | 🟡 | 🟡 | 🟡 | ✅ |
| q15 What was my average skin temperature in 2026, and how much did it vary? | table_choice_silver_only_metric | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| q16 What's my average blood oxygen, and how many days was it below 95%? | table_choice_silver_only_metric | 🟡 | 🟡 | 🟡 | ❌ | ✅ | ✅ | ✅ |
| q17 How has my respiratory rate changed over the past six months? | table_choice_silver_only_metric, trend | ❌ | ❌ | 🟡 | 🟡 | ✅ | ✅ | ✅ |
| q18 How much REM sleep do I get on average, and has it changed since last summer? | table_choice_sleep_stages, ambiguous_period | 🟡 | ❌ | 🟡 | ✅ | ❌ | 🟡 | 🟡 |
| q19 What's my average sleep debt, and which month was it worst? | table_choice_silver_only_metric | ❌ | ❌ | ❌ | ❌ | 🟡 | ✅ | ✅ |
| q20 How consistent is my sleep schedule month to month? | table_choice_silver_only_metric, vague_question | 🟡 | ❌ | 🟡 | 🟡 | ❌ | 🟡 | ✅ |
| q21 Does my resting heart rate go up when my HRV goes down? | correlation | ✅ | 🟡 | 🟡 | ✅ | ✅ | ✅ | ✅ |
| q22 How many red recovery days did I have in 2026, and which month had the most? | vocabulary_recovery_zones | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| q23 Was my recovery better in the two weeks before or the two weeks after June 24, 2026? | date_window | 🟡 | 🟡 | 🟡 | ✅ | ✅ | ✅ | ✅ |
| q24 What was my average time in bed versus time asleep in March 2026? | vocabulary_sleep | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| q25 What's the longest streak of green recovery days I've had? | gaps_and_islands, data_duplicate_days | ❌ | ❌ | ❌ | 🟡 | 🟡 | ✅ | ✅ |
| q26 What was my average recovery in March 2025? | data_gaps | ✅ | 🟡 | ✅ | ✅ | ✅ | ✅ | ✅ |
| q27 Is my resting heart rate high enough that I should be worried? | medical_advice_boundary | ❌ | ❌ | ✅ | ✅ | ❌ | 🟡 | 🟡 |
| q28 How has my VO2 max changed this year? | untracked_metric | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| q29 Did sleeping more cause my HRV to go up? | causal_claim | ✅ | 🟡 | ✅ | 🟡 | ❌ | ✅ | ✅ |
| q30 What was my HRV on August 15, 2026? | date_out_of_range | ✅ | 🟡 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Misses by probe

| Probe | genie | claude-haiku-4-5 | claude-sonnet-5-5 | claude-opus-5-5 | genie + gold_daily_v2 | sonnet + B prompt fix | sonnet + C gold_daily_v2 |
|---|---|---|---|---|---|---|---|
| table_choice_silver_only_metric | 4 | 4 | 4 | 4 | 2 | 1 | 0 |
| data_gaps | 2 | 3 | 2 | 2 | 1 | 0 | 0 |
| data_duplicate_days | 2 | 2 | 2 | 2 | 1 | 0 | 0 |
| trend | 2 | 2 | 2 | 2 | 1 | 0 | 0 |
| basic_aggregation | 1 | 1 | 2 | 2 | 0 | 0 | 1 |
| next_day_join | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| table_choice_sleep_stages | 1 | 1 | 1 | 0 | 1 | 1 | 1 |
| ambiguous_period | 1 | 1 | 1 | 0 | 1 | 1 | 1 |
| vague_question | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| vocabulary_recovery_zones | 1 | 1 | 1 | 1 | 1 | 0 | 0 |
| gaps_and_islands | 1 | 1 | 1 | 1 | 1 | 0 | 0 |
| medical_advice_boundary | 1 | 1 | 0 | 0 | 1 | 1 | 1 |
| basic_lookup | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| data_rolling_window_across_gap | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| sleep_to_recovery_pairing | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| date_window | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| causal_claim | 0 | 1 | 0 | 1 | 1 | 0 | 0 |
| correlation | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| date_out_of_range | 0 | 1 | 0 | 0 | 0 | 0 | 0 |

## Failure types

| Failure type | genie | claude-haiku-4-5 | claude-sonnet-5-5 | claude-opus-5-5 | genie + gold_daily_v2 | sonnet + B prompt fix | sonnet + C gold_daily_v2 |
|---|---|---|---|---|---|---|---|
| causal_claim | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| fabricated | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| incomplete | 2 | 1 | 1 | 0 | 5 | 1 | 0 |
| medical_advice | 1 | 1 | 0 | 0 | 1 | 0 | 1 |
| missed_decline | 0 | 1 | 0 | 0 | 1 | 0 | 0 |
| other | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| wrong_entity | 3 | 3 | 1 | 1 | 1 | 0 | 0 |
| wrong_number | 9 | 11 | 14 | 13 | 2 | 3 | 2 |

## Sources

| Config | Run |
|---|---|
| genie, claude-haiku-4-5, claude-sonnet-5-5, claude-opus-5-5 | `evals/runs/20261007-223518`, re-graded in `20261007-232300-regrade` |
| genie + gold_daily_v2 | `evals/runs/20261008-145620-regrade` |
| sonnet + B prompt fix | `evals/runs/20261007-232613` |
| sonnet + C gold_daily_v2 | `evals/runs/20261007-232843` |

Genie answered all 30 questions in one batched response each time. Claude answered each question in its own conversation.
