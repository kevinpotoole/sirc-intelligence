import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data
from utils.styles import apply_plotly_theme, header, section, SIRC_CSS, SIRC_NAVY, SIRC_GOLD, SIRC_CREAM

st.set_page_config(page_title="Pipeline Tracker | SIRC", layout="wide")
header("Pipeline Tracker", "Active → Pending → Closed Deal Flow")

df = load_data()
if df.empty:
    st.stop()

if "status" not in df.columns:
    st.warning("Status column not found in data.")
    st.stop()

# Normalise status into pipeline stages
def pipeline_stage(s):
    s = str(s).strip().upper()
    if s in ("ACTIVE", "A"):
        return "Active"
    if s in ("PENDING", "P"):
        return "Pending"
    if s in ("F", "FIRM"):
        return "Firm"
    if s in ("CLOSED", "SOLD"):
        return "Closed"
    return "Other"

df["pipeline_stage"] = df["status"].apply(pipeline_stage)

# ── Sidebar filters ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Filters")

    cities = sorted(df["city"].dropna().unique())
    sel_cities = st.multiselect("City", cities, default=[])

    prop_types = ["All"] + sorted(df["prop_type"].dropna().unique())
    sel_type = st.selectbox("Property Type", prop_types)

    years = sorted(df["sold_year"].dropna().unique().astype(int), reverse=True)
    sel_year = st.selectbox("Year (for Closed)", [int(y) for y in years], index=0)

    sirc_only = st.checkbox("SIRC Involved Only", value=False)

# ── Filter ─────────────────────────────────────────────────────────────────
filtered = df.copy()
if sel_cities:
    filtered = filtered[filtered["city"].isin(sel_cities)]
if sel_type != "All":
    filtered = filtered[filtered["prop_type"] == sel_type]
if sirc_only:
    filtered = filtered[filtered["is_sirc_involved"] == True]

# Separate by stage (closed filtered by year)
active_df  = filtered[filtered["pipeline_stage"] == "Active"]
pending_df = filtered[filtered["pipeline_stage"] == "Pending"]
firm_df    = filtered[filtered["pipeline_stage"] == "Firm"]
closed_df  = filtered[(filtered["pipeline_stage"] == "Closed") & (filtered["sold_year"] == sel_year)]

# ── Funnel KPIs ────────────────────────────────────────────────────────────
section("Pipeline Overview")

cols = st.columns(4)
stages = [
    ("Active", active_df, SIRC_CREAM),
    ("Pending", pending_df, "#C9A96E"),
    ("Firm", firm_df, "#8B7355"),
    ("Closed", closed_df, SIRC_NAVY),
]
for col, (label, sdf, color) in zip(cols, stages):
    count = len(sdf)
    vol = sdf["sold_price"].sum() if label == "Closed" else sdf["list_price"].sum()
    col.metric(f"{label} Listings", f"{count:,}")
    col.metric(f"{label} Value", f"${vol/1e6:.1f}M" if vol > 0 else "—")

# ── Funnel chart ───────────────────────────────────────────────────────────
stage_counts = [len(active_df), len(pending_df), len(firm_df), len(closed_df)]
stage_labels = [f"Active\n{len(active_df):,}", f"Pending\n{len(pending_df):,}",
                f"Firm\n{len(firm_df):,}", f"Closed ({sel_year})\n{len(closed_df):,}"]

fig_funnel = go.Figure(go.Funnel(
    y=stage_labels,
    x=stage_counts,
    marker=dict(color=[SIRC_CREAM, SIRC_GOLD, "#8B7355", SIRC_NAVY]),
    textinfo="value+percent initial",
    connector=dict(line=dict(color="#E8E0D5", width=1)),
))
fig_funnel.update_layout(height=380)
apply_plotly_theme(fig_funnel, "Deal Pipeline Funnel")
st.plotly_chart(fig_funnel, use_container_width=True)

# ── Pipeline by city ───────────────────────────────────────────────────────
section("Pipeline by City")

city_pipeline = (
    filtered[filtered["pipeline_stage"].isin(["Active","Pending","Firm","Closed"])]
    .groupby(["city","pipeline_stage"])
    .size()
    .reset_index(name="Count")
)
city_totals = city_pipeline.groupby("city")["Count"].sum().nlargest(15).index
city_pipeline = city_pipeline[city_pipeline["city"].isin(city_totals)]

fig_city = px.bar(
    city_pipeline,
    x="city", y="Count", color="pipeline_stage",
    barmode="stack",
    color_discrete_map={
        "Active": SIRC_CREAM,
        "Pending": SIRC_GOLD,
        "Firm": "#8B7355",
        "Closed": SIRC_NAVY,
    },
)
fig_city.update_layout(height=380, xaxis_title="", xaxis_tickangle=-30,
                       legend_title="Stage", legend=dict(orientation="h", y=1.08))
apply_plotly_theme(fig_city, "Deal Pipeline by City (top 15)")
st.plotly_chart(fig_city, use_container_width=True)

# ── Monthly closed trend with pipeline overlay ─────────────────────────────
section(f"Monthly Closed Volume — {sel_year}")

monthly_closed = (
    closed_df.dropna(subset=["sold_date","sold_price"])
    .groupby("sold_ym")
    .agg(Units=("mls_number","count"), Volume=("sold_price","sum"))
    .reset_index()
    .sort_values("sold_ym")
)

if not monthly_closed.empty:
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(
        x=monthly_closed["sold_ym"], y=monthly_closed["Units"],
        name="Closed Units", marker_color=SIRC_NAVY,
    ))
    fig_trend.update_layout(height=320, xaxis_title="Month", yaxis_title="Closed Deals",
                             xaxis_tickangle=-30)
    apply_plotly_theme(fig_trend, f"Monthly Closed Transactions — {sel_year}")
    st.plotly_chart(fig_trend, use_container_width=True)

# ── Active listings table ──────────────────────────────────────────────────
section("Current Active & Pending Listings")

pipeline_open = filtered[filtered["pipeline_stage"].isin(["Active","Pending","Firm"])].copy()
if not pipeline_open.empty:
    show = [c for c in ["mls_number","address","city","sub_area","prop_type",
                        "list_price","days_on_market","pipeline_stage","listing_agent","listing_office"]
            if c in pipeline_open.columns]
    disp = pipeline_open[show].sort_values("pipeline_stage").copy()
    if "list_price" in disp.columns:
        disp["list_price"] = disp["list_price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    if "days_on_market" in disp.columns:
        disp["days_on_market"] = disp["days_on_market"].apply(lambda v: f"{v:.0f}" if pd.notna(v) else "—")
    st.dataframe(
        disp.rename(columns={
            "mls_number":"MLS #","address":"Address","city":"City","sub_area":"Sub-Area",
            "prop_type":"Type","list_price":"List Price","days_on_market":"DOM",
            "pipeline_stage":"Stage","listing_agent":"Agent","listing_office":"Office",
        }),
        hide_index=True, use_container_width=True, height=400,
    )
else:
    st.info("No Active or Pending listings in current filters.")
