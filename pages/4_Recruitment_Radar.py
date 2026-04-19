import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils.data_loader import load_data
from utils.styles import header, section, apply_plotly_theme, SIRC_CSS, SIRC_NAVY, SIRC_GOLD

st.set_page_config(page_title="Recruitment Radar | SIRC", layout="wide")
header("Recruitment Radar", "Talent Intelligence & Competitor Agent Research")

df = load_data()
if df.empty:
    st.stop()

# Exclude SIRC agents from this view
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

    min_units = st.number_input("Min. Units (listing side)", min_value=1, value=3)

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

# ── Build agent profiles ───────────────────────────────────────────────────
@st.cache_data(ttl=900)
def build_agent_profiles(listing_hash, buying_hash):
    agents_set = set(fl["listing_agent"].dropna().unique()) | set(fb["buying_agent"].dropna().unique())
    rows = []
    for agent in agents_set:
        al = fl[fl["listing_agent"] == agent]
        ab = fb[fb["buying_agent"] == agent]
        list_units = len(al)
        buy_units = len(ab)
        if list_units < min_units and buy_units < 1:
            continue
        total_vol = al["sold_price"].sum() + ab["sold_price"].sum()
        avg_price = pd.concat([al["sold_price"], ab["sold_price"]]).mean()
        avg_dom = al["days_on_market"].mean()
        lsr = al["list_to_sale_ratio"].mean()
        office = al["listing_office"].mode().iloc[0] if len(al) > 0 else (
            ab["buying_office"].mode().iloc[0] if len(ab) > 0 else "Unknown"
        )
        cities_active = pd.concat([al["city"], ab["city"]]).value_counts().head(3).index.tolist()
        top_areas = pd.concat([al["sub_area"], ab["sub_area"]]).value_counts().head(3).index.tolist()
        price_min = pd.concat([al["sold_price"], ab["sold_price"]]).min()
        price_max = pd.concat([al["sold_price"], ab["sold_price"]]).max()
        rows.append({
            "Agent": agent,
            "Current Brokerage": office,
            "List Units": list_units,
            "Buy Units": buy_units,
            "Total Units": list_units + buy_units,
            "Total Volume": total_vol,
            "Avg Sale Price": avg_price,
            "Avg DOM": avg_dom,
            "L/S Ratio": lsr,
            "Price Min": price_min,
            "Price Max": price_max,
            "Top Cities": ", ".join(cities_active),
            "Top Areas": ", ".join(top_areas),
        })
    return pd.DataFrame(rows).sort_values("Total Volume", ascending=False)

profiles = build_agent_profiles(hash(str(fl.shape)), hash(str(fb.shape)))

# ── KPIs ───────────────────────────────────────────────────────────────────
section("Talent Pool Overview")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Agents Identified", f"{len(profiles):,}")
k2.metric("Brokerages Represented", f"{profiles['Current Brokerage'].nunique():,}")
k3.metric("Avg Volume per Agent", f"${profiles['Total Volume'].mean() / 1e6:.2f}M" if len(profiles) else "—")
k4.metric("Top Agent Volume", f"${profiles['Total Volume'].max() / 1e6:.2f}M" if len(profiles) else "—")

# ── Top targets ────────────────────────────────────────────────────────────
section("Top Recruitment Targets")

tab1, tab2, tab3 = st.tabs(["By Volume", "By Units", "By Avg Price (Luxury)"])

def fmt_profiles(p):
    p = p.copy()
    p["Total Volume"] = p["Total Volume"].apply(lambda v: f"${v / 1e6:.2f}M")
    p["Avg Sale Price"] = p["Avg Sale Price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    p["Price Min"] = p["Price Min"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    p["Price Max"] = p["Price Max"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    p["Avg DOM"] = p["Avg DOM"].apply(lambda v: f"{v:.0f}" if pd.notna(v) else "—")
    p["L/S Ratio"] = p["L/S Ratio"].apply(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
    return p

with tab1:
    t = fmt_profiles(profiles.head(50).reset_index(drop=True))
    t.insert(0, "Rank", range(1, len(t) + 1))
    st.dataframe(t, hide_index=True, use_container_width=True)

with tab2:
    t = fmt_profiles(profiles.sort_values("Total Units", ascending=False).head(50).reset_index(drop=True))
    t.insert(0, "Rank", range(1, len(t) + 1))
    st.dataframe(t, hide_index=True, use_container_width=True)

with tab3:
    luxury = profiles[profiles["Avg Sale Price"] > 2_000_000].sort_values("Total Volume", ascending=False)
    t = fmt_profiles(luxury.head(50).reset_index(drop=True))
    t.insert(0, "Rank", range(1, len(t) + 1))
    st.dataframe(t, hide_index=True, use_container_width=True)

# ── Agent spotlight ────────────────────────────────────────────────────────
section("Agent Deep Dive")

if len(profiles) > 0:
    sel_recruit = st.selectbox("Select an Agent to Investigate", profiles["Agent"].tolist())
    agent_row = profiles[profiles["Agent"] == sel_recruit].iloc[0]

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Current Brokerage", agent_row["Current Brokerage"])
    col_b.metric("Total Volume", f"${agent_row['Total Volume'] / 1e6:.2f}M")
    col_c.metric("Units (L+B)", f"{int(agent_row['List Units'])} + {int(agent_row['Buy Units'])}")
    col_d.metric("Avg Sale Price", f"${agent_row['Avg Sale Price']:,.0f}" if pd.notna(agent_row["Avg Sale Price"]) else "—")

    st.markdown(f"""
    **Active Markets:** {agent_row['Top Cities']}
    **Top Neighbourhoods:** {agent_row['Top Areas']}
    **Price Range:** {f"${agent_row['Price Min']:,.0f}" if pd.notna(agent_row['Price Min']) else '—'} — {f"${agent_row['Price Max']:,.0f}" if pd.notna(agent_row['Price Max']) else '—'}
    """)

    # Transaction history
    agent_txns = pd.concat([
        fl[fl["listing_agent"] == sel_recruit][["mls_number", "address", "city", "sold_price", "sold_date", "days_on_market", "list_to_sale_ratio", "listing_office"]].assign(Role="Listing"),
        fb[fb["buying_agent"] == sel_recruit][["mls_number", "address", "city", "sold_price", "sold_date", "days_on_market", "list_to_sale_ratio", "buying_office"]].rename(columns={"buying_office": "listing_office"}).assign(Role="Buying"),
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
    profiles.groupby("Current Brokerage")
    .agg(
        Agents=("Agent", "count"),
        Total_Volume=("Total Volume", "sum") if "Total Volume" in profiles.columns else ("Agent", "count"),
    )
    .reset_index()
    .sort_values("Agents", ascending=False)
    .head(20)
)

fig = px.treemap(
    brok_talent, path=["Current Brokerage"], values="Agents",
    color="Agents", color_continuous_scale=[[0, "#E8E0D5"], [1, SIRC_NAVY]],
    title="Agent Count by Competing Brokerage"
)
fig.update_layout(height=420)
apply_plotly_theme(fig)
st.plotly_chart(fig, use_container_width=True)
