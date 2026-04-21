import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load_data
from utils.styles import (
    apply_plotly_theme, header, section,
    SIRC_CSS, SIRC_NAVY, SIRC_GOLD, SIRC_CREAM,
)

header("Neighbourhood Drill-Down", "City → Sub-Area Market Analysis")

df = load_data()
if df.empty:
    st.stop()

# ── Sidebar filters ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Filters")

    years = sorted(df["sold_year"].dropna().unique().astype(int), reverse=True)
    sel_years = st.multiselect("Year(s)", years, default=[y for y in years if y >= 2023])

    cities = sorted(df["city"].dropna().unique())
    sel_city = st.selectbox("City", cities, index=cities.index("VANCOUVER") if "VANCOUVER" in cities else 0)

    prop_types = ["All"] + sorted(df["prop_type"].dropna().unique())
    sel_type = st.selectbox("Property Type", prop_types)

    # Sub-area multi-select within chosen city
    city_df = df[df["city"] == sel_city]
    sub_areas = sorted(city_df["sub_area"].dropna().unique())
    sel_sub_areas = st.multiselect(
        "Sub-Areas (leave blank for all)",
        sub_areas,
        default=[],
        help="Select specific neighbourhoods to compare, or leave blank to see all"
    )

    st.markdown("---")
    min_txns = st.number_input("Min transactions (filter noise)", min_value=1, value=5)

# ── Apply filters ──────────────────────────────────────────────────────────
filtered = df.copy()
if sel_years:
    filtered = filtered[filtered["sold_year"].isin(sel_years)]
filtered = filtered[filtered["city"] == sel_city]
if sel_type != "All":
    filtered = filtered[filtered["prop_type"] == sel_type]
if sel_sub_areas:
    filtered = filtered[filtered["sub_area"].isin(sel_sub_areas)]

if filtered.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# ── Sub-area summary table ─────────────────────────────────────────────────
section(f"Sub-Area Summary — {sel_city}{' · ' + sel_type if sel_type != 'All' else ''}")

sub_stats = (
    filtered.groupby("sub_area")
    .agg(
        Transactions=("mls_number", "count"),
        Total_Volume=("sold_price", "sum"),
        Median_Price=("sold_price", "median"),
        Avg_Price=("sold_price", "mean"),
        Avg_DOM=("days_on_market", "mean"),
        Avg_LSR=("list_to_sale_ratio", "mean"),
        SIRC_Listings=("is_sirc_listing", "sum"),
        SIRC_Buying=("is_sirc_buying", "sum"),
    )
    .reset_index()
)
sub_stats = sub_stats[sub_stats["Transactions"] >= min_txns].copy()
sub_stats["SIRC_Involved"] = sub_stats["SIRC_Listings"] + sub_stats["SIRC_Buying"]
sub_stats["SIRC_Share"] = (sub_stats["SIRC_Involved"] / sub_stats["Transactions"]).clip(0, 1)
sub_stats = sub_stats.sort_values("Total_Volume", ascending=False).reset_index(drop=True)
sub_stats.insert(0, "Rank", range(1, len(sub_stats) + 1))

# KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Sub-Areas", f"{len(sub_stats)}")
k2.metric("Total Transactions", f"{sub_stats['Transactions'].sum():,}")
k3.metric("Total Volume", f"${sub_stats['Total_Volume'].sum()/1e6:.1f}M")
k4.metric("City Median Price", f"${filtered['sold_price'].median():,.0f}")

# Treemap: volume by sub-area
fig_tree = px.treemap(
    sub_stats.head(40),
    path=["sub_area"],
    values="Total_Volume",
    color="Median_Price",
    color_continuous_scale=[[0, SIRC_CREAM], [1, SIRC_NAVY]],
    hover_data={"Transactions": True, "SIRC_Share": ":.1%"},
    custom_data=["Transactions", "Median_Price", "SIRC_Share"],
)
fig_tree.update_traces(
    hovertemplate="<b>%{label}</b><br>Volume: $%{value:,.0f}<br>Transactions: %{customdata[0]}<br>Median: $%{customdata[1]:,.0f}<br>SIRC Share: %{customdata[2]:.1%}<extra></extra>"
)
fig_tree.update_layout(height=420)
apply_plotly_theme(fig_tree, f"{sel_city} — Volume by Sub-Area (top 40)")
st.plotly_chart(fig_tree, use_container_width=True)

# Summary table
disp = sub_stats.copy()
disp["Total_Volume"]  = disp["Total_Volume"].apply(lambda v: f"${v/1e6:.2f}M")
disp["Median_Price"]  = disp["Median_Price"].apply(lambda v: f"${v:,.0f}")
disp["Avg_Price"]     = disp["Avg_Price"].apply(lambda v: f"${v:,.0f}")
disp["Avg_DOM"]       = disp["Avg_DOM"].apply(lambda v: f"{v:.0f}" if pd.notna(v) else "—")
disp["Avg_LSR"]       = disp["Avg_LSR"].apply(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
disp["SIRC_Share"]    = disp["SIRC_Share"].apply(lambda v: f"{v:.1%}")

st.dataframe(
    disp[["Rank", "sub_area", "Transactions", "Total_Volume", "Median_Price",
          "Avg_Price", "Avg_DOM", "Avg_LSR", "SIRC_Listings", "SIRC_Buying", "SIRC_Share"]].rename(columns={
        "sub_area": "Sub-Area", "Total_Volume": "Volume", "Median_Price": "Median Price",
        "Avg_Price": "Avg Price", "Avg_DOM": "Avg DOM", "Avg_LSR": "L/S Ratio",
        "SIRC_Listings": "SIRC List", "SIRC_Buying": "SIRC Buy", "SIRC_Share": "SIRC Share",
    }),
    hide_index=True, use_container_width=True, height=400,
)

# ── Price comparison bar chart ─────────────────────────────────────────────
section("Median Price by Sub-Area")

top_n = sub_stats.head(25).sort_values("Median_Price", ascending=True)
fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    y=top_n["sub_area"],
    x=top_n["Median_Price"],
    orientation="h",
    marker_color=[SIRC_GOLD if v >= top_n["Median_Price"].median() else SIRC_NAVY for v in top_n["Median_Price"]],
    text=top_n["Median_Price"].apply(lambda v: f"${v/1e6:.2f}M" if v >= 1e6 else f"${v:,.0f}"),
    textposition="outside",
))
fig_bar.update_layout(height=max(380, len(top_n) * 22),
                      xaxis_tickformat="$,.0f", yaxis_title="")
apply_plotly_theme(fig_bar, f"Median Sale Price by Sub-Area — {sel_city} (top 25 by volume)")
st.plotly_chart(fig_bar, use_container_width=True)

# ── SIRC market share by sub-area ─────────────────────────────────────────
section("SIRC Market Share by Sub-Area")

sirc_chart = sub_stats[sub_stats["Transactions"] >= max(min_txns, 10)].sort_values("SIRC_Share", ascending=False).head(25)
colors = [SIRC_GOLD if v >= 0.1 else "#8B7355" if v >= 0.05 else "#E8E0D5" for v in sirc_chart["SIRC_Share"]]

fig_sirc = go.Figure(go.Bar(
    y=sirc_chart["sub_area"],
    x=sirc_chart["SIRC_Share"],
    orientation="h",
    marker_color=colors,
    text=sirc_chart["SIRC_Share"].apply(lambda v: f"{v:.1%}"),
    textposition="outside",
    customdata=sirc_chart[["SIRC_Involved", "Transactions"]].values,
    hovertemplate="<b>%{y}</b><br>SIRC: %{x:.1%}<br>SIRC transactions: %{customdata[0]:.0f} of %{customdata[1]:.0f}<extra></extra>",
))
fig_sirc.update_layout(height=max(350, len(sirc_chart) * 22),
                       xaxis_tickformat=".0%", xaxis_range=[0, min(sirc_chart["SIRC_Share"].max() * 1.3, 1)])
apply_plotly_theme(fig_sirc, f"SIRC Market Share by Sub-Area (top 25, min {max(min_txns,10)} transactions)")
st.plotly_chart(fig_sirc, use_container_width=True)

# ── Year-over-year trend for selected sub-areas ────────────────────────────
section("Price Trend Over Time by Sub-Area")

# Use selected sub-areas or top 6 by volume
trend_subs = sel_sub_areas if sel_sub_areas else sub_stats["sub_area"].head(6).tolist()

trend_df = (
    df[
        (df["city"] == sel_city) &
        (df["sub_area"].isin(trend_subs)) &
        (df["sold_year"].notna()) &
        (df["sold_price"].notna())
    ]
    .groupby(["sub_area", "sold_year"])
    .agg(Median_Price=("sold_price", "median"), Transactions=("mls_number", "count"))
    .reset_index()
)
trend_df["sold_year"] = trend_df["sold_year"].astype(int)
trend_df = trend_df[trend_df["Transactions"] >= 3]

if not trend_df.empty:
    fig_trend = px.line(
        trend_df, x="sold_year", y="Median_Price", color="sub_area",
        markers=True,
        color_discrete_sequence=[SIRC_NAVY, SIRC_GOLD, "#5A8A9F", "#8B7355", "#4A6741", "#8A3A3A"],
        hover_data={"Transactions": True},
    )
    fig_trend.update_layout(height=360, xaxis_title="Year",
                            yaxis_title="Median Price", yaxis_tickformat="$,.0f",
                            legend_title="Sub-Area",
                            legend=dict(orientation="h", y=-0.25))
    apply_plotly_theme(fig_trend, "Median Price Trend by Sub-Area")
    st.plotly_chart(fig_trend, use_container_width=True)

# ── DOM trend ──────────────────────────────────────────────────────────────
section("Days on Market Trend by Sub-Area")

dom_trend = (
    df[
        (df["city"] == sel_city) &
        (df["sub_area"].isin(trend_subs)) &
        (df["sold_year"].notna()) &
        (df["days_on_market"].notna())
    ]
    .groupby(["sub_area", "sold_year"])
    .agg(Avg_DOM=("days_on_market", "mean"), Transactions=("mls_number", "count"))
    .reset_index()
)
dom_trend["sold_year"] = dom_trend["sold_year"].astype(int)
dom_trend = dom_trend[dom_trend["Transactions"] >= 3]

if not dom_trend.empty:
    fig_dom = px.line(
        dom_trend, x="sold_year", y="Avg_DOM", color="sub_area",
        markers=True,
        color_discrete_sequence=[SIRC_NAVY, SIRC_GOLD, "#5A8A9F", "#8B7355", "#4A6741", "#8A3A3A"],
    )
    fig_dom.update_layout(height=320, xaxis_title="Year",
                          yaxis_title="Avg Days on Market",
                          legend_title="Sub-Area",
                          legend=dict(orientation="h", y=-0.3))
    apply_plotly_theme(fig_dom, "Average Days on Market by Sub-Area")
    st.plotly_chart(fig_dom, use_container_width=True)

# ── Property type mix by sub-area ──────────────────────────────────────────
section("Property Type Mix by Sub-Area")

type_mix = (
    filtered[filtered["sub_area"].isin(sub_stats["sub_area"].head(15).tolist())]
    .groupby(["sub_area", "prop_type"])
    .size()
    .reset_index(name="Count")
)

if not type_mix.empty:
    fig_mix = px.bar(
        type_mix,
        x="sub_area", y="Count", color="prop_type",
        barmode="stack",
        color_discrete_sequence=[SIRC_NAVY, SIRC_GOLD, "#5A8A9F", "#8B7355"],
    )
    fig_mix.update_layout(height=360, xaxis_title="", yaxis_title="Transactions",
                          xaxis_tickangle=-35,
                          legend_title="Property Type",
                          legend=dict(orientation="h", y=1.12))
    apply_plotly_theme(fig_mix, "Property Type Mix — Top 15 Sub-Areas by Volume")
    st.plotly_chart(fig_mix, use_container_width=True)

# ── Single sub-area deep dive ──────────────────────────────────────────────
section("Sub-Area Deep Dive")

sel_single = st.selectbox(
    "Select a sub-area for detailed view",
    sub_stats["sub_area"].tolist(),
    key="deep_dive_sub",
)

single_df = df[
    (df["city"] == sel_city) &
    (df["sub_area"] == sel_single)
].copy()
if sel_type != "All":
    single_df = single_df[single_df["prop_type"] == sel_type]

if not single_df.empty:
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("Total Transactions", f"{len(single_df):,}")
    d2.metric("Total Volume", f"${single_df['sold_price'].sum()/1e6:.1f}M")
    d3.metric("Median Price", f"${single_df['sold_price'].median():,.0f}")
    d4.metric("Avg DOM", f"{single_df['days_on_market'].mean():.0f}" if single_df["days_on_market"].notna().any() else "—")
    sirc_share_single = single_df["is_sirc_involved"].mean()
    d5.metric("SIRC Share", f"{sirc_share_single:.1%}")

    # Quarterly price trend
    q_trend = (
        single_df.dropna(subset=["sold_date", "sold_price"])
        .groupby("sold_ym")
        .agg(Median=("sold_price", "median"), Count=("mls_number", "count"))
        .reset_index()
        .sort_values("sold_ym")
    )
    q_trend = q_trend[q_trend["Count"] >= 2]

    if len(q_trend) >= 3:
        fig_single = go.Figure()
        fig_single.add_trace(go.Scatter(
            x=q_trend["sold_ym"], y=q_trend["Median"],
            mode="lines+markers",
            line=dict(color=SIRC_NAVY, width=2),
            fill="tozeroy", fillcolor=f"rgba(0,35,73,0.08)",
            name="Median Price",
        ))
        fig_single.update_layout(height=300, xaxis_title="Month",
                                  yaxis_tickformat="$,.0f",
                                  xaxis_tickangle=-45)
        apply_plotly_theme(fig_single, f"{sel_single} — Monthly Median Price")
        st.plotly_chart(fig_single, use_container_width=True)

    # Recent transactions
    st.markdown(f"**Recent transactions in {sel_single}**")
    recent_txns = single_df.sort_values("sold_date", ascending=False).head(20).copy()
    recent_txns["sold_price"] = recent_txns["sold_price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    recent_txns["list_to_sale_ratio"] = recent_txns["list_to_sale_ratio"].apply(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
    recent_txns["sold_date"] = recent_txns["sold_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(
        recent_txns[["mls_number", "address", "prop_type", "sold_price", "sold_date",
                     "days_on_market", "list_to_sale_ratio", "listing_office"]].rename(columns={
            "mls_number": "MLS #", "address": "Address", "prop_type": "Type",
            "sold_price": "Sold Price", "sold_date": "Date", "days_on_market": "DOM",
            "list_to_sale_ratio": "L/S Ratio", "listing_office": "Listing Office",
        }),
        hide_index=True, use_container_width=True,
    )
