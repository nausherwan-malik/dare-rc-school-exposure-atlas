# AGENTS.md

Instructions for AI coding agents working in this repository. Read this before touching `app.py` or any `build_*.sql` script.

## What this repository is

A Streamlit dashboard (`app.py`) that shows Punjab school exposure to two climate hazards — heatwave and extreme rainfall — plus a combined cross-hazard view, PMIU-visit-based coping-capacity, and vulnerability priority. It answers Policy Question 1 from `Climate Disruptions Scoping Paper Mid Point Progress Report.pdf` (where/when schools are exposed and how many students, by level and gender, are affected), following the methodology in `Punjab School Heatwave Vulnerability Analysis.docx` and `Punjab_School_Extreme_Rainfall_Vulnerability_Analysis.docx`.

The app is **one page with five sections**, switched by `section` (a `st.segmented_control` near the top, gating a plain `if/elif` — not `st.tabs`): Where the risk is (default) → Heat → Extreme rainfall → Find a school → How this works. A sidebar `show_detail` toggle reveals raw priority codes, the combined-view driver column, full data tables and downloads; off by default so a first-time policymaker sees a plain-language page, on for anyone who wants the underlying rigor. **Heat and Extreme rainfall are the same code path** — one shared `render_hazard_section(cfg, ...)` function, configured per hazard by `HEAT_CONFIG`/`RAIN_CONFIG` — not two independently written sections. See README's "What the dashboard answers" for the full description.

This is a **private dashboard package**: `.gitignore` blocks everything except the app, its documentation, and its final CSV outputs. Raw sources, intermediate files, and SQL build scripts stay local — never remove them from `.gitignore`'s exclusion just to "make them visible"; if a new derived file needs to ship with the dashboard, add it to the allowlist explicitly and say why.

**The live app never names an unanswered policy question or an unbuilt workstream.** It states what it does answer, positively, and stops there. Honest scope/limitations documentation (Policy Question 2 not implemented, Workstream 3 partial, etc.) lives in README's "Important limitations" section, not in the UI — see README's "Framing" section for why, and keep that split if you touch either.

## Before making changes

1. **Read the two methodology docx files and the scoping PDF first** if the change touches exposure classification, capacity scoring, or priority logic. They are the source of truth, not the SQL scripts — the SQL scripts are one interpretation of them, adapted to what data actually exists.
2. **Read `README.md`'s Methodology section** for the current, human-readable summary of what's implemented versus what deviates from the docx briefs (and why).
3. **Check whether a build script already exists** for the transformation you need (`build_*.sql`). Heatwave and rainfall each have three: event-clean → school-year capacity → final cumulative vulnerability. Mirror that three-stage shape for any new hazard rather than inventing a different structure.

## Data model you must not break

- **EMIS code convention.** Every dashboard CSV uses the corrected 8-digit EMIS code (`monitoring_emis`), not the 9-digit exposure-source code. The correction is `substr(exposure_emis, 2)` — see `build_rainfall_event_clean.sql` for the canonical example. This is what makes the heatwave and rainfall cumulative files joinable in the Where the risk is section. If you add a new hazard, correct its EMIS code the same way before it touches PMIU data.
- **Nearest-visit matching.** Both hazards select the single PMIU visit closest (by date) to one of the school's own event years — not the latest visit, not an average. This is deliberate: it ties the capacity snapshot to a plausible moment near the hazard exposure. Don't silently switch to "latest visit" (a real prior version of the rainfall data did this — it's wrong for this dashboard's purpose).
- **Priority is exposure × capacity, not a weighted score.** Priority 1 = High exposure + Weak capacity; Priority 5 = Low/Moderate exposure + Adequate capacity; "Unclassified" = capacity couldn't be determined (missing PMIU data), never treated as low-risk. Keep this table structure if you add a hazard — don't switch to a different scoring scheme without updating "How this works" and README to match.
- **Combined priority takes the worse of the two hazard priorities — it does not average them.** A school at heatwave Priority 1 and rainfall Priority 4 is combined Priority 1. `compounding_high_risk` is a separate, stricter flag: both hazards independently at Priority 1 or 2.
- **Exposed-only files.** `final_school_*_vulnerability_nearest_event.csv` only contain schools exposed to that hazard. The dashboard deliberately doesn't load the full-Punjab-population rainfall file (`punjab_school_rainfall_exposure_clean.csv`) — every section only shows exposed schools, symmetric across both hazards. If you reintroduce a never-exposed population anywhere, do it for both hazards, not just one, or the sections drift apart again.
- **Exposure-rule and capacity-coverage tables are computed live**, not hardcoded (`exposure_rule_table()`, `coverage_percent()`, `heat_capacity_rules()`, `rain_capacity_rules()`). Don't paste static percentiles or coverage percentages back in — they will drift from the actual loaded CSVs the next time the data is rebuilt. The one exception is rainfall's drainage-coverage figure (0.04%), which describes free-text PMIU fields the dashboard has no column for and can't compute.

## When you change a `build_*.sql` script

1. Regenerate the CSV it produces: `duckdb < build_whatever.sql` (this repo runs duckdb CLI directly against `data.jsonl` — decompress `data.jsonl.gz` first with `gunzip -k data.jsonl.gz` if it isn't already present; it's ~22GB uncompressed, so `rm data.jsonl` when you're done to avoid leaving a multi-GB scratch file in the repo).
2. Validate the output before wiring it into `app.py` — at minimum, check row counts and the distribution of `vulnerability_priority` / `exposure_class` with a quick `duckdb -c "SELECT ... GROUP BY ..."` query.
3. Update README's file guide and row-count table if row counts materially change.

## When you change `app.py`

1. **Run `python3 -m py_compile app.py`** before anything else — cheap and catches syntax errors immediately.
2. **Smoke-test with Streamlit's `AppTest`, across all 5 sections** — it's headless, fast, and catches exceptions without needing a browser. `section` is a plain Python `if/elif`, not `st.tabs`, so **only the active section's code executes per run** — this is deliberate (it's what makes only one map compute per rerun, the single biggest fix for map load time) but it means testing the default alone only exercises "Where the risk is":
   ```python
   from streamlit.testing.v1 import AppTest
   SECTIONS = [
       ':material/public: Where the risk is', ':material/thermostat: Heat',
       ':material/water_drop: Extreme rainfall', ':material/school: Find a school',
       ':material/info: How this works',
   ]
   for label in SECTIONS:
       at = AppTest.from_file('app.py', default_timeout=300)
       at.run()
       at.segmented_control[0].set_value(label).run()
       assert len(at.exception) == 0, (label, at.exception)
   ```
   Use a **fresh `AppTest` instance per section** rather than reusing one across many `.set_value().run()` hops in sequence — the test harness (not the app) can raise a spurious `KeyError` on a widget key from a previously-visited, now-unmounted section (e.g. `overview_school_search`) when you chain 3+ section switches in one instance. This is an `AppTest` artifact, confirmed by the fact each section is exception-free in isolation and round-trips cleanly (A→B→A); it is not evidence of a real bug, but don't waste time chasing it as one.
   Also note: `AppTest`'s `.options` on a `segmented_control`/`selectbox` strips `:material/...:` icon shortcodes for display, but `.set_value()` needs the **raw, icon-prefixed value** to actually match (e.g. `':material/thermostat: Heat'`, not `'Heat'`) — passing the stripped label silently sets a value that matches no real option. Similarly, a `selectbox` built with `format_func` (e.g. the rainfall event picker) needs `.set_value()` called with the underlying raw option, not the formatted display string — extract it from `.options` if you don't have it directly (e.g. `event_code = formatted.split(' · ')[1]`).
3. **If you don't have `streamlit`/`pandas`/`plotly`/`pydeck` in your active environment**, check for a pre-existing venv before creating one — this machine has one at `/Users/mac-air/Documents/venv/analytics` with everything the app needs.
4. **Every new number on screen needs an explanation.** When `show_detail` is on, that means a row in "How this works"'s tables (and in README). When it's off, that means a plain-English sentence in the glossary expander or an inline caption — assume the reader has never seen "EMIS code," "PMIU," or "percentile" before.
5. **Don't reintroduce hazard-specific duplication.** `hazard_map()` + `prepare_map_points()` is the one map factory for every map (cross-hazard, Heat, Rainfall) — it previously existed as two nearly-identical copies, one of which was missing its `return` statement and silently rendered nothing. `legend_pills()` is the one legend widget — every map's legend must use it (clickable, live counts); never fall back to a static `st.badge` row as a legend (two of those existed and both got removed in the redesign — `st.badge` is fine for the decorative Step 1/2/3 markers in "How this works," never as a legend). `render_hazard_section()` + `render_year_detail()` are the one code path for Heat and Rainfall — don't fork a hazard-specific copy for a one-off need; add a config field instead.
6. **The map is Punjab-only by construction.** `PUNJAB_VIEW` sets `min_zoom=5.6` specifically so a user can't scroll out to a world view, and `pitch=0` keeps it flat. Don't loosen `min_zoom` or reintroduce `pitch` without a reason — both were deliberate fixes for "the map takes a long time loading" / "need only a map of Pakistan, not the world" feedback.
7. **Keep the plain-language state (`show_detail=False`) a pure relabeling of existing data.** No render function may compute a new classification, threshold, or score depending on `show_detail` — it may only rename, hide, or plain-language-translate fields that already exist in the frame passed in. If a change to risk logic is needed, make it in the shared build functions (`build_combined()`, `HEAT_CONFIG`/`RAIN_CONFIG`'s rule-table functions, or the SQL scripts) so both detail states stay consistent automatically. `PLAIN_PRIORITY` and `PLAIN_HAZARD_EXPOSURE` are the only place plain-language labels are defined — extend them rather than inlining new label strings elsewhere.
8. **Adding a hazard-section field?** Add it to both `HEAT_CONFIG` and `RAIN_CONFIG`, even if one hazard's value is `None`/empty (e.g. `HEAT_CONFIG["extra_panel"] = None`) — `render_hazard_section()` and `render_year_detail()` assume every config key exists for both hazards.

## Style

- No comments explaining *what* the code does — names and structure should carry that. Comments (rare) are for non-obvious *why*.
- Match the existing terse, data-forward Streamlit style: `st.container(horizontal=True)` metric rows, `st.pills` for multi-select filters with live counts in the label, `st.caption` under every chart/table explaining how to read it.
- Keep hazard-specific and combined code visually separable — prefix combined-view variables/keys with `combined_`, heat-specific ones with `heat_`, rainfall-specific ones with `rain_`/`rainfall_`.

## Verifying before you claim something is fixed or shipped

- `git status` and `git log` — this repo has been pushed to GitHub (`origin/main`) and Streamlit Cloud deploys from it. Local changes are not live until committed *and* pushed. Don't tell a user something is "on the dashboard" unless you've confirmed the push succeeded.
- Never commit or push without the user's explicit go-ahead for that specific change — this is a shared, deployed dashboard, not a scratch branch.
