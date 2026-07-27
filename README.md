# Punjab school monitoring and heatwave exposure data

> **Private dashboard package:** this repository intentionally contains only the Streamlit dashboard and its two final analysis outputs. The raw monitoring file, raw exposure file, visit-level merge, source reports, and build artefacts remain only in the local research workspace.

## Run the dashboard

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app reads:

- `final_school_heatwave_vulnerability_nearest_event.csv` — one cumulative row per exposed school.
- `school_year_heatwave_capacity.csv` — one row per school and heatwave year, using the monitoring visit closest to a heatwave in that same year.

The current dashboard package includes individual-school data. Everyone invited to the private app can view and download the filtered results.

## Purpose

This folder links Punjab school-monitoring visits to school-level heatwave exposure. It supports two complementary questions:

1. Which schools and enrolled students were exposed to recorded heatwave events?
2. How did monitoring indicators, especially enrolment, look before and after those events?

The data are suitable for descriptive analysis and for building an event-study panel. They do not, by themselves, establish that a heatwave caused a change in enrolment or attendance.

## Files

| File | What it contains |
| --- | --- |
| `data.jsonl` | Raw Punjab monitoring records: one JSON object per school visit, covering 2014 to May 2026. It contains 4.09 million visits and 54,091 EMIS codes. |
| `school_heatwave_event_exposure_2021_2026.csv` | Source heatwave output for affected schools in Punjab and Sindh. Each row is a school-event exposure record. |
| `monitoring_heatwave_events_2021_2026.csv` | Punjab-only analysis file created from the two sources. It retains every affected Punjab school-event row and attaches monitoring visits where available. |

## High-level coverage and insights

- The merged Punjab file contains 52,053 distinct exposed schools, 14 Punjab heatwave events, and 1,563,095 rows.
- 51,948 exposure-school IDs match a monitoring EMIS code after removing the leading `1` from the exposure-file EMIS code. The remaining 105 do not have a direct monitoring-ID match.
- 47,643 schools have at least one monitoring visit in the same year as an exposure event. Their matching visit-event rows have monitoring fields populated.
- Monitoring is not continuous monthly coverage for every school. A missing monitoring value means no visit was available for that school/event year; it does not mean zero enrolment or zero attendance.
- The heatwave source contains affected-school rows (`affected_flag = 1`). It does not by itself provide a complete unexposed comparison group.
- The monitoring and heatwave school masters were compiled at different times. School names and school levels can differ even when the corrected EMIS code matches; use the corrected EMIS code as the linkage key.

## How the files were linked

For Punjab, the exposure EMIS code has one extra leading digit:

```text
Exposure EMIS:   137110004
Monitoring EMIS:  37110004
```

The merged file uses:

```text
monitoring_emis = exposure_emis without its first character
```

Each heatwave exposure row is retained. Monitoring visits are joined only when they have both the same corrected EMIS code and the same calendar year as the heatwave event. A school may therefore appear multiple times: once for every monitoring visit and heatwave event in the relevant year.

## Reading `monitoring_heatwave_events_2021_2026.csv`

### Exposure and event fields

| Column | Meaning |
| --- | --- |
| `exposure_emis` | School ID in the heatwave source. |
| `monitoring_emis` | Corrected EMIS used to link monitoring records. |
| `event_code` | Heatwave-event identifier. |
| `event_start_date`, `event_end_date` | Event dates. |
| `school_heatwave_days` | Number of heatwave days assigned to the school. |
| `exposure_*` | School name, location, level, gender, baseline enrolment, and coordinates from the exposure source. |

### Monitoring fields

| Column | Meaning |
| --- | --- |
| `visit_date`, `visit_year` | Date and year of the monitoring visit. |
| `school_name`, `district`, `tehsil`, `school_level`, `school_status` | School information recorded at that visit. |
| `enrolled_total` | Total enrolment recorded at the visit. |
| `teachers_total`, `teachers_present` | Teacher count and teachers present at the visit. |
| `classrooms_total`, `classrooms_used_for_teaching`, `classrooms_used_for_storage` | Classroom counts recorded at the visit. |
| `toilets_available`, `toilets_functional` | Toilet counts recorded at the visit. |
| `electricity_*`, `drinking_water_*`, `toilet_facility_*`, `boundary_wall_*` | Availability and functionality of core facilities. |
| `monitoring_record_json` | The complete source monitoring record for that visit, including all remaining nested JSONL fields. It is empty when there is no same-year monitoring visit. |
| `days_from_event_start` | Visit date minus heatwave start date. Negative values are before the event; positive values are after it. |

### Filter flags

| Column/value | How to use it |
| --- | --- |
| `same_year_monitoring_visit_flag = 1` | Keep these rows for analyses using merged monitoring outcomes. |
| `monitoring_school_match_flag = 1` | The exposure school is found somewhere in the monitoring source, even if it lacks a visit in that event year. |
| `merge_status = 'same_year_monitoring_visit'` | Equivalent to the first flag; the preferred analysis subset. |
| `merge_status = 'monitoring_only_other_year'` | The school is in monitoring data but has no visit in the event year. |
| `merge_status = 'no_monitoring_id_match'` | No corrected-EMIS match is available. |

## Suggested first checks in DuckDB

```sql
-- Coverage by merge status
SELECT merge_status, count(*) AS rows, count(DISTINCT exposure_emis) AS schools
FROM read_csv_auto('monitoring_heatwave_events_2021_2026.csv')
GROUP BY merge_status;

-- Enrolment observations around events
SELECT
  event_code,
  days_from_event_start,
  avg(enrolled_total) AS mean_enrolment,
  count(*) AS visits
FROM read_csv_auto('monitoring_heatwave_events_2021_2026.csv')
WHERE same_year_monitoring_visit_flag = 1
  AND days_from_event_start BETWEEN -90 AND 180
GROUP BY event_code, days_from_event_start
ORDER BY event_code, days_from_event_start;
```

## Important limitations

- Same-year matching is a convenient first integration step. It is not a causal design on its own.
- Close-together heatwaves can give the same visit more than one event row. Account for overlapping event windows before estimating effects.
- The file covers exposed schools. A proper exposed-versus-unexposed analysis requires a complete Punjab school-location master with zero-exposure records for schools outside each event footprint.
