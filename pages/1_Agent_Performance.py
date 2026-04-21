import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils.data_loader import load_data
from utils.styles import header, section, apply_plotly_theme, SIRC_CSS, SIRC_NAVY, SIRC_GOLD, SIRC_CREAM

header("Agent Performance", "Individual & Team Analysis")

df = load_data()
if df.empty:
    st.stop()

sirc_list = df[df["is_sirc_listing"]]
sirc_buy = df[df["is_sirc_buying"]]

# Build agent universe — combine listing + buying appearances
list_agents = sirc_list["listing_agent"].dropna().unique()
buy_agents = sirc_buy["buying_agent"].dropna().unique()
all_agents = sorted(set(list_agents) | set(buy_agents))

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Filters")

    years = sorted(df["sold_year"].dropna().unique().astype(int), reverse=True)
    sel_years = st.multiselect("Year(s)", years, default=years[:2] if len(years) >= 2 else years)

    view = st.radio("View", ["Individual Agent", "Team Leaderboard"])
    sel_agent = None
    if view == "Individual Agent":
        sel_agent = st.selectbox("Select Agent", all_agents)

# ── Apply year filter ──────────────────────────────────────────────────────
if sel_years:
    df_f = df[df["sold_year"].isin(sel_years)]
else:
    df_f = df.copy()

sirc_list_f = df_f[df_f["is_sirc_listing"]]
sirc_buy_f = df_f[df_f["is_sirc_buying"]]

# ══════════════════════════════════════════════════════════════════════════
# INDIVIDUAL AGENT VIEW
# ══════════════════════════════════════════════════════════════════════════
if view == "Individual Agent" and sel_agent:
    agent_list = sirc_list_f[sirc_list_f["listing_agent"] == sel_agent]
    agent_buy = sirc_buy_f[sirc_buy_f["buying_agent"] == sel_agent]

    list_vol = agent_list["sold_price"].sum()
    buy_vol = agent_buy["sold_price"].sum()
    total_vol = list_vol + buy_vol
    total_units = len(agent_list) + len(agent_buy)
    avg_price = pd.concat([agent_list["sold_price"], agent_buy["sold_price"]]).mean()
    avg_dom = pd.concat([agent_list["days_on_market"], agent_buy["days_on_market"]]).mean()
    lsr = agent_list["list_to_sale_ratio"].mean()

    section(f"Scorecard — {sel_agent}")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Volume", f"${total_vol / 1e6:.2f}M")
    c2.metric("Total Units", str(total_units))
    c3.metric("Listing Units", str(len(agent_list)))
    c4.metric("Buying Units", str(len(agent_buy)))
    c5.metric("Avg Sale Price", f"${avg_price:,.0f}" if pd.notna(avg_price) else "—")
    c6.metric("Avg Days on Mkt", f"{avg_dom:.0f}" if pd.notna(avg_dom) else "—")

    col_a, col_b = st.columns(2)

    with col_a:
        section("Volume by Year")
        yearly = []
        for yr in sorted(df["sold_year"].dropna().unique().astype(int)):
            yl = df[(df["is_sirc_listing"]) & (df["listing_agent"] == sel_agent) & (df["sold_year"] == yr)]
            yb = df[(df["is_sirc_buying"]) & (df["buying_agent"] == sel_agent) & (df["sold_year"] == yr)]
            yearly.append({
                "Year": yr,
                "Listing Volume": yl["sold_price"].sum(),
                "Buying Volume": yb["sold_price"].sum(),
                "Total Units": len(yl) + len(yb),
            })
        yearly_df = pd.DataFrame(yearly)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=yearly_df["Year"], y=yearly_df["Listing Volume"] / 1e6,
                              name="Listing Side", marker_color=SIRC_NAVY))
        fig.add_trace(go.Bar(x=yearly_df["Year"], y=yearly_df["Buying Volume"] / 1e6,
                              name="Buying Side", marker_color=SIRC_GOLD))
        fig.update_layout(barmode="stack", yaxis_title="Volume ($M)", height=350)
        apply_plotly_theme(fig, "Annual Volume")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section("Activity Map — Cities")
        all_agent = pd.concat([
            agent_list[["city", "sold_price"]].assign(role="Listing"),
            agent_buy[["city", "sold_price"]].assign(role="Buying"),
        ])
        city_sum = all_agent.groupby("city")["sold_price"].sum().sort_values(ascending=False).head(10)
        fig2 = px.bar(city_sum.reset_index(), x="sold_price", y="city", orientation="h",
                      labels={"sold_price": "Volume ($)", "city": "City"},
                      color_discrete_sequence=[SIRC_NAVY])
        fig2.update_layout(height=350, yaxis=dict(autorange="reversed"))
        apply_plotly_theme(fig2, "Volume by City")
        st.plotly_chart(fig2, use_container_width=True)

    section("Recent Transactions")
    recent = pd.concat([
        agent_list[["mls_number", "address", "city", "sold_price", "sold_date", "days_on_market", "list_to_sale_ratio"]].assign(Role="Listing"),
        agent_buy[["mls_number", "address", "city", "sold_price", "sold_date", "days_on_market", "list_to_sale_ratio"]].assign(Role="Buying"),
    ]).sort_values("sold_date", ascending=False).head(30)
    recent["sold_price"] = recent["sold_price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    recent["list_to_sale_ratio"] = recent["list_to_sale_ratio"].apply(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
    recent["sold_date"] = recent["sold_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(recent.rename(columns={
        "mls_number": "MLS #", "address": "Address", "city": "City",
        "sold_price": "Sold Price", "sold_date": "Sold Date",
        "days_on_market": "DOM", "list_to_sale_ratio": "L/S Ratio",
    }), hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# TEAM LEADERBOARD VIEW
# ══════════════════════════════════════════════════════════════════════════
else:
    section("Team Leaderboard")

    tab1, tab2, tab3 = st.tabs(["By Total Volume", "By Listing Units", "By Buying Units"])

    def build_leaderboard(listing_df, buying_df):
        rows = []
        for agent in all_agents:
            al = listing_df[listing_df["listing_agent"] == agent]
            ab = buying_df[buying_df["buying_agent"] == agent]
            list_vol = al["sold_price"].sum()
            buy_vol = ab["sold_price"].sum()
            total = list_vol + buy_vol
            units = len(al) + len(ab)
            avg_p = pd.concat([al["sold_price"], ab["sold_price"]]).mean()
            avg_d = pd.concat([al["days_on_market"], ab["days_on_market"]]).mean()
            lsr = al["list_to_sale_ratio"].mean()
            rows.append({
                "Agent": agent,
                "Total Volume": total,
                "Listing Vol": list_vol,
                "Buying Vol": buy_vol,
                "Total Units": units,
                "Listing Units": len(al),
                "Buying Units": len(ab),
                "Avg Sale Price": avg_p,
                "Avg DOM": avg_d,
                "L/S Ratio": lsr,
            })
        result = pd.DataFrame(rows)
        result = result[result["Total Units"] > 0]
        return result

    board = build_leaderboard(sirc_list_f, sirc_buy_f)

    def fmt_board(b):
        b = b.copy()
        b["Total Volume"] = b["Total Volume"].apply(lambda v: f"${v / 1e6:.2f}M")
        b["Listing Vol"] = b["Listing Vol"].apply(lambda v: f"${v / 1e6:.2f}M")
        b["Buying Vol"] = b["Buying Vol"].apply(lambda v: f"${v / 1e6:.2f}M")
        b["Avg Sale Price"] = b["Avg Sale Price"].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
        b["Avg DOM"] = b["Avg DOM"].apply(lambda v: f"{v:.0f}" if pd.notna(v) else "—")
        b["L/S Ratio"] = b["L/S Ratio"].apply(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
        return b

    with tab1:
        t = fmt_board(board.sort_values("Total Volume", ascending=False).reset_index(drop=True))
        t.insert(0, "Rank", range(1, len(t) + 1))
        st.dataframe(t, hide_index=True, use_container_width=True)

    with tab2:
        t = fmt_board(board.sort_values("Listing Units", ascending=False).reset_index(drop=True))
        t.insert(0, "Rank", range(1, len(t) + 1))
        st.dataframe(t, hide_index=True, use_container_width=True)

    with tab3:
        t = fmt_board(board.sort_values("Buying Units", ascending=False).reset_index(drop=True))
        t.insert(0, "Rank", range(1, len(t) + 1))
        st.dataframe(t, hide_index=True, use_container_width=True)

    section("Volume Distribution")
    board_raw = build_leaderboard(sirc_list_f, sirc_buy_f).sort_values("Total Volume", ascending=False).head(20)
    fig = go.Figure(go.Bar(
        x=board_raw["Agent"],
        y=board_raw["Total Volume"] / 1e6,
        marker_color=SIRC_NAVY,
        text=(board_raw["Total Volume"] / 1e6).apply(lambda v: f"${v:.1f}M"),
        textposition="outside",
    ))
    apply_plotly_theme(fig, "Top 20 Agents by Volume")
    fig.update_layout(xaxis_tickangle=-35, yaxis_title="Volume ($M)", height=420)
    st.plotly_chart(fig, use_container_width=True)
