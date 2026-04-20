import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load_data
from utils.styles import (
    apply_plotly_theme, header, section,
    SIRC_CSS, SIRC_NAVY, SIRC_GOLD, SIRC_CREAM,
)

st.set_page_config(page_title="Agent Search | SIRC", layout="wide")
header("Agent Search", "Full profile for any agent in the market")

df = load_data()
if df.empty:
    st.stop()

# ── Build a master agent index across both listing and buying sides ─────────
@st.cache_data(show_spinner=False)
def build_agent_index(_df):
    listing = (
        _df.groupby("listing_agent")
        .agg(
            List_Units=("mls_number", "count"),
            List_Volume=("sold_price", "sum"),
            Avg_List_Price=("sold_price", "mean"),
            Avg_DOM=("days_on_market", "mean"),
            LSR=("list_to_sale_ratio", "mean"),
            Price_Min=("sold_price", "min"),
            Price_Max=("sold_price", "max"),
            Primary_Office=("listing_office", lambda x: x.mode().iloc[0] if len(x) else "Unknown"),
            First_Txn=("sold_date", "min"),
            Last_Txn=("sold_date", "max"),
        )
        .reset_index()
        .rename(columns={"listing_agent": "Agent"})
    )
    buying = (
        _df.groupby("buying_agent")
        .agg(
            Buy_Units=("mls_number", "count"),
            Buy_Volume=("sold_price", "sum"),
        )
        .reset_index()
        .rename(columns={"buying_agent": "Agent"})
    )
    idx = listing.merge(buying, on="Agent", how="outer").fillna(0)
    idx["Total_Units"] = idx["List_Units"] + idx["Buy_Units"]
    idx["Total_Volume"] = idx["List_Volume"] + idx["Buy_Volume"]
    idx["Primary_Office"] = idx["Primary_Office"].replace(0, "Unknown")
    idx = idx[
        (idx["Agent"] != "Unknown") &
        (idx["Agent"] != "") &
        (idx["Total_Units"] > 0)
    ].sort_values("Total_Volume", ascending=False).reset_index(drop=True)
    return idx

agent_index = build_agent_index(df)
all_agent_names = agent_index["Agent"].tolist()

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Agent Search")
    st.markdown(
        f"<small style='color:#C9A96E'>{len(all_agent_names):,} agents in dataset</small>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown("<small style='color:#F7F3EE'>Search across all brokerages including SIRC agents. Partial name matches are supported.</small>", unsafe_allow_html=True)

# ── Search box ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:{SIRC_NAVY};padding:1rem 1.5rem;border-radius:4px;margin-bottom:1.5rem">
<p style="color:#C9A96E;font-size:0.75rem;letter-spacing:0.1em;text-transform:uppercase;margin:0 0 0.3rem 0">
Agent Intelligence Search
</p>
<p style="color:#F7F3EE;font-size:0.85rem;margin:0">
Search any agent by name — partial matches work. Results include all agents across every brokerage in the market.
</p>
</div>
""", unsafe_allow_html=True)

search_query = st.text_input(
    "Enter agent name",
    placeholder="e.g. Smith, Jane D, John A...",
    label_visibility="collapsed",
)

if not search_query or len(search_query.strip()) < 2:
    st.info("Type at least 2 characters to search.")
    st.stop()

# ── Match agents ────────────────────────────────────────────────────────────
query_lower = search_query.strip().lower()
matches = agent_index[agent_index["Agent"].str.lower().str.contains(query_lower, na=False)]

if matches.empty:
    st.warning(f"No agents found matching **{search_query}**. Try a shorter name or check spelling.")
    st.stop()

# ── If multiple matches, show a picker ────────────────────────────────────
section(f"{len(matches):,} agent{'s' if len(matches) != 1 else ''} matching \"{search_query}\"")

if len(matches) == 1:
    selected_name = matches.iloc[0]["Agent"]
else:
    match_labels = [
        f"{row['Agent']}  —  {row['Primary_Office']}  —  ${row['Total_Volume']/1e6:.2f}M"
        for _, row in matches.head(50).iterrows()
    ]
    chosen = st.selectbox("Select agent", match_labels)
    selected_name = chosen.split("  —  ")[0].strip()

# ── Pull full profile ──────────────────────────────────────────────────────
row = agent_index[agent_index["Agent"] == selected_name].iloc[0]

agent_listings = df[df["listing_agent"] == selected_name].copy()
agent_buying   = df[df["buying_agent"]  == selected_name].copy()

is_sirc = any(
    k in str(row["Primary_Office"]).lower()
    for k in ["sotheby", "sothebys", "sotheby's"]
)

# ── Name + brokerage banner ────────────────────────────────────────────────
badge_color = SIRC_GOLD if is_sirc else "#E8E0D5"
badge_text_color = SIRC_NAVY if is_sirc else "#8B7355"
badge_label = "SIRC Agent" if is_sirc else "Competitor Agent"

st.markdown(f"""
<div style="background:{SIRC_NAVY};padding:1.2rem 1.8rem;border-radius:4px;margin-bottom:1rem;display:flex;align-items:center;justify-content:space-between">
  <div>
    <p style="color:{SIRC_GOLD};font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:600;margin:0">{selected_name}</p>
    <p style="color:#F7F3EE;font-size:0.85rem;margin:0.2rem 0 0 0">{row['Primary_Office']}</p>
  </div>
  <div style="background:{badge_color};color:{badge_text_color};font-size:0.65rem;letter-spacing:0.12em;text-transform:uppercase;padding:0.25rem 0.8rem;border-radius:2px;font-weight:600">
    {badge_label}
  </div>
</div>
""", unsafe_allow_html=True)

# ── KPI row ────────────────────────────────────────────────────────────────
section("Career Summary")
k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric("Total Volume", f"${row['Total_Volume']/1e6:.2f}M")
k2.metric("Total Transactions", f"{int(row['Total_Units']):,}")
k3.metric("Listing Side", f"{int(row['List_Units']):,}")
k4.metric("Buying Side", f"{int(row['Buy_Units']):,}")
k5.metric("Avg Sale Price",
          f"${row['Avg_List_Price']:,.0f}" if row["Avg_List_Price"] and row["Avg_List_Price"] != 0 else "—")
k6.metric("Avg Days on Market",
          f"{row['Avg_DOM']:.0f}" if row["Avg_DOM"] and row["Avg_DOM"] != 0 else "—")

# Price range + LSR
pr_col, lsr_col, date_col, _ = st.columns([1, 1, 1, 1])
pr_col.metric("Price Range",
    f"${row['Price_Min']:,.0f} – ${row['Price_Max']:,.0f}"
    if row["Price_Min"] and row["Price_Max"] else "—")
lsr_col.metric("Avg List/Sale Ratio",
    f"{row['LSR']:.2%}" if row["LSR"] and row["LSR"] != 0 else "—")

first_str = row["First_Txn"].strftime("%b %Y") if pd.notna(row.get("First_Txn")) and row["First_Txn"] != 0 else "—"
last_str  = row["Last_Txn"].strftime("%b %Y")  if pd.notna(row.get("Last_Txn"))  and row["Last_Txn"]  != 0 else "—"
date_col.metric("Active Period", f"{first_str} → {last_str}")

# ── Markets + neighbourhoods ───────────────────────────────────────────────
section("Markets & Specialisation")
mc1, mc2, mc3 = st.columns(3)

top_cities = pd.concat([agent_listings["city"], agent_buying["city"]]).value_counts().head(5)
top_areas  = pd.concat([agent_listings["sub_area"], agent_buying["sub_area"]]).value_counts().head(5)
top_types  = pd.concat([agent_listings["prop_type"], agent_buying["prop_type"]]).value_counts().head(5)

with mc1:
    st.markdown("**Top Cities / Markets**")
    for city, cnt in top_cities.items():
        st.markdown(f"<small>• {city} ({cnt})</small>", unsafe_allow_html=True)

with mc2:
    st.markdown("**Top Neighbourhoods**")
    for area, cnt in top_areas.items():
        st.markdown(f"<small>• {area} ({cnt})</small>", unsafe_allow_html=True)

with mc3:
    st.markdown("**Property Types**")
    for ptype, cnt in top_types.items():
        st.markdown(f"<small>• {ptype} ({cnt})</small>", unsafe_allow_html=True)

# ── Year-by-year volume chart ──────────────────────────────────────────────
section("Annual Volume & Transaction Count")

yearly = pd.concat([
    agent_listings[["sold_year", "sold_price"]].assign(Role="Listing"),
    agent_buying[["sold_year", "sold_price"]].assign(Role="Buying"),
]).dropna(subset=["sold_year", "sold_price"])

if not yearly.empty:
    yearly_agg = (
        yearly.groupby(["sold_year", "Role"])
        .agg(Volume=("sold_price", "sum"), Units=("sold_price", "count"))
        .reset_index()
    )
    yearly_agg["sold_year"] = yearly_agg["sold_year"].astype(int)

    fig = go.Figure()
    colors = {"Listing": SIRC_NAVY, "Buying": SIRC_GOLD}
    for role in ["Listing", "Buying"]:
        sub = yearly_agg[yearly_agg["Role"] == role]
        fig.add_trace(go.Bar(
            x=sub["sold_year"], y=sub["Volume"],
            name=role, marker_color=colors[role],
            text=sub["Units"].apply(lambda u: f"{u} txn"),
            textposition="inside", textfont=dict(size=10, color="white"),
        ))
    fig.update_layout(barmode="group", xaxis_title="Year", yaxis_title="Volume ($)",
                      yaxis_tickformat="$,.0f", height=320)
    apply_plotly_theme(fig, f"{selected_name} — Annual Volume")
    st.plotly_chart(fig, use_container_width=True)

# ── Offices worked with (co-op analysis) ──────────────────────────────────
section("Co-operating Brokerages")
coop_col1, coop_col2 = st.columns(2)

with coop_col1:
    st.markdown("**Buying agents used on their listings**")
    coop_buyers = agent_listings["buying_office"].value_counts().head(10).reset_index()
    coop_buyers.columns = ["Brokerage", "Transactions"]
    st.dataframe(coop_buyers, hide_index=True, use_container_width=True)

with coop_col2:
    st.markdown("**Listing brokerages they bought from**")
    coop_list = agent_buying["listing_office"].value_counts().head(10).reset_index()
    coop_list.columns = ["Brokerage", "Transactions"]
    st.dataframe(coop_list, hide_index=True, use_container_width=True)

# ── All transactions ───────────────────────────────────────────────────────
section("All Transactions")

all_txns = pd.concat([
    agent_listings[[
        "mls_number", "address", "city", "sub_area", "prop_type",
        "sold_price", "list_price", "sold_date", "days_on_market",
        "list_to_sale_ratio", "listing_office", "buying_office",
    ]].assign(Role="Listing Agent"),
    agent_buying[[
        "mls_number", "address", "city", "sub_area", "prop_type",
        "sold_price", "list_price", "sold_date", "days_on_market",
        "list_to_sale_ratio", "listing_office", "buying_office",
    ]].assign(Role="Buying Agent"),
]).sort_values("sold_date", ascending=False).reset_index(drop=True)

# Format for display
disp = all_txns.copy()
disp["sold_price"]        = disp["sold_price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
disp["list_price"]        = disp["list_price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
disp["list_to_sale_ratio"]= disp["list_to_sale_ratio"].apply(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
disp["sold_date"]         = disp["sold_date"].dt.strftime("%Y-%m-%d")
disp["days_on_market"]    = disp["days_on_market"].apply(lambda v: f"{int(v)}" if pd.notna(v) else "—")

# Year filter
years = sorted(all_txns["sold_date"].dt.year.dropna().unique().astype(int), reverse=True)
if len(years) > 1:
    sel_years = st.multiselect("Filter by year", years, default=years, key="txn_year_filter")
    if sel_years:
        mask = all_txns["sold_date"].dt.year.isin(sel_years)
        disp = disp[mask.values]

st.markdown(f"<small style='color:#8B7355'>{len(disp):,} transactions shown</small>", unsafe_allow_html=True)

st.dataframe(
    disp.rename(columns={
        "mls_number": "MLS #", "address": "Address", "city": "City",
        "sub_area": "Neighbourhood", "prop_type": "Type",
        "sold_price": "Sold Price", "list_price": "List Price",
        "sold_date": "Date", "days_on_market": "DOM",
        "list_to_sale_ratio": "L/S Ratio",
        "listing_office": "Listing Office", "buying_office": "Buying Office",
        "Role": "Role",
    }),
    hide_index=True,
    use_container_width=True,
    height=500,
)

# ── Export ──────────────────────────────────────────────────────────────────
csv = all_txns.copy()
csv["sold_date"] = csv["sold_date"].dt.strftime("%Y-%m-%d")
st.download_button(
    "⬇  Export All Transactions (CSV)",
    data=csv.to_csv(index=False),
    file_name=f"{selected_name.replace(' ', '_')}_transactions.csv",
    mime="text/csv",
)
