# Punjab school climate-exposure dashboard

> **Private dashboard package:** this repository intentionally contains only the Streamlit dashboard and its final heatwave, rainfall and combined analysis outputs. The raw monitoring file, raw exposure files, visit-level merges, source reports, and SQL build scripts remain only in the local research workspace (see `.gitignore`).

## Run the dashboard

```bash
pip install -r requirements.txt
streamlit run app.py
```

Everyone invited to the private app can view and download the filtered results for every tab.

## What the dashboard answers

The app is one Streamlit page with seven tabs. Start at **Combined hazards** for a single cross-hazard view; drill into **Heatwave** or **Rainfall** tabs for hazard-specific detail; use **School profile** to look up one school across both hazards.

| Tab | Question it answers |
| --- | --- |
| 🌍 Combined hazards | Which schools face heatwave risk, rainfall risk, or both — and where do the two hazards compound? |
| 📊 Heatwave decision view | Which schools are the most urgent heatwave-vulnerability targets right now? |
| 📈 Heatwave cumulative view | How much cumulative heatwave exposure has each school had since 2021, and with what service capacity? |
| 📅 Heatwave school-year view | How did a specific school look in a specific heatwave year? |
| 💧 Rainfall exposure & priority | Where and when did extreme-rainfall events hit, and which exposed schools have weak coping capacity? |
| 🏫 School profile | Full heatwave and rainfall history for one chosen school. |
| ℹ️ Method | Definitions, matching rules, and priority construction for both hazards and the combined view — read this before citing any number from the app. |

Sidebar filters (district, school level) apply to every tab.

## Data the app reads

| File | Rows | Description |
| --- | --- | --- |
| `final_school_heatwave_vulnerability_nearest_event.csv` | ~52,053 | One cumulative row per heatwave-exposed school, 2021–2026, with vulnerability priority. |
| `school_year_heatwave_capacity.csv` | ~380,000 | One row per school × heatwave year, using the PMIU visit closest to that year's heatwave. |
| `punjab_school_rainfall_exposure_clean.csv` | ~52,107 | One row per Punjab school (including never-exposed), rainfall exposure across 46 events, 2021–2025. |
| `punjab_rainfall_event_summary.csv`, `punjab_rainfall_event_disaggregation.csv` | 46 / ~13,000 | Event-level and event×group rainfall roll-ups. |
| `final_school_rainfall_vulnerability_nearest_event.csv` | ~51,320 | One cumulative row per rainfall-exposed school, with a PMIU-visit-based coping-capacity priority. |
| `school_year_rainfall_capacity.csv` | ~208,000 | One row per school × rainfall-exposure year, using the PMIU visit closest to that year's event. |

The app builds one more dataset **in memory, on load** — it is not a file:

- **Combined hazard table** (`build_combined()` in `app.py`): an outer join of the two cumulative vulnerability files on EMIS code, adding `hazard_exposure` (Heatwave only / Rainfall only / Heatwave and rainfall), `combined_priority` (the more severe of the two hazard priorities), `combined_priority_driver`, and `compounding_high_risk` (independently Priority 1–2 on both hazards). See the Method tab for the exact rule.

## Methodology

Full detail, including live counts from the current data, is in the app's **Method** tab. Summary:

### Heatwave (`Punjab School Heatwave Vulnerability Analysis.docx`)

1. **Exposure** — cumulative heatwave days per school across all matched events, classified Low / Moderate / High by the 33rd/67th percentile among exposed schools.
2. **Capacity** — electricity and drinking-water availability/functionality/extent from the PMIU visit closest to a heatwave in one of that school's exposed years, classified Adequate / Weak / Partial / Missing.
3. **Priority** — exposure class × capacity class → Priority 1 (High/Weak, most urgent) through Priority 5 (Low-Moderate/Adequate), or "Unclassified - PMIU missing" when capacity can't be determined.

### Rainfall (`Punjab_School_Extreme_Rainfall_Vulnerability_Analysis.docx`)

Same two-step exposure × capacity logic, adapted because no ASC/SIS capacity extract was available — only PMIU visit data (the same source heatwave uses):

| Dimension | Proxy | PMIU coverage |
| --- | --- | --- |
| Structural condition | Building cleanliness status | 96.3% |
| Learning-space continuity | Classrooms used for teaching ÷ total classrooms | 99.8% |
| Sanitation | Functional toilets ÷ total toilets | 99.8% |
| Safe water | Water availability, functionality and extent | 96.2% |
| Drainage/sewerage | Only free-text mentions | 0.04% — excluded, not usable |

Priority combines exposure class (Low/Moderate/High) with the four-dimension coping-capacity class, using the same Priority 1–5 table as heatwave. Schools never exposed to an extreme-rainfall event are not assigned a priority — they remain visible in the exposure map/table as "No recorded exposure."

**Known deviations from the rainfall docx**, since the assumed ASC/SIS extract doesn't exist in this repo:
- No damage-severity modifier (the docx's reported rain/flood damage field isn't in PMIU visit data).
- No `dangerous_classrooms` / `water_quality` fields (PMIU has no equivalent).
- Priority is computed only for exposed schools, not the full ~52,000-school Punjab population the docx specifies.
- `rural_urban` is not available in either source file.

### Combined hazards

A per-school overlay of the two independent priorities above, joined on EMIS code — it does not recompute exposure or capacity. `combined_priority` takes the more severe (lower-numbered) of the heatwave and rainfall priorities; `compounding_high_risk` flags schools that are independently Priority 1–2 on **both** hazards. This is a lightweight stand-in for the scoping paper's Workstream 3 Tier A composite risk index, not the full index — it has no district-level SES, population-density or poverty proxies, and no Workstream 2 observed-sensitivity input.

## Repository file guide

| File | Short description |
| --- | --- |
| `app.py` | Streamlit dashboard application — all seven tabs described above. |
| `requirements.txt` | Core Python dependencies needed to run the dashboard. |
| `requirements-analytics.txt` | Extra Python packages used for analysis, SQL, and data-processing work. |
| `AGENTS.md` | Instructions for AI coding agents working in this repository. |
| `Punjab School Heatwave Vulnerability Analysis.docx` | Heatwave methodology brief. |
| `Punjab_School_Extreme_Rainfall_Vulnerability_Analysis.docx` | Rainfall methodology brief. |
| `Climate Disruptions Scoping Paper Mid Point Progress Report.pdf` | Source of the Workstream 1–3 policy questions the dashboard answers. |
| `dare_rc.duckdb` | Local DuckDB database used for intermediate analysis and SQL-based data assembly. |
| `data.jsonl.gz` | Compressed raw Punjab PMIU monitoring records. One JSON object per school visit, covering 2014 to May 2026. |
| `school_heatwave_event_exposure_2021_2026.csv` | Source heatwave exposure output for affected schools in Punjab and Sindh. |
| `school_event_clean.csv` | Cleaned Punjab heatwave school-event file, intermediate input to the heatwave build scripts. |
| `rainfall_event_clean.csv` | Cleaned Punjab extreme-rainfall school-event file (EMIS-corrected), intermediate input to the rainfall build scripts. |
| `monitoring_heatwave_events_2021_2026.csv` | Punjab-only visit-level merge of heatwave exposure and PMIU monitoring visits. |
| `final_school_heatwave_vulnerability.csv` | Earlier/alternative heatwave vulnerability output, kept for comparison. |
| `final_school_heatwave_vulnerability_nearest_event.csv` | Final cumulative heatwave dashboard dataset. |
| `school_year_heatwave_capacity.csv` | School-by-year heatwave capacity dataset. |
| `final_school_rainfall_vulnerability_nearest_event.csv` | Final cumulative rainfall dashboard dataset. |
| `school_year_rainfall_capacity.csv` | School-by-year rainfall capacity dataset. |
| `build_merged_visits.sql` | SQL for merging heatwave school-event exposure with monitoring visits. |
| `build_vulnerability_analysis.sql` | SQL for the heatwave vulnerability analysis dataset. |
| `build_school_year_capacity.sql` | SQL for the heatwave school-year capacity view. |
| `build_final_vulnerability_nearest_event.sql` | SQL for the final cumulative nearest-event heatwave vulnerability file. |
| `build_rainfall_event_clean.sql` | SQL for extracting and EMIS-correcting Punjab extreme-rainfall school-event rows. |
| `build_school_year_rainfall_capacity.sql` | SQL for the rainfall school-year capacity view. |
| `build_final_rainfall_vulnerability_nearest_event.sql` | SQL for the final cumulative nearest-event rainfall vulnerability and priority file. |
| `intro meeting.txt` | Notes from an introductory meeting. |
| `tmp/` | Temporary working folder for local notes, drafts, and supporting documents. |
| `tmp/pdfs/climate_disruptions_scoping.txt` | Plain-text extract of the scoping paper, used for the Workstream 1–3 wording. |
| `rainfall-data/` | Raw rainfall exposure and enrolment inputs from the rainfall workstream, kept local (large files). |

## How schools are linked across sources (EMIS code correction)

Both hazards' source files use a 9-digit exposure EMIS code with an extra leading `1`; PMIU monitoring visits use the 8-digit code without it:

```text
Exposure EMIS:   137110004
Monitoring EMIS:  37110004
```

Every build script applies `monitoring_emis = exposure_emis without its first character` before joining to `data.jsonl`. The same corrected 8-digit code is the `emis_code` in every dashboard CSV, which is what makes the heatwave and rainfall cumulative files directly joinable for the Combined hazards tab.

## Reading `monitoring_heatwave_events_2021_2026.csv` (local-only, not published)

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
| `monitoring_record_json` | The complete source monitoring record for that visit, including all remaining nested JSONL fields. Empty when there is no same-year monitoring visit. |
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

- **Not causal.** Same-year/nearest-visit matching is a descriptive integration step, for both hazards and the combined view. It is not an event-study or causal design.
- **Enrolment-disruption analysis (Workstream 2) is not implemented.** It needs a monthly enrolment panel and an exposed-versus-unexposed event-study design. `rainfall-data/punjab_school_monthly_enrolment_2021_2025.csv` exists locally as a starting point but isn't wired into the dashboard.
- **Combined hazards is a two-hazard overlay, not the full Workstream 3 composite index.** No district-level SES, population-density or poverty proxies are included.
- **Priority supports review and targeting, not a causal-impact ranking**, for heatwave, rainfall, and the combined view alike.
- **Overlapping events.** Close-together events can give the same visit more than one event row; account for overlapping windows before estimating effects.
- **Exposed-schools-only coverage** for the heatwave file and the two priority files. A complete unexposed comparison group needs a full Punjab school-location master.
