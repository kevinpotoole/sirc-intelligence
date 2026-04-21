import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load_data, refresh_data
from utils.styles import apply_plotly_theme, header, section, SIRC_CSS, SIRC_NAVY, SIRC_GOLD

df = load_data()
header("Command Centre", "Managing Broker Overview")

if df.empty:
    st.stop()

# ── Sidebar filters ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Filters")

    years = sorted(df["sold_year"].dropna().unique().astype(int), reverse=True)
    sel_years = st.multiselect("Year(s)", years, default=years[:2] if len(years) >= 2 else years)

    cities = ["All"] + sorted(df["city"].dropna().unique())
    sel_city = st.selectbox("City / Market", cities)

    prop_types = ["All"] + sorted(df["prop_type"].dropna().unique())
    sel_type = st.selectbox("Property Type", prop_types)

    st.markdown("---")
    if st.button("🔄  Refresh Data"):
        refresh_data()
        st.rerun()

    st.markdown(f"<small style='color:#C9A96E'>Data: {len(df):,} transactions loaded</small>", unsafe_allow_html=True)

# ── Apply filters ──────────────────────────────────────────────────────────
fdf = df.copy()
if sel_years:
    fdf = fdf[fdf["sold_year"].isin(sel_years)]
if sel_city != "All":
    fdf = fdf[fdf["city"] == sel_city]
if sel_type != "All":
    fdf = fdf[fdf["prop_type"] == sel_type]

sirc_df   = fdf[fdf["is_sirc_involved"]]
sirc_list = fdf[fdf["is_sirc_listing"]]
sirc_buy  = fdf[fdf["is_sirc_buying"]]

# ── Top KPIs ───────────────────────────────────────────────────────────────
section("Brokerage at a Glance")
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.metric("Total SIRC Volume", f"${sirc_df['sold_price'].sum() / 1e6:.1f}M")
with k2:
    st.metric("Transactions Involved", f"{len(sirc_df):,}")
with k3:
    st.metric("Listing Side", f"{len(sirc_list):,}")
with k4:
    st.metric("Buying Side", f"{len(sirc_buy):,}")
with k5:
    avg_price = sirc_df["sold_price"].mean()
    st.metric("Avg Sale Price", f"${avg_price:,.0f}" if pd.notna(avg_price) else "—")

# ── Market Share ───────────────────────────────────────────────────────────
section("Market Share vs. Competitors")

col_a, col_b = st.columns([3, 2])

with col_a:
    office_vol = (
        fdf.groupby("listing_office")["sold_price"]
        .sum().sort_values(ascending=False).head(15).reset_index()
    )
    office_vol.columns = ["Office", "Volume"]
    office_vol["is_sirc"] = office_vol["Office"].str.lower().apply(
        lambda x: any(k in x for k in ["sotheby", "sothebys"])
    )
    colors = [SIRC_GOLD if s else SIRC_NAVY for s in office_vol["is_sirc"]]
    fig = go.Figure(go.Bar(
        x=office_vol["Volume"] / 1e6, y=office_vol["Office"],
        orientation="h", marker_color=colors,
        text=(office_vol["Volume"] / 1e6).apply(lambda v: f"${v:.1f}M"),
        textposition="outside",
    ))
    apply_plotly_theme(fig, "Listing Volume by Office (Top 15)")
    fig.update_layout(height=500, yaxis=dict(autorange="reversed"), xaxis_title="Volume ($M)")
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    total_vol = fdf["sold_price"].sum()
    sirc_vol  = sirc_list["sold_price"].sum()
    fig2 = go.Figure(go.Pie(
        labels=["SIRC (Listing)", "All Others"],
        values=[sirc_vol, total_vol - sirc_vol],
        marker_colors=[SIRC_GOLD, SIRC_NAVY],
        hole=0.55, textinfo="percent+label",
    ))
    apply_plotly_theme(fig2, "SIRC Listing Market Share")
    fig2.update_layout(height=380)
    st.plotly_chart(fig2, use_container_width=True)
    mkt_share   = (sirc_vol / total_vol * 100) if total_vol > 0 else 0
    units_share = (len(sirc_list) / len(fdf) * 100) if len(fdf) > 0 else 0
    st.metric("Volume Market Share", f"{mkt_share:.1f}%")
    st.metric("Units Market Share",  f"{units_share:.1f}%")

# ── Monthly trend ──────────────────────────────────────────────────────────
section("Volume Trend Over Time")

monthly = (
    sirc_df.groupby("sold_ym")["sold_price"]
    .agg(["sum", "count"]).reset_index()
)
monthly.columns = ["Month", "Volume", "Units"]
monthly = monthly.sort_values("Month")

fig3 = go.Figure()
fig3.add_trace(go.Bar(x=monthly["Month"], y=monthly["Volume"] / 1e6,
                      name="Volume ($M)", marker_color=SIRC_NAVY, opacity=0.8))
fig3.add_trace(go.Scatter(x=monthly["Month"], y=monthly["Units"],
                          name="Units Sold", line=dict(color=SIRC_GOLD, width=2.5),
                          yaxis="y2", mode="lines+markers"))
fig3.update_layout(
    yaxis=dict(title="Volume ($M)"),
    yaxis2=dict(title="Units Sold", overlaying="y", side="right"),
    legend=dict(orientation="h", y=1.1), height=380,
)
apply_plotly_theme(fig3, "SIRC Monthly Volume & Units")
st.plotly_chart(fig3, use_container_width=True)

# ── Top SIRC Agents ────────────────────────────────────────────────────────
section("Top Performing Agents — Quick View")

col_l, col_r = st.columns(2)
with col_l:
    st.markdown("**Top Listing Agents**")
    top_list = (
        sirc_list.groupby("listing_agent")
        .agg(Units=("mls_number","count"), Volume=("sold_price","sum"))
        .sort_values("Volume", ascending=False).head(10).reset_index()
    )
    top_list["Volume"] = top_list["Volume"].apply(lambda v: f"${v/1e6:.2f}M")
    st.dataframe(top_list, hide_index=True, use_container_width=True)

with col_r:
    st.markdown("**Top Buying Agents**")
    top_buy = (
        sirc_buy.groupby("buying_agent")
        .agg(Units=("mls_number","count"), Volume=("sold_price","sum"))
        .sort_values("Volume", ascending=False).head(10).reset_index()
    )
    top_buy["Volume"] = top_buy["Volume"].apply(lambda v: f"${v/1e6:.2f}M")
    st.dataframe(top_buy, hide_index=True, use_container_width=True)

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#8B7355;font-size:0.7rem;letter-spacing:0.1em'>"
    "SOTHEBY'S INTERNATIONAL REALTY CANADA — CONFIDENTIAL INTELLIGENCE PLATFORM"
    "</p>",
    unsafe_allow_html=True,
)
