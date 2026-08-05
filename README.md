# Punjab school monitoring, heatwave and rainfall exposure data

> **Private dashboard package:** this repository intentionally contains only the Streamlit dashboard and its final heatwave and rainfall analysis outputs. The raw monitoring file, raw exposure files, visit-level merges, source reports, and build artefacts remain only in the local research workspace.

## Run the dashboard

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app reads:

- `final_school_heatwave_vulnerability_nearest_event.csv` — one cumulative row per exposed school.
- `school_year_heatwave_capacity.csv` — one row per school and heatwave year, using the monitoring visit closest to a heatwave in that same year.
- `punjab_school_rainfall_exposure_clean.csv`, `punjab_rainfall_event_summary.csv`, `punjab_rainfall_event_disaggregation.csv` — Punjab extreme-rainfall exposure, 2021–2025, one row per school / event / event-and-group.
- `final_school_rainfall_vulnerability_nearest_event.csv` — one cumulative row per rainfall-exposed school, with a PMIU-visit-based coping-capacity priority.
- `school_year_rainfall_capacity.csv` — one row per school and rainfall-exposure year, using the monitoring visit closest to one of that school's extreme-rainfall events in the same year.

The current dashboard package includes individual-school data. Everyone invited to the private app can view and download the filtered results.

## Purpose

This folder links Punjab school-monitoring visits to school-level heatwave and extreme-rainfall exposure. It supports two complementary questions per hazard:

1. Which schools and enrolled students were exposed to recorded heatwave or extreme-rainfall events?
2. How did monitoring indicators, especially enrolment, look before and after those events?

The data are suitable for descriptive analysis and for building an event-study panel. They do not, by themselves, establish that a heatwave or rainfall event caused a change in enrolment or attendance.

## Rainfall coping-capacity methodology

The rainfall vulnerability priority mirrors the heatwave methodology: cumulative extreme-rainfall exposure (already computed in `punjab_school_rainfall_exposure_clean.csv`, following `Punjab_School_Extreme_Rainfall_Vulnerability_Analysis.docx`) is combined with a PMIU-visit-based coping-capacity score, using the monitoring visit closest to one of the school's own extreme-rainfall event years. No ASC/SIS capacity extract was available, so coping capacity uses four PMIU-visit proxies instead of the docx's five ASC/SIS dimensions:

| Dimension | Proxy | PMIU coverage |
| --- | --- | --- |
| Structural condition | Building cleanliness status | 96.3% |
| Learning-space continuity | Classrooms used for teaching ÷ total classrooms | 99.8% |
| Sanitation | Functional toilets ÷ total toilets | 99.8% |
| Safe water | Water availability, functionality and extent | 96.2% |
| Drainage/sewerage | Only free-text mentions | 0.04% — excluded, not usable |

Priority combines exposure class (Low/Moderate/High, from the cumulative exposure file) with the four-dimension coping-capacity class (Adequate/Partial/Weak), using the same Priority 1–5 table as heatwave. Schools never exposed to an extreme-rainfall event are not assigned a priority. No damage-severity modifier is applied — the docx's reported rain/flood damage field was not available in the PMIU visit data used here.

## Repository file guide

| File | Short description |
| --- | --- |
| `app.py` | Streamlit dashboard application. It reads the two final analysis CSVs and renders the decision view, cumulative view, annual view, and school profile screens. |
| `requirements.txt` | Core Python dependencies needed to run the dashboard. |
| `requirements-analytics.txt` | Extra Python packages used for analysis, SQL, and data-processing work. |
| `dare_rc.duckdb` | Local DuckDB database used for intermediate analysis and SQL-based data assembly. |
| `data.jsonl.gz` | Compressed raw Punjab monitoring records. One JSON object per school visit, covering 2014 to May 2026. |
| `school_heatwave_event_exposure_2021_2026.csv` | Source heatwave exposure output for affected schools in Punjab and Sindh. One row per school-event exposure record. |
| `school_event_clean.csv` | Cleaned school-event exposure file used as an intermediate processing input. |
| `monitoring_heatwave_events_2021_2026.csv` | Punjab-only analysis file created from the source exposure and monitoring data. It retains affected Punjab school-event rows and attaches monitoring visits where available. |
| `final_school_heatwave_vulnerability.csv` | Earlier/alternative vulnerability output. Useful as a historical or comparison version of the cumulative vulnerability file. |
| `final_school_heatwave_vulnerability_nearest_event.csv` | Final cumulative dashboard dataset. One row per exposed school, used for the main decision view and the most shareable team-facing summary. |
| `school_year_heatwave_capacity.csv` | School-by-year analysis file. One row per school and heatwave year, using the monitoring visit closest to a heatwave event in that same year. |
| `build_merged_visits.sql` | SQL logic for merging school-event exposure data with monitoring visits. |
| `build_vulnerability_analysis.sql` | SQL logic for building the vulnerability analysis dataset. |
| `build_school_year_capacity.sql` | SQL logic for generating the school-year capacity view used in the annual dashboard tab. |
| `build_final_vulnerability_nearest_event.sql` | SQL logic for producing the final, cumulative nearest-event vulnerability file used by the dashboard. |
| `build_rainfall_event_clean.sql` | SQL logic for extracting Punjab extreme-rainfall school-event rows and correcting the EMIS code, from the rainfall team's extreme-only exposure file. |
| `build_school_year_rainfall_capacity.sql` | SQL logic for generating the school-year rainfall capacity view (one row per school and rainfall-exposure year). |
| `build_final_rainfall_vulnerability_nearest_event.sql` | SQL logic for producing the final, cumulative nearest-event rainfall vulnerability and priority file used by the dashboard. |
| `intro meeting.txt` | Notes or discussion summary from an introductory meeting. |
| `tmp/` | Temporary working folder for local notes, drafts, and supporting documents. |
| `tmp/pdfs/climate_disruptions_scoping.txt` | Supporting scoping note tied to the climate disruptions work. |

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
