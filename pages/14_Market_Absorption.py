import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data
from utils.styles import apply_plotly_theme, header, section, SIRC_CSS, SIRC_NAVY, SIRC_GOLD, SIRC_CREAM

header("Market Absorption", "Months of Supply & Market Balance")

df = load_data()
if df.empty:
    st.stop()

if "status" not in df.columns:
    st.warning("Status column not found.")
    st.stop()

active = df[df["status"].str.upper().isin(["ACTIVE", "A"])].copy()
sold   = df[~df["status"].str.upper().isin(["ACTIVE", "A"])].copy()

if active.empty:
    st.info("No Active listings found yet. Add CSV files with Active status listings to enable absorption analysis.")
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Filters")

    cities = sorted(active["city"].dropna().unique())
    sel_cities = st.multiselect("City", cities, default=[])

    prop_types = ["All"] + sorted(active["prop_type"].dropna().unique())
    sel_type = st.selectbox("Property Type", prop_types)

    lookback = st.slider("Sales lookback (months)", 1, 12, 3,
                         help="Number of months of sales used to calculate average monthly sales rate")

    st.markdown("---")
    st.markdown("""
    **Market interpretation:**
    - **< 2 months** — Strong seller's market
    - **2–4 months** — Balanced (seller-leaning)
    - **4–6 months** — Balanced market
    - **> 6 months** — Buyer's market
    """)

# ── Filter ─────────────────────────────────────────────────────────────────
if sel_cities:
    active = active[active["city"].isin(sel_cities)]
    sold   = sold[sold["city"].isin(sel_cities)]
if sel_type != "All":
    active = active[active["prop_type"] == sel_type]
    sold   = sold[sold["prop_type"] == sel_type]

cutoff = pd.Timestamp.now() - pd.DateOffset(months=lookback)
sold_recent = sold[sold["sold_date"] >= cutoff].copy()
monthly_sales_rate = len(sold_recent) / lookback if lookback > 0 else 0

# ── Overall KPIs ───────────────────────────────────────────────────────────
active_count = len(active)
months_supply = (active_count / monthly_sales_rate) if monthly_sales_rate > 0 else None

k1, k2, k3, k4 = st.columns(4)
k1.metric("Active Listings", f"{active_count:,}")
k2.metric(f"Avg Monthly Sales (last {lookback}mo)", f"{monthly_sales_rate:.0f}")
k3.metric("Months of Supply", f"{months_supply:.1f}" if months_supply else "—")

if months_supply:
    if months_supply < 2:
        market = "🔴 Strong Seller's Market"
    elif months_supply < 4:
        market = "🟡 Seller's Market"
    elif months_supply <= 6:
        market = "🟢 Balanced Market"
    else:
        market = "🔵 Buyer's Market"
    k4.metric("Market Condition", market)

# ── Absorption by city ─────────────────────────────────────────────────────
section("Months of Supply by City")

city_active = active.groupby("city").size().reset_index(name="active_count")
city_sold   = sold_recent.groupby("city").size().reset_index(name="sold_count")
city_abs = city_active.merge(city_sold, on="city", how="left").fillna(0)
city_abs["monthly_rate"] = city_abs["sold_count"] / lookback
city_abs["months_supply"] = city_abs.apply(
    lambda r: r["active_count"] / r["monthly_rate"] if r["monthly_rate"] > 0 else None, axis=1
)
city_abs = city_abs.dropna(subset=["months_supply"]).sort_values("months_supply")

def supply_color(v):
    if v < 2:   return "#8A3A3A"   # red — seller's
    if v < 4:   return SIRC_GOLD   # gold — mild seller's
    if v <= 6:  return "#4A6741"   # green — balanced
    return "#2E5090"               # blue — buyer's

colors = [supply_color(v) for v in city_abs["months_supply"]]

fig_city = go.Figure(go.Bar(
    x=city_abs["months_supply"],
    y=city_abs["city"],
    orientation="h",
    marker_color=colors,
    text=city_abs["months_supply"].apply(lambda v: f"{v:.1f}mo"),
    textposition="outside",
    customdata=city_abs[["active_count","sold_count"]].values,
    hovertemplate="<b>%{y}</b><br>Supply: %{x:.1f} months<br>Active: %{customdata[0]:.0f} | Sold/mo: %{customdata[1]:.1f}<extra></extra>",
))
fig_city.add_vline(x=2, line_dash="dot", line_color="#8A3A3A", annotation_text="Seller's", annotation_position="top")
fig_city.add_vline(x=6, line_dash="dot", line_color="#2E5090", annotation_text="Buyer's", annotation_position="top")
fig_city.update_layout(height=max(380, len(city_abs)*24), xaxis_title="Months of Supply", yaxis_title="")
apply_plotly_theme(fig_city, f"Months of Supply by City (active ÷ avg monthly sales, last {lookback}mo)")
st.plotly_chart(fig_city, use_container_width=True)

# ── Absorption by sub-area ─────────────────────────────────────────────────
if "sub_area" in active.columns and active["sub_area"].notna().any():
    section("Months of Supply by Sub-Area")

    sub_active = active.groupby("sub_area").size().reset_index(name="active_count")
    sub_sold   = sold_recent.groupby("sub_area").size().reset_index(name="sold_count")
    sub_abs = sub_active.merge(sub_sold, on="sub_area", how="left").fillna(0)
    sub_abs["monthly_rate"] = sub_abs["sold_count"] / lookback
    sub_abs["months_supply"] = sub_abs.apply(
        lambda r: r["active_count"] / r["monthly_rate"] if r["monthly_rate"] > 0 else None, axis=1
    )
    sub_abs = sub_abs.dropna(subset=["months_supply"]).sort_values("months_supply").head(30)

    sub_colors = [supply_color(v) for v in sub_abs["months_supply"]]

    fig_sub = go.Figure(go.Bar(
        x=sub_abs["months_supply"],
        y=sub_abs["sub_area"],
        orientation="h",
        marker_color=sub_colors,
        text=sub_abs["months_supply"].apply(lambda v: f"{v:.1f}mo"),
        textposition="outside",
    ))
    fig_sub.add_vline(x=2, line_dash="dot", line_color="#8A3A3A")
    fig_sub.add_vline(x=6, line_dash="dot", line_color="#2E5090")
    fig_sub.update_layout(height=max(420, len(sub_abs)*22), xaxis_title="Months of Supply", yaxis_title="")
    apply_plotly_theme(fig_sub, "Months of Supply by Sub-Area (top 30)")
    st.plotly_chart(fig_sub, use_container_width=True)

# ── Historical absorption trend ────────────────────────────────────────────
section("Monthly Sales Trend (Sold Volume)")

monthly_all = (
    sold[sold["sold_date"].notna()]
    .groupby("sold_ym")
    .agg(Sales=("mls_number","count"), Volume=("sold_price","sum"))
    .reset_index()
    .sort_values("sold_ym")
    .tail(24)
)

if not monthly_all.empty:
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(
        x=monthly_all["sold_ym"], y=monthly_all["Sales"],
        name="Monthly Sales", marker_color=SIRC_NAVY,
    ))
    avg_line = [monthly_sales_rate] * len(monthly_all)
    fig_trend.add_trace(go.Scatter(
        x=monthly_all["sold_ym"], y=avg_line,
        name=f"Avg last {lookback}mo ({monthly_sales_rate:.0f}/mo)",
        line=dict(color=SIRC_GOLD, dash="dash", width=2),
    ))
    fig_trend.update_layout(height=320, xaxis_title="Month", yaxis_title="Transactions",
                             xaxis_tickangle=-30,
                             legend=dict(orientation="h", y=1.05))
    apply_plotly_theme(fig_trend, "Monthly Sales Volume (last 24 months)")
    st.plotly_chart(fig_trend, use_container_width=True)

# ── Summary table ──────────────────────────────────────────────────────────
section("Absorption Summary Table")

city_abs_disp = city_abs.copy()
city_abs_disp["monthly_rate"] = city_abs_disp["monthly_rate"].apply(lambda v: f"{v:.1f}")
city_abs_disp["months_supply"] = city_abs_disp["months_supply"].apply(lambda v: f"{v:.1f}")
city_abs_disp["Market"] = city_abs[["months_supply"]].apply(
    lambda r: "Seller's" if r["months_supply"] < 4 else ("Balanced" if r["months_supply"] <= 6 else "Buyer's"), axis=1
)
st.dataframe(
    city_abs_disp.rename(columns={
        "city":"City","active_count":"Active Listings",
        "sold_count":f"Sold (last {lookback}mo)","monthly_rate":"Sales/Month",
        "months_supply":"Months Supply",
    })[["City","Active Listings",f"Sold (last {lookback}mo)","Sales/Month","Months Supply","Market"]],
    hide_index=True, use_container_width=True,
)
