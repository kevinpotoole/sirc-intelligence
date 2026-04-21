import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data
from utils.styles import apply_plotly_theme, header, section, SIRC_CSS, SIRC_NAVY, SIRC_GOLD, SIRC_CREAM

header("List vs Sold Analysis", "Active Listings vs Recent Comparable Sales")

df = load_data()
if df.empty:
    st.stop()

active = df[df["status"].str.upper().isin(["ACTIVE", "A"])].copy() if "status" in df.columns else pd.DataFrame()
sold   = df[~df["status"].str.upper().isin(["ACTIVE", "A"])].copy() if "status" in df.columns else df.copy()

if active.empty:
    st.info("No Active listings found yet. Add CSV files with Active status listings to enable this analysis.")
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Filters")

    cities = sorted(active["city"].dropna().unique())
    sel_city = st.selectbox("City", cities, index=cities.index("VANCOUVER") if "VANCOUVER" in cities else 0)

    prop_types = ["All"] + sorted(active["prop_type"].dropna().unique())
    sel_type = st.selectbox("Property Type", prop_types)

    comp_months = st.slider("Comparable sales lookback (months)", 1, 24, 6)

# ── Filter ─────────────────────────────────────────────────────────────────
act_city = active[active["city"] == sel_city].copy()
if sel_type != "All":
    act_city = act_city[act_city["prop_type"] == sel_type]

cutoff = pd.Timestamp.now() - pd.DateOffset(months=comp_months)
sold_city = sold[
    (sold["city"] == sel_city) &
    (sold["sold_date"] >= cutoff)
].copy()
if sel_type != "All":
    sold_city = sold_city[sold_city["prop_type"] == sel_type]

if act_city.empty:
    st.warning(f"No active listings in {sel_city} for the selected filters.")
    st.stop()

# ── KPIs ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Active Listings", f"{len(act_city):,}")
k2.metric("Median List Price", f"${act_city['list_price'].median():,.0f}" if act_city["list_price"].notna().any() else "—")
k3.metric(f"Sold (last {comp_months}mo)", f"{len(sold_city):,}")
k4.metric("Median Sold Price", f"${sold_city['sold_price'].median():,.0f}" if sold_city["sold_price"].notna().any() else "—")

# ── Price comparison by sub-area ───────────────────────────────────────────
section(f"Median List Price vs Median Sold Price by Sub-Area — {sel_city}")

act_sub = (
    act_city.groupby("sub_area")["list_price"]
    .median().reset_index()
    .rename(columns={"list_price": "Median List"})
)
sold_sub = (
    sold_city.groupby("sub_area")["sold_price"]
    .median().reset_index()
    .rename(columns={"sold_price": "Median Sold"})
)
merged = act_sub.merge(sold_sub, on="sub_area", how="inner").dropna()
merged["Price Gap %"] = ((merged["Median List"] - merged["Median Sold"]) / merged["Median Sold"] * 100).round(1)
merged = merged.sort_values("Median Sold", ascending=False).head(20)

if not merged.empty:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Median List Price",
        y=merged["sub_area"], x=merged["Median List"],
        orientation="h", marker_color=SIRC_GOLD,
    ))
    fig.add_trace(go.Bar(
        name="Median Sold Price",
        y=merged["sub_area"], x=merged["Median Sold"],
        orientation="h", marker_color=SIRC_NAVY,
    ))
    fig.update_layout(
        barmode="group", height=max(380, len(merged)*30),
        xaxis_tickformat="$,.0f", yaxis_title="",
        legend=dict(orientation="h", y=1.05),
    )
    apply_plotly_theme(fig, f"List vs Sold — {sel_city} (top 20 sub-areas by sold price)")
    st.plotly_chart(fig, use_container_width=True)

    # Gap table
    disp = merged.copy()
    disp["Median List"] = disp["Median List"].apply(lambda v: f"${v:,.0f}")
    disp["Median Sold"] = disp["Median Sold"].apply(lambda v: f"${v:,.0f}")
    disp["Price Gap %"] = disp["Price Gap %"].apply(lambda v: f"+{v:.1f}%" if v > 0 else f"{v:.1f}%")
    st.dataframe(
        disp.rename(columns={"sub_area": "Sub-Area"}),
        hide_index=True, use_container_width=True, height=350,
    )
else:
    st.info("Not enough overlapping sub-area data to compare. Try increasing the lookback period.")

# ── Scatter: list price vs sold price (individual listings) ────────────────
section("Individual Listing vs Recent Comps Scatter")

if sold_city["sold_price"].notna().any() and act_city["list_price"].notna().any():
    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=sold_city["sold_price"], y=sold_city["sold_price"],
        mode="markers",
        marker=dict(color=SIRC_NAVY, size=5, opacity=0.4),
        name=f"Sold (last {comp_months}mo)",
        hovertemplate="Sold: $%{x:,.0f}<extra></extra>",
    ))
    fig_scatter.add_trace(go.Scatter(
        x=act_city["list_price"], y=act_city["list_price"],
        mode="markers",
        marker=dict(color=SIRC_GOLD, size=7, opacity=0.8, symbol="diamond"),
        name="Active Listings",
        hovertemplate="Listed: $%{x:,.0f}<extra></extra>",
    ))
    fig_scatter.update_layout(
        height=380,
        xaxis_title="Price", xaxis_tickformat="$,.0f",
        yaxis_title="Price", yaxis_tickformat="$,.0f",
        legend=dict(orientation="h", y=1.05),
    )
    apply_plotly_theme(fig_scatter, "Active List Prices vs Recent Sold Prices")
    st.plotly_chart(fig_scatter, use_container_width=True)

# ── Days on market comparison ──────────────────────────────────────────────
section("Days on Market: Active vs Time-to-Sell")

col1, col2 = st.columns(2)
with col1:
    if act_city["days_on_market"].notna().any():
        avg_dom_active = act_city["days_on_market"].mean()
        st.metric("Avg Days Currently Listed (Active)", f"{avg_dom_active:.0f} days")
        fig_dom_a = px.histogram(act_city.dropna(subset=["days_on_market"]), x="days_on_market",
                                  nbins=30, color_discrete_sequence=[SIRC_GOLD])
        fig_dom_a.update_layout(height=260, xaxis_title="Days Listed", yaxis_title="Listings")
        apply_plotly_theme(fig_dom_a, "Active — Days Listed Distribution")
        st.plotly_chart(fig_dom_a, use_container_width=True)

with col2:
    if sold_city["days_on_market"].notna().any():
        avg_dom_sold = sold_city["days_on_market"].mean()
        st.metric("Avg Days to Sell (Recent Sold)", f"{avg_dom_sold:.0f} days")
        fig_dom_s = px.histogram(sold_city.dropna(subset=["days_on_market"]), x="days_on_market",
                                  nbins=30, color_discrete_sequence=[SIRC_NAVY])
        fig_dom_s.update_layout(height=260, xaxis_title="Days on Market", yaxis_title="Sales")
        apply_plotly_theme(fig_dom_s, "Sold — Days on Market Distribution")
        st.plotly_chart(fig_dom_s, use_container_width=True)
