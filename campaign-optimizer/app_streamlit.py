"""
Campaign Optimizer — Streamlit app.
Upload files, set KPI goals and weighting, configure optimization settings, run pipeline,
and download the color-coded Excel report.
"""

import os
import tempfile
import streamlit as st
from optimizer import run_optimization, col_letter_to_idx

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
            help="Campaign/site-level bid and delivery data. Limit 200MB. XLSX only.",
        )
        if not internal_file:
            st.caption("Drag and drop file here — Limit 200MB per file · XLSX")
with col2:
    with st.container():
        st.caption("Advertiser Performance Report (CSV)")
        advertiser_file = st.file_uploader(
            "Advertiser Performance Report (CSV)",
            type=["csv"],
            key="advertiser",
            label_visibility="collapsed",
            help="ROAS/ROI performance per site. Limit 200MB. CSV only.",
        )
        if not advertiser_file:
            st.caption("Drag and drop file here — Limit 200MB per file · CSV")

st.divider()

# ---------------------------------------------------------------------------
# 2 — Set Your KPI Goals
# ---------------------------------------------------------------------------
st.markdown("### 2 Set Your KPI Goals")

k1, k2 = st.columns(2)
with k1:
    main_col_letter = st.text_input(
        "Column letter in the CSV (e.g. I)",
        value="I",
        max_chars=2,
        key="main_col",
        help="Primary KPI column (e.g. ROI D7). Single letter A–Z.",
    ).strip().upper() or "I"
    main_target = st.number_input(
        "Target (%)",
        min_value=0.0,
        max_value=100.0,
        value=10.0,
        step=0.01,
        format="%.2f",
        key="main_target",
        help="Target percentage for the primary KPI.",
    )
with k2:
    secondary_col_letter = st.text_input(
        "Column letter in the CSV (e.g. K)",
        value="K",
        max_chars=2,
        key="secondary_col",
        help="Secondary KPI column (e.g. ROI D14 or D30). Single letter A–Z.",
    ).strip().upper() or "K"
    secondary_target = st.number_input(
        "Target (%)",
        min_value=0.0,
        max_value=100.0,
        value=5.0,
        step=0.01,
        format="%.2f",
        key="secondary_target",
        help="Target percentage for the secondary KPI.",
    )

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
    # Validate column letters and targets
    def valid_col(c, name):
        c = (c or "").strip().upper()
        if len(c) != 1 or not c.isalpha():
            st.error(f"{name} must be a single letter A–Z.")
            return None
        return c

    main_col = valid_col(main_col_letter, "Main KPI column")
    secondary_col = valid_col(secondary_col_letter, "Secondary KPI column")
    if main_col is None or secondary_col is None:
        st.stop()
    if main_target <= 0 or secondary_target <= 0:
        st.error("KPI targets must be greater than 0.")
        st.stop()
    try:
        kpi_col_d7_idx = col_letter_to_idx(main_col)
        kpi_col_d2nd_idx = col_letter_to_idx(secondary_col)
    except ValueError as e:
        st.error(str(e))
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
                kpi_col_d7_idx=kpi_col_d7_idx,
                kpi_col_d2nd_idx=kpi_col_d2nd_idx,
                kpi_d7_pct=main_target,
                kpi_d2nd_pct=secondary_target,
                weight_main=weight_main / 100.0,
                weight_secondary=weight_secondary / 100.0,
            )
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
