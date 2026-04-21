import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils.data_loader import load_data
from utils.styles import header, section, apply_plotly_theme, SIRC_CSS, SIRC_NAVY, SIRC_GOLD

header("Market Research", "Trends, Pricing & Opportunity")

df = load_data()
if df.empty:
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Filters")
    years = sorted(df["sold_year"].dropna().unique().astype(int), reverse=True)
    sel_years = st.multiselect("Year(s)", years, default=years[:3] if len(years) >= 3 else years)
    cities = ["All"] + sorted(df["city"].dropna().unique())
    sel_city = st.selectbox("City / Market", cities)
    prop_types = ["All"] + sorted(df["prop_type"].dropna().unique())
    sel_type = st.selectbox("Property Type", prop_types)

fdf = df.copy()
if sel_years:
    fdf = fdf[fdf["sold_year"].isin(sel_years)]
if sel_city != "All":
    fdf = fdf[fdf["city"] == sel_city]
if sel_type != "All":
    fdf = fdf[fdf["prop_type"] == sel_type]

# ── Market KPIs ────────────────────────────────────────────────────────────
section("Market Overview")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Market Volume", f"${fdf['sold_price'].sum() / 1e6:.0f}M")
k2.metric("Total Transactions", f"{len(fdf):,}")
k3.metric("Median Sale Price", f"${fdf['sold_price'].median():,.0f}" if len(fdf) else "—")
k4.metric("Avg Days on Market", f"{fdf['days_on_market'].mean():.0f}" if len(fdf) else "—")
k5.metric("Avg L/S Ratio", f"{fdf['list_to_sale_ratio'].mean():.2%}" if len(fdf) else "—")

# ── Price trends ───────────────────────────────────────────────────────────
section("Price Trends Over Time")

monthly = (
    fdf.groupby("sold_ym")
    .agg(
        Median_Price=("sold_price", "median"),
        Avg_Price=("sold_price", "mean"),
        Units=("mls_number", "count"),
        Avg_DOM=("days_on_market", "mean"),
    )
    .reset_index()
    .sort_values("sold_ym")
)

col_a, col_b = st.columns(2)

with col_a:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly["sold_ym"], y=monthly["Median_Price"],
                              name="Median Price", line=dict(color=SIRC_NAVY, width=2.5)))
    fig.add_trace(go.Scatter(x=monthly["sold_ym"], y=monthly["Avg_Price"],
                              name="Avg Price", line=dict(color=SIRC_GOLD, width=2, dash="dot")))
    apply_plotly_theme(fig, "Monthly Median & Average Sale Price")
    fig.update_layout(height=350, yaxis_title="Price ($)", xaxis_tickangle=-35,
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=monthly["sold_ym"], y=monthly["Units"],
                           marker_color=SIRC_NAVY, name="Units Sold", opacity=0.8))
    fig2.add_trace(go.Scatter(x=monthly["sold_ym"], y=monthly["Avg_DOM"],
                               name="Avg DOM", line=dict(color=SIRC_GOLD, width=2),
                               yaxis="y2"))
    fig2.update_layout(
        yaxis=dict(title="Units Sold"),
        yaxis2=dict(title="Avg Days on Market", overlaying="y", side="right"),
        height=350, xaxis_tickangle=-35, legend=dict(orientation="h", y=1.1),
    )
    apply_plotly_theme(fig2, "Monthly Volume & Days on Market")
    st.plotly_chart(fig2, use_container_width=True)

# ── By property type ────────────────────────────────────────────────────────
section("Performance by Property Type")

pt_stats = (
    fdf.groupby("prop_type")
    .agg(
        Units=("mls_number", "count"),
        Total_Volume=("sold_price", "sum"),
        Median_Price=("sold_price", "median"),
        Avg_DOM=("days_on_market", "mean"),
        LSR=("list_to_sale_ratio", "mean"),
    )
    .reset_index()
    .sort_values("Total_Volume", ascending=False)
)

col_c, col_d = st.columns(2)
with col_c:
    fig3 = px.pie(pt_stats, names="prop_type", values="Units",
                  color_discrete_sequence=[SIRC_NAVY, SIRC_GOLD, "#5A8A9F", "#8B7355", "#4A6741", "#8A3A3A"])
    apply_plotly_theme(fig3, "Units by Property Type")
    fig3.update_layout(height=350)
    st.plotly_chart(fig3, use_container_width=True)

with col_d:
    fig4 = px.bar(pt_stats, x="prop_type", y="Median_Price",
                  color_discrete_sequence=[SIRC_NAVY],
                  text=pt_stats["Median_Price"].apply(lambda v: f"${v:,.0f}"))
    fig4.update_traces(textposition="outside")
    apply_plotly_theme(fig4, "Median Price by Property Type")
    fig4.update_layout(height=350, xaxis_title="", yaxis_title="Median Price ($)", xaxis_tickangle=-25)
    st.plotly_chart(fig4, use_container_width=True)

# ── City breakdown ────────────────────────────────────────────────────────
section("Market Activity by City")

city_stats = (
    fdf.groupby("city")
    .agg(
        Units=("mls_number", "count"),
        Total_Volume=("sold_price", "sum"),
        Median_Price=("sold_price", "median"),
        Avg_DOM=("days_on_market", "mean"),
    )
    .reset_index()
    .sort_values("Total_Volume", ascending=False)
    .head(20)
)

fig5 = go.Figure()
fig5.add_trace(go.Bar(x=city_stats["city"], y=city_stats["Total_Volume"] / 1e6,
                       name="Volume ($M)", marker_color=SIRC_NAVY))
fig5.add_trace(go.Scatter(x=city_stats["city"], y=city_stats["Median_Price"],
                           name="Median Price", line=dict(color=SIRC_GOLD, width=2),
                           yaxis="y2", mode="lines+markers"))
fig5.update_layout(
    yaxis=dict(title="Volume ($M)"),
    yaxis2=dict(title="Median Price ($)", overlaying="y", side="right"),
    height=400, xaxis_tickangle=-35, legend=dict(orientation="h", y=1.1),
)
apply_plotly_theme(fig5, "Volume & Median Price by City (Top 20)")
st.plotly_chart(fig5, use_container_width=True)

# ── Price band analysis ────────────────────────────────────────────────────
section("Price Band Analysis")

bins = [0, 500_000, 750_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000, 5_000_000, float("inf")]
labels = ["<$500K", "$500K–750K", "$750K–1M", "$1M–1.5M", "$1.5M–2M", "$2M–3M", "$3M–5M", "$5M+"]
fdf = fdf.copy()
fdf["price_band"] = pd.cut(fdf["sold_price"], bins=bins, labels=labels)

band_stats = fdf.groupby("price_band", observed=True).agg(
    Units=("mls_number", "count"),
    SIRC_Units=("is_sirc_listing", "sum"),
).reset_index()
band_stats["SIRC_Share"] = (band_stats["SIRC_Units"] / band_stats["Units"] * 100).round(1)

fig6 = go.Figure()
fig6.add_trace(go.Bar(x=band_stats["price_band"].astype(str), y=band_stats["Units"],
                       name="Total Market", marker_color=SIRC_NAVY, opacity=0.7))
fig6.add_trace(go.Bar(x=band_stats["price_band"].astype(str), y=band_stats["SIRC_Units"],
                       name="SIRC", marker_color=SIRC_GOLD))
fig6.update_layout(barmode="overlay", height=380, xaxis_title="Price Range",
                   yaxis_title="Units Sold", legend=dict(orientation="h", y=1.1))
apply_plotly_theme(fig6, "Market vs. SIRC Activity by Price Band")
st.plotly_chart(fig6, use_container_width=True)

col_e, col_f = st.columns(2)
with col_e:
    st.markdown("**Transactions by Price Band**")
    band_display = band_stats.copy()
    band_display["price_band"] = band_display["price_band"].astype(str)
    band_display["SIRC_Share"] = band_display["SIRC_Share"].apply(lambda v: f"{v:.1f}%")
    st.dataframe(band_display.rename(columns={
        "price_band": "Price Band", "Units": "Market Units",
        "SIRC_Units": "SIRC Units", "SIRC_Share": "SIRC Share"
    }), hide_index=True, use_container_width=True)
