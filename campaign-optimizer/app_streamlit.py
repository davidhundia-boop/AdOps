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
from optimizer import run_optimization, col_letter_to_idx
from appsflyer_tracking import AppsFlyerTrackingLink, parse_tracking_link, generate_test_link

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

# ---------------------------------------------------------------------------
# AppsFlyer Tracking Link Tools
# ---------------------------------------------------------------------------
st.divider()
with st.expander("🔗 AppsFlyer Tracking Link Tools", expanded=False):
    st.markdown("**Parse, generate, and test AppsFlyer tracking links**")
    
    tab1, tab2, tab3 = st.tabs(["Parse & Analyze", "Generate Test Link", "Create New Link"])
    
    with tab1:
        st.markdown("##### Parse Tracking Link")
        st.caption("Paste an AppsFlyer tracking link to analyze its parameters and validate it.")
        
        tracking_url_input = st.text_area(
            "Tracking Link URL",
            placeholder="https://app.appsflyer.com/com.example.app?pid=partner_int&c=campaign_name&...",
            height=100,
            key="parse_url",
            label_visibility="collapsed",
        )
        
        if st.button("🔍 Analyze Link", key="btn_analyze"):
            if tracking_url_input.strip():
                try:
                    link = parse_tracking_link(tracking_url_input)
                    summary = link.get_summary()
                    validation = link.validate()
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**Link Summary**")
                        st.write(f"**App ID:** `{summary['app_id']}`")
                        st.write(f"**Partner ID:** `{summary['partner_id']}`")
                        st.write(f"**Campaign:** `{summary['campaign']}`")
                        st.write(f"**Campaign ID:** `{summary['campaign_id']}`")
                        st.write(f"**Site ID:** `{summary['site_id']}`")
                        st.write(f"**Partner:** `{summary['partner']}`")
                        st.write(f"**Lookback:** `{summary['click_lookback']}`")
                    
                    with col_b:
                        st.markdown("**Validation**")
                        if validation['valid']:
                            st.success("✓ Link is valid")
                        else:
                            st.error("✗ Link has issues")
                            for issue in validation['issues']:
                                st.write(f"- {issue}")
                        
                        if validation['warnings']:
                            st.warning("Warnings:")
                            for warning in validation['warnings']:
                                st.write(f"- {warning}")
                        
                        if summary['placeholders']:
                            st.info(f"Placeholders found: {', '.join(summary['placeholders'])}")
                    
                    with st.expander("All Parameters", expanded=False):
                        st.json(link.params)
                    
                except Exception as e:
                    st.error(f"Error parsing link: {str(e)}")
            else:
                st.warning("Please enter a tracking link URL")
    
    with tab2:
        st.markdown("##### Generate Test Link")
        st.caption("Create a test tracking link with a device ID for attribution testing.")
        
        test_url_input = st.text_area(
            "Template Tracking Link",
            placeholder="Paste your tracking link template here...",
            height=80,
            key="test_url",
            label_visibility="collapsed",
        )
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            device_id_input = st.text_input(
                "Device ID (GAID/IDFA)",
                placeholder="e.g., 65a53a0f-87a1-43aa-9df8-da3ed7f6c954",
                key="device_id",
                help="The advertising ID of the test device",
            )
        with col_t2:
            test_param_input = st.text_input(
                "Test Parameter (af_sub1)",
                placeholder="e.g., Onurthegamer",
                key="test_param",
                help="Custom test identifier added as af_sub1",
            )
        
        st.markdown("**Placeholder Replacements** (optional)")
        st.caption("Replace placeholders like [SITE_ID], [CAMPAIGN_NAME] with actual values")
        
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            replace_site_id = st.text_input("SITE_ID", key="replace_site_id")
        with col_r2:
            replace_campaign = st.text_input("CAMPAIGN_NAME", key="replace_campaign")
        with col_r3:
            replace_campaign_id = st.text_input("CAMPAIGN_ID", key="replace_campaign_id")
        
        if st.button("🧪 Generate Test Link", key="btn_test"):
            if test_url_input.strip() and device_id_input.strip():
                try:
                    replacements = {}
                    if replace_site_id:
                        replacements['SITE_ID'] = replace_site_id
                    if replace_campaign:
                        replacements['CAMPAIGN_NAME'] = replace_campaign
                    if replace_campaign_id:
                        replacements['CAMPAIGN_ID'] = replace_campaign_id
                    
                    test_link = generate_test_link(
                        url=test_url_input,
                        device_id=device_id_input,
                        test_param=test_param_input if test_param_input else None,
                        replacements=replacements if replacements else None,
                    )
                    
                    st.success("Test link generated!")
                    st.code(test_link, language=None)
                    
                    st.markdown(f"[Open Test Link]({test_link})")
                    
                except Exception as e:
                    st.error(f"Error generating test link: {str(e)}")
            else:
                st.warning("Please enter both a tracking link template and device ID")
    
    with tab3:
        st.markdown("##### Create New Tracking Link")
        st.caption("Build a new AppsFlyer tracking link from campaign parameters.")
        
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            new_app_id = st.text_input(
                "App ID (Package/Bundle)",
                placeholder="com.example.app",
                key="new_app_id",
            )
            new_campaign_name = st.text_input(
                "Campaign Name",
                placeholder="DT_Motorola",
                key="new_campaign_name",
            )
            new_site_id = st.text_input(
                "Site ID",
                placeholder="12345",
                key="new_site_id",
            )
        
        with col_n2:
            new_partner_id = st.text_input(
                "Partner ID (pid)",
                value="onedigitalturbine_int",
                key="new_partner_id",
            )
            new_campaign_id = st.text_input(
                "Campaign ID",
                placeholder="49378",
                key="new_campaign_id",
            )
            new_partner_name = st.text_input(
                "Partner Name (af_prt)",
                placeholder="affinityveve",
                key="new_partner_name",
            )
        
        new_lookback = st.selectbox(
            "Click Lookback Window",
            options=["7d", "1d", "3d", "14d", "30d"],
            index=0,
            key="new_lookback",
        )
        
        if st.button("🔗 Create Tracking Link", key="btn_create"):
            if new_app_id and new_campaign_name and new_campaign_id and new_site_id:
                try:
                    link = AppsFlyerTrackingLink.from_campaign_data(
                        app_id=new_app_id,
                        campaign_name=new_campaign_name,
                        campaign_id=new_campaign_id,
                        site_id=new_site_id,
                        partner_id=new_partner_id,
                        partner_name=new_partner_name,
                        click_lookback=new_lookback,
                    )
                    
                    generated_url = link.generate()
                    st.success("Tracking link created!")
                    st.code(generated_url, language=None)
                    
                    st.markdown(f"[Open Link]({generated_url})")
                    
                except Exception as e:
                    st.error(f"Error creating link: {str(e)}")
            else:
                st.warning("Please fill in all required fields: App ID, Campaign Name, Campaign ID, and Site ID")
