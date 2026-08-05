"""Punjab school climate-exposure dashboard."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st


ROOT = Path(__file__).parent
CUMULATIVE_FILE = ROOT / "final_school_heatwave_vulnerability_nearest_event.csv"
YEARLY_FILE = ROOT / "school_year_heatwave_capacity.csv"
RAINFALL_SCHOOLS_FILE = ROOT / "punjab_school_rainfall_exposure_clean.csv"
RAINFALL_EVENTS_FILE = ROOT / "punjab_rainfall_event_summary.csv"
RAINFALL_EVENT_GROUPS_FILE = ROOT / "punjab_rainfall_event_disaggregation.csv"
RAINFALL_CUMULATIVE_FILE = ROOT / "final_school_rainfall_vulnerability_nearest_event.csv"
RAINFALL_YEARLY_FILE = ROOT / "school_year_rainfall_capacity.csv"
RAINFALL_CAPACITY_DIMENSIONS = {
    "structural_condition_status": "Structural condition (building cleanliness)",
    "learning_space_status": "Learning-space continuity (classrooms)",
    "sanitation_status": "Sanitation (toilets)",
    "safe_water_status": "Safe water",
}
PRIORITY_OPTIONS = [
    "Priority 1",
    "Priority 2",
    "Priority 3",
    "Priority 4",
    "Priority 5",
    "Unclassified - PMIU missing",
]
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

st.set_page_config(
    page_title="School Exposure Atlas",
    page_icon=":material/map:",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_data(show_spinner="Loading cumulative school data…")
def load_cumulative() -> pd.DataFrame:
    return pd.read_csv(CUMULATIVE_FILE, dtype={"emis_code": "string"}, parse_dates=["monitoring_date_used"])


@st.cache_data(show_spinner="Loading school-year data…")
def load_yearly() -> pd.DataFrame:
    frame = pd.read_csv(YEARLY_FILE, dtype={"emis_code": "string"}, low_memory=False)
    for column in ("selected_event_start_date", "selected_event_end_date", "monitoring_date_used"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


@st.cache_data(show_spinner="Loading rainfall school exposure data…")
def load_rainfall_schools() -> pd.DataFrame:
    return pd.read_csv(RAINFALL_SCHOOLS_FILE, dtype={"emis_code": "string"})


@st.cache_data(show_spinner="Loading rainfall event summaries…")
def load_rainfall_events() -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(RAINFALL_EVENTS_FILE, parse_dates=["event_start_date", "event_end_date"])
    groups = pd.read_csv(RAINFALL_EVENT_GROUPS_FILE, parse_dates=["event_start_date", "event_end_date"])
    return events, groups


@st.cache_data(show_spinner="Loading rainfall coping-capacity data…")
def load_rainfall_cumulative() -> pd.DataFrame:
    return pd.read_csv(RAINFALL_CUMULATIVE_FILE, dtype={"emis_code": "string"}, parse_dates=["monitoring_date_used"])


@st.cache_data(show_spinner="Loading rainfall-year monitoring data…")
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
        "essential_service_capacity", "vulnerability_priority",
    ]].rename(columns={
        "exposure_class": "heatwave_exposure_class",
        "essential_service_capacity": "heatwave_capacity",
        "vulnerability_priority": "heatwave_priority",
    })
    rf = rainfall[shared + [
        "emis_code", "cumulative_extreme_days", "events_exposed_count", "exposure_class",
        "rainfall_coping_capacity", "vulnerability_priority",
    ]].rename(columns={
        "exposure_class": "rainfall_exposure_class",
        "rainfall_coping_capacity": "rainfall_capacity",
        "vulnerability_priority": "rainfall_priority",
    })
    combined = hw.merge(rf, on="emis_code", how="outer", suffixes=("", "_rf"))
    for column in shared:
        combined[column] = combined[column].combine_first(combined[f"{column}_rf"])
        combined = combined.drop(columns=[f"{column}_rf"])

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
        counts,
        x=category,
        y="schools",
        color=category,
        text="schools",
        title=title,
        color_discrete_sequence=px.colors.qualitative.Safe,
    ).update_layout(showlegend=False, margin=dict(l=10, r=10, t=55, b=10))


def priority_map(frame: pd.DataFrame, priority_column: str, tooltip_html: str, layer_id: str) -> pdk.Deck:
    map_data = frame.dropna(subset=["latitude", "longitude"]).copy()
    map_data["map_color"] = map_data[priority_column].map(PRIORITY_MAP_COLORS).apply(
        lambda value: value if isinstance(value, list) else [150, 150, 150, 60]
    )
    return pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(latitude=30.5, longitude=71.5, zoom=6.2, pitch=20),
        layers=[pdk.Layer(
            "ScatterplotLayer", id=layer_id, data=map_data, get_position="[longitude, latitude]",
            get_fill_color="map_color", get_radius=450, radius_min_pixels=2, radius_max_pixels=10,
            pickable=True,
        )],
        tooltip={"html": tooltip_html},
    )


def rainfall_exposure_map(frame: pd.DataFrame) -> pdk.Deck:
    map_data = frame.dropna(subset=["latitude", "longitude"]).copy()
    colors = {
        "High": [173, 32, 32, 210],
        "Moderate": [232, 126, 4, 170],
        "Low": [246, 190, 0, 110],
        "No recorded exposure": [120, 130, 145, 40],
    }
    map_data["map_color"] = map_data["exposure_class"].map(colors).apply(
        lambda value: value if isinstance(value, list) else [150, 150, 150, 60]
    )
    return pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(latitude=30.5, longitude=71.5, zoom=6.2, pitch=20),
        layers=[pdk.Layer(
            "ScatterplotLayer", id="rainfall_schools", data=map_data, get_position="[longitude, latitude]",
            get_fill_color="map_color", get_radius=450, radius_min_pixels=2, radius_max_pixels=10,
            pickable=True,
        )],
        tooltip={"html": "<b>{school_name}</b><br/>{district}<br/>{exposure_class}<br/>{events_exposed_count} of 46 rainfall events<br/>{cumulative_extreme_days} extreme-rainfall days"},
    )


def school_profile(
    frame: pd.DataFrame, yearly_frame: pd.DataFrame,
    rainfall_frame: pd.DataFrame, rainfall_yearly_frame: pd.DataFrame, key: str,
) -> None:
    if frame.empty:
        st.warning("No schools match the current filters.", icon=":material/filter_alt_off:")
        return
    choices = frame.assign(
        _priority_order=frame["vulnerability_priority"].str.extract(r"Priority (\d)")[0].astype(float).fillna(99)
    ).sort_values(["_priority_order", "priority_rank", "school_name"], na_position="last").copy()
    choices["school_choice"] = choices["school_name"].fillna("Unnamed school") + " · " + choices["emis_code"].astype(str)
    selected = st.selectbox("Find a school", choices["school_choice"], key=key)
    school = choices.loc[choices["school_choice"] == selected].iloc[0]
    visit_date = school["monitoring_date_used"].strftime("%d %b %Y") if pd.notna(school["monitoring_date_used"]) else "—"
    st.subheader(school["school_name"])
    st.caption(f"{school['district']} · {school['tehsil']} · EMIS {school['emis_code']}")
    with st.container(horizontal=True):
        st.metric("Vulnerability", school["vulnerability_priority"], border=True)
        st.metric("Heatwave days", f"{school['total_heatwave_days']:.0f}", border=True)
        st.metric("Capacity", school["essential_service_capacity"], border=True)
        st.metric("Selected visit date", visit_date, border=True)
    st.dataframe(
        pd.DataFrame([{
            "Enrolment": school["total_enrolment"],
            "Students per classroom": school["students_per_classroom"],
            "Students per functional toilet": school["students_per_functional_toilet"],
            "Electricity": school["electricity_status"],
            "Water": school["water_status"],
            "Selected visit date": school["monitoring_date_used"],
            "Data quality": school["data_quality_flag"],
        }]),
        hide_index=True,
        column_config={
            "Students per classroom": st.column_config.NumberColumn(format="%d"),
            "Students per functional toilet": st.column_config.NumberColumn(format="%.1f"),
            "Selected visit date": st.column_config.DateColumn(format="DD MMM YYYY"),
        },
    )
    st.subheader("Heatwave-year monitoring history")
    st.caption("One selected monitoring visit per heatwave year. A blank monitoring date means there was no PMIU visit in that year.")
    history = yearly_frame[yearly_frame["emis_code"].astype(str) == str(school["emis_code"])].sort_values("event_year")
    history_columns = [
        "event_year", "selected_event_code", "selected_event_start_date", "selected_event_heatwave_days",
        "monitoring_date_used", "days_from_selected_event_start", "total_enrolment", "students_per_classroom",
        "functional_toilets", "electricity_status", "water_status", "essential_service_capacity", "data_quality_flag",
    ]
    st.dataframe(
        history[history_columns], hide_index=True,
        column_config={
            "event_year": st.column_config.NumberColumn("Heatwave year", format="%d"),
            "selected_event_code": "Selected heatwave event",
            "selected_event_start_date": st.column_config.DateColumn("Event start", format="DD MMM YYYY"),
            "selected_event_heatwave_days": st.column_config.NumberColumn("Event heatwave days", format="%.0f"),
            "monitoring_date_used": st.column_config.DateColumn("Selected monitoring date", format="DD MMM YYYY"),
            "days_from_selected_event_start": st.column_config.NumberColumn("Days from event start", format="%d"),
            "total_enrolment": st.column_config.NumberColumn("Enrolment", format="%.0f"),
            "students_per_classroom": st.column_config.NumberColumn("Students per classroom", format="%d"),
            "functional_toilets": st.column_config.NumberColumn("Functional toilets", format="%.0f"),
            "essential_service_capacity": "Service capacity",
            "data_quality_flag": "Data quality",
        },
    )

    st.divider()
    st.subheader("Rainfall exposure & coping capacity")
    rain_match = rainfall_frame[rainfall_frame["emis_code"].astype(str) == str(school["emis_code"])]
    if rain_match.empty:
        st.caption("This school has no recorded extreme-rainfall exposure in 2021–2025, or was not matched to a Punjab EMIS code.")
    else:
        rain_school = rain_match.iloc[0]
        rain_visit_date = (
            rain_school["monitoring_date_used"].strftime("%d %b %Y") if pd.notna(rain_school["monitoring_date_used"]) else "—"
        )
        with st.container(horizontal=True):
            st.metric("Rainfall priority", rain_school["vulnerability_priority"], border=True)
            st.metric("Extreme-rainfall days", f"{rain_school['cumulative_extreme_days']:.0f}", border=True)
            st.metric("Coping capacity", rain_school["rainfall_coping_capacity"], border=True)
            st.metric("Selected visit date", rain_visit_date, border=True)
        st.dataframe(
            pd.DataFrame([{
                "Events exposed": rain_school["events_exposed_count"],
                "Exposure class": rain_school["exposure_class"],
                "Structural condition": rain_school["structural_condition_status"],
                "Learning-space continuity": rain_school["learning_space_status"],
                "Sanitation": rain_school["sanitation_status"],
                "Safe water": rain_school["safe_water_status"],
                "Selected visit date": rain_school["monitoring_date_used"],
                "Data quality": rain_school["data_quality_flag"],
            }]),
            hide_index=True,
            column_config={"Selected visit date": st.column_config.DateColumn(format="DD MMM YYYY")},
        )
        st.caption("Rainfall-year monitoring history — one selected monitoring visit per exposed rainfall year.")
        rain_history = rainfall_yearly_frame[
            rainfall_yearly_frame["emis_code"].astype(str) == str(school["emis_code"])
        ].sort_values("event_year")
        rain_history_columns = [
            "event_year", "selected_event_code", "selected_event_start_date", "selected_event_extreme_days",
            "monitoring_date_used", "days_from_selected_event_start", "total_enrolment",
            "structural_condition_status", "learning_space_status", "sanitation_status", "safe_water_status",
            "rainfall_coping_capacity", "data_quality_flag",
        ]
        st.dataframe(
            rain_history[rain_history_columns], hide_index=True,
            column_config={
                "event_year": st.column_config.NumberColumn("Rainfall year", format="%d"),
                "selected_event_code": "Selected rainfall event",
                "selected_event_start_date": st.column_config.DateColumn("Event start", format="DD MMM YYYY"),
                "selected_event_extreme_days": st.column_config.NumberColumn("Event extreme-rainfall days", format="%.0f"),
                "monitoring_date_used": st.column_config.DateColumn("Selected monitoring date", format="DD MMM YYYY"),
                "days_from_selected_event_start": st.column_config.NumberColumn("Days from event start", format="%d"),
                "total_enrolment": st.column_config.NumberColumn("Enrolment", format="%.0f"),
                "rainfall_coping_capacity": "Coping capacity",
                "data_quality_flag": "Data quality",
            },
        )


REQUIRED_FILES = [
    CUMULATIVE_FILE, YEARLY_FILE, RAINFALL_SCHOOLS_FILE, RAINFALL_EVENTS_FILE, RAINFALL_EVENT_GROUPS_FILE,
    RAINFALL_CUMULATIVE_FILE, RAINFALL_YEARLY_FILE,
]
if any(not file.exists() for file in REQUIRED_FILES):
    st.error("Required analysis files are missing. Keep this app beside the heatwave and rainfall output CSV files.")
    st.stop()

cumulative = load_cumulative()
yearly = load_yearly()
rainfall_schools = load_rainfall_schools()
rainfall_events, rainfall_event_groups = load_rainfall_events()
rainfall_cumulative = load_rainfall_cumulative()
rainfall_yearly = load_rainfall_yearly()

st.title(":material/map: School exposure atlas")
st.caption("Punjab school exposure to heatwaves and extreme rainfall, with heatwave-year monitoring context where available.")

st.sidebar.header(":material/tune: Filters")
districts = select_values("District", cumulative["district"], "district")
levels = select_values("School level", cumulative["school_level"], "level")
st.sidebar.caption("Filters apply to both views. The annual view also has a year filter.")

cum = apply_filters(cumulative, districts, levels)
annual = apply_filters(yearly, districts, levels)
rain_cap = apply_filters(rainfall_cumulative, districts, levels)
combined = apply_filters(build_combined(cumulative, rainfall_cumulative), districts, levels)

tab_combined, tab_overview, tab_cumulative, tab_annual, tab_rainfall, tab_profile, tab_notes = st.tabs([
    ":material/public: Combined hazards",
    ":material/dashboard: Heatwave decision view", ":material/monitoring: Heatwave cumulative view",
    ":material/calendar_month: Heatwave school-year view", ":material/water_drop: Rainfall exposure & priority",
    ":material/school: School profile", ":material/info: Method",
])

with tab_combined:
    st.caption(
        "Every school exposed to at least one recorded hazard (heatwave or extreme rainfall), 2021–2026. "
        "Combined priority takes the more severe of the two hazard-specific priorities per school; it does not average them."
    )
    both_count = (combined["hazard_exposure"] == "Heatwave and rainfall").sum()
    compounding_count = combined["compounding_high_risk"].sum()
    combined_urgent = combined["combined_priority"].isin(["Priority 1", "Priority 2"]).sum()
    with st.container(horizontal=True):
        st.metric("Schools exposed to at least one hazard", f"{len(combined):,}", border=True)
        st.metric("Exposed to both heatwave and rainfall", f"{both_count:,}", border=True)
        st.metric("Compounding high risk (Priority 1–2 in both)", f"{compounding_count:,}", border=True)
        st.metric("Combined Priority 1–2 schools", f"{combined_urgent:,}", border=True)

    st.subheader("Hazard overlap")
    st.caption("How many exposed schools face one hazard versus both, in the current filter selection.")
    left, right = st.columns([1, 1.4])
    with left:
        overlap = combined["hazard_exposure"].value_counts().reindex(
            ["Heatwave and rainfall", "Heatwave only", "Rainfall only"], fill_value=0
        ).rename_axis("hazard_exposure").reset_index(name="schools")
        st.plotly_chart(
            px.bar(overlap, x="hazard_exposure", y="schools", color="hazard_exposure", text="schools",
                title="Schools by hazard overlap", color_discrete_sequence=px.colors.qualitative.Safe)
            .update_layout(showlegend=False, margin=dict(l=10, r=10, t=55, b=10)),
            width="stretch",
        )
    with right:
        district_overlap = combined.groupby("district", dropna=False).agg(
            schools=("emis_code", "size"),
            both_hazards=("hazard_exposure", lambda s: (s == "Heatwave and rainfall").sum()),
            compounding=("compounding_high_risk", "sum"),
        ).reset_index().sort_values("compounding", ascending=False).head(15)
        st.plotly_chart(
            px.bar(district_overlap, x="compounding", y="district", orientation="h",
                title="Most compounding-risk schools by district (top 15)",
                color="compounding", color_continuous_scale="YlOrRd",
                labels={"compounding": "Compounding-risk schools", "district": "District"})
            .update_layout(margin=dict(l=10, r=10, t=55, b=10)),
            width="stretch",
        )

    st.subheader("Combined vulnerability priority")
    st.caption(
        "Priority is the more severe of the heatwave and rainfall priorities for each school. "
        "'Unclassified' means neither hazard-specific priority could be determined (usually missing PMIU capacity data)."
    )
    combined_priority_counts = combined["combined_priority"].value_counts()
    combined_priorities = st.pills(
        "Map priority legend",
        COMBINED_PRIORITY_OPTIONS,
        selection_mode="multi",
        format_func=lambda priority: f"{COMBINED_PRIORITY_LABELS[priority]} ({combined_priority_counts.get(priority, 0):,})",
        key="combined_priority_map_filter",
    )
    combined_map_schools = (
        combined[combined["combined_priority"].isin(combined_priorities)] if combined_priorities else combined
    )
    combined_tooltip = (
        "<b>{school_name}</b><br/>{district}<br/>{combined_priority} (driver: {combined_priority_driver})"
        "<br/>Heatwave: {heatwave_priority}<br/>Rainfall: {rainfall_priority}"
    )
    st.pydeck_chart(
        priority_map(combined_map_schools, "combined_priority", combined_tooltip, "combined_priority_schools"),
        height=520, key="combined_priority_map",
    )
    st.caption(f"Showing {len(combined_map_schools):,} schools on the map.")

    combined_shortlist = combined.sort_values(
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
        "Download combined hazard data", combined.to_csv(index=False).encode("utf-8"),
        "filtered_combined_hazard_vulnerability.csv", "text/csv",
    )
    st.info(
        "This is a two-hazard overlay (heatwave × rainfall), not the full Workstream 3 composite risk index. It does not "
        "include district-level SES, population density or poverty proxies, or Workstream 2's observed enrolment "
        "sensitivity — none of that data is available in this repository yet.",
        icon=":material/info:",
    )

with tab_overview:
    urgent = cum["vulnerability_priority"].isin(["Priority 1", "Priority 2"]).sum()
    high = (cum["exposure_class"] == "High").sum()
    missing = (cum["monitoring_visit_status"] != "heatwave-year visit selected").sum()
    with st.container(horizontal=True):
        st.metric("Priority 1–2 schools", f"{urgent:,}", border=True)
        st.metric("High-exposure schools", f"{high:,}", border=True)
        st.metric("No heatwave-year visit", f"{missing:,}", border=True)
        st.metric("Schools in selection", f"{len(cum):,}", border=True)

    st.subheader("Priority schools at a glance")
    st.caption("Select one or more priorities to filter the map. No selection shows all schools; hover over a point for details.")
    map_counts = cum["vulnerability_priority"].value_counts()
    map_priorities = st.pills(
        "Map priority legend",
        PRIORITY_OPTIONS,
        selection_mode="multi",
        format_func=lambda priority: f"{PRIORITY_LABELS[priority]} ({map_counts.get(priority, 0):,})",
        key="map_priority_filter",
    )
    map_schools = cum[cum["vulnerability_priority"].isin(map_priorities)] if map_priorities else cum
    heatwave_tooltip = "<b>{school_name}</b><br/>{district}<br/>{vulnerability_priority}<br/>{total_heatwave_days} heatwave days"
    st.pydeck_chart(priority_map(map_schools, "vulnerability_priority", heatwave_tooltip, "heatwave_priority_schools"), height=520, key="priority_map")
    st.caption(f"Showing {len(map_schools):,} schools on the map.")

    shortlist = cum.assign(
        _priority_order=cum["vulnerability_priority"].str.extract(r"Priority (\d)")[0].astype(float).fillna(99)
    ).sort_values(["_priority_order", "priority_rank", "total_heatwave_days"], na_position="last").head(100)
    with st.container(border=True):
        st.subheader("Priority school shortlist")
        st.caption("The first 100 schools after applying the current filters, ordered by the existing priority rank.")
        st.dataframe(
            shortlist[["priority_rank", "school_name", "district", "tehsil", "total_heatwave_days", "essential_service_capacity", "monitoring_date_used", "monitoring_visit_status"]],
            hide_index=True, height=360,
            column_config={
                "priority_rank": st.column_config.NumberColumn("Priority rank", format="%d"),
                "total_heatwave_days": st.column_config.NumberColumn("Heatwave days", format="%.0f"),
                "monitoring_date_used": st.column_config.DateColumn("Selected visit date", format="DD MMM YYYY"),
                "monitoring_visit_status": "Monitoring status",
            },
        )

with tab_cumulative:
    cumulative_counts = cum["vulnerability_priority"].value_counts()
    priorities = st.pills(
        "Filter cumulative view by priority",
        PRIORITY_OPTIONS,
        selection_mode="multi",
        format_func=lambda priority: f"{PRIORITY_LABELS[priority]} ({cumulative_counts.get(priority, 0):,})",
        key="cumulative_priority_filter",
        help="Select one or more priorities. No selection includes every category.",
    )
    if priorities:
        cum = cum[cum["vulnerability_priority"].isin(priorities)]

    urgent = cum["vulnerability_priority"].isin(["Priority 1", "Priority 2"]).sum()
    available = cum["monitoring_date_used"].notna().sum()
    with st.container(horizontal=True):
        st.metric("Schools", f"{len(cum):,}", border=True)
        st.metric("Average heatwave days", f"{cum['total_heatwave_days'].mean():.1f}" if len(cum) else "—", border=True)
        st.metric("Priority 1 or 2", f"{urgent:,}", border=True)
        st.metric("Monitoring record available", f"{available:,}", border=True)

    left, right = st.columns(2)
    with left:
        priority = cum["vulnerability_priority"].fillna("Unclassified - PMIU missing").value_counts().reindex(PRIORITY_OPTIONS, fill_value=0)
        priority = priority.rename_axis("priority").reset_index(name="schools")
        priority["priority"] = priority["priority"].replace({"Unclassified - PMIU missing": "Unclassified"})
        st.plotly_chart(px.bar(priority, x="priority", y="schools", color="priority", text="schools",
            title="Schools by vulnerability priority", color_discrete_sequence=px.colors.qualitative.Safe)
            .update_layout(showlegend=False, margin=dict(l=10, r=10, t=55, b=10)), width="stretch")
    with right:
        district_summary = cum.groupby("district", dropna=False).agg(
            schools=("emis_code", "size"), mean_heatwave_days=("total_heatwave_days", "mean")
        ).reset_index().sort_values("mean_heatwave_days", ascending=False).head(15)
        st.plotly_chart(px.bar(district_summary, x="mean_heatwave_days", y="district", orientation="h",
            color="mean_heatwave_days", title="Highest average exposure by district (top 15)",
            color_continuous_scale="YlOrRd").update_layout(margin=dict(l=10, r=10, t=55, b=10)), width="stretch")

    pressure = cum[
        cum["vulnerability_priority"].isin(["Priority 1", "Priority 2", "Priority 3"])
    ].dropna(subset=["students_per_classroom"]).nlargest(20, "students_per_classroom")
    with st.container(border=True):
        st.subheader("Highest classroom pressure among Priority 1–3 schools")
        st.caption("This ranking highlights schools that combine high or moderate heatwave vulnerability with the highest observed number of students per usable classroom. It does not apply an external overcrowding threshold.")
        if pressure.empty:
            st.caption("No Priority 1–3 schools with a valid classroom count match the current filters.")
        else:
            st.plotly_chart(px.bar(pressure.sort_values("students_per_classroom"), x="students_per_classroom", y="school_name",
                orientation="h", color="total_heatwave_days", color_continuous_scale="YlOrRd",
                hover_data=["district", "tehsil", "functional_toilets", "students_per_functional_toilet", "monitoring_date_used"],
                labels={"students_per_classroom": "Students per usable classroom", "school_name": "School", "total_heatwave_days": "Heatwave days"})
                .update_layout(margin=dict(l=10, r=10, t=30, b=10), yaxis={"categoryorder": "total ascending"}), width="stretch")

    display_columns = ["emis_code", "school_name", "district", "tehsil", "total_heatwave_days", "total_heatwave_events",
                       "monitoring_date_used", "monitoring_visit_status", "students_per_classroom", "students_per_functional_toilet",
                       "essential_service_capacity", "vulnerability_priority", "data_quality_flag"]
    st.dataframe(cum[display_columns], hide_index=True, height=420, column_config={
        "students_per_classroom": st.column_config.NumberColumn("Students per usable classroom", format="%d"),
    })
    st.download_button("Download filtered cumulative data", cum.to_csv(index=False).encode("utf-8"),
        "filtered_cumulative_school_vulnerability.csv", "text/csv")

with tab_annual:
    years = sorted(annual["event_year"].dropna().unique())
    selected_year = st.selectbox("Heatwave year", years, index=len(years) - 1)
    annual = annual[annual["event_year"] == selected_year]
    monitored = annual["monitoring_date_used"].notna().sum()
    weak = (annual["essential_service_capacity"] == "Weak").sum()
    with st.container(horizontal=True):
        st.metric("School-year records", f"{len(annual):,}", border=True)
        st.metric("Monitoring record available", f"{monitored:,}", border=True)
        st.metric("Average heatwave days", f"{annual['total_heatwave_days_year'].mean():.1f}" if len(annual) else "—", border=True)
        st.metric("Weak service capacity", f"{weak:,}", border=True)

    left, right = st.columns(2)
    with left:
        st.plotly_chart(capacity_chart(annual, "essential_service_capacity", "Essential-service capacity"), width="stretch")
    with right:
        district_summary = annual.groupby("district", dropna=False).agg(
            schools=("emis_code", "size"), mean_heatwave_days=("total_heatwave_days_year", "mean")
        ).reset_index().sort_values("mean_heatwave_days", ascending=False).head(15)
        st.plotly_chart(px.bar(district_summary, x="mean_heatwave_days", y="district", orientation="h",
            title="Highest average exposure by district (top 15)", color="mean_heatwave_days", color_continuous_scale="YlOrRd")
            .update_layout(margin=dict(l=10, r=10, t=55, b=10)), width="stretch")

    with st.container(border=True):
        st.subheader("School priority ranking")
        st.caption("Choose one measure to identify the 20 schools that most need review in the selected heatwave year. Hover over a bar for the selected heatwave event and monitoring visit date.")
        ranking_choice = st.segmented_control(
            "Rank schools by",
            ["Selected-event heatwave days", "Classroom pressure", "Toilet pressure"],
            default="Selected-event heatwave days",
            key="annual_ranking_choice",
        )
        ranking_fields = {
            "Selected-event heatwave days": ("selected_event_heatwave_days", "Heatwave days during selected event"),
            "Classroom pressure": ("students_per_classroom", "Students per usable classroom"),
            "Toilet pressure": ("students_per_functional_toilet", "Students per functional toilet"),
        }
        ranking_field, ranking_label = ranking_fields[ranking_choice]
        ranked_schools = annual.dropna(subset=[ranking_field]).nlargest(20, ranking_field)
        st.plotly_chart(px.bar(
            ranked_schools.sort_values(ranking_field), x=ranking_field, y="school_name", orientation="h",
            color="essential_service_capacity", hover_data=["district", "tehsil", "selected_event_code", "monitoring_date_used", "days_from_selected_event_start", "total_enrolment"],
            labels={ranking_field: ranking_label, "school_name": "School", "essential_service_capacity": "Service capacity"},
            title=f"Top 20 schools by {ranking_label.lower()}", color_discrete_sequence=px.colors.qualitative.Safe,
        ).update_layout(margin=dict(l=10, r=10, t=50, b=10), yaxis={"categoryorder": "total ascending"}), width="stretch")
    display_columns = ["emis_code", "school_name", "district", "tehsil", "event_year", "total_heatwave_days_year",
                       "selected_event_code", "monitoring_date_used", "days_from_selected_event_start", "total_enrolment",
                       "students_per_classroom", "students_per_functional_toilet", "essential_service_capacity", "data_quality_flag"]
    st.dataframe(annual[display_columns], hide_index=True, height=420, column_config={
        "students_per_classroom": st.column_config.NumberColumn("Students per usable classroom", format="%d"),
    })
    st.download_button("Download filtered school-year data", annual.to_csv(index=False).encode("utf-8"),
        f"filtered_school_year_heatwave_capacity_{selected_year}.csv", "text/csv")

with tab_rainfall:
    rain = apply_filters(rainfall_schools, districts, levels)
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
    event_rollup["schools_exposed_percent"] = event_rollup["schools_exposed"] * 100 / event_rollup["schools_in_universe"]
    event_rollup = event_rollup.sort_values("event_start_date")

    st.caption("Workstream 1: 46 extreme-rainfall events, 2021–2025. Enrolment is the school record supplied with the exposure data; it is not a measure of enrolment disruption.")
    ever_exposed = rain["ever_exposed_to_extreme_rainfall"].eq(1)
    with st.container(horizontal=True):
        st.metric("Schools in selection", f"{len(rain):,}", border=True)
        st.metric("Ever exposed", f"{ever_exposed.sum():,}", border=True)
        st.metric("High exposure", f"{rain['exposure_class'].eq('High').sum():,}", border=True)
        st.metric("Students at ever-exposed schools", f"{rain.loc[ever_exposed, 'total_enrolment'].sum():,.0f}", border=True)

    st.subheader("Where schools have experienced extreme rainfall")
    exposure_classes = ["High", "Moderate", "Low", "No recorded exposure"]
    selected_classes = st.pills(
        "Exposure class on map", exposure_classes, selection_mode="multi", key="rainfall_map_exposure_class",
        help="Select one or more classes. No selection shows all schools.",
    )
    st.caption("Map legend — colours show cumulative rainfall exposure; the pills above filter the displayed points.")
    with st.container(horizontal=True, gap="small"):
        st.badge("High · above the 67th percentile", icon=":material/circle:", color="red")
        st.badge("Moderate · 33rd–67th percentile", icon=":material/circle:", color="orange")
        st.badge("Low · at or below the 33rd percentile", icon=":material/circle:", color="yellow")
        st.badge("No recorded exposure", icon=":material/circle:", color="gray")
    rainfall_map_schools = rain[rain["exposure_class"].isin(selected_classes)] if selected_classes else rain
    st.pydeck_chart(rainfall_exposure_map(rainfall_map_schools), height=520, key="rainfall_exposure_map")
    st.caption(f"Showing {len(rainfall_map_schools):,} schools. High, moderate and low classes use percentile cut-offs among schools exposed at least once.")

    st.subheader("When extreme-rainfall events affected schools")
    if event_rollup.empty:
        st.warning("No rainfall events match the current district and school-level filters.", icon=":material/filter_alt_off:")
    else:
        event_labels = {
            row.event_code: f"{row.event_start_date:%d %b %Y} · {row.event_code} · {row.event_type}"
            for row in event_rollup.itertuples()
        }
        selected_event_code = st.selectbox("Rainfall event", event_rollup["event_code"], format_func=event_labels.get)
        selected_event = event_rollup.loc[event_rollup["event_code"] == selected_event_code].iloc[0]
        with st.container(horizontal=True):
            st.metric("Schools exposed", f"{selected_event['schools_exposed']:,.0f}", border=True)
            st.metric("Share of selection", f"{selected_event['schools_exposed_percent']:.1f}%", border=True)
            st.metric("Students at exposed schools", f"{selected_event['enrolled_students_exposed']:,.0f}", border=True)
            st.metric("Maximum 3-day rainfall", f"{selected_event['maximum_3day_rainfall_mm_exposed']:.1f} mm", border=True)

        event_breakdown = rain_groups[rain_groups["event_code"] == selected_event_code].groupby(
            ["school_level", "school_gender"], dropna=False
        ).agg(
            schools_exposed=("schools_exposed", "sum"),
            enrolled_students_exposed=("enrolled_students_exposed", "sum"),
        ).reset_index()
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
                    labels={"schools_exposed": "Schools exposed", "event_code": "Rainfall event"},
                    title="All 46 rainfall events")
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

    st.subheader("School-level cumulative rainfall exposure")
    rainfall_table = rain.sort_values(["rainfall_exposure_score", "events_exposed_count"], ascending=False)
    st.dataframe(
        rainfall_table[["emis_code", "school_name", "district", "tehsil", "school_level", "school_gender", "events_exposed_count", "event_exposure_frequency_percent", "cumulative_extreme_days", "maximum_daily_rainfall_mm", "maximum_3day_rainfall_mm", "rainfall_exposure_score", "exposure_class"]],
        hide_index=True, height=420,
        column_config={
            "event_exposure_frequency_percent": st.column_config.NumberColumn("Event exposure", format="%.1f%%"),
            "rainfall_exposure_score": st.column_config.NumberColumn("Exposure score", format="%.1f"),
            "maximum_daily_rainfall_mm": st.column_config.NumberColumn("Maximum daily rainfall (mm)", format="%.1f"),
            "maximum_3day_rainfall_mm": st.column_config.NumberColumn("Maximum 3-day rainfall (mm)", format="%.1f"),
        },
    )
    st.download_button(
        "Download filtered rainfall school data", rainfall_table.to_csv(index=False).encode("utf-8"),
        "filtered_punjab_school_rainfall_exposure.csv", "text/csv",
    )

    st.subheader("Rainfall coping-capacity priority")
    st.caption(
        "Combines each school's cumulative rainfall exposure with PMIU-visit proxies for structural condition, "
        "learning-space continuity, sanitation and safe water. Sewerage/drainage is not scored — free-text mentions "
        "cover under 1% of visits. Uses the PMIU visit closest to one of the school's own extreme-rainfall events, "
        "matched by calendar year, the same nearest-visit rule used for heatwave."
    )
    rain_priority_counts = rain_cap["vulnerability_priority"].value_counts()
    urgent_rain = rain_cap["vulnerability_priority"].isin(["Priority 1", "Priority 2"]).sum()
    weak_capacity = (rain_cap["rainfall_coping_capacity"] == "Weak").sum()
    with st.container(horizontal=True):
        st.metric("Exposed schools with a priority", f"{len(rain_cap):,}", border=True)
        st.metric("Priority 1–2 schools", f"{urgent_rain:,}", border=True)
        st.metric("Weak coping capacity", f"{weak_capacity:,}", border=True)
        st.metric("No PMIU capacity match", f"{rain_priority_counts.get('Unclassified - capacity data missing', 0):,}", border=True)

    rain_priorities = st.pills(
        "Map priority legend",
        RAINFALL_PRIORITY_OPTIONS,
        selection_mode="multi",
        format_func=lambda priority: f"{RAINFALL_PRIORITY_LABELS[priority]} ({rain_priority_counts.get(priority, 0):,})",
        key="rainfall_priority_map_filter",
    )
    rain_map_schools = rain_cap[rain_cap["vulnerability_priority"].isin(rain_priorities)] if rain_priorities else rain_cap
    rainfall_priority_tooltip = "<b>{school_name}</b><br/>{district}<br/>{vulnerability_priority}<br/>Exposure: {exposure_class} · Capacity: {rainfall_coping_capacity}"
    st.pydeck_chart(priority_map(rain_map_schools, "vulnerability_priority", rainfall_priority_tooltip, "rainfall_priority_schools"), height=520, key="rainfall_priority_map")
    st.caption(f"Showing {len(rain_map_schools):,} exposed schools on the map.")

    left, right = st.columns(2)
    with left:
        priority = rain_cap["vulnerability_priority"].fillna("Unclassified - capacity data missing").value_counts().reindex(
            RAINFALL_PRIORITY_OPTIONS, fill_value=0
        ).rename_axis("priority").reset_index(name="schools")
        st.plotly_chart(px.bar(priority, x="priority", y="schools", color="priority", text="schools",
            title="Exposed schools by rainfall vulnerability priority", color_discrete_sequence=px.colors.qualitative.Safe)
            .update_layout(showlegend=False, margin=dict(l=10, r=10, t=55, b=10)), width="stretch")
    with right:
        dimension_choice = st.selectbox("Capacity dimension", list(RAINFALL_CAPACITY_DIMENSIONS.values()), key="rainfall_capacity_dimension")
        dimension_column = next(key for key, label in RAINFALL_CAPACITY_DIMENSIONS.items() if label == dimension_choice)
        st.plotly_chart(capacity_chart(rain_cap, dimension_column, dimension_choice), width="stretch")

    rain_shortlist = rain_cap.assign(
        _priority_order=rain_cap["vulnerability_priority"].str.extract(r"Priority (\d)")[0].astype(float).fillna(99)
    ).sort_values(["_priority_order", "priority_rank", "rainfall_exposure_score"], ascending=[True, True, False]).head(100)
    with st.container(border=True):
        st.subheader("Priority school shortlist")
        st.caption("The first 100 exposed schools after applying the current filters, ordered by priority category and rank.")
        st.dataframe(
            rain_shortlist[["priority_rank", "school_name", "district", "tehsil", "exposure_class", "rainfall_coping_capacity",
                             "cumulative_extreme_days", "monitoring_date_used", "monitoring_visit_status"]],
            hide_index=True, height=360,
            column_config={
                "priority_rank": st.column_config.NumberColumn("Priority rank", format="%d"),
                "cumulative_extreme_days": st.column_config.NumberColumn("Extreme-rainfall days", format="%.0f"),
                "monitoring_date_used": st.column_config.DateColumn("Selected visit date", format="DD MMM YYYY"),
                "monitoring_visit_status": "Monitoring status",
                "rainfall_coping_capacity": "Coping capacity",
            },
        )
    st.download_button(
        "Download rainfall vulnerability priority data", rain_cap.to_csv(index=False).encode("utf-8"),
        "filtered_school_rainfall_vulnerability_priority.csv", "text/csv",
    )
    st.info(
        "Rainfall-enrolment disruption is not yet estimated here. It requires an event-study design over the "
        "monthly enrolment panel, matching exposed and unexposed schools around each event.",
        icon=":material/info:",
    )

with tab_profile:
    st.caption(
        "Search finds schools from the heatwave-exposed population. Service and infrastructure values come from the "
        "PMIU visit closest to a heatwave (or, in the rainfall section below, an extreme-rainfall event) in the same year."
    )
    school_profile(cum, yearly, rainfall_cumulative, rainfall_yearly, "school_profile")

with tab_notes:
    st.subheader("Method")
    st.caption("A quick guide to the atlas, its data choices, and the vulnerability-priority logic.")

    with st.container(border=True):
        st.markdown("#### :material/explore: How to read the atlas")
        st.caption("Each section answers a different question. Use the sidebar filters to narrow the same school population throughout.")
        st.dataframe(
            pd.DataFrame([
                ["Sidebar filters", "District and school level", "Filters every tab's school-level results, including Combined hazards."],
                ["Combined hazards: headline metrics", "Schools exposed to at least one hazard, both hazards, and compounding-risk counts", "Start here for a single view of overall climate risk across the two hazards."],
                ["Combined hazards: overlap", "Bar chart and district ranking of heatwave-only, rainfall-only, and both-hazard schools", "Identifies districts where the two hazards compound rather than just co-occur."],
                ["Combined hazards: priority map & shortlist", "Schools coloured by combined priority, with the driving hazard in the tooltip", "Use for cross-hazard targeting; drill into a single hazard using the dedicated tabs below."],
                ["Heatwave decision view: headline metrics", "Counts of exposed, high-exposure, urgent, and unmatched schools", "A quick summary of the current district and level selection, heatwave only."],
                ["Heatwave decision view: priority map", "School locations coloured by heatwave vulnerability priority", "Use the priority pills to show one or several categories; hover for school details."],
                ["Heatwave decision view: shortlist", "First 100 schools ordered by priority category and rank", "Use as a review or targeting list, not as a causal-impact ranking."],
                ["Heatwave cumulative view", "One row per exposed school; heatwave exposure summed across 2021–2026", "Capacity comes from the closest eligible PMIU visit in one of that school's heatwave years."],
                ["Heatwave cumulative: classroom pressure", "Priority 1–3 schools with the most students per usable classroom", "Highlights schools where heat exposure and observed classroom pressure overlap."],
                ["Heatwave school-year view", "One row per school and heatwave year", "Uses one PMIU visit: the visit closest to a heatwave in that same year."],
                ["Heatwave school-year: priority ranking", "Top 20 schools for exposure, classroom pressure, or toilet pressure", "Switch the measure to review different operational pressures."],
                ["Rainfall exposure & priority", "Punjab exposure across 46 extreme-rainfall events, 2021–2025, plus rainfall vulnerability priority", "Use the event selector for timing and composition; use the priority section for PMIU-linked coping capacity and targeting."],
                ["School profile: heatwave summary", "Cumulative heatwave exposure and selected school-capacity indicators", "Describes the chosen school using the heatwave cumulative output."],
                ["School profile: heatwave visit history", "One selected monitoring visit for every exposed heatwave year", "A blank date means no PMIU visit was available in that year."],
                ["School profile: rainfall section", "Cumulative rainfall exposure, capacity, and rainfall-year visit history for the same school", "Shows 'no recorded exposure' if the selected school was never in an extreme-rainfall footprint."],
                ["Method", "Definitions, matching rules, and priority construction for both hazards and the combined view", "Use this section when interpreting or reporting dashboard results."],
            ], columns=["Tab / section", "What it shows", "How to use it"]),
            hide_index=True,
            height=940,
            row_height=52,
            column_config={
                "Tab / section": st.column_config.TextColumn(width="medium"),
                "What it shows": st.column_config.TextColumn(width="large"),
                "How to use it": st.column_config.TextColumn(width="large"),
            },
        )

    with st.container(border=True):
        st.markdown("#### :material/fact_check: Workstream coverage")
        st.dataframe(
            pd.DataFrame([
                ["Policy Question 1", "Where and when schools are exposed, and the affected school/enrolment counts", "Heatwave and rainfall exposure views support this for Punjab; rainfall is disaggregated by school level and gender."],
                ["Policy Question 2", "Whether climate events cause enrolment disruption, recovery or persistent decline", "Not yet estimated. This requires a monthly enrolment panel and an exposed-versus-unexposed event-study design."],
                ["Risk prioritisation", "Which exposed schools also have weak capacity", "Available for heatwave and rainfall. Rainfall capacity uses PMIU-visit proxies (cleanliness, classrooms, toilets, water); no ASC/SIS structural or drainage extract was available, so drainage is excluded."],
                ["Workstream 3 (compounding exposure)", "Which schools and districts face both hazards at once", "Partial. The Combined hazards tab overlays heatwave and rainfall priority per school, but is not the full Tier A composite index — it has no district-level SES, population density or poverty proxies, and no Workstream 2 sensitivity input."],
            ], columns=["Question", "Dashboard coverage", "Current status"]),
            hide_index=True,
            height=270,
            row_height=56,
            column_config={
                "Question": st.column_config.TextColumn(width="medium"),
                "Dashboard coverage": st.column_config.TextColumn(width="large"),
                "Current status": st.column_config.TextColumn(width="large"),
            },
        )

    with st.container(border=True):
        st.markdown("#### :material/public: How the combined hazard view is built")
        st.caption(
            "The Combined hazards tab is a per-school overlay of the two independent hazard-specific priorities below — "
            "it does not recompute exposure or capacity from scratch."
        )
        st.dataframe(
            pd.DataFrame([
                ["Hazard exposure", "Heatwave only, Rainfall only, or Heatwave and rainfall", "Based on whether the school appears in the heatwave and/or rainfall cumulative vulnerability files."],
                ["Combined priority", "The more severe (lower-numbered) of the heatwave and rainfall priorities", "Not an average. A school at heatwave Priority 1 and rainfall Priority 4 is shown as combined Priority 1."],
                ["Combined priority driver", "Which hazard produced the combined priority: Heatwave, Rainfall, or Both (tied)", "Shown in the map tooltip and useful for deciding which single-hazard tab to open next."],
                ["Compounding high risk", "True when a school is independently Priority 1 or 2 on both heatwave and rainfall", "The clearest signal of a school needing attention on more than one hazard, not just the more severe one."],
                ["Unclassified", "Neither hazard could assign a numbered priority", "Usually missing PMIU capacity data for both hazards, not evidence of low risk."],
            ], columns=["Field", "Values", "Rule"]),
            hide_index=True,
            height=214,
            row_height=56,
            column_config={"Field": st.column_config.TextColumn(width="medium")},
        )
        st.info(
            "This overlay only combines Workstream 1 exposure and capacity for two hazards. It is a simplified stand-in "
            "for Workstream 3's Tier A composite risk index, which additionally requires observed enrolment sensitivity "
            "(Workstream 2) and district-level SES/population/poverty proxies — none of which exist in this repository yet.",
            icon=":material/info:",
        )

    with st.container(border=True):
        st.markdown("#### :material/account_tree: How heatwave priorities are set")
        st.caption("Priority is calculated from the full cumulative school dataset before dashboard filters are applied.")

        exposure_step, capacity_step = st.columns([1, 1.4], gap="large")
        with exposure_step:
            st.badge("Step 1 · Exposure", icon=":material/thermostat:", color="orange")
            st.markdown("**Cumulative heatwave exposure**")
            st.dataframe(
                pd.DataFrame([
                    ["Low", "14–34 cumulative heatwave days", "At or below the 33rd percentile"],
                    ["Moderate", "35–38 cumulative heatwave days", "Between the 33rd and 67th percentiles"],
                    ["High", "39–48 cumulative heatwave days", "Above the 67th percentile"],
                ], columns=["Class", "Current range", "Rule"]),
                hide_index=True,
                height=214,
                row_height=56,
            )

        with capacity_step:
            st.badge("Step 2 · School capacity", icon=":material/electric_bolt:", color="blue")
            st.markdown("**Essential services at the selected PMIU visit**")
            st.dataframe(
                pd.DataFrame([
                    ["Adequate", "Electricity and drinking water are both available, functional, and wholly provided."],
                    ["Weak", "Electricity and drinking water are both unavailable or non-functional."],
                    ["Partial", "Any other observed combination, including one adequate service and one weak/partial service."],
                    ["Missing", "No eligible heatwave-year visit, or electricity/water availability or functionality is missing."],
                ], columns=["Class", "Rule"]),
                hide_index=True,
                height=258,
                row_height=56,
            )

        method_priority_counts = cumulative["vulnerability_priority"].value_counts()
        st.badge("Step 3 · Priority", icon=":material/priority_high:", color="red")
        st.markdown("**Combine exposure and capacity**")
        st.dataframe(
            pd.DataFrame([
                [PRIORITY_LABELS["Priority 1"], "High", "Weak", int(method_priority_counts.get("Priority 1", 0))],
                [PRIORITY_LABELS["Priority 2"], "High", "Partial", int(method_priority_counts.get("Priority 2", 0))],
                [PRIORITY_LABELS["Priority 3"], "High", "Adequate", int(method_priority_counts.get("Priority 3", 0))],
                [PRIORITY_LABELS["Priority 4"], "Low or moderate", "Weak or partial", int(method_priority_counts.get("Priority 4", 0))],
                [PRIORITY_LABELS["Priority 5"], "Low or moderate", "Adequate", int(method_priority_counts.get("Priority 5", 0))],
                [PRIORITY_LABELS["Unclassified - PMIU missing"], "Any", "Missing", int(method_priority_counts.get("Unclassified - PMIU missing", 0))],
            ], columns=["Priority", "Exposure", "Capacity", "Schools"]),
            hide_index=True,
            height=312,
            row_height=44,
            column_config={
                "Priority": st.column_config.TextColumn(width="medium"),
                "Schools": st.column_config.NumberColumn(format="%d"),
            },
        )

        st.info(
            "Priority rank orders schools within each category by cumulative heatwave days, then EMIS code. "
            "It supports review and targeting; it is not a causal estimate. Facility status describes the selected visit, not a cumulative physical condition.",
            icon=":material/info:",
        )

    with st.container(border=True):
        st.markdown("#### :material/water_drop: How rainfall priorities are set")
        st.caption(
            "Rainfall priority follows the same two-step exposure-then-capacity logic as heatwave, using proxies from PMIU "
            "visits instead of an ASC/SIS capacity extract. Only exposed schools (events_exposed_count > 0) receive a priority."
        )

        rain_exposure_step, rain_capacity_step = st.columns([1, 1.6], gap="large")
        with rain_exposure_step:
            st.badge("Step 1 · Exposure", icon=":material/water_drop:", color="blue")
            st.markdown("**Cumulative rainfall exposure**")
            st.caption("Composite of event frequency, intensity and persistence — see the rainfall exposure tab legend.")
            st.dataframe(
                pd.DataFrame([
                    ["Low", "At or below the 33rd percentile among exposed schools"],
                    ["Moderate", "Between the 33rd and 67th percentiles"],
                    ["High", "Above the 67th percentile"],
                ], columns=["Class", "Rule"]),
                hide_index=True,
                height=145,
                row_height=48,
            )

        with rain_capacity_step:
            st.badge("Step 2 · Coping capacity", icon=":material/handyman:", color="orange")
            st.markdown("**Four PMIU-visit proxies, scored at the visit closest to one of the school's exposed rainfall years**")
            st.dataframe(
                pd.DataFrame([
                    ["Structural condition", "Building cleanliness status", "96.3%", "Adequate = good; Partial = average; Weak = poor."],
                    ["Learning-space continuity", "Classrooms used for teaching ÷ total classrooms", "99.8%", "Adequate ≥90%; Partial 70–<90%; Weak <70%."],
                    ["Sanitation", "Functional toilets ÷ total toilets", "99.8%", "Adequate ≥90%; Partial 50–<90%; Weak <50% or none functional."],
                    ["Safe water", "Availability, functionality and extent", "96.2%", "Adequate = available, functional and wholly provided; Weak = unavailable or non-functional."],
                    ["Drainage/sewerage", "Only free-text mentions", "0.04%", "Not usable — excluded from the capacity score."],
                ], columns=["Dimension", "Proxy", "PMIU coverage", "Rule"]),
                hide_index=True,
                height=214,
                row_height=44,
                column_config={"Dimension": st.column_config.TextColumn(width="medium")},
            )
            st.caption("Each of the four scored dimensions contributes Adequate = 2, Partial = 1, Weak = 0 to a 0–8 capacity score.")

        rain_priority_counts = rainfall_cumulative["vulnerability_priority"].value_counts()
        st.badge("Step 3 · Priority", icon=":material/priority_high:", color="red")
        st.markdown("**Combine exposure and coping capacity**")
        st.dataframe(
            pd.DataFrame([
                [PRIORITY_LABELS["Priority 1"], "High", "Weak", int(rain_priority_counts.get("Priority 1", 0))],
                [PRIORITY_LABELS["Priority 2"], "High", "Partial", int(rain_priority_counts.get("Priority 2", 0))],
                [PRIORITY_LABELS["Priority 3"], "High", "Adequate", int(rain_priority_counts.get("Priority 3", 0))],
                [PRIORITY_LABELS["Priority 4"], "Low or moderate", "Weak or partial", int(rain_priority_counts.get("Priority 4", 0))],
                [PRIORITY_LABELS["Priority 5"], "Low or moderate", "Adequate", int(rain_priority_counts.get("Priority 5", 0))],
                [PRIORITY_LABELS["Unclassified - PMIU missing"], "Any", "Missing", int(rain_priority_counts.get("Unclassified - capacity data missing", 0))],
            ], columns=["Priority", "Exposure", "Capacity", "Schools"]),
            hide_index=True,
            height=312,
            row_height=44,
            column_config={
                "Priority": st.column_config.TextColumn(width="medium"),
                "Schools": st.column_config.NumberColumn(format="%d"),
            },
        )

        st.info(
            "Priority rank orders schools within each category by rainfall exposure score, then EMIS code. It supports review "
            "and targeting, not a causal estimate. Schools never exposed to an extreme-rainfall event are excluded from "
            "priority, not scored as low-risk. No damage-severity modifier is applied, unlike the original methodology brief, "
            "because a reported rain/flood damage field was not available in the PMIU visit data used here.",
            icon=":material/info:",
        )
