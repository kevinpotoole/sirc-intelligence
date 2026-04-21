import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils.data_loader import load_data
from utils.styles import header, section, apply_plotly_theme, SIRC_CSS, SIRC_NAVY, SIRC_GOLD

header("Recruitment Radar", "Talent Intelligence & Competitor Agent Research")

df = load_data()
if df.empty:
    st.stop()

non_sirc_list = df[~df["is_sirc_listing"]]
non_sirc_buy = df[~df["is_sirc_buying"]]

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
    offices = sorted(non_sirc_list["listing_office"].dropna().unique())
    sel_office = st.selectbox("Filter by Brokerage", ["All"] + offices)
    min_units = st.number_input("Min. Listing Units", min_value=1, value=3)

# ── Apply filters ──────────────────────────────────────────────────────────
fl = non_sirc_list.copy()
fb = non_sirc_buy.copy()
if sel_years:
    fl = fl[fl["sold_year"].isin(sel_years)]
    fb = fb[fb["sold_year"].isin(sel_years)]
if sel_city != "All":
    fl = fl[fl["city"] == sel_city]
    fb = fb[fb["city"] == sel_city]
if sel_type != "All":
    fl = fl[fl["prop_type"] == sel_type]
    fb = fb[fb["prop_type"] == sel_type]
if sel_office != "All":
    fl = fl[fl["listing_office"] == sel_office]
    fb = fb[fb["buying_office"] == sel_office]

# ── Build profiles using vectorized groupby (fast) ─────────────────────────
list_stats = (
    fl.groupby("listing_agent")
    .agg(
        List_Units=("mls_number", "count"),
        List_Volume=("sold_price", "sum"),
        Avg_Price=("sold_price", "mean"),
        Avg_DOM=("days_on_market", "mean"),
        LSR=("list_to_sale_ratio", "mean"),
        Price_Min=("sold_price", "min"),
        Price_Max=("sold_price", "max"),
        Current_Brokerage=("listing_office", lambda x: x.mode().iloc[0] if len(x) > 0 else "Unknown"),
    )
    .reset_index()
    .rename(columns={"listing_agent": "Agent"})
)

buy_stats = (
    fb.groupby("buying_agent")
    .agg(
        Buy_Units=("mls_number", "count"),
        Buy_Volume=("sold_price", "sum"),
    )
    .reset_index()
    .rename(columns={"buying_agent": "Agent"})
)

profiles = list_stats.merge(buy_stats, on="Agent", how="outer").fillna(0)
profiles["Total_Units"] = profiles["List_Units"] + profiles["Buy_Units"]
profiles["Total_Volume"] = profiles["List_Volume"] + profiles["Buy_Volume"]

# Apply min units filter and remove unknown agents
profiles = profiles[
    (profiles["List_Units"] >= min_units) &
    (profiles["Agent"] != "Unknown") &
    (profiles["Agent"] != "")
].sort_values("Total_Volume", ascending=False).reset_index(drop=True)

# Fix brokerage column for agents who only appear on buy side
profiles["Current_Brokerage"] = profiles["Current_Brokerage"].replace(0, "Unknown")

# ── KPIs ───────────────────────────────────────────────────────────────────
section("Talent Pool Overview")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Agents Identified", f"{len(profiles):,}")
k2.metric("Brokerages Represented", f"{profiles['Current_Brokerage'].nunique():,}")
k3.metric("Avg Volume per Agent", f"${profiles['Total_Volume'].mean() / 1e6:.2f}M" if len(profiles) else "—")
k4.metric("Top Agent Volume", f"${profiles['Total_Volume'].max() / 1e6:.2f}M" if len(profiles) else "—")

# ── Top targets ────────────────────────────────────────────────────────────
section("Top Recruitment Targets")

def fmt_profiles(p):
    p = p.copy()
    p["Total_Volume"] = p["Total_Volume"].apply(lambda v: f"${v / 1e6:.2f}M")
    p["Avg_Price"] = p["Avg_Price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) and v != 0 else "—")
    p["Price_Min"] = p["Price_Min"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) and v != 0 else "—")
    p["Price_Max"] = p["Price_Max"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) and v != 0 else "—")
    p["Avg_DOM"] = p["Avg_DOM"].apply(lambda v: f"{v:.0f}" if pd.notna(v) and v != 0 else "—")
    p["LSR"] = p["LSR"].apply(lambda v: f"{v:.2%}" if pd.notna(v) and v != 0 else "—")
    return p.rename(columns={
        "Agent": "Agent", "Current_Brokerage": "Current Brokerage",
        "List_Units": "List Units", "Buy_Units": "Buy Units",
        "Total_Units": "Total Units", "Total_Volume": "Total Volume",
        "Avg_Price": "Avg Sale Price", "Avg_DOM": "Avg DOM",
        "LSR": "L/S Ratio", "Price_Min": "Price Min", "Price_Max": "Price Max",
    })

tab1, tab2, tab3 = st.tabs(["By Volume", "By Units", "By Avg Price (Luxury)"])

display_cols = ["Agent", "Current Brokerage", "Total Volume", "List Units",
                "Buy Units", "Total Units", "Avg Sale Price", "Avg DOM", "L/S Ratio"]

with tab1:
    t = fmt_profiles(profiles.head(50).reset_index(drop=True))
    t.insert(0, "Rank", range(1, len(t) + 1))
    st.dataframe(t[["Rank"] + display_cols], hide_index=True, use_container_width=True)

with tab2:
    t = fmt_profiles(profiles.sort_values("Total_Units", ascending=False).head(50).reset_index(drop=True))
    t.insert(0, "Rank", range(1, len(t) + 1))
    st.dataframe(t[["Rank"] + display_cols], hide_index=True, use_container_width=True)

with tab3:
    luxury = profiles[profiles["Avg_Price"] > 2_000_000].sort_values("Total_Volume", ascending=False)
    t = fmt_profiles(luxury.head(50).reset_index(drop=True))
    t.insert(0, "Rank", range(1, len(t) + 1))
    st.dataframe(t[["Rank"] + display_cols], hide_index=True, use_container_width=True)

# ── Agent Deep Dive ────────────────────────────────────────────────────────
section("Agent Deep Dive")

if len(profiles) > 0:
    sel_recruit = st.selectbox("Select an Agent to Investigate", profiles["Agent"].tolist())
    row = profiles[profiles["Agent"] == sel_recruit].iloc[0]

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Current Brokerage", row["Current_Brokerage"])
    col_b.metric("Total Volume", f"${row['Total_Volume'] / 1e6:.2f}M")
    col_c.metric("Units (L+B)", f"{int(row['List_Units'])} listing + {int(row['Buy_Units'])} buying")
    col_d.metric("Avg Sale Price", f"${row['Avg_Price']:,.0f}" if pd.notna(row["Avg_Price"]) and row["Avg_Price"] != 0 else "—")

    # Compute top cities/areas only for the selected agent
    agent_l = fl[fl["listing_agent"] == sel_recruit]
    agent_b = fb[fb["buying_agent"] == sel_recruit]
    top_cities = pd.concat([agent_l["city"], agent_b["city"]]).value_counts().head(3).index.tolist()
    top_areas = pd.concat([agent_l["sub_area"], agent_b["sub_area"]]).value_counts().head(3).index.tolist()

    st.markdown(f"""
**Active Markets:** {', '.join(top_cities) if top_cities else '—'}
**Top Neighbourhoods:** {', '.join(top_areas) if top_areas else '—'}
**Price Range:** {'${:,.0f}'.format(row['Price_Min']) if row['Price_Min'] != 0 else '—'} — {'${:,.0f}'.format(row['Price_Max']) if row['Price_Max'] != 0 else '—'}
    """)

    agent_txns = pd.concat([
        agent_l[["mls_number", "address", "city", "sold_price", "sold_date",
                  "days_on_market", "list_to_sale_ratio", "listing_office"]].assign(Role="Listing"),
        agent_b[["mls_number", "address", "city", "sold_price", "sold_date",
                  "days_on_market", "list_to_sale_ratio", "buying_office"]]
                .rename(columns={"buying_office": "listing_office"}).assign(Role="Buying"),
    ]).sort_values("sold_date", ascending=False)

    agent_txns["sold_price"] = agent_txns["sold_price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    agent_txns["list_to_sale_ratio"] = agent_txns["list_to_sale_ratio"].apply(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
    agent_txns["sold_date"] = agent_txns["sold_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(agent_txns.rename(columns={
        "mls_number": "MLS #", "address": "Address", "city": "City",
        "sold_price": "Sold Price", "sold_date": "Date", "days_on_market": "DOM",
        "list_to_sale_ratio": "L/S Ratio", "listing_office": "Office",
    }), hide_index=True, use_container_width=True)

# ── Brokerage talent map ───────────────────────────────────────────────────
section("Talent Distribution by Brokerage")

brok_talent = (
    profiles.groupby("Current_Brokerage")
    .agg(Agents=("Agent", "count"), Volume=("Total_Volume", "sum"))
    .reset_index()
    .sort_values("Agents", ascending=False)
    .head(20)
)

fig = px.treemap(
    brok_talent, path=["Current_Brokerage"], values="Agents",
    color="Agents", color_continuous_scale=[[0, "#E8E0D5"], [1, SIRC_NAVY]],
)
fig.update_layout(height=420)
apply_plotly_theme(fig, "Agent Count by Competing Brokerage")
st.plotly_chart(fig, use_container_width=True)
