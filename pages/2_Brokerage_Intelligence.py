import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils.data_loader import load_data
from utils.styles import header, section, apply_plotly_theme, SIRC_CSS, SIRC_NAVY, SIRC_GOLD

st.set_page_config(page_title="Brokerage Intelligence | SIRC", layout="wide")
header("Brokerage Intelligence", "SIRC vs. The Market")

df = load_data()
if df.empty:
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Filters")
    years = sorted(df["sold_year"].dropna().unique().astype(int), reverse=True)
    sel_years = st.multiselect("Year(s)", years, default=years[:2] if len(years) >= 2 else years)
    cities = ["All"] + sorted(df["city"].dropna().unique())
    sel_city = st.selectbox("City / Market", cities)
    prop_types = ["All"] + sorted(df["prop_type"].dropna().unique())
    sel_type = st.selectbox("Property Type", prop_types)
    top_n = st.slider("Top N Competitors", 5, 25, 10)

fdf = df.copy()
if sel_years:
    fdf = fdf[fdf["sold_year"].isin(sel_years)]
if sel_city != "All":
    fdf = fdf[fdf["city"] == sel_city]
if sel_type != "All":
    fdf = fdf[fdf["prop_type"] == sel_type]

sirc_df = fdf[fdf["is_sirc_involved"]]
sirc_list = fdf[fdf["is_sirc_listing"]]
sirc_buy = fdf[fdf["is_sirc_buying"]]

# ── Office performance matrix ──────────────────────────────────────────────
section("Office Performance Matrix")

office_stats = (
    fdf.groupby("listing_office")
    .agg(
        Units=("mls_number", "count"),
        Volume=("sold_price", "sum"),
        Avg_Price=("sold_price", "mean"),
        Avg_DOM=("days_on_market", "mean"),
        LSR=("list_to_sale_ratio", "mean"),
    )
    .reset_index()
    .sort_values("Volume", ascending=False)
    .head(top_n + 1)
)
office_stats["is_sirc"] = office_stats["listing_office"].str.lower().apply(
    lambda x: any(k in x for k in ["sotheby", "sothebys"])
)
office_stats["Market Share %"] = (office_stats["Volume"] / fdf["sold_price"].sum() * 100).round(2)

display = office_stats.copy()
display["Volume"] = display["Volume"].apply(lambda v: f"${v / 1e6:.1f}M")
display["Avg_Price"] = display["Avg_Price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
display["Avg_DOM"] = display["Avg_DOM"].apply(lambda v: f"{v:.0f}" if pd.notna(v) else "—")
display["LSR"] = display["LSR"].apply(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
display = display.rename(columns={
    "listing_office": "Brokerage", "Units": "Units",
    "Avg_Price": "Avg Sale Price", "Avg_DOM": "Avg DOM", "LSR": "L/S Ratio",
})

def highlight_sirc(row):
    if row.get("is_sirc", False):
        return [f"background-color: {SIRC_GOLD}20; font-weight: bold"] * len(row)
    return [""] * len(row)

st.dataframe(
    display.drop(columns=["is_sirc"]),
    hide_index=True,
    use_container_width=True,
)

# ── Volume comparison charts ───────────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    section("Volume by Brokerage")
    colors = [SIRC_GOLD if s else SIRC_NAVY for s in office_stats["is_sirc"]]
    fig = go.Figure(go.Bar(
        y=office_stats["listing_office"],
        x=office_stats["Volume"] / 1e6,
        orientation="h",
        marker_color=colors,
        text=(office_stats["Volume"] / 1e6).apply(lambda v: f"${v:.1f}M"),
        textposition="outside",
    ))
    apply_plotly_theme(fig, f"Top {top_n} Brokerages by Volume")
    fig.update_layout(height=450, yaxis=dict(autorange="reversed"), xaxis_title="Volume ($M)")
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    section("Units by Brokerage")
    fig2 = go.Figure(go.Bar(
        y=office_stats["listing_office"],
        x=office_stats["Units"],
        orientation="h",
        marker_color=colors,
        text=office_stats["Units"],
        textposition="outside",
    ))
    apply_plotly_theme(fig2, f"Top {top_n} Brokerages by Units Sold")
    fig2.update_layout(height=450, yaxis=dict(autorange="reversed"), xaxis_title="Units Sold")
    st.plotly_chart(fig2, use_container_width=True)

# ── Year-over-year trend ───────────────────────────────────────────────────
section("SIRC Year-over-Year Performance")

yoy = []
for yr in sorted(df["sold_year"].dropna().unique().astype(int)):
    yr_df = df[df["sold_year"] == yr]
    if sel_city != "All":
        yr_df = yr_df[yr_df["city"] == sel_city]
    if sel_type != "All":
        yr_df = yr_df[yr_df["prop_type"] == sel_type]
    s = yr_df[yr_df["is_sirc_listing"]]
    yoy.append({
        "Year": yr,
        "SIRC Volume": s["sold_price"].sum(),
        "SIRC Units": len(s),
        "Market Volume": yr_df["sold_price"].sum(),
        "Market Units": len(yr_df),
    })
yoy_df = pd.DataFrame(yoy)
yoy_df["Market Share %"] = (yoy_df["SIRC Volume"] / yoy_df["Market Volume"] * 100).round(2)

fig3 = go.Figure()
fig3.add_trace(go.Bar(x=yoy_df["Year"], y=yoy_df["SIRC Volume"] / 1e6,
                       name="SIRC Volume ($M)", marker_color=SIRC_NAVY))
fig3.add_trace(go.Scatter(x=yoy_df["Year"], y=yoy_df["Market Share %"],
                           name="Market Share %", line=dict(color=SIRC_GOLD, width=3),
                           yaxis="y2", mode="lines+markers+text",
                           text=yoy_df["Market Share %"].apply(lambda v: f"{v:.1f}%"),
                           textposition="top center"))
fig3.update_layout(
    yaxis=dict(title="Volume ($M)"),
    yaxis2=dict(title="Market Share %", overlaying="y", side="right"),
    height=380, legend=dict(orientation="h", y=1.1),
)
apply_plotly_theme(fig3, "SIRC Volume & Market Share by Year")
st.plotly_chart(fig3, use_container_width=True)

# ── Neighbourhood strength ─────────────────────────────────────────────────
section("SIRC Strength by Neighbourhood")

neigh = (
    fdf.groupby("sub_area")
    .agg(
        Total_Volume=("sold_price", "sum"),
        Total_Units=("mls_number", "count"),
    )
    .reset_index()
)
sirc_neigh = (
    sirc_list.groupby("sub_area")
    .agg(
        SIRC_Volume=("sold_price", "sum"),
        SIRC_Units=("mls_number", "count"),
    )
    .reset_index()
)
neigh = neigh.merge(sirc_neigh, on="sub_area", how="left").fillna(0)
neigh["SIRC_Share"] = (neigh["SIRC_Volume"] / neigh["Total_Volume"] * 100).round(1)
neigh = neigh[neigh["Total_Units"] >= 5].sort_values("SIRC_Share", ascending=False).head(20)

fig4 = px.bar(
    neigh, x="SIRC_Share", y="sub_area", orientation="h",
    color="SIRC_Share", color_continuous_scale=[[0, "#E8E0D5"], [0.5, SIRC_NAVY], [1, SIRC_GOLD]],
    text="SIRC_Share", labels={"SIRC_Share": "SIRC Share %", "sub_area": "Neighbourhood"},
)
fig4.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig4.update_layout(height=500, yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
apply_plotly_theme(fig4, "SIRC Listing Market Share by Neighbourhood")
st.plotly_chart(fig4, use_container_width=True)
