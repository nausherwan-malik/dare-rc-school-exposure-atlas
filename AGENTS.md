# AGENTS.md

Instructions for AI coding agents working in this repository. Read this before touching `app.py` or any `build_*.sql` script.

## What this repository is

A Streamlit dashboard (`app.py`) that shows Punjab school exposure to two climate hazards — heatwave and extreme rainfall — plus a combined cross-hazard view, PMIU-visit-based coping-capacity, and vulnerability priority. It answers the Workstream 1 and Workstream 2 policy questions from `Climate Disruptions Scoping Paper Mid Point Progress Report.pdf`, following the methodology in `Punjab School Heatwave Vulnerability Analysis.docx` and `Punjab_School_Extreme_Rainfall_Vulnerability_Analysis.docx`.

The app has **two modes**, toggled by `view_mode` (a `st.segmented_control` near the top): **🏠 Simple overview** (default — plain language, one page, for a non-technical audience) and **🔬 Full dashboard** (the seven-tab research view). Both modes read the same underlying data; Simple overview never introduces a new number, only relabels and reorganizes what the detailed tabs already compute. See README's "What the dashboard answers" for the full description of each mode.

This is a **private dashboard package**: `.gitignore` blocks everything except the app, its documentation, and its final CSV outputs. Raw sources, intermediate files, and SQL build scripts stay local — never remove them from `.gitignore`'s exclusion just to "make them visible"; if a new derived file needs to ship with the dashboard, add it to the allowlist explicitly and say why.

## Before making changes

1. **Read the two methodology docx files and the scoping PDF first** if the change touches exposure classification, capacity scoring, or priority logic. They are the source of truth, not the SQL scripts — the SQL scripts are one interpretation of them, adapted to what data actually exists.
2. **Read `README.md`'s Methodology section** for the current, human-readable summary of what's implemented versus what deviates from the docx briefs (and why).
3. **Check whether a build script already exists** for the transformation you need (`build_*.sql`). Heatwave and rainfall each have three: event-clean → school-year capacity → final cumulative vulnerability. Mirror that three-stage shape for any new hazard rather than inventing a different structure.

## Data model you must not break

- **EMIS code convention.** Every dashboard CSV uses the corrected 8-digit EMIS code (`monitoring_emis`), not the 9-digit exposure-source code. The correction is `substr(exposure_emis, 2)` — see `build_rainfall_event_clean.sql` for the canonical example. This is what makes the heatwave and rainfall cumulative files joinable for the Combined hazards tab. If you add a new hazard, correct its EMIS code the same way before it touches PMIU data.
- **Nearest-visit matching.** Both hazards select the single PMIU visit closest (by date) to one of the school's own event years — not the latest visit, not an average. This is deliberate: it ties the capacity snapshot to a plausible moment near the hazard exposure. Don't silently switch to "latest visit" (a real prior version of the rainfall data did this — it's wrong for this dashboard's purpose).
- **Priority is exposure × capacity, not a weighted score.** Priority 1 = High exposure + Weak capacity; Priority 5 = Low/Moderate exposure + Adequate capacity; "Unclassified" = capacity couldn't be determined (missing PMIU data), never treated as low-risk. Keep this table structure if you add a hazard — don't switch to a different scoring scheme without updating the Method tab and README to match.
- **Combined priority takes the worse of the two hazard priorities — it does not average them.** A school at heatwave Priority 1 and rainfall Priority 4 is combined Priority 1. `compounding_high_risk` is a separate, stricter flag: both hazards independently at Priority 1 or 2.
- **Exposed-only files.** `final_school_*_vulnerability_nearest_event.csv` only contain schools exposed to that hazard. Never-exposed schools are visible only via the base exposure file (`punjab_school_rainfall_exposure_clean.csv` for rainfall). If you change this scope, update the row-count expectations in README and the Method tab's coverage numbers.

## When you change a `build_*.sql` script

1. Regenerate the CSV it produces: `duckdb < build_whatever.sql` (this repo runs duckdb CLI directly against `data.jsonl` — decompress `data.jsonl.gz` first with `gunzip -k data.jsonl.gz` if it isn't already present; it's ~22GB uncompressed, so `rm data.jsonl` when you're done to avoid leaving a multi-GB scratch file in the repo).
2. Validate the output before wiring it into `app.py` — at minimum, check row counts and the distribution of `vulnerability_priority` / `exposure_class` with a quick `duckdb -c "SELECT ... GROUP BY ..."` query, and sanity-check them against the coverage percentages already documented in README.
3. Update README's file guide and row-count table if row counts materially change.

## When you change `app.py`

1. **Run `python3 -m py_compile app.py`** before anything else — cheap and catches syntax errors immediately.
2. **Smoke-test with Streamlit's `AppTest`, in BOTH modes** — it's headless, fast, and catches exceptions without needing a browser. `view_mode` is a plain Python `if/else`, not `st.tabs`, so **only the active branch executes per run** — testing the default (`at.run()`) alone only exercises Simple overview, and only exercises Full dashboard's seven tabs after you switch modes:
   ```python
   from streamlit.testing.v1 import AppTest
   at = AppTest.from_file('app.py', default_timeout=300)
   at.run()                                   # Simple overview (default)
   assert len(at.exception) == 0, at.exception
   at.segmented_control[0].set_value('🔬 Full dashboard').run()   # Full dashboard
   assert len(at.exception) == 0, at.exception
   assert len(at.tabs) == 7
   ```
   Within Full dashboard mode, `st.tabs` still renders every tab's content on every run regardless of which is visually active, so that one `.run()` call exercises all seven tabs. Then interact with the widgets you touched (`.set_value(...).run()` on selectboxes/pills/multiselects/text_input) in whichever mode(s) they live in, and re-check `at.exception` each time.
3. **If you don't have `streamlit`/`pandas`/`plotly`/`pydeck` in your active environment**, check for a pre-existing venv before creating one — this machine has one at `/Users/mac-air/Documents/venv/analytics` with everything the app needs.
4. **Every new number on screen needs an explanation.** In Full dashboard, that means a row in the Method tab's tables (and in README). In Simple overview, that means a plain-English sentence in the glossary expander or inline caption — assume the reader has never seen "EMIS code," "PMIU," or "percentile" before. Self-explanatory to a first-time, non-technical visitor is the standard for Simple overview specifically.
5. **Don't reintroduce hazard-specific duplication.** `priority_map()` is a single parameterised helper (`priority_column`, `tooltip_html`, `layer_id`) used by all four priority maps (heatwave, rainfall, combined, overview) — extend it rather than copy-pasting a fifth near-identical map function. It previously existed in two nearly-identical copies, one of which was missing its `return` statement and silently rendered nothing; keep it consolidated so that class of bug can't recur.
6. **Keep Simple overview a pure relabeling of existing data.** `render_overview()` must not compute a new classification, threshold, or score — it may only rename, group, or plain-language-translate fields that already exist in `combined` (built once by `build_combined()` and shared by both modes). If a change to risk logic is needed, make it in the shared build functions (`build_combined()` or the SQL scripts) so both modes stay consistent automatically, not by patching `render_overview()` separately. The `PLAIN_PRIORITY` and `PLAIN_HAZARD_EXPOSURE` dicts are the only place plain-language labels are defined — extend them rather than inlining new label strings elsewhere.

## Style

- No comments explaining *what* the code does — names and structure should carry that. Comments (rare) are for non-obvious *why*.
- Match the existing terse, data-forward Streamlit style: `st.container(horizontal=True)` metric rows, `st.pills` for multi-select filters with live counts in the label, `st.caption` under every chart/table explaining how to read it.
- Keep hazard-specific and combined code visually separable — prefix combined-view variables/keys with `combined_`, rainfall-specific ones with `rain_`/`rainfall_`, to keep the three parallel sections easy to distinguish while scanning.

## Verifying before you claim something is fixed or shipped

- `git status` and `git log` — this repo has been pushed to GitHub (`origin/main`) and Streamlit Cloud deploys from it. Local changes are not live until committed *and* pushed. Don't tell a user something is "on the dashboard" unless you've confirmed the push succeeded.
- Never commit or push without the user's explicit go-ahead for that specific change — this is a shared, deployed dashboard, not a scratch branch.
