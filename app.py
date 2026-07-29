"""Punjab school heatwave vulnerability dashboard."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st


ROOT = Path(__file__).parent
CUMULATIVE_FILE = ROOT / "final_school_heatwave_vulnerability_nearest_event.csv"
YEARLY_FILE = ROOT / "school_year_heatwave_capacity.csv"
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


def priority_map(frame: pd.DataFrame) -> pdk.Deck:
    map_data = frame.dropna(subset=["latitude", "longitude"]).copy()
    colors = {
        "Priority 1": [153, 27, 27, 210],
        "Priority 2": [220, 72, 39, 190],
        "Priority 3": [245, 158, 11, 130],
        "Priority 4": [45, 125, 210, 100],
        "Priority 5": [87, 125, 155, 55],
    }
    map_data["map_color"] = map_data["vulnerability_priority"].map(colors).apply(
        lambda value: value if isinstance(value, list) else [150, 150, 150, 60]
    )
    return pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(latitude=30.5, longitude=71.5, zoom=6.2, pitch=20),
        layers=[pdk.Layer(
            "ScatterplotLayer", id="schools", data=map_data, get_position="[longitude, latitude]",
            get_fill_color="map_color", get_radius=450, radius_min_pixels=2, radius_max_pixels=10,
            pickable=True,
        )],
        tooltip={"html": "<b>{school_name}</b><br/>{district}<br/>{vulnerability_priority}<br/>{total_heatwave_days} heatwave days"},
    )


def school_profile(frame: pd.DataFrame, yearly_frame: pd.DataFrame, key: str) -> None:
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


if not CUMULATIVE_FILE.exists() or not YEARLY_FILE.exists():
    st.error("Required analysis files are missing. Keep this app beside both final CSV files.")
    st.stop()

cumulative = load_cumulative()
yearly = load_yearly()

st.title(":material/map: School exposure atlas")
st.caption("A decision view of cumulative school vulnerability and monitoring visits selected only from a school’s heatwave year, 2021–2026.")

st.sidebar.header(":material/tune: Filters")
districts = select_values("District", cumulative["district"], "district")
levels = select_values("School level", cumulative["school_level"], "level")
st.sidebar.caption("Filters apply to both views. The annual view also has a year filter.")

cum = apply_filters(cumulative, districts, levels)
annual = apply_filters(yearly, districts, levels)

tab_overview, tab_cumulative, tab_annual, tab_profile, tab_notes = st.tabs([
    ":material/dashboard: Decision view", ":material/monitoring: Cumulative view",
    ":material/calendar_month: School-year view", ":material/school: School profile", ":material/info: Method",
])

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
    st.pydeck_chart(priority_map(map_schools), height=520, key="priority_map")
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

with tab_profile:
    st.caption("Service and infrastructure values come from the selected monitoring visit nearest to a heatwave in the same year.")
    school_profile(cum, yearly, "school_profile")

with tab_notes:
    st.subheader("Dashboard guide")
    st.dataframe(
        pd.DataFrame([
            ["Sidebar filters", "District and school level", "Filters both cumulative and school-year results."],
            ["Decision view: headline metrics", "Counts of exposed, high-exposure, urgent, and unmatched schools", "A quick summary of the current district and level selection."],
            ["Decision view: priority map", "School locations coloured by vulnerability priority", "Use the priority pills to show one or several categories; hover for school details."],
            ["Decision view: shortlist", "First 100 schools ordered by priority category and rank", "Use as a review or targeting list, not as a causal-impact ranking."],
            ["Cumulative view", "One row per exposed school; heatwave exposure summed across 2021–2026", "Capacity comes from the closest eligible PMIU visit in one of that school's heatwave years."],
            ["Cumulative: classroom pressure", "Priority 1–3 schools with the most students per usable classroom", "Highlights schools where heat exposure and observed classroom pressure overlap."],
            ["School-year view", "One row per school and heatwave year", "Uses one PMIU visit: the visit closest to a heatwave in that same year."],
            ["School-year: priority ranking", "Top 20 schools for exposure, classroom pressure, or toilet pressure", "Switch the measure to review different operational pressures."],
            ["School profile: summary", "Cumulative exposure and selected school-capacity indicators", "Describes the chosen school using the cumulative output."],
            ["School profile: visit history", "One selected monitoring visit for every exposed heatwave year", "A blank date means no PMIU visit was available in that year."],
            ["Method", "Definitions, matching rules, and priority construction", "Use this section when interpreting or reporting dashboard results."],
        ], columns=["Tab / section", "What it shows", "How to use it"]),
        hide_index=True,
        height="content",
    )

    st.subheader("How priorities are set")
    st.caption("Priority is determined in three steps using the full cumulative school dataset, before dashboard filters are applied.")

    st.markdown("**1. Cumulative heatwave exposure class**")
    st.dataframe(
        pd.DataFrame([
            ["Low", "14–34 cumulative heatwave days", "At or below the 33rd percentile"],
            ["Moderate", "35–38 cumulative heatwave days", "Between the 33rd and 67th percentiles"],
            ["High", "39–48 cumulative heatwave days", "Above the 67th percentile"],
        ], columns=["Exposure class", "Current-data range", "Rule"]),
        hide_index=True,
        height="content",
    )

    st.markdown("**2. Essential-service capacity from the selected PMIU visit**")
    st.dataframe(
        pd.DataFrame([
            ["Adequate", "Electricity and drinking water are both available, functional, and wholly provided."],
            ["Weak", "Electricity and drinking water are both unavailable or non-functional."],
            ["Partial", "Any other observed combination, including one adequate service and one weak/partial service."],
            ["Missing", "No eligible heatwave-year visit, or electricity/water availability or functionality is missing."],
        ], columns=["Capacity class", "Rule"]),
        hide_index=True,
        height="content",
    )

    method_priority_counts = cumulative["vulnerability_priority"].value_counts()
    st.markdown("**3. Vulnerability priority**")
    st.dataframe(
        pd.DataFrame([
            ["Priority 1", "High", "Weak", int(method_priority_counts.get("Priority 1", 0))],
            ["Priority 2", "High", "Partial", int(method_priority_counts.get("Priority 2", 0))],
            ["Priority 3", "High", "Adequate", int(method_priority_counts.get("Priority 3", 0))],
            ["Priority 4", "Low or moderate", "Weak or partial", int(method_priority_counts.get("Priority 4", 0))],
            ["Priority 5", "Low or moderate", "Adequate", int(method_priority_counts.get("Priority 5", 0))],
            ["Unclassified", "Any", "Missing", int(method_priority_counts.get("Unclassified - PMIU missing", 0))],
        ], columns=["Priority", "Exposure class", "Essential-service capacity", "Current schools"]),
        hide_index=True,
        height="content",
        column_config={"Current schools": st.column_config.NumberColumn(format="%d")},
    )

    st.caption(
        "Priority rank orders schools within each priority category by cumulative heatwave days, then EMIS code. "
        "Priority supports review and targeting; it is not a causal estimate. Facility status describes the selected visit, not a cumulative physical condition."
    )
