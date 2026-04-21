import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load_data
from utils.styles import apply_plotly_theme, header, section, SIRC_CSS, SIRC_NAVY, SIRC_GOLD, SIRC_CREAM

st.set_page_config(page_title="Active Listings | SIRC", layout="wide")
header("Active Listings", "Current Inventory Browser")

df = load_data()
if df.empty:
    st.stop()

active = df[df["status"].str.upper().isin(["ACTIVE", "A"])].copy() if "status" in df.columns else pd.DataFrame()

if active.empty:
    st.info("No Active listings found in the current dataset. Add CSV files containing Active status listings to see inventory data here.")
    st.stop()

# ── Sidebar filters ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Filters")

    cities = sorted(active["city"].dropna().unique())
    sel_cities = st.multiselect("City", cities, default=[])

    prop_types = ["All"] + sorted(active["prop_type"].dropna().unique())
    sel_type = st.selectbox("Property Type", prop_types)

    price_min = int(active["list_price"].dropna().min()) if active["list_price"].notna().any() else 0
    price_max = int(active["list_price"].dropna().max()) if active["list_price"].notna().any() else 5000000
    price_range = st.slider("List Price Range", price_min, price_max, (price_min, price_max), step=50000,
                            format="$%d")

    sirc_only = st.checkbox("SIRC Listings Only", value=False)

# ── Apply filters ──────────────────────────────────────────────────────────
filtered = active.copy()
if sel_cities:
    filtered = filtered[filtered["city"].isin(sel_cities)]
if sel_type != "All":
    filtered = filtered[filtered["prop_type"] == sel_type]
filtered = filtered[
    (filtered["list_price"] >= price_range[0]) &
    (filtered["list_price"] <= price_range[1])
]
if sirc_only:
    filtered = filtered[filtered["is_sirc_listing"] == True]

if filtered.empty:
    st.warning("No listings match the selected filters.")
    st.stop()

# ── KPIs ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Active Listings", f"{len(filtered):,}")
k2.metric("Total Inventory Value", f"${filtered['list_price'].sum()/1e6:.1f}M")
k3.metric("Median List Price", f"${filtered['list_price'].median():,.0f}")
k4.metric("Avg Days Listed", f"{filtered['days_on_market'].mean():.0f}" if filtered["days_on_market"].notna().any() else "—")
sirc_count = filtered["is_sirc_listing"].sum() if "is_sirc_listing" in filtered.columns else 0
k5.metric("SIRC Listings", f"{sirc_count:,} ({sirc_count/len(filtered):.1%})")

# ── Price distribution ─────────────────────────────────────────────────────
section("List Price Distribution")

fig_hist = px.histogram(
    filtered.dropna(subset=["list_price"]),
    x="list_price",
    nbins=40,
    color_discrete_sequence=[SIRC_NAVY],
)
fig_hist.update_layout(height=320, xaxis_tickformat="$,.0f", xaxis_title="List Price", yaxis_title="Listings")
apply_plotly_theme(fig_hist, "Active Listings — Price Distribution")
st.plotly_chart(fig_hist, use_container_width=True)

# ── Inventory by city ──────────────────────────────────────────────────────
section("Inventory by City")

city_inv = (
    filtered.groupby("city")
    .agg(Listings=("mls_number","count"), Median_Price=("list_price","median"), Total_Value=("list_price","sum"))
    .reset_index()
    .sort_values("Listings", ascending=False)
    .head(20)
)

col1, col2 = st.columns(2)
with col1:
    fig_city = px.bar(
        city_inv.sort_values("Listings"),
        x="Listings", y="city", orientation="h",
        color_discrete_sequence=[SIRC_NAVY],
        text="Listings",
    )
    fig_city.update_layout(height=max(300, len(city_inv)*24), yaxis_title="", xaxis_title="Active Listings")
    apply_plotly_theme(fig_city, "Listings by City")
    st.plotly_chart(fig_city, use_container_width=True)

with col2:
    fig_price = px.bar(
        city_inv.sort_values("Median_Price"),
        x="Median_Price", y="city", orientation="h",
        color_discrete_sequence=[SIRC_GOLD],
        text=city_inv.sort_values("Median_Price")["Median_Price"].apply(lambda v: f"${v/1e6:.2f}M" if v >= 1e6 else f"${v:,.0f}"),
    )
    fig_price.update_layout(height=max(300, len(city_inv)*24), yaxis_title="", xaxis_tickformat="$,.0f")
    apply_plotly_theme(fig_price, "Median List Price by City")
    st.plotly_chart(fig_price, use_container_width=True)

# ── Property type mix ──────────────────────────────────────────────────────
section("Property Type Mix")

type_counts = filtered["prop_type"].value_counts().reset_index()
type_counts.columns = ["prop_type", "count"]

fig_pie = px.pie(
    type_counts, names="prop_type", values="count",
    color_discrete_sequence=[SIRC_NAVY, SIRC_GOLD, "#5A8A9F", "#8B7355", "#4A6741"],
    hole=0.4,
)
fig_pie.update_traces(textposition="outside", textinfo="percent+label")
fig_pie.update_layout(height=360, showlegend=False)
apply_plotly_theme(fig_pie, "Active Listings by Property Type")
st.plotly_chart(fig_pie, use_container_width=True)

# ── Sub-area breakdown ─────────────────────────────────────────────────────
if "sub_area" in filtered.columns and filtered["sub_area"].notna().any():
    section("Inventory by Sub-Area")
    sub_inv = (
        filtered.groupby("sub_area")
        .agg(Listings=("mls_number","count"), Median_Price=("list_price","median"))
        .reset_index()
        .sort_values("Listings", ascending=False)
        .head(25)
    )
    fig_sub = px.bar(
        sub_inv.sort_values("Listings"),
        x="Listings", y="sub_area", orientation="h",
        color="Median_Price",
        color_continuous_scale=[[0, SIRC_CREAM], [1, SIRC_NAVY]],
        text="Listings",
    )
    fig_sub.update_layout(height=max(350, len(sub_inv)*22), yaxis_title="")
    apply_plotly_theme(fig_sub, "Active Listings by Sub-Area (top 25)")
    st.plotly_chart(fig_sub, use_container_width=True)

# ── Listings table ─────────────────────────────────────────────────────────
section("Active Listings")

show_cols = [c for c in ["mls_number","address","city","sub_area","prop_type","list_price","days_on_market","listing_agent","listing_office"] if c in filtered.columns]
disp = filtered[show_cols].copy().sort_values("list_price", ascending=False)
if "list_price" in disp.columns:
    disp["list_price"] = disp["list_price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
if "days_on_market" in disp.columns:
    disp["days_on_market"] = disp["days_on_market"].apply(lambda v: f"{v:.0f}" if pd.notna(v) else "—")

st.dataframe(
    disp.rename(columns={
        "mls_number":"MLS #","address":"Address","city":"City","sub_area":"Sub-Area",
        "prop_type":"Type","list_price":"List Price","days_on_market":"DOM",
        "listing_agent":"Agent","listing_office":"Office",
    }),
    hide_index=True, use_container_width=True, height=450,
)

csv = filtered[show_cols].to_csv(index=False)
st.download_button("Download CSV", csv, "active_listings.csv", "text/csv")
