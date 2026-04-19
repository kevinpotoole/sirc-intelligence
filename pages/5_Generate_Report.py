import io
import streamlit as st
import pandas as pd
from datetime import date

from utils.data_loader import load_data
from utils.styles import header, section, SIRC_CSS, SIRC_NAVY, SIRC_GOLD

st.set_page_config(page_title="Generate Report | SIRC", layout="wide")
header("Generate Report", "Branded Exports for Ownership & Internal Use")

df = load_data()
if df.empty:
    st.stop()

with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Report Options")
    years = sorted(df["sold_year"].dropna().unique().astype(int), reverse=True)
    sel_years = st.multiselect("Year(s)", years, default=years[:1] if years else [])
    cities = ["All"] + sorted(df["city"].dropna().unique())
    sel_city = st.selectbox("City / Market", cities)

fdf = df.copy()
if sel_years:
    fdf = fdf[fdf["sold_year"].isin(sel_years)]
if sel_city != "All":
    fdf = fdf[fdf["city"] == sel_city]

sirc_list = fdf[fdf["is_sirc_listing"]]
sirc_buy = fdf[fdf["is_sirc_buying"]]
sirc_df = fdf[fdf["is_sirc_involved"]]

section("Select Report Type")

report_type = st.radio("Report", [
    "Brokerage Performance Summary",
    "Agent Performance Report",
    "Market Overview Report",
    "Recruitment Intelligence Report",
], horizontal=True)

st.markdown("---")

# ── Brokerage Performance Summary ─────────────────────────────────────────
if report_type == "Brokerage Performance Summary":
    st.markdown(f"""
    <div style="border:2px solid {SIRC_GOLD};padding:2rem;border-radius:4px;background:#FFFFFF">
    <div style="text-align:center;margin-bottom:1.5rem">
        <p style="color:{SIRC_NAVY};font-size:0.7rem;letter-spacing:0.15em;text-transform:uppercase;margin:0">
        CONFIDENTIAL INTERNAL REPORT
        </p>
        <h2 style="font-family:'Georgia',serif;color:{SIRC_NAVY};font-size:1.6rem;margin:0.5rem 0">
        Sotheby's International Realty Canada
        </h2>
        <h3 style="color:{SIRC_GOLD};font-size:1rem;font-weight:400;margin:0">
        Brokerage Performance Summary
        </h3>
        <p style="color:#8B7355;font-size:0.8rem;margin:0.5rem 0 0 0">
        {('Years: ' + ', '.join(map(str,sel_years))) if sel_years else 'All Years'} &nbsp;|&nbsp;
        Market: {sel_city} &nbsp;|&nbsp;
        Generated: {date.today().strftime('%B %d, %Y')}
        </p>
    </div>
    <hr style="border:none;border-top:1px solid {SIRC_GOLD};margin:1.5rem 0">
    """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Volume (SIRC)", f"${sirc_df['sold_price'].sum() / 1e6:.1f}M")
    k2.metric("Total Transactions", f"{len(sirc_df):,}")
    k3.metric("Listing Side", f"{len(sirc_list):,} units")
    k4.metric("Buying Side", f"{len(sirc_buy):,} units")

    mkt_share = sirc_list["sold_price"].sum() / fdf["sold_price"].sum() * 100 if fdf["sold_price"].sum() > 0 else 0
    st.metric("Listing Market Share (Volume)", f"{mkt_share:.1f}%")

    st.markdown("#### Top Agents")
    top_agents = (
        sirc_list.groupby("listing_agent")
        .agg(Units=("mls_number", "count"), Volume=("sold_price", "sum"))
        .sort_values("Volume", ascending=False)
        .head(15)
        .reset_index()
    )
    top_agents["Volume"] = top_agents["Volume"].apply(lambda v: f"${v / 1e6:.2f}M")
    top_agents.insert(0, "Rank", range(1, len(top_agents) + 1))
    st.dataframe(top_agents, hide_index=True, use_container_width=True)

    st.markdown("#### Top Performing Neighbourhoods")
    top_neigh = (
        sirc_list.groupby("sub_area")
        .agg(Units=("mls_number", "count"), Volume=("sold_price", "sum"))
        .sort_values("Volume", ascending=False)
        .head(10)
        .reset_index()
    )
    top_neigh["Volume"] = top_neigh["Volume"].apply(lambda v: f"${v / 1e6:.2f}M")
    st.dataframe(top_neigh, hide_index=True, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ── Agent Performance Report ───────────────────────────────────────────────
elif report_type == "Agent Performance Report":
    list_agents = sorted(sirc_list["listing_agent"].dropna().unique())
    buy_agents = sorted(sirc_buy["buying_agent"].dropna().unique())
    all_agents = sorted(set(list_agents) | set(buy_agents))
    sel_agent = st.selectbox("Select Agent", all_agents)

    al = sirc_list[sirc_list["listing_agent"] == sel_agent]
    ab = sirc_buy[sirc_buy["buying_agent"] == sel_agent]
    total_vol = al["sold_price"].sum() + ab["sold_price"].sum()

    st.markdown(f"""
    <div style="border:2px solid {SIRC_GOLD};padding:2rem;border-radius:4px;background:#FFFFFF">
    <div style="text-align:center;margin-bottom:1.5rem">
        <p style="color:{SIRC_NAVY};font-size:0.7rem;letter-spacing:0.15em;text-transform:uppercase;margin:0">
        CONFIDENTIAL — MANAGING BROKER
        </p>
        <h2 style="font-family:'Georgia',serif;color:{SIRC_NAVY};font-size:1.6rem;margin:0.5rem 0">
        Agent Performance Report
        </h2>
        <h3 style="color:{SIRC_GOLD};font-size:1.1rem;font-weight:400;margin:0">
        {sel_agent}
        </h3>
        <p style="color:#8B7355;font-size:0.8rem;margin:0.5rem 0 0 0">
        Sotheby's International Realty Canada &nbsp;|&nbsp; {date.today().strftime('%B %d, %Y')}
        </p>
    </div>
    <hr style="border:none;border-top:1px solid {SIRC_GOLD};margin:1.5rem 0">
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Volume", f"${total_vol / 1e6:.2f}M")
    c2.metric("Total Units", str(len(al) + len(ab)))
    c3.metric("Avg DOM", f"{al['days_on_market'].mean():.0f}" if len(al) else "—")
    c4.metric("L/S Ratio", f"{al['list_to_sale_ratio'].mean():.2%}" if len(al) and al['list_to_sale_ratio'].notna().any() else "—")

    recent = pd.concat([
        al[["mls_number", "address", "city", "sold_price", "sold_date"]].assign(Role="Listing"),
        ab[["mls_number", "address", "city", "sold_price", "sold_date"]].assign(Role="Buying"),
    ]).sort_values("sold_date", ascending=False)
    recent["sold_price"] = recent["sold_price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    recent["sold_date"] = recent["sold_date"].dt.strftime("%Y-%m-%d")
    st.markdown("#### Transaction History")
    st.dataframe(recent.rename(columns={
        "mls_number": "MLS #", "address": "Address", "city": "City",
        "sold_price": "Sold Price", "sold_date": "Sold Date",
    }), hide_index=True, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ── Market Overview Report ────────────────────────────────────────────────
elif report_type == "Market Overview Report":
    st.markdown(f"""
    <div style="border:2px solid {SIRC_GOLD};padding:2rem;border-radius:4px;background:#FFFFFF">
    <div style="text-align:center;margin-bottom:1.5rem">
        <h2 style="font-family:'Georgia',serif;color:{SIRC_NAVY};font-size:1.6rem;margin:0.5rem 0">
        Market Overview Report
        </h2>
        <h3 style="color:{SIRC_GOLD};font-size:1rem;font-weight:400;margin:0">
        {sel_city} Market &nbsp;|&nbsp; {', '.join(map(str, sel_years)) if sel_years else 'All Years'}
        </h3>
        <p style="color:#8B7355;font-size:0.8rem">{date.today().strftime('%B %d, %Y')}</p>
    </div>
    <hr style="border:none;border-top:1px solid {SIRC_GOLD};margin:1.5rem 0">
    """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Market Volume", f"${fdf['sold_price'].sum() / 1e6:.0f}M")
    k2.metric("Total Transactions", f"{len(fdf):,}")
    k3.metric("Median Sale Price", f"${fdf['sold_price'].median():,.0f}" if len(fdf) else "—")
    k4.metric("Avg Days on Market", f"{fdf['days_on_market'].mean():.0f}" if len(fdf) else "—")

    st.markdown("#### Top Brokerages by Volume")
    top_brok = (
        fdf.groupby("listing_office")["sold_price"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    top_brok.columns = ["Brokerage", "Volume"]
    top_brok["Volume"] = top_brok["Volume"].apply(lambda v: f"${v / 1e6:.1f}M")
    top_brok.insert(0, "Rank", range(1, len(top_brok) + 1))
    st.dataframe(top_brok, hide_index=True, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ── Recruitment Intelligence Report ───────────────────────────────────────
elif report_type == "Recruitment Intelligence Report":
    st.markdown(f"""
    <div style="border:2px solid {SIRC_GOLD};padding:2rem;border-radius:4px;background:#FFFFFF">
    <div style="text-align:center;margin-bottom:1.5rem">
        <p style="color:{SIRC_NAVY};font-size:0.7rem;letter-spacing:0.15em;text-transform:uppercase;margin:0">
        STRICTLY CONFIDENTIAL — MANAGING BROKER ONLY
        </p>
        <h2 style="font-family:'Georgia',serif;color:{SIRC_NAVY};font-size:1.6rem;margin:0.5rem 0">
        Recruitment Intelligence Report
        </h2>
        <p style="color:#8B7355;font-size:0.8rem">{date.today().strftime('%B %d, %Y')}</p>
    </div>
    <hr style="border:none;border-top:1px solid {SIRC_GOLD};margin:1.5rem 0">
    """, unsafe_allow_html=True)

    non_sirc = fdf[~fdf["is_sirc_listing"]]
    top_targets = (
        non_sirc.groupby(["listing_agent", "listing_office"])
        .agg(Units=("mls_number", "count"), Volume=("sold_price", "sum"), Avg_Price=("sold_price", "mean"))
        .reset_index()
        .sort_values("Volume", ascending=False)
        .head(30)
    )
    top_targets["Volume"] = top_targets["Volume"].apply(lambda v: f"${v / 1e6:.2f}M")
    top_targets["Avg_Price"] = top_targets["Avg_Price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    top_targets.insert(0, "Rank", range(1, len(top_targets) + 1))
    top_targets = top_targets.rename(columns={
        "listing_agent": "Agent", "listing_office": "Current Brokerage",
        "Avg_Price": "Avg Sale Price",
    })
    st.markdown("#### Top 30 Recruitment Targets by Volume")
    st.dataframe(top_targets, hide_index=True, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── CSV Export ─────────────────────────────────────────────────────────────
st.markdown("---")
section("Export Data")
st.markdown("Download a CSV of the filtered dataset for external use.")

csv_data = fdf.copy()
for col in ["sold_date", "list_date"]:
    if col in csv_data.columns:
        csv_data[col] = csv_data[col].dt.strftime("%Y-%m-%d")

csv_bytes = csv_data.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download Filtered Dataset (CSV)",
    data=csv_bytes,
    file_name=f"SIRC_data_{date.today().isoformat()}.csv",
    mime="text/csv",
)
