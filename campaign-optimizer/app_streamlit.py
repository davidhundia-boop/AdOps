"""
Campaign Optimizer — Streamlit app.
Upload files, set KPI goals and weighting, configure optimization settings, run pipeline,
and download the color-coded Excel report.
"""

import os
import sys
import tempfile

# Ensure app directory is on path when run from repo root (e.g. Streamlit Community Cloud)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import streamlit as st
from optimizer import run_optimization, col_letter_to_idx, find_kpi_column, ROAS_D7_PATTERNS

st.set_page_config(
    page_title="Campaign Optimizer",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom styling to align with reference (dark header area optional; keeping clean light/dark compatible)
st.markdown("""
<style>
    .main-header { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem; }
    .main-caption { color: #666; margin-bottom: 1.5rem; }
    .section-head { font-weight: 600; margin: 1.25rem 0 0.75rem 0; }
    .stSlider [data-baseweb="slider"] { margin-top: 0.5rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🎯 Campaign Optimizer</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="main-caption">Upload your files, enter your goals, and get instant bid recommendations.</p>',
    unsafe_allow_html=True,
)
st.divider()

# ---------------------------------------------------------------------------
# 1 — Upload Your Data Files
# ---------------------------------------------------------------------------
st.markdown("### 1 Upload Your Data Files")
col1, col2 = st.columns(2)
with col1:
    with st.container():
        st.caption("Internal Campaign Data (Excel .xlsx)")
        internal_file = st.file_uploader(
            "Internal Campaign Data (Excel .xlsx)",
            type=["xlsx"],
            key="internal",
            label_visibility="collapsed",
            help="Campaign/site-level bid and delivery data (e.g., site_performance.xlsx). Limit 200MB. XLSX only.",
        )
        if not internal_file:
            st.caption("e.g., site_performance.xlsx — Limit 200MB per file · XLSX")
with col2:
    with st.container():
        st.caption("Advertiser/Client Performance Report (CSV)")
        advertiser_file = st.file_uploader(
            "Advertiser Performance Report (CSV)",
            type=["csv"],
            key="advertiser",
            label_visibility="collapsed",
            help="ROAS/ROI performance per site from client (e.g., DT_DX.csv). Limit 200MB. CSV only.",
        )
        if not advertiser_file:
            st.caption("e.g., DT_DX.csv — Limit 200MB per file · CSV")

st.divider()

# ---------------------------------------------------------------------------
# 2 — Set Your KPI Goals
# ---------------------------------------------------------------------------
st.markdown("### 2 Set Your KPI Goals")

# Preset configurations
PRESETS = {
    "Custom": {
        "main_col": "I",
        "main_target": 10.0,
        "secondary_col": "K",
        "secondary_target": 5.0,
    },
    "Domino Dreams ROAS D7 (2.18%)": {
        "main_col": "Domino Dreams Marketing Campaigns Daily Metrics Full ROAS D7",
        "main_target": 2.18,
        "secondary_col": "K",
        "secondary_target": 5.0,
    },
}

preset_choice = st.selectbox(
    "KPI Preset",
    options=list(PRESETS.keys()),
    index=1,  # Default to Domino Dreams preset
    help="Select a preset configuration or choose Custom to specify your own.",
)

preset = PRESETS[preset_choice]
is_custom = preset_choice == "Custom"

k1, k2 = st.columns(2)
with k1:
    st.markdown("**Primary KPI (D7 ROAS)**")
    main_col_spec = st.text_input(
        "Column (letter or name)",
        value=preset["main_col"],
        key="main_col",
        help="Primary KPI column - can be a letter (A-Z, AA-ZZ) or column name (e.g., 'Domino Dreams Marketing Campaigns Daily Metrics Full ROAS D7').",
        disabled=not is_custom,
    ).strip() or preset["main_col"]
    main_target = st.number_input(
        "Target (%)",
        min_value=0.0,
        max_value=100.0,
        value=preset["main_target"],
        step=0.01,
        format="%.2f",
        key="main_target",
        help="Target percentage for the primary KPI (e.g., 2.18 for ROAS D7 goal of 2.18%).",
        disabled=not is_custom,
    )
with k2:
    st.markdown("**Secondary KPI (D14/D30 ROAS)**")
    secondary_col_spec = st.text_input(
        "Column (letter or name)",
        value=preset["secondary_col"],
        key="secondary_col",
        help="Secondary KPI column - can be a letter (A-Z, AA-ZZ) or column name.",
        disabled=not is_custom,
    ).strip() or preset["secondary_col"]
    secondary_target = st.number_input(
        "Target (%)",
        min_value=0.0,
        max_value=100.0,
        value=preset["secondary_target"],
        step=0.01,
        format="%.2f",
        key="secondary_target",
        help="Target percentage for the secondary KPI.",
        disabled=not is_custom,
    )

# Use preset values when not custom
if not is_custom:
    main_col_spec = preset["main_col"]
    main_target = preset["main_target"]
    secondary_col_spec = preset["secondary_col"]
    secondary_target = preset["secondary_target"]

st.markdown("**How important is the Main KPI compared to the Secondary KPI?**")
weight_main = st.slider(
    "Main KPI weight",
    min_value=0,
    max_value=100,
    value=80,
    step=5,
    key="weight_slider",
    label_visibility="collapsed",
)
weight_secondary = 100 - weight_main
st.caption(f"Main {weight_main}% / Secondary {weight_secondary}% — The optimizer will weight the Main KPI at {weight_main}% and the Secondary KPI at {weight_secondary}% when scoring each campaign.")

st.divider()

# ---------------------------------------------------------------------------
# 3 — Optimization Settings
# ---------------------------------------------------------------------------
st.markdown("### 3 Optimization Settings")
opt_goal = st.radio(
    "Optimization goal",
    options=["Scale", "Performance", "Other"],
    index=0,
    horizontal=True,
    help="Primary optimization objective.",
)
report_days = st.radio(
    "Report covers the last...",
    options=["30 days", "60 days", "Other"],
    index=0,
    horizontal=True,
    help="Time window of the report data.",
)
additional_notes = st.text_area(
    "Additional notes or constraints (optional)",
    placeholder="e.g. Advertiser wants to scale but keep performance — no single campaign should spend more than $100/day. Need at least 50 installs per week.",
    height=80,
    help="Optional context or constraints for the optimization.",
)

st.divider()

# ---------------------------------------------------------------------------
# Actions: prerequisite message vs Run Optimization
# ---------------------------------------------------------------------------
files_ready = internal_file is not None and advertiser_file is not None

if not files_ready:
    st.button(
        "📄 Upload both files above to enable the optimizer.",
        type="primary",
        use_container_width=True,
        disabled=True,
    )
    run_clicked = False
else:
    run_clicked = st.button("🚀 Run Optimization", type="primary", use_container_width=True)

if run_clicked and files_ready:
    # Validate column specs and targets
    if not main_col_spec:
        st.error("Primary KPI column is required (letter or column name).")
        st.stop()
    if not secondary_col_spec:
        st.error("Secondary KPI column is required (letter or column name).")
        st.stop()
    if main_target <= 0 or secondary_target <= 0:
        st.error("KPI targets must be greater than 0.")
        st.stop()

    with st.spinner("Running optimization…"):
        internal_path = None
        advertiser_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f:
                f.write(internal_file.getvalue())
                internal_path = f.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
                f.write(advertiser_file.getvalue())
                advertiser_path = f.name
            output_bytes, summary = run_optimization(
                internal_file=internal_path,
                advertiser_file=advertiser_path,
                kpi_col_d7_spec=main_col_spec,
                kpi_col_d2nd_spec=secondary_col_spec,
                kpi_d7_pct=main_target,
                kpi_d2nd_pct=secondary_target,
                weight_main=weight_main / 100.0,
                weight_secondary=weight_secondary / 100.0,
            )
        except ValueError as e:
            st.error(f"Error finding KPI column: {e}")
            st.stop()
        finally:
            for p in (internal_path, advertiser_path):
                if p and os.path.isfile(p):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    st.success(f"Done! {summary.get('rows_actioned', 0)} sites actioned.")
    a, b, c, d, e = st.columns(5)
    a.metric("Total sites", summary.get("total_rows", 0))
    b.metric("Sites actioned", summary.get("rows_actioned", 0))
    c.metric("Sites disregarded", summary.get("rows_disregarded", 0))
    d.metric("Daily cap suggestions", summary.get("rows_with_cap", 0))
    e.metric("KPI column", summary.get("roi_d2nd_col", "–"))
    ab = summary.get("action_breakdown") or {}
    sb = summary.get("segment_breakdown") or {}
    t1, t2 = st.columns(2)
    with t1:
        st.write("**Action breakdown**")
        st.dataframe(
            [{"Action": k, "Count": v} for k, v in sorted(ab.items(), key=lambda x: -x[1])],
            use_container_width=True,
            hide_index=True,
        )
    with t2:
        st.write("**Segment breakdown**")
        st.dataframe(
            [{"Segment": k, "Count": v} for k, v in sorted(sb.items(), key=lambda x: -x[1])],
            use_container_width=True,
            hide_index=True,
        )
    st.download_button(
        "Save Optimization Report",
        data=output_bytes.getvalue(),
        file_name="optimization_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
