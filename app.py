"""Punjab school climate-risk dashboard."""

import html as html_lib
from pathlib import Path

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st


ROOT = Path(__file__).parent
CUMULATIVE_FILE = ROOT / "final_school_heatwave_vulnerability_nearest_event.csv"
YEARLY_FILE = ROOT / "school_year_heatwave_capacity.csv"
RAINFALL_EVENTS_FILE = ROOT / "punjab_rainfall_event_summary.csv"
RAINFALL_EVENT_GROUPS_FILE = ROOT / "punjab_rainfall_event_disaggregation.csv"
RAINFALL_CUMULATIVE_FILE = ROOT / "final_school_rainfall_vulnerability_nearest_event.csv"
RAINFALL_YEARLY_FILE = ROOT / "school_year_rainfall_capacity.csv"
FLOOD_HAZARD_FILE = ROOT / "rainfall-data/OneDrive_1_17-08-2026/School_Flood_Hazard_Index.csv"

RAINFALL_CAPACITY_DIMENSIONS = {
    "structural_condition_status": "Structural condition (building cleanliness)",
    "learning_space_status": "Learning-space continuity (classrooms)",
    "sanitation_status": "Sanitation (toilets)",
    "safe_water_status": "Safe water",
}
HEAT_CAPACITY_DIMENSIONS = {
    "electricity_status": "Electricity",
    "water_status": "Drinking water",
}
PRIORITY_OPTIONS = ["Priority 1", "Priority 2", "Priority 3", "Priority 4", "Priority 5", "Unclassified - PMIU missing"]
PRIORITY_LABELS = {
    "Priority 1": "🔴 Priority 1",
    "Priority 2": "🟠 Priority 2",
    "Priority 3": "🟡 Priority 3",
    "Priority 4": "🔵 Priority 4",
    "Priority 5": "⚪ Priority 5",
    "Unclassified - PMIU missing": "⚫ Unclassified",
}
RAINFALL_PRIORITY_OPTIONS = PRIORITY_OPTIONS[:5] + ["Unclassified - capacity data missing"]
RAINFALL_PRIORITY_LABELS = {**{k: v for k, v in PRIORITY_LABELS.items() if k != "Unclassified - PMIU missing"},
                             "Unclassified - capacity data missing": "⚫ Unclassified"}
COMBINED_PRIORITY_OPTIONS = ["Priority 1", "Priority 2", "Priority 3", "Priority 4", "Priority 5", "Unclassified"]
COMBINED_PRIORITY_LABELS = {**{k: v for k, v in PRIORITY_LABELS.items() if k != "Unclassified - PMIU missing"},
                             "Unclassified": "⚫ Unclassified"}
PRIORITY_MAP_COLORS = {
    "Priority 1": [153, 27, 27, 210],
    "Priority 2": [220, 72, 39, 190],
    "Priority 3": [245, 158, 11, 130],
    "Priority 4": [45, 125, 210, 100],
    "Priority 5": [87, 125, 155, 55],
}
PLAIN_PRIORITY = {
    "Priority 1": ("🔴", "Urgent", "Facing frequent extreme weather and the school's water, power, toilets or building condition are weak."),
    "Priority 2": ("🟠", "High concern", "Facing frequent extreme weather and coping capacity has real gaps."),
    "Priority 3": ("🟡", "Exposed, but coping", "Facing frequent extreme weather, but the school is comparatively well-equipped."),
    "Priority 4": ("🔵", "Watch", "Less frequent extreme weather, and coping capacity has some gaps."),
    "Priority 5": ("⚪", "Lower concern", "Less frequent extreme weather and the school is comparatively well-equipped."),
    "Unclassified": ("⚫", "Not enough data", "No recent visit recorded the school's water, power, toilet or building condition."),
}
PLAIN_HAZARD_EXPOSURE = {
    "Heatwave and rainfall": "Faces both heatwaves and extreme rainfall",
    "Heatwave only": "Faces heatwaves (no recorded extreme-rainfall exposure)",
    "Rainfall only": "Faces extreme rainfall (no recorded heatwave exposure)",
}

SECTIONS = [
    ":material/public: Where the risk is",
    ":material/thermostat: Heat",
    ":material/water_drop: Extreme rainfall",
    ":material/school: Find a school",
    ":material/info: How this works",
]

# Punjab's approximate bounding box (27.7-34.0N, 69.3-75.4E). zoom=5.6 keeps the whole
# province in frame on a typical browser window; min_zoom stops a user scrolling out to
# a world view. pitch=0 keeps the map flat (was pitch=20 — flat is faster and clearer).
PUNJAB_VIEW = pdk.ViewState(
    latitude=30.85, longitude=72.35, zoom=6.1, min_zoom=5.6, max_zoom=12, pitch=0, bearing=0,
)

st.set_page_config(
    page_title="Punjab School Climate Risk",
    page_icon=":material/public:",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_CSS = """
<style>
:root {
    --dare-ink: #102a43;
    --dare-border: #d7e0ea;
    --dare-panel: #eef2f7;
    --dare-accent: #c2410c;
    --dare-accent-soft: #fdece3;
}

/* Hero title block */
h1 {
    letter-spacing: -0.02em;
}

/* Section nav (segmented control) reads as a tab strip, sticky under the header */
div[data-testid="stSegmentedControl"] {
    position: sticky;
    top: 0.25rem;
    z-index: 999;
    background: rgba(248, 250, 252, 0.92);
    backdrop-filter: blur(6px);
    padding: 0.35rem 0.1rem;
    border-radius: 999px;
    border: 1px solid var(--dare-border);
    margin-bottom: 0.25rem;
}

/* Metric cards get a colored top accent and a touch of lift */
div[data-testid="stMetric"] {
    border-top: 3px solid var(--dare-accent);
    border-radius: 0.6rem;
    padding: 0.65rem 0.9rem 0.5rem 0.9rem;
    box-shadow: 0 1px 2px rgba(16, 42, 67, 0.06);
}
div[data-testid="stMetricValue"] {
    font-size: 1.55rem;
}

/* Bordered containers (cards) get a soft shadow instead of a flat rule */
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    box-shadow: 0 1px 3px rgba(16, 42, 67, 0.07);
}

/* Legend / filter pills */
div[data-testid="stPills"] button, div[data-testid="stSegmentedControl"] button {
    border-radius: 999px !important;
}

/* Buttons and downloads: rounder, slightly bolder */
div[data-testid="stDownloadButton"] button, div[data-testid="stButton"] button {
    border-radius: 0.6rem;
    font-weight: 600;
}

/* Custom wrapping reference tables (st.dataframe can't wrap text — it's canvas-rendered) */
.dare-table-wrap {
    overflow-x: auto;
    margin: 0.15rem 0 0.85rem 0;
    border: 1px solid var(--dare-border);
    border-radius: 0.6rem;
}
table.dare-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
    background: white;
}
table.dare-table th {
    text-align: left;
    background: var(--dare-panel);
    color: var(--dare-ink);
    font-weight: 700;
    padding: 0.6rem 0.85rem;
    border-bottom: 2px solid var(--dare-border);
    position: sticky;
    top: 0;
}
table.dare-table td {
    padding: 0.6rem 0.85rem;
    border-bottom: 1px solid var(--dare-border);
    vertical-align: top;
    white-space: normal;
    word-break: break-word;
    line-height: 1.4;
    color: var(--dare-ink);
}
table.dare-table tbody tr:last-child td {
    border-bottom: none;
}
table.dare-table tbody tr:nth-child(even) {
    background: rgba(238, 242, 247, 0.5);
}
table.dare-table tbody tr:hover {
    background: var(--dare-accent-soft);
}
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner="Loading cumulative school data…")
def load_cumulative() -> pd.DataFrame:
    return pd.read_csv(CUMULATIVE_FILE, dtype={"emis_code": "string"}, parse_dates=["monitoring_date_used"])


@st.cache_data(show_spinner="Loading heatwave year-by-year data…")
def load_yearly() -> pd.DataFrame:
    frame = pd.read_csv(YEARLY_FILE, dtype={"emis_code": "string"}, low_memory=False)
    for column in ("selected_event_start_date", "selected_event_end_date", "monitoring_date_used"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


@st.cache_data(show_spinner="Loading rainfall event summaries…")
def load_rainfall_events() -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(RAINFALL_EVENTS_FILE, parse_dates=["event_start_date", "event_end_date"])
    groups = pd.read_csv(RAINFALL_EVENT_GROUPS_FILE, parse_dates=["event_start_date", "event_end_date"])
    return events, groups


@st.cache_data(show_spinner="Loading rainfall coping-capacity data…")
def load_rainfall_cumulative(flood_data_version: int | None) -> pd.DataFrame:
    rainfall = pd.read_csv(RAINFALL_CUMULATIVE_FILE, dtype={"emis_code": "string"}, parse_dates=["monitoring_date_used"])
    if not FLOOD_HAZARD_FILE.exists():
        return add_flood_policy(rainfall.assign(**{column: pd.NA for column in ["flood_source_emis", "s1_flood_frequency", "rainfall_norm", "s1_norm", "sfhi", "sfhi_100", "hazard_class"]}))
    flood = pd.read_csv(FLOOD_HAZARD_FILE, dtype={"school_id": "string"})
    flood["emis_code"] = flood["school_id"].str.slice(1)
    flood = flood.rename(columns={"school_id": "flood_source_emis"})
    return add_flood_policy(rainfall.merge(
        flood[["emis_code", "flood_source_emis", "s1_flood_frequency", "rainfall_norm", "s1_norm", "sfhi", "sfhi_100", "hazard_class"]],
        on="emis_code", how="left", validate="one_to_one",
    ))


def add_flood_policy(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["flood_evidence"] = pd.NA
    result["flood_policy_action"] = pd.NA
    signal = result["s1_norm"].dropna()
    observed = signal[signal.gt(0)]
    if observed.empty:
        return result
    threshold = observed.quantile(0.67)
    high_rain = result["exposure_class"].eq("High")
    repeated_flood = result["s1_norm"].ge(threshold)
    result["flood_evidence"] = "Lower flood evidence"
    result.loc[high_rain & repeated_flood, "flood_evidence"] = "Confirmed high flood hazard"
    result.loc[high_rain & ~repeated_flood, "flood_evidence"] = "High rainfall, unconfirmed inundation"
    result.loc[~high_rain & repeated_flood, "flood_evidence"] = "Observed flooding, lower rainfall signal"
    result["flood_policy_action"] = "Monitor and maintain"
    result.loc[result["flood_evidence"].eq("Confirmed high flood hazard") & result["rainfall_coping_capacity"].isin(["Weak", "Partial"]), "flood_policy_action"] = "Immediate protection"
    result.loc[result["flood_evidence"].isin(["High rainfall, unconfirmed inundation", "Observed flooding, lower rainfall signal"]), "flood_policy_action"] = "Field verification"
    result.loc[result["flood_evidence"].eq("Confirmed high flood hazard") & result["rainfall_coping_capacity"].eq("Adequate"), "flood_policy_action"] = "Resilience investment"
    result["flood_s1_threshold"] = threshold
    return result


@st.cache_data(show_spinner="Loading rainfall year-by-year data…")
def load_rainfall_yearly() -> pd.DataFrame:
    frame = pd.read_csv(RAINFALL_YEARLY_FILE, dtype={"emis_code": "string"}, low_memory=False)
    for column in ("selected_event_start_date", "selected_event_end_date", "monitoring_date_used"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


def priority_number(series: pd.Series) -> pd.Series:
    return series.str.extract(r"Priority (\d)")[0].astype(float)


@st.cache_data(show_spinner="Combining heatwave and rainfall exposure…")
def build_combined(heatwave: pd.DataFrame, rainfall: pd.DataFrame) -> pd.DataFrame:
    shared = ["school_name", "district", "tehsil", "school_level", "school_gender", "latitude", "longitude"]
    hw = heatwave[shared + [
        "emis_code", "total_heatwave_days", "total_heatwave_events", "exposure_class",
        "essential_service_capacity", "vulnerability_priority", "total_enrolment",
    ]].rename(columns={
        "exposure_class": "heatwave_exposure_class",
        "essential_service_capacity": "heatwave_capacity",
        "vulnerability_priority": "heatwave_priority",
        "total_enrolment": "heatwave_enrolment",
    })
    rf = rainfall[shared + [
        "emis_code", "cumulative_extreme_days", "events_exposed_count", "exposure_class",
        "rainfall_coping_capacity", "vulnerability_priority", "total_enrolment",
    ]].rename(columns={
        "exposure_class": "rainfall_exposure_class",
        "rainfall_coping_capacity": "rainfall_capacity",
        "vulnerability_priority": "rainfall_priority",
        "total_enrolment": "rainfall_enrolment",
    })
    combined = hw.merge(rf, on="emis_code", how="outer", suffixes=("", "_rf"))
    for column in shared:
        combined[column] = combined[column].combine_first(combined[f"{column}_rf"])
        combined = combined.drop(columns=[f"{column}_rf"])
    combined["combined_enrolment"] = combined["heatwave_enrolment"].combine_first(combined["rainfall_enrolment"])

    combined["hazard_exposure"] = "Unmatched"
    combined.loc[combined["heatwave_priority"].notna(), "hazard_exposure"] = "Heatwave only"
    combined.loc[combined["rainfall_priority"].notna(), "hazard_exposure"] = "Rainfall only"
    combined.loc[
        combined["heatwave_priority"].notna() & combined["rainfall_priority"].notna(), "hazard_exposure"
    ] = "Heatwave and rainfall"

    combined["heatwave_priority_number"] = priority_number(combined["heatwave_priority"])
    combined["rainfall_priority_number"] = priority_number(combined["rainfall_priority"])
    combined["combined_priority_number"] = combined[["heatwave_priority_number", "rainfall_priority_number"]].min(axis=1, skipna=True)
    combined["combined_priority"] = combined["combined_priority_number"].apply(
        lambda n: f"Priority {int(n)}" if pd.notna(n) else "Unclassified"
    )
    combined["compounding_high_risk"] = (
        combined["heatwave_priority_number"].le(2) & combined["rainfall_priority_number"].le(2)
    )

    def driver(row: pd.Series) -> str:
        hw_n, rf_n = row["heatwave_priority_number"], row["rainfall_priority_number"]
        if pd.isna(hw_n) and pd.isna(rf_n):
            return "Neither classified"
        if pd.isna(rf_n) or (pd.notna(hw_n) and hw_n < rf_n):
            return "Heatwave"
        if pd.isna(hw_n) or (pd.notna(rf_n) and rf_n < hw_n):
            return "Rainfall"
        return "Both (tied)"

    combined["combined_priority_driver"] = combined.apply(driver, axis=1)
    return combined


def select_values(label: str, values: pd.Series, key: str) -> list[str]:
    options = sorted(values.dropna().astype(str).unique().tolist())
    return st.sidebar.multiselect(label, options, key=key)


def apply_filters(frame: pd.DataFrame, districts: list[str], levels: list[str]) -> pd.DataFrame:
    result = frame.copy()
    if districts:
        result = result[result["district"].astype(str).isin(districts)]
    if levels:
        result = result[result["school_level"].astype(str).isin(levels)]
    return result


def capacity_chart(frame: pd.DataFrame, category: str, title: str):
    counts = frame[category].fillna("Not available").value_counts().rename_axis(category).reset_index(name="schools")
    return px.bar(
        counts, x=category, y="schools", color=category, text="schools", title=title,
        color_discrete_sequence=px.colors.qualitative.Safe,
    ).update_layout(showlegend=False, margin=dict(l=10, r=10, t=55, b=10))


def coverage_percent(frame: pd.DataFrame, column: str) -> float:
    """Share of rows where a PMIU-derived status column isn't 'Missing'."""
    return float((frame[column].astype(str) != "Missing").mean() * 100)


def exposure_rule_table(base_frame: pd.DataFrame, amount_column: str) -> pd.DataFrame:
    """Low/Moderate/High thresholds, computed live from the current data so they can't go stale."""
    values = base_frame[amount_column].dropna()
    p33, p67 = values.quantile(0.33), values.quantile(0.67)
    lo, hi = values.min(), values.max()
    return pd.DataFrame([
        ["Low", f"{lo:.0f}–{p33:.0f}", "At or below the 33rd percentile"],
        ["Moderate", f"{p33:.0f}–{p67:.0f}", "Between the 33rd and 67th percentiles"],
        ["High", f"{p67:.0f}–{hi:.0f}", "Above the 67th percentile"],
    ], columns=["Class", "Current range", "Rule"])


def heat_capacity_rules(base_frame: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([
        ["Electricity", "Availability, functionality and extent at the selected visit",
         f"{coverage_percent(base_frame, 'electricity_status'):.1f}%",
         "Adequate = available, functional and wholly provided; Partial = one condition unmet; Weak = unavailable or non-functional."],
        ["Drinking water", "Availability, functionality and extent at the selected visit",
         f"{coverage_percent(base_frame, 'water_status'):.1f}%",
         "Same rule as electricity."],
        ["Combined essential-service capacity", "Electricity × drinking water", "—",
         "Adequate when both are adequate; Weak when both are weak; Partial otherwise."],
    ], columns=["Dimension", "Proxy", "PMIU coverage", "Rule"])


def rain_capacity_rules(base_frame: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([
        ["Structural condition", "Building cleanliness status",
         f"{coverage_percent(base_frame, 'structural_condition_status'):.1f}%", "Adequate = good; Partial = average; Weak = poor."],
        ["Learning-space continuity", "Classrooms used for teaching ÷ total classrooms",
         f"{coverage_percent(base_frame, 'learning_space_status'):.1f}%", "Adequate ≥90%; Partial 70–<90%; Weak <70%."],
        ["Sanitation", "Functional toilets ÷ total toilets",
         f"{coverage_percent(base_frame, 'sanitation_status'):.1f}%", "Adequate ≥90%; Partial 50–<90%; Weak <50% or none functional."],
        ["Safe water", "Availability, functionality and extent",
         f"{coverage_percent(base_frame, 'safe_water_status'):.1f}%", "Adequate = available, functional and wholly provided; Weak = unavailable or non-functional."],
        ["Drainage/sewerage", "Only free-text mentions", "0.04%", "Not usable — excluded from the capacity score."],
    ], columns=["Dimension", "Proxy", "PMIU coverage", "Rule"])


_COLUMN_WIDTH_CSS = {"small": "14%", "medium": "20%", "large": "30%"}


def render_table(df: pd.DataFrame, column_widths: dict | None = None) -> None:
    """Render a reference/explanation table with wrapping text.

    st.dataframe renders cells to a canvas grid and cannot wrap long text no matter
    the row height — this renders real HTML instead, for tables where the point is to
    be read, not sorted or scrolled.
    """
    widths = column_widths or {}
    head_cells = "".join(
        f'<th style="width:{_COLUMN_WIDTH_CSS.get(widths.get(c), widths.get(c, ""))}">{html_lib.escape(str(c))}</th>'
        for c in df.columns
    )
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{html_lib.escape(str(value))}</td>" for value in row) + "</tr>"
        for row in df.itertuples(index=False)
    )
    st.markdown(
        f'<div class="dare-table-wrap"><table class="dare-table"><thead><tr>{head_cells}</tr></thead>'
        f"<tbody>{body_rows}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def render_flood_policy_panel(frame: pd.DataFrame) -> None:
    if frame["s1_norm"].notna().sum() == 0:
        st.caption("Flood evidence will appear when the SFHI source file is available.")
        return
    policy = frame
    st.caption("Confirmed hazard combines high rainfall exposure with repeated satellite flood evidence. Where the two signals disagree, the action is field verification. PMIU capacity then distinguishes immediate protection from longer-term resilience investment.")
    with st.container(horizontal=True):
        st.metric("Immediate protection", f"{(policy['flood_policy_action'] == 'Immediate protection').sum():,}", border=True)
        st.metric("Field verification", f"{(policy['flood_policy_action'] == 'Field verification').sum():,}", border=True)
        st.metric("Resilience investment", f"{(policy['flood_policy_action'] == 'Resilience investment').sum():,}", border=True)
    colors = {"Immediate protection": [153, 27, 27, 210], "Field verification": [245, 158, 11, 170], "Resilience investment": [45, 125, 210, 150], "Monitor and maintain": [87, 125, 155, 70]}
    points = prepare_map_points(policy, "flood_policy_action", colors, ["school_name", "district", "flood_evidence", "flood_policy_action", "sfhi_100", "rainfall_coping_capacity"])
    st.pydeck_chart(hazard_map(points, "flood_policy_map", "<b>{school_name}</b><br/>{district}<br/>{flood_policy_action}<br/>{flood_evidence}<br/>SFHI: {sfhi_100}<br/>Capacity: {rainfall_coping_capacity}"), height=420, key="flood_policy_map")
    st.caption(f"Repeated Sentinel-1 flood evidence means at or above the current 67th percentile among schools with observed flood signal ({policy['flood_s1_threshold'].dropna().iloc[0]:.3f}). Evidence disagreement is a field-verification flag, not a lower-risk judgement.")
    st.dataframe(policy.sort_values(["flood_policy_action", "sfhi_100", "total_enrolment"], ascending=[True, False, False])[['school_name', 'district', 'tehsil', 'flood_evidence', 'flood_policy_action', 'sfhi_100', 'total_enrolment', 'rainfall_coping_capacity']], hide_index=True, height=360, column_config={"sfhi_100": st.column_config.NumberColumn("SFHI (0–100)", format="%.1f"), "total_enrolment": st.column_config.NumberColumn("Enrolment", format="%.0f"), "rainfall_coping_capacity": "PMIU capacity"})
def legend_pills(options: list[str], labels: dict, counts: pd.Series, key: str, plain: bool = False) -> list[str]:
    """A clickable, multi-select map legend with live counts — used for every map in the app."""
    def fmt(option: str) -> str:
        if plain:
            plain_key = option if option in PLAIN_PRIORITY else "Unclassified"
            emoji, plain_label, _ = PLAIN_PRIORITY[plain_key]
            return f"{emoji} {plain_label} ({counts.get(option, 0):,})"
        return f"{labels[option]} ({counts.get(option, 0):,})"

    return st.pills(
        "Map legend", options, selection_mode="multi", format_func=fmt, key=key,
        help="Select one or more categories to filter the map. No selection shows every school.",
    )


@st.cache_data(show_spinner=False)
def prepare_map_points(frame: pd.DataFrame, color_column: str, color_map: dict, tooltip_fields: list[str]) -> pd.DataFrame:
    """Trim to only the columns a map actually needs before it hits the browser."""
    keep = ["latitude", "longitude", color_column] + [f for f in tooltip_fields if f not in ("latitude", "longitude", color_column)]
    points = frame.dropna(subset=["latitude", "longitude"])[keep].copy()
    points["map_color"] = points[color_column].map(color_map).apply(
        lambda value: value if isinstance(value, list) else [150, 150, 150, 60]
    )
    return points


def hazard_map(points: pd.DataFrame, layer_id: str, tooltip_html: str) -> pdk.Deck:
    return pdk.Deck(
        map_style=None,
        initial_view_state=PUNJAB_VIEW,
        views=[pdk.View(type="MapView", controller=True)],
        layers=[pdk.Layer(
            "ScatterplotLayer", id=layer_id, data=points, get_position="[longitude, latitude]",
            get_fill_color="map_color", get_radius=450, radius_min_pixels=2, radius_max_pixels=10,
            pickable=True,
        )],
        tooltip={"html": tooltip_html},
    )


def render_school_card(row: pd.Series) -> None:
    emoji, label, explanation = PLAIN_PRIORITY.get(row["combined_priority"], ("⚫", "Not enough data", ""))
    with st.container(border=True):
        st.markdown(f"**{row['school_name']}** — {row['district']}, {row['tehsil']}")
        st.markdown(f"{emoji} **{label}** · {PLAIN_HAZARD_EXPOSURE.get(row['hazard_exposure'], row['hazard_exposure'])}")
        st.caption(explanation)
        with st.expander("See technical details"):
            st.dataframe(
                pd.DataFrame([{
                    "EMIS code": row["emis_code"],
                    "Heatwave priority": row["heatwave_priority"] if pd.notna(row["heatwave_priority"]) else "Not exposed",
                    "Rainfall priority": row["rainfall_priority"] if pd.notna(row["rainfall_priority"]) else "Not exposed",
                    "Combined priority": row["combined_priority"],
                    "Compounding high risk": bool(row["compounding_high_risk"]),
                    "Enrolment (most recent record)": row["combined_enrolment"],
                }]),
                hide_index=True,
            )
            st.caption("For this school's full visit-by-visit history, use Find a school.")


def render_cross_hazard_section(combined_df: pd.DataFrame, show_detail: bool) -> None:
    st.markdown(
        "This page tracks how government schools in Punjab are affected by two kinds of extreme weather — "
        "**heatwaves** and **extreme rainfall** — using official school-visit records matched to weather data "
        "from 2021 onward. It shows which schools are most exposed, how well-equipped they are to cope, and "
        "where the two hazards compound each other."
    )
    if combined_df.empty:
        st.warning("No schools match the current sidebar filters. Clear a filter to see results.", icon=":material/filter_alt_off:")
        return

    urgent = combined_df["combined_priority"].isin(["Priority 1", "Priority 2"]).sum()
    compounding = combined_df["compounding_high_risk"].sum()
    students = combined_df["combined_enrolment"].sum()
    with st.container(horizontal=True):
        st.metric("Schools tracked here", f"{len(combined_df):,}", border=True)
        st.metric("Students in schools with any climate exposure", f"{students:,.0f}", border=True)
        st.metric("Schools needing urgent attention", f"{urgent:,}", border=True)
        st.metric("Schools facing both hazards at once", f"{compounding:,}", border=True)
    st.caption(
        "\"Urgent\" combines how often a school faces extreme weather with how well-equipped it is to cope, "
        "based on its most recent government visit — it's the more severe of the school's heatwave and rainfall "
        "priorities. See the glossary below for exact definitions."
    )

    st.subheader(":material/search: Look up a school")
    picker = combined_df.assign(
        school_choice=combined_df["school_name"].fillna("Unnamed school") + " · " + combined_df["district"].fillna("") + " · " + combined_df["emis_code"].astype(str)
    ).sort_values("school_choice")
    picked = st.selectbox(
        "Pick a school", picker["school_choice"], index=None, key="overview_school_search",
        placeholder="Start typing or pick a school from the list…", label_visibility="collapsed",
    )
    if picked:
        render_school_card(picker.loc[picker["school_choice"] == picked].iloc[0])

    st.subheader(":material/join_inner: Where hazards overlap")
    st.caption("How many exposed schools face one hazard versus both, and which districts have the most schools facing both at once.")
    left, right = st.columns([1, 1.4])
    with left:
        overlap = combined_df["hazard_exposure"].value_counts().reindex(
            ["Heatwave and rainfall", "Heatwave only", "Rainfall only"], fill_value=0
        ).rename_axis("hazard_exposure").reset_index(name="schools")
        st.plotly_chart(
            px.bar(overlap, x="hazard_exposure", y="schools", color="hazard_exposure", text="schools",
                title="Schools by hazard overlap", color_discrete_sequence=px.colors.qualitative.Safe)
            .update_layout(showlegend=False, margin=dict(l=10, r=10, t=55, b=10)),
            width="stretch",
        )
    with right:
        district_overlap = combined_df.groupby("district", dropna=False).agg(
            compounding=("compounding_high_risk", "sum"),
        ).reset_index().sort_values("compounding", ascending=False).head(10)
        st.plotly_chart(
            px.bar(district_overlap.sort_values("compounding"), x="compounding", y="district", orientation="h",
                title="Top 10 districts by compounding-risk school count",
                color="compounding", color_continuous_scale="YlOrRd",
                labels={"compounding": "Compounding-risk schools", "district": "District"})
            .update_layout(margin=dict(l=10, r=10, t=55, b=10)),
            width="stretch",
        )

    st.subheader(":material/map: Where the risk is")
    counts = combined_df["combined_priority"].value_counts()
    selected = legend_pills(COMBINED_PRIORITY_OPTIONS, COMBINED_PRIORITY_LABELS, counts, "combined_priority_pills", plain=not show_detail)
    map_schools = combined_df[combined_df["combined_priority"].isin(selected)] if selected else combined_df
    tooltip_fields = ["school_name", "district", "combined_priority", "heatwave_priority", "rainfall_priority"]
    tooltip_html = (
        "<b>{school_name}</b><br/>{district}<br/>{combined_priority}"
        "<br/>Heatwave: {heatwave_priority}<br/>Rainfall: {rainfall_priority}"
    )
    points = prepare_map_points(map_schools, "combined_priority", PRIORITY_MAP_COLORS, tooltip_fields)
    st.pydeck_chart(hazard_map(points, "combined_priority_schools", tooltip_html), height=480, key="combined_priority_map")
    st.caption(f"Showing {len(map_schools):,} schools on the map.")

    st.subheader(":material/location_city: Districts needing the most attention")
    district_summary = combined_df.groupby("district", dropna=False).agg(
        urgent_schools=("combined_priority", lambda s: s.isin(["Priority 1", "Priority 2"]).sum()),
    ).reset_index().sort_values("urgent_schools", ascending=False).head(10)
    st.plotly_chart(
        px.bar(district_summary.sort_values("urgent_schools"), x="urgent_schools", y="district", orientation="h",
            color="urgent_schools", color_continuous_scale="YlOrRd",
            labels={"urgent_schools": "Schools needing urgent attention", "district": "District"},
            title="Top 10 districts by urgent-attention school count")
        .update_layout(margin=dict(l=10, r=10, t=55, b=10)),
        width="stretch",
    )

    if show_detail:
        combined_shortlist = combined_df.sort_values(
            ["combined_priority_number", "compounding_high_risk", "school_name"],
            ascending=[True, False, True], na_position="last",
        ).head(100)
        with st.container(border=True):
            st.subheader("Compounding-risk shortlist")
            st.caption("The first 100 schools after applying the current filters, ordered by combined priority and compounding risk.")
            st.dataframe(
                combined_shortlist[[
                    "school_name", "district", "tehsil", "hazard_exposure", "heatwave_priority", "rainfall_priority",
                    "combined_priority", "compounding_high_risk",
                ]],
                hide_index=True, height=360,
                column_config={
                    "hazard_exposure": "Hazard exposure",
                    "heatwave_priority": "Heatwave priority",
                    "rainfall_priority": "Rainfall priority",
                    "combined_priority": "Combined priority",
                    "compounding_high_risk": st.column_config.CheckboxColumn("Compounding"),
                },
            )
        st.download_button(
            "Download combined hazard data", combined_df.to_csv(index=False).encode("utf-8"),
            "filtered_combined_hazard_vulnerability.csv", "text/csv",
        )

    st.subheader(":material/help: What do these hazards mean?")
    hazard_left, hazard_right = st.columns(2)
    with hazard_left:
        with st.container(border=True):
            st.markdown("#### 🌡️ Heatwaves")
            st.write(
                "Runs of unusually hot days for the local area — hotter than about 95% of days that area normally "
                "sees. Long heatwaves make classrooms unsafe, especially where a school has no reliable electricity "
                "or drinking water to help students and teachers cope."
            )
    with hazard_right:
        with st.container(border=True):
            st.markdown("#### 🌧️ Extreme rainfall")
            st.write(
                "Days or short spells of rainfall far above what an area normally sees. It can damage buildings, "
                "flood classrooms and toilets, and cut off the path to school — especially where sanitation and "
                "safe water are already weak."
            )

    with st.expander(":material/menu_book: Glossary — what the terms on this page mean"):
        render_table(
            pd.DataFrame([
                ["EMIS code", "The government's unique ID number for a school."],
                ["Government visit (PMIU)", "A field visit by government monitoring staff that records a school's enrolment, classrooms, toilets, electricity and water."],
                ["Exposure", "How often and how severely a school has experienced the hazard since 2021."],
                ["Coping capacity", "How well-equipped the school was, at its most recent relevant visit, to handle that stress — its water, power, toilets, classrooms and (for rainfall) building cleanliness."],
                ["Priority", "Exposure combined with coping capacity, from Urgent (frequent exposure + weak capacity) to Lower concern (infrequent exposure + strong capacity)."],
                ["Compounding risk", "A school independently at Urgent or High concern for both heatwave and extreme rainfall — not just the worse of the two."],
                ["Not enough data", "No recent government visit recorded the facts needed to judge coping capacity. This is a data gap, not a sign the school is safe."],
            ], columns=["Term", "Meaning"]),
            column_widths={"Term": "small"},
        )

    st.caption("For hazard-specific timing, event history and downloadable data, open the Heat or Extreme rainfall sections above.")


def render_hazard_section(cfg: dict, base_frame: pd.DataFrame, frame: pd.DataFrame, show_detail: bool, districts: list[str], levels: list[str]) -> None:
    st.caption(cfg["intro"])
    if show_detail and cfg.get("flood_hazard_note"):
        st.caption(cfg["flood_hazard_note"])
    if cfg["flood_policy_panel"] and frame["hazard_class"].notna().any():
        with st.container(border=True):
            st.markdown("#### :material/flood: Flood filters")
            st.caption("Apply flood-hazard and policy-action filters together to every rainfall result below.")
            flood_hazard_counts = frame["hazard_class"].value_counts()
            flood_action_counts = frame["flood_policy_action"].value_counts()
            with st.container(horizontal=True):
                flood_hazard_filter = st.pills("SFHI hazard class", cfg["flood_hazard_options"], selection_mode="multi", format_func=lambda x: f"{x} ({flood_hazard_counts.get(x, 0):,})", key=f"{cfg['key']}_flood_hazard")
                flood_action_filter = st.pills("Policy action", ["Immediate protection", "Field verification", "Resilience investment", "Monitor and maintain"], selection_mode="multi", format_func=lambda x: f"{x} ({flood_action_counts.get(x, 0):,})", key=f"{cfg['key']}_flood_action")
            if flood_hazard_filter:
                frame = frame[frame["hazard_class"].isin(flood_hazard_filter)]
            if flood_action_filter:
                frame = frame[frame["flood_policy_action"].isin(flood_action_filter)]
    if frame.empty:
        st.warning("No schools match the current filters.", icon=":material/filter_alt_off:")
        return

    high = (frame["exposure_class"] == "High").sum()
    urgent = frame["vulnerability_priority"].isin(["Priority 1", "Priority 2"]).sum()
    no_visit = (frame["monitoring_visit_status"] != cfg["visit_selected_status"]).sum()
    with st.container(horizontal=True):
        st.metric("Schools exposed", f"{len(frame):,}", border=True)
        st.metric("High exposure", f"{high:,}", border=True)
        st.metric("Priority 1–2 schools", f"{urgent:,}", border=True)
        st.metric("No matching PMIU visit", f"{no_visit:,}", border=True)

    with st.container(border=True):
        st.markdown("#### :material/rule: How exposure and coping capacity are measured")
        exposure_col, capacity_col = st.columns([1, 1.5], gap="large")
        with exposure_col:
            st.markdown(f"**{cfg['exposure_amount_label']}**")
            render_table(exposure_rule_table(base_frame, cfg["exposure_class_column"]))
        with capacity_col:
            st.markdown(f"**{cfg['capacity_label']}**")
            render_table(cfg["capacity_rules_fn"](base_frame), column_widths={"Dimension": "medium"})
            if cfg.get("capacity_caption"):
                st.caption(cfg["capacity_caption"])

    counts = frame["vulnerability_priority"].value_counts()
    selected = legend_pills(cfg["priority_options"], cfg["priority_labels"], counts, f"{cfg['key']}_priority_pills", plain=not show_detail)
    map_schools = frame[frame["vulnerability_priority"].isin(selected)] if selected else frame
    points = prepare_map_points(map_schools, "vulnerability_priority", PRIORITY_MAP_COLORS, cfg["tooltip_fields"])
    st.pydeck_chart(hazard_map(points, f"{cfg['key']}_priority_schools", cfg["tooltip_html"]), height=480, key=f"{cfg['key']}_map")
    st.caption(f"Showing {len(map_schools):,} schools on the map.")

    left, right = st.columns(2)
    with left:
        priority_counts = frame["vulnerability_priority"].fillna(cfg["unclassified_label"]).value_counts().reindex(
            cfg["priority_options"], fill_value=0
        ).rename_axis("priority").reset_index(name="schools")
        priority_counts["priority"] = priority_counts["priority"].replace({cfg["unclassified_label"]: "Unclassified"})
        st.plotly_chart(
            px.bar(priority_counts, x="priority", y="schools", color="priority", text="schools",
                title=f"Schools by {cfg['label'].lower()} priority", color_discrete_sequence=px.colors.qualitative.Safe)
            .update_layout(showlegend=False, margin=dict(l=10, r=10, t=55, b=10)),
            width="stretch",
        )
    with right:
        district_summary = frame.groupby("district", dropna=False).agg(
            schools=("emis_code", "size"), mean_amount=(cfg["exposure_amount_column"], "mean"),
        ).reset_index().sort_values("mean_amount", ascending=False).head(15)
        st.plotly_chart(
            px.bar(district_summary, x="mean_amount", y="district", orientation="h",
                title=f"Highest average {cfg['exposure_amount_label'].lower()} by district (top 15)",
                color="mean_amount", color_continuous_scale="YlOrRd",
                labels={"mean_amount": cfg["exposure_amount_label"]})
            .update_layout(margin=dict(l=10, r=10, t=55, b=10)),
            width="stretch",
        )

    if cfg["capacity_dimensions"]:
        dimension_choice = st.selectbox(
            "Capacity dimension breakdown", list(cfg["capacity_dimensions"].values()), key=f"{cfg['key']}_capacity_dimension",
        )
        dimension_column = next(k for k, v in cfg["capacity_dimensions"].items() if v == dimension_choice)
        st.plotly_chart(capacity_chart(frame, dimension_column, dimension_choice), width="stretch")

    shortlist = frame.assign(
        _priority_order=priority_number(frame["vulnerability_priority"]).fillna(99)
    ).sort_values(["_priority_order", "priority_rank", cfg["exposure_amount_column"]], ascending=[True, True, False], na_position="last").head(100)
    with st.container(border=True):
        st.subheader("Priority school shortlist")
        st.caption("The first 100 schools after applying the current filters, ordered by priority category and rank.")
        st.dataframe(shortlist[cfg["shortlist_columns"]], hide_index=True, height=360, column_config=cfg["shortlist_column_config"])

    if show_detail:
        st.dataframe(frame[cfg["full_table_columns"]], hide_index=True, height=420, column_config=cfg["full_table_column_config"])
        st.download_button(
            f"Download {cfg['label'].lower()} data", frame.to_csv(index=False).encode("utf-8"), cfg["download_name"], "text/csv",
        )

    with st.expander(":material/calendar_month: Year-by-year detail"):
        render_year_detail(cfg, districts, levels)

    if cfg.get("extra_panel"):
        with st.expander(cfg["extra_panel_label"]):
            cfg["extra_panel"](districts, levels)
    if cfg["flood_policy_panel"]:
        with st.expander(":material/flood: Flood evidence and policy actions"):
            render_flood_policy_panel(frame)


def render_year_detail(cfg: dict, districts: list[str], levels: list[str]) -> None:
    yearly = apply_filters(cfg["yearly_loader"](), districts, levels)
    years = sorted(yearly[cfg["yearly_year_column"]].dropna().unique())
    if not years:
        st.caption("No year-by-year records match the current filters.")
        return
    selected_year = st.selectbox("Year", years, index=len(years) - 1, key=f"{cfg['key']}_year")
    year_frame = yearly[yearly[cfg["yearly_year_column"]] == selected_year]
    monitored = year_frame["monitoring_date_used"].notna().sum()
    weak = (year_frame[cfg["capacity_column"]] == "Weak").sum()
    with st.container(horizontal=True):
        st.metric("School-year records", f"{len(year_frame):,}", border=True)
        st.metric("Monitoring record available", f"{monitored:,}", border=True)
        st.metric(f"Average {cfg['exposure_amount_label'].lower()}", f"{year_frame[cfg['yearly_amount_column']].mean():.1f}" if len(year_frame) else "—", border=True)
        st.metric("Weak coping capacity", f"{weak:,}", border=True)

    left, right = st.columns(2)
    with left:
        st.plotly_chart(capacity_chart(year_frame, cfg["capacity_column"], f"{cfg['label']} coping capacity"), width="stretch")
    with right:
        district_summary = year_frame.groupby("district", dropna=False).agg(
            schools=("emis_code", "size"), mean_amount=(cfg["yearly_amount_column"], "mean"),
        ).reset_index().sort_values("mean_amount", ascending=False).head(15)
        st.plotly_chart(
            px.bar(district_summary, x="mean_amount", y="district", orientation="h",
                title=f"Highest average {cfg['exposure_amount_label'].lower()} by district (top 15)",
                color="mean_amount", color_continuous_scale="YlOrRd", labels={"mean_amount": cfg["exposure_amount_label"]})
            .update_layout(margin=dict(l=10, r=10, t=55, b=10)),
            width="stretch",
        )

    ranking_options = list(cfg["yearly_ranking_fields"].keys())
    ranking_choice = st.segmented_control("Rank schools by", ranking_options, default=ranking_options[0], key=f"{cfg['key']}_year_rank")
    ranking_field, ranking_label = cfg["yearly_ranking_fields"][ranking_choice]
    ranked = year_frame.dropna(subset=[ranking_field]).nlargest(20, ranking_field)
    if ranked.empty:
        st.caption("No schools with a valid value for this measure in the current selection.")
    else:
        st.plotly_chart(
            px.bar(ranked.sort_values(ranking_field), x=ranking_field, y="school_name", orientation="h",
                color=cfg["capacity_column"], hover_data=["district", "tehsil", cfg["yearly_selected_event_column"], "monitoring_date_used"],
                labels={ranking_field: ranking_label, "school_name": "School", cfg["capacity_column"]: "Coping capacity"},
                title=f"Top 20 schools by {ranking_label.lower()}", color_discrete_sequence=px.colors.qualitative.Safe)
            .update_layout(margin=dict(l=10, r=10, t=50, b=10), yaxis={"categoryorder": "total ascending"}),
            width="stretch",
        )

    st.dataframe(year_frame[cfg["yearly_table_columns"]], hide_index=True, height=380, column_config=cfg["yearly_table_column_config"])
    st.download_button(
        f"Download {selected_year} data", year_frame.to_csv(index=False).encode("utf-8"),
        f"{cfg['yearly_download_prefix']}_{selected_year}.csv", "text/csv", key=f"{cfg['key']}_year_download",
    )


def render_rainfall_event_timeline(districts: list[str], levels: list[str]) -> None:
    _, rainfall_event_groups = load_rainfall_events()
    rain_groups = apply_filters(rainfall_event_groups, districts, levels)
    event_rollup = rain_groups.groupby(
        ["event_code", "event_type", "event_start_date", "event_end_date"], dropna=False
    ).agg(
        schools_in_universe=("schools_in_universe", "sum"),
        schools_exposed=("schools_exposed", "sum"),
        enrolled_students_exposed=("enrolled_students_exposed", "sum"),
        maximum_daily_rainfall_mm_exposed=("maximum_daily_rainfall_mm_exposed", "max"),
        maximum_3day_rainfall_mm_exposed=("maximum_3day_rainfall_mm_exposed", "max"),
    ).reset_index()
    if event_rollup.empty:
        st.caption("No rainfall events match the current district and school-level filters.")
        return
    event_rollup["schools_exposed_percent"] = event_rollup["schools_exposed"] * 100 / event_rollup["schools_in_universe"]
    event_rollup = event_rollup.sort_values("event_start_date")

    event_labels = {
        row.event_code: f"{row.event_start_date:%d %b %Y} · {row.event_code} · {row.event_type}"
        for row in event_rollup.itertuples()
    }
    selected_event_code = st.selectbox("Rainfall event", event_rollup["event_code"], format_func=event_labels.get, key="rainfall_event_select")
    selected_event = event_rollup.loc[event_rollup["event_code"] == selected_event_code].iloc[0]
    with st.container(horizontal=True):
        st.metric("Schools exposed", f"{selected_event['schools_exposed']:,.0f}", border=True)
        st.metric("Share of selection", f"{selected_event['schools_exposed_percent']:.1f}%", border=True)
        st.metric("Students at exposed schools", f"{selected_event['enrolled_students_exposed']:,.0f}", border=True)
        st.metric("Maximum 3-day rainfall", f"{selected_event['maximum_3day_rainfall_mm_exposed']:.1f} mm", border=True)

    event_breakdown = rain_groups[rain_groups["event_code"] == selected_event_code].groupby(
        ["school_level", "school_gender"], dropna=False
    ).agg(schools_exposed=("schools_exposed", "sum"), enrolled_students_exposed=("enrolled_students_exposed", "sum")).reset_index()
    event_measure = st.segmented_control(
        "Break down the selected event by", ["Schools exposed", "Students at exposed schools"],
        default="Schools exposed", key="rainfall_event_measure",
    )
    event_measure_column = "schools_exposed" if event_measure == "Schools exposed" else "enrolled_students_exposed"
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            px.bar(event_rollup, x="schools_exposed", y="event_code", orientation="h", color="event_type",
                hover_data=["event_start_date", "event_end_date", "schools_exposed_percent", "enrolled_students_exposed"],
                labels={"schools_exposed": "Schools exposed", "event_code": "Rainfall event"}, title="All 46 rainfall events")
            .update_layout(margin=dict(l=10, r=10, t=55, b=10), yaxis={"categoryorder": "total ascending"}),
            width="stretch",
        )
    with right:
        st.plotly_chart(
            px.bar(event_breakdown, x=event_measure_column, y="school_level", color="school_gender", barmode="group",
                labels={event_measure_column: event_measure, "school_level": "School level", "school_gender": "School gender"},
                title="Selected event by school level and gender")
            .update_layout(margin=dict(l=10, r=10, t=55, b=10)),
            width="stretch",
        )

    st.dataframe(
        event_rollup[["event_code", "event_type", "event_start_date", "event_end_date", "schools_exposed", "schools_exposed_percent", "enrolled_students_exposed", "maximum_daily_rainfall_mm_exposed", "maximum_3day_rainfall_mm_exposed"]],
        hide_index=True, height=360,
        column_config={
            "event_start_date": st.column_config.DateColumn("Start", format="DD MMM YYYY"),
            "event_end_date": st.column_config.DateColumn("End", format="DD MMM YYYY"),
            "schools_exposed_percent": st.column_config.NumberColumn("Schools exposed", format="%.1f%%"),
            "enrolled_students_exposed": st.column_config.NumberColumn("Students at exposed schools", format="%.0f"),
            "maximum_daily_rainfall_mm_exposed": st.column_config.NumberColumn("Maximum daily rainfall (mm)", format="%.1f"),
            "maximum_3day_rainfall_mm_exposed": st.column_config.NumberColumn("Maximum 3-day rainfall (mm)", format="%.1f"),
        },
    )


def school_profile(frame: pd.DataFrame, yearly_frame: pd.DataFrame, rainfall_frame: pd.DataFrame, rainfall_yearly_frame: pd.DataFrame, key: str) -> None:
    if frame.empty:
        st.warning("No schools match the current filters.", icon=":material/filter_alt_off:")
        return
    choices = frame.assign(
        _priority_order=priority_number(frame["vulnerability_priority"]).fillna(99)
    ).sort_values(["_priority_order", "priority_rank", "school_name"], na_position="last").copy()
    choices["school_choice"] = choices["school_name"].fillna("Unnamed school") + " · " + choices["emis_code"].astype(str)
    selected = st.selectbox("Pick from the list", choices["school_choice"], key=key)
    school = choices.loc[choices["school_choice"] == selected].iloc[0]
    visit_date = school["monitoring_date_used"].strftime("%d %b %Y") if pd.notna(school["monitoring_date_used"]) else "—"
    st.subheader(school["school_name"])
    st.caption(f"{school['district']} · {school['tehsil']} · EMIS {school['emis_code']}")
    with st.container(horizontal=True):
        st.metric("Heatwave priority", school["vulnerability_priority"], border=True)
        st.metric("Heatwave days", f"{school['total_heatwave_days']:.0f}", border=True)
        st.metric("Capacity", school["essential_service_capacity"], border=True)
        st.metric("Selected visit date", visit_date, border=True)

    rain_match = rainfall_frame[rainfall_frame["emis_code"].astype(str) == str(school["emis_code"])]
    if rain_match.empty:
        st.caption("This school has no recorded extreme-rainfall exposure in 2021–2025, or was not matched to a Punjab EMIS code.")
    else:
        rain_school = rain_match.iloc[0]
        rain_visit_date = rain_school["monitoring_date_used"].strftime("%d %b %Y") if pd.notna(rain_school["monitoring_date_used"]) else "—"
        with st.container(horizontal=True):
            st.metric("Rainfall priority", rain_school["vulnerability_priority"], border=True)
            st.metric("Extreme-rainfall days", f"{rain_school['cumulative_extreme_days']:.0f}", border=True)
            st.metric("Coping capacity", rain_school["rainfall_coping_capacity"], border=True)
            st.metric("Selected visit date", rain_visit_date, border=True)
        st.caption(f"Exposure class: {rain_school['exposure_class']} · Events exposed since 2021: {rain_school['events_exposed_count']:.0f}")

    st.subheader("School visit record")
    st.caption(
        "One row per year with a heatwave and/or rainfall exposure record, most recent first — heatwave and "
        "rainfall use separately matched PMIU visits, so their visit dates can differ. A blank cell means that "
        "hazard had no exposure or no matching visit that year."
    )
    hw_hist = yearly_frame[yearly_frame["emis_code"].astype(str) == str(school["emis_code"])][[
        "event_year", "selected_event_code", "selected_event_heatwave_days", "monitoring_date_used",
        "total_enrolment", "students_per_classroom", "functional_toilets", "electricity_status",
        "water_status", "essential_service_capacity", "data_quality_flag",
    ]]
    rf_hist = rainfall_yearly_frame[rainfall_yearly_frame["emis_code"].astype(str) == str(school["emis_code"])][[
        "event_year", "selected_event_code", "selected_event_extreme_days", "monitoring_date_used",
        "structural_condition_status", "learning_space_status", "sanitation_status", "safe_water_status",
        "rainfall_coping_capacity", "data_quality_flag",
    ]]
    visit_record = pd.merge(hw_hist, rf_hist, on="event_year", how="outer", suffixes=("_heat", "_rain"))
    visit_record["data_quality_flag"] = visit_record["data_quality_flag_heat"].combine_first(visit_record["data_quality_flag_rain"])
    visit_record = visit_record.sort_values("event_year", ascending=False)
    display_columns = [
        "event_year",
        "selected_event_code_heat", "selected_event_heatwave_days", "monitoring_date_used_heat",
        "electricity_status", "water_status", "essential_service_capacity",
        "selected_event_code_rain", "selected_event_extreme_days", "monitoring_date_used_rain",
        "structural_condition_status", "learning_space_status", "sanitation_status", "safe_water_status", "rainfall_coping_capacity",
        "total_enrolment", "students_per_classroom", "functional_toilets", "data_quality_flag",
    ]
    st.dataframe(
        visit_record[display_columns], hide_index=True, height=420,
        column_config={
            "event_year": st.column_config.NumberColumn("Year", format="%d"),
            "selected_event_code_heat": "Heatwave event",
            "selected_event_heatwave_days": st.column_config.NumberColumn("Heatwave days", format="%.0f"),
            "monitoring_date_used_heat": st.column_config.DateColumn("Heatwave visit date", format="DD MMM YYYY"),
            "electricity_status": "Electricity",
            "water_status": "Water",
            "essential_service_capacity": "Heatwave capacity",
            "selected_event_code_rain": "Rainfall event",
            "selected_event_extreme_days": st.column_config.NumberColumn("Rainfall days", format="%.0f"),
            "monitoring_date_used_rain": st.column_config.DateColumn("Rainfall visit date", format="DD MMM YYYY"),
            "structural_condition_status": "Structural",
            "learning_space_status": "Learning space",
            "sanitation_status": "Sanitation",
            "safe_water_status": "Safe water",
            "rainfall_coping_capacity": "Rainfall capacity",
            "total_enrolment": st.column_config.NumberColumn("Enrolment", format="%.0f"),
            "students_per_classroom": st.column_config.NumberColumn("Students/classroom", format="%d"),
            "functional_toilets": st.column_config.NumberColumn("Functional toilets", format="%.0f"),
            "data_quality_flag": "Data quality",
        },
    )


def render_school_lookup(cum: pd.DataFrame, rainfall_cumulative: pd.DataFrame) -> None:
    st.caption("Search or pick a school to see its full heatwave and rainfall history.")
    query = st.text_input(
        "Type a school name", placeholder="e.g. Government Girls High School Model Town", key="lookup_search",
    )
    frame = cum
    if query:
        matches = cum[cum["school_name"].str.contains(query, case=False, na=False)]
        if matches.empty:
            st.caption("No school matched that name. Showing every school in the current filter instead.")
        else:
            frame = matches
    school_profile(frame, load_yearly(), rainfall_cumulative, load_rainfall_yearly(), "school_lookup_select")


def render_method(cumulative: pd.DataFrame, rainfall_cumulative: pd.DataFrame) -> None:
    st.caption("A quick guide to the atlas, its data choices, and the vulnerability-priority logic.")

    with st.container(border=True):
        st.markdown("#### :material/flag: What this atlas answers")
        st.write(
            "**Where and when are schools in Punjab exposed to extreme heat and extreme rainfall, and how many "
            "students, by school level and gender, are affected?**"
        )
        st.write(
            "This dashboard answers that question for Punjab government schools, 2021–2026: every recorded "
            "heatwave and extreme-rainfall event, matched to each school's location, combined with the school's "
            "own coping capacity from the nearest government (PMIU) monitoring visit — producing ranked district "
            "and school lists for both hazards, and a cross-hazard view of the schools facing both at once."
        )

    with st.container(border=True):
        st.markdown("#### :material/explore: How to read the atlas")
        st.caption("Use the sidebar filters and the technical-detail toggle to shape the same school population everywhere.")
        render_table(
            pd.DataFrame([
                ["Sidebar filters", "District and school level", "Filters every section."],
                ["Show technical detail (sidebar)", "Raw priority codes, driver columns and CSV downloads", "Off by default for a plain-language view; turn on for the full underlying data and downloads."],
                ["Where the risk is", "Cross-hazard headline numbers, school search, hazard overlap, combined-priority map, districts needing attention", "Start here for the single-page view of overall climate risk."],
                ["Heat", "Cumulative heatwave exposure since 2021, coping-capacity rules, priority map and shortlist, year-by-year detail", "Drill into heatwave-only risk and targeting."],
                ["Extreme rainfall", "Cumulative extreme-rainfall exposure since 2021, coping-capacity rules, priority map and shortlist, the 46-event timeline, year-by-year detail", "Drill into rainfall-only risk, timing and targeting."],
                ["Find a school", "Search or pick any school; see its full heatwave and rainfall history", "Use for a single school's story."],
                ["How this works", "Definitions, matching rules, and priority construction for both hazards and the combined view", "Use this section when interpreting or reporting dashboard results."],
            ], columns=["Section", "What it shows", "How to use it"]),
            column_widths={"Section": "medium", "What it shows": "large", "How to use it": "large"},
        )

    with st.container(border=True):
        st.markdown("#### :material/public: How the combined hazard view is built")
        st.caption(
            "'Where the risk is' is a per-school overlay of the two independent hazard-specific priorities below — "
            "it does not recompute exposure or capacity from scratch."
        )
        render_table(
            pd.DataFrame([
                ["Hazard exposure", "Heatwave only, Rainfall only, or Heatwave and rainfall", "Based on whether the school appears in the heatwave and/or rainfall cumulative vulnerability files."],
                ["Combined priority", "The more severe (lower-numbered) of the heatwave and rainfall priorities", "Not an average. A school at heatwave Priority 1 and rainfall Priority 4 is shown as combined Priority 1."],
                ["Combined priority driver", "Which hazard produced the combined priority: Heatwave, Rainfall, or Both (tied)", "Shown in the map tooltip and useful for deciding which single-hazard section to open next."],
                ["Compounding high risk", "True when a school is independently Priority 1 or 2 on both heatwave and rainfall", "The clearest signal of a school needing attention on more than one hazard, not just the more severe one."],
                ["Unclassified", "Neither hazard could assign a numbered priority", "Usually missing PMIU capacity data for both hazards, not evidence of low risk."],
            ], columns=["Field", "Values", "Rule"]),
            column_widths={"Field": "medium"},
        )

    with st.container(border=True):
        st.markdown("#### :material/flood: How flood evidence becomes a policy action")
        st.caption("This is a separate decision layer in Extreme rainfall; it does not replace the established PMIU-based rainfall priority.")
        render_table(pd.DataFrame([
            ["Confirmed high flood hazard", "High rainfall exposure and Sentinel-1 flood evidence at or above the live 67th percentile among schools with observed flood signal", "Immediate protection when PMIU capacity is Weak or Partial; resilience investment when capacity is Adequate."],
            ["Evidence disagreement", "High rainfall with limited satellite flood evidence, or repeated satellite flood evidence with lower rainfall exposure", "Field verification: assess drainage, river/canal exposure, imagery timing, and local conditions."],
            ["Lower flood evidence", "Neither signal is elevated", "Monitor and maintain."],
        ], columns=["Evidence state", "Rule", "Policy action"]), column_widths={"Evidence state": "medium", "Policy action": "medium"})
        st.caption("SFHI hazard class and policy-action filters are in the sidebar. Enrolment shows the potential scale of impact; it does not change the action category.")

    with st.container(border=True):
        st.markdown("#### :material/account_tree: How heatwave priorities are set")
        st.caption("Priority is calculated from the full cumulative school dataset before dashboard filters are applied.")
        exposure_step, capacity_step = st.columns([1, 1.4], gap="large")
        with exposure_step:
            st.badge("Step 1 · Exposure", icon=":material/thermostat:", color="orange")
            st.markdown("**Cumulative heatwave exposure**")
            render_table(exposure_rule_table(cumulative, "total_heatwave_days"))
        with capacity_step:
            st.badge("Step 2 · School capacity", icon=":material/electric_bolt:", color="blue")
            st.markdown("**Essential services at the selected PMIU visit**")
            render_table(
                pd.DataFrame([
                    ["Adequate", "Electricity and drinking water are both available, functional, and wholly provided."],
                    ["Weak", "Electricity and drinking water are both unavailable or non-functional."],
                    ["Partial", "Any other observed combination, including one adequate service and one weak/partial service."],
                    ["Missing", "No eligible heatwave-year visit, or electricity/water availability or functionality is missing."],
                ], columns=["Class", "Rule"]),
            )
        method_priority_counts = cumulative["vulnerability_priority"].value_counts()
        st.badge("Step 3 · Priority", icon=":material/priority_high:", color="red")
        st.markdown("**Combine exposure and capacity**")
        render_table(
            pd.DataFrame([
                [PRIORITY_LABELS["Priority 1"], "High", "Weak", f"{int(method_priority_counts.get('Priority 1', 0)):,}"],
                [PRIORITY_LABELS["Priority 2"], "High", "Partial", f"{int(method_priority_counts.get('Priority 2', 0)):,}"],
                [PRIORITY_LABELS["Priority 3"], "High", "Adequate", f"{int(method_priority_counts.get('Priority 3', 0)):,}"],
                [PRIORITY_LABELS["Priority 4"], "Low or moderate", "Weak or partial", f"{int(method_priority_counts.get('Priority 4', 0)):,}"],
                [PRIORITY_LABELS["Priority 5"], "Low or moderate", "Adequate", f"{int(method_priority_counts.get('Priority 5', 0)):,}"],
                [PRIORITY_LABELS["Unclassified - PMIU missing"], "Any", "Missing", f"{int(method_priority_counts.get('Unclassified - PMIU missing', 0)):,}"],
            ], columns=["Priority", "Exposure", "Capacity", "Schools"]),
            column_widths={"Priority": "medium"},
        )
        st.info(
            "Priority rank orders schools within each category by cumulative heatwave days, then EMIS code. "
            "It supports review and targeting; it is not a causal estimate. Facility status describes the selected visit, not a cumulative physical condition.",
            icon=":material/info:",
        )

    with st.container(border=True):
        st.markdown("#### :material/water_drop: How rainfall priorities are set")
        st.caption(
            "Rainfall priority follows the same two-step exposure-then-capacity logic as heatwave, using four "
            "coping-capacity proxies recorded at PMIU visits. Only exposed schools (events_exposed_count > 0) receive a priority."
        )
        rain_exposure_step, rain_capacity_step = st.columns([1, 1.6], gap="large")
        with rain_exposure_step:
            st.badge("Step 1 · Exposure", icon=":material/water_drop:", color="blue")
            st.markdown("**Cumulative rainfall exposure**")
            st.caption("Composite of event frequency, intensity and persistence — see the Extreme rainfall section.")
            render_table(exposure_rule_table(rainfall_cumulative, "rainfall_exposure_score"))
        with rain_capacity_step:
            st.badge("Step 2 · Coping capacity", icon=":material/handyman:", color="orange")
            st.markdown("**Four PMIU-visit proxies, scored at the visit closest to one of the school's exposed rainfall years**")
            render_table(rain_capacity_rules(rainfall_cumulative), column_widths={"Dimension": "medium"})
            st.caption("Each of the four scored dimensions contributes Adequate = 2, Partial = 1, Weak = 0 to a 0–8 capacity score.")
        rain_priority_counts = rainfall_cumulative["vulnerability_priority"].value_counts()
        st.badge("Step 3 · Priority", icon=":material/priority_high:", color="red")
        st.markdown("**Combine exposure and coping capacity**")
        render_table(
            pd.DataFrame([
                [PRIORITY_LABELS["Priority 1"], "High", "Weak", f"{int(rain_priority_counts.get('Priority 1', 0)):,}"],
                [PRIORITY_LABELS["Priority 2"], "High", "Partial", f"{int(rain_priority_counts.get('Priority 2', 0)):,}"],
                [PRIORITY_LABELS["Priority 3"], "High", "Adequate", f"{int(rain_priority_counts.get('Priority 3', 0)):,}"],
                [PRIORITY_LABELS["Priority 4"], "Low or moderate", "Weak or partial", f"{int(rain_priority_counts.get('Priority 4', 0)):,}"],
                [PRIORITY_LABELS["Priority 5"], "Low or moderate", "Adequate", f"{int(rain_priority_counts.get('Priority 5', 0)):,}"],
                [PRIORITY_LABELS["Unclassified - PMIU missing"], "Any", "Missing", f"{int(rain_priority_counts.get('Unclassified - capacity data missing', 0)):,}"],
            ], columns=["Priority", "Exposure", "Capacity", "Schools"]),
            column_widths={"Priority": "medium"},
        )
        st.info(
            "Priority rank orders schools within each category by rainfall exposure score, then EMIS code. It supports "
            "review and targeting, not a causal estimate. Schools never exposed to an extreme-rainfall event are excluded "
            "from priority, not scored as low-risk.",
            icon=":material/info:",
        )

HEAT_CONFIG = {
    "key": "heat",
    "label": "Heat",
    "intro": "Every government school in Punjab exposed to at least one recorded heatwave, 2021–2026.",
    "visit_selected_status": "heatwave-year visit selected",
    "exposure_amount_column": "total_heatwave_days",
    "exposure_amount_label": "Heatwave days",
    "exposure_class_column": "total_heatwave_days",
    "capacity_column": "essential_service_capacity",
    "capacity_label": "Essential-service capacity (electricity & water)",
    "capacity_rules_fn": heat_capacity_rules,
    "capacity_rules_height": 145,
    "capacity_dimensions": HEAT_CAPACITY_DIMENSIONS,
    "priority_options": PRIORITY_OPTIONS,
    "priority_labels": PRIORITY_LABELS,
    "unclassified_label": "Unclassified - PMIU missing",
    "tooltip_fields": ["school_name", "district", "vulnerability_priority", "total_heatwave_days"],
    "tooltip_html": "<b>{school_name}</b><br/>{district}<br/>{vulnerability_priority}<br/>{total_heatwave_days} heatwave days",
    "shortlist_columns": ["priority_rank", "school_name", "district", "tehsil", "total_heatwave_days", "essential_service_capacity", "monitoring_date_used", "monitoring_visit_status"],
    "shortlist_column_config": {
        "priority_rank": st.column_config.NumberColumn("Priority rank", format="%d"),
        "total_heatwave_days": st.column_config.NumberColumn("Heatwave days", format="%.0f"),
        "monitoring_date_used": st.column_config.DateColumn("Selected visit date", format="DD MMM YYYY"),
        "monitoring_visit_status": "Monitoring status",
    },
    "full_table_columns": ["emis_code", "school_name", "district", "tehsil", "total_heatwave_days", "total_heatwave_events", "monitoring_date_used", "monitoring_visit_status", "students_per_classroom", "students_per_functional_toilet", "essential_service_capacity", "vulnerability_priority", "data_quality_flag"],
    "full_table_column_config": {"students_per_classroom": st.column_config.NumberColumn("Students per usable classroom", format="%d")},
    "download_name": "filtered_heatwave_school_vulnerability.csv",
    "yearly_loader": load_yearly,
    "yearly_year_column": "event_year",
    "yearly_amount_column": "total_heatwave_days_year",
    "yearly_selected_event_column": "selected_event_code",
    "yearly_ranking_fields": {
        "Selected-event heatwave days": ("selected_event_heatwave_days", "Heatwave days during selected event"),
        "Classroom pressure": ("students_per_classroom", "Students per usable classroom"),
        "Toilet pressure": ("students_per_functional_toilet", "Students per functional toilet"),
    },
    "yearly_table_columns": ["emis_code", "school_name", "district", "tehsil", "event_year", "total_heatwave_days_year", "selected_event_code", "monitoring_date_used", "days_from_selected_event_start", "total_enrolment", "students_per_classroom", "students_per_functional_toilet", "essential_service_capacity", "data_quality_flag"],
    "yearly_table_column_config": {"students_per_classroom": st.column_config.NumberColumn("Students per usable classroom", format="%d")},
    "yearly_download_prefix": "filtered_school_year_heatwave_capacity",
    "extra_panel": None,
    "flood_hazard_note": None,
    "flood_hazard_options": None,
    "flood_hazard_caption": None,
    "flood_policy_panel": False,
}

RAIN_CONFIG = {
    "key": "rain",
    "label": "Extreme rainfall",
    "intro": "Every government school in Punjab exposed to at least one of the 46 extreme-rainfall events, 2021–2025.",
    "visit_selected_status": "rainfall-event-year visit selected",
    "exposure_amount_column": "cumulative_extreme_days",
    "exposure_amount_label": "Extreme-rainfall days",
    "exposure_class_column": "rainfall_exposure_score",
    "capacity_column": "rainfall_coping_capacity",
    "capacity_label": "Coping capacity (structural, learning space, sanitation, safe water)",
    "capacity_rules_fn": rain_capacity_rules,
    "capacity_rules_height": 214,
    "capacity_caption": "Each of the four scored dimensions contributes Adequate = 2, Partial = 1, Weak = 0 to a 0–8 capacity score. Sewerage/drainage is not scored — free-text mentions cover under 1% of visits.",
    "capacity_dimensions": RAINFALL_CAPACITY_DIMENSIONS,
    "priority_options": RAINFALL_PRIORITY_OPTIONS,
    "priority_labels": RAINFALL_PRIORITY_LABELS,
    "unclassified_label": "Unclassified - capacity data missing",
    "tooltip_fields": ["school_name", "district", "vulnerability_priority", "exposure_class", "rainfall_coping_capacity"],
    "tooltip_html": "<b>{school_name}</b><br/>{district}<br/>{vulnerability_priority}<br/>Exposure: {exposure_class} · Capacity: {rainfall_coping_capacity}",
    "shortlist_columns": ["priority_rank", "school_name", "district", "tehsil", "exposure_class", "rainfall_coping_capacity", "cumulative_extreme_days", "monitoring_date_used", "monitoring_visit_status"],
    "shortlist_column_config": {
        "priority_rank": st.column_config.NumberColumn("Priority rank", format="%d"),
        "cumulative_extreme_days": st.column_config.NumberColumn("Extreme-rainfall days", format="%.0f"),
        "monitoring_date_used": st.column_config.DateColumn("Selected visit date", format="DD MMM YYYY"),
        "monitoring_visit_status": "Monitoring status",
        "rainfall_coping_capacity": "Coping capacity",
    },
    "full_table_columns": ["emis_code", "school_name", "district", "tehsil", "school_level", "school_gender", "sfhi_100", "hazard_class", "s1_flood_frequency", "events_exposed_count", "event_exposure_frequency_percent", "cumulative_extreme_days", "maximum_daily_rainfall_mm", "maximum_3day_rainfall_mm", "rainfall_exposure_score", "exposure_class", "total_enrolment", "classrooms_used_for_teaching", "functional_toilets", "building_cleanliness", "structural_condition_status", "learning_space_status", "sanitation_status", "safe_water_status", "rainfall_coping_capacity", "vulnerability_priority", "data_quality_flag"],
    "full_table_column_config": {
        "sfhi_100": st.column_config.NumberColumn("School Flood Hazard Index (0–100)", format="%.1f"),
        "hazard_class": "Flood hazard class",
        "s1_flood_frequency": st.column_config.NumberColumn("Sentinel-1 flood frequency", format="%.3f"),
        "event_exposure_frequency_percent": st.column_config.NumberColumn("Event exposure", format="%.1f%%"),
        "rainfall_exposure_score": st.column_config.NumberColumn("Exposure score", format="%.1f"),
        "maximum_daily_rainfall_mm": st.column_config.NumberColumn("Maximum daily rainfall (mm)", format="%.1f"),
        "maximum_3day_rainfall_mm": st.column_config.NumberColumn("Maximum 3-day rainfall (mm)", format="%.1f"),
        "rainfall_coping_capacity": "Coping capacity",
    },
    "download_name": "filtered_rainfall_school_vulnerability.csv",
    "yearly_loader": load_rainfall_yearly,
    "yearly_year_column": "event_year",
    "yearly_amount_column": "total_extreme_rainfall_days_year",
    "yearly_selected_event_column": "selected_event_code",
    "yearly_ranking_fields": {
        "Selected-event extreme-rainfall days": ("selected_event_extreme_days", "Extreme-rainfall days during selected event"),
        "Classroom pressure": ("students_per_classroom", "Students per usable classroom"),
        "Toilet pressure": ("students_per_functional_toilet", "Students per functional toilet"),
    },
    "yearly_table_columns": ["emis_code", "school_name", "district", "tehsil", "event_year", "total_extreme_rainfall_days_year", "selected_event_code", "monitoring_date_used", "days_from_selected_event_start", "total_enrolment", "students_per_classroom", "students_per_functional_toilet", "rainfall_coping_capacity", "data_quality_flag"],
    "yearly_table_column_config": {"students_per_classroom": st.column_config.NumberColumn("Students per usable classroom", format="%d")},
    "yearly_download_prefix": "filtered_school_year_rainfall_capacity",
    "extra_panel": render_rainfall_event_timeline,
    "extra_panel_label": ":material/history: When extreme-rainfall events affected schools (46-event timeline)",
    "flood_hazard_note": "The School Flood Hazard Index is joined to the nearest-event PMIU indicators by corrected EMIS code. It combines equally weighted, 0–1-normalized CHIRP rainfall exposure and Sentinel-1 flood evidence; it is available for review and download, but does not change the existing rainfall priority.",
    "flood_hazard_options": ["Very High", "High", "Moderate", "Low", "Very Low"],
    "flood_hazard_caption": "SFHI flood-hazard class combines CHIRP rainfall exposure and Sentinel-1 flood evidence with equal weight. It filters the map, charts, shortlist, technical table and download below; it does not replace the PMIU-based rainfall vulnerability priority.",
    "flood_policy_panel": True,
}


REQUIRED_FILES = [
    CUMULATIVE_FILE, YEARLY_FILE, RAINFALL_EVENTS_FILE, RAINFALL_EVENT_GROUPS_FILE,
    RAINFALL_CUMULATIVE_FILE, RAINFALL_YEARLY_FILE,
]
if any(not file.exists() for file in REQUIRED_FILES):
    st.error("Required analysis files are missing. Keep this app beside the heatwave and rainfall output CSV files.")
    st.stop()

cumulative = load_cumulative()
rainfall_cumulative = load_rainfall_cumulative(
    FLOOD_HAZARD_FILE.stat().st_mtime_ns if FLOOD_HAZARD_FILE.exists() else None
)

st.title(":material/public: Punjab school climate risk")
st.caption("How heatwaves and extreme rainfall affect government schools in Punjab, 2021 onward — and which schools need attention.")

section = st.segmented_control("Section", SECTIONS, default=SECTIONS[0], key="section", label_visibility="collapsed")
if section is None:
    section = SECTIONS[0]

st.sidebar.header(":material/tune: Filters")
districts = select_values(
    "District", pd.concat([cumulative["district"], rainfall_cumulative["district"]], ignore_index=True), "district",
)
levels = select_values(
    "School level", pd.concat([cumulative["school_level"], rainfall_cumulative["school_level"]], ignore_index=True), "level",
)
show_detail = st.sidebar.toggle("Show technical detail", value=False, key="show_detail", help="Reveals raw priority codes, driver columns, full data tables and CSV downloads.")
st.sidebar.caption("Filters apply everywhere.")

cum = apply_filters(cumulative, districts, levels)
rain_cap = apply_filters(rainfall_cumulative, districts, levels)
combined = apply_filters(build_combined(cumulative, rainfall_cumulative), districts, levels)

if section == SECTIONS[0]:
    render_cross_hazard_section(combined, show_detail)
elif section == SECTIONS[1]:
    render_hazard_section(HEAT_CONFIG, cumulative, cum, show_detail, districts, levels)
elif section == SECTIONS[2]:
    render_hazard_section(RAIN_CONFIG, rainfall_cumulative, rain_cap, show_detail, districts, levels)
elif section == SECTIONS[3]:
    render_school_lookup(cum, rainfall_cumulative)
else:
    render_method(cumulative, rainfall_cumulative)
