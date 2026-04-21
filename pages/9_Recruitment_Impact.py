"""
Recruitment Impact Analyser
Combines an agent's MLS transaction history with SIRC's internal financials
to project the P&L impact of recruiting them.
"""
import os

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data
from utils.styles import (
    apply_plotly_theme, header, section,
    SIRC_CSS, SIRC_NAVY, SIRC_GOLD, SIRC_CREAM,
)

header("Recruitment Impact Analyser", "Project the P&L effect of recruiting a target agent")

MB_REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "mb_report.xlsx"
)
INTERNAL_FOLDER_ID = "19Zh42MU7WHSjglsapRjr7SXcofArqn84"


def _get_api_key():
    try:
        return st.secrets["google_drive"]["api_key"]
    except Exception:
        return ""


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_mb_from_drive(folder_id, api_key):
    if not api_key:
        return None
    try:
        import requests as _req
        params = {
            "q": (
                f"'{folder_id}' in parents"
                " and mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'"
                " and trashed=false"
            ),
            "fields": "files(id,modifiedTime)",
            "orderBy": "modifiedTime desc",
            "pageSize": 5,
            "key": api_key,
        }
        r = _req.get("https://www.googleapis.com/drive/v3/files", params=params, timeout=20)
        r.raise_for_status()
        files = r.json().get("files", [])
        if not files:
            return None
        dl = _req.get(
            f"https://www.googleapis.com/drive/v3/files/{files[0]['id']}?alt=media&key={api_key}",
            timeout=120,
        )
        dl.raise_for_status()
        return dl.content
    except Exception:
        return None


# Auto-fetch MB report from Drive if not already present
if not os.path.exists(MB_REPORT_PATH):
    _raw = _fetch_mb_from_drive(INTERNAL_FOLDER_ID, _get_api_key())
    if _raw:
        os.makedirs(os.path.dirname(MB_REPORT_PATH), exist_ok=True)
        with open(MB_REPORT_PATH, "wb") as _f:
            _f.write(_raw)

# ── Load market data ────────────────────────────────────────────────────────
df = load_data()
if df.empty:
    st.stop()

# ── Load internal benchmarks from MB report if available ───────────────────
mb_loaded = os.path.exists(MB_REPORT_PATH)
brokerage_gci_pct   = 0.025   # default: 2.5% of volume → GCI
brokerage_gp_pct    = 0.10    # default: 10% of GCI stays as GP
avg_agent_gci       = 191_707  # default annual budget GCI per agent
opex_per_agent      = 35_000   # default incremental annual OpEx per new agent

if mb_loaded:
    try:
        from utils.mb_report_loader import load_mb_report
        mb = load_mb_report(MB_REPORT_PATH)
        sc = mb["scorecard_summary"]

        def _sc(name, field):
            row = sc[sc["metric"].str.contains(name, case=False, na=False)]
            return float(row.iloc[0][field]) if not row.empty else None

        _gci_pct = _sc("GCI %", "month_actual")
        _gp_pct  = _sc(r"GP \(%\)", "month_actual")
        if _gci_pct:
            brokerage_gci_pct = _gci_pct
        if _gp_pct:
            brokerage_gp_pct  = _gp_pct

        active_agents = mb["agent_gci"][mb["agent_gci"]["status_group"] == "Active"]
        if not active_agents.empty:
            avg_agent_gci = float(active_agents["budget_gci_annual"].mean())

        # Estimate incremental OpEx from monthly actuals (annualised OpEx / agent count)
        opex_row   = _sc("Total Opex", "ytd_actual")
        agents_row = _sc("Agent Count", "month_actual")
        if opex_row and agents_row and agents_row > 0:
            # YTD is 3 months, annualise and divide by headcount
            opex_per_agent = (opex_row / 3 * 12) / agents_row * 0.15  # ~15% marginal

        mb_status = "✓ Using your actual brokerage financials"
    except Exception:
        mb_status = "⚠ Could not read MB report — using default assumptions"
else:
    mb_status = "ℹ MB report not loaded — using default assumptions. Upload it on the Internal Reporting page."

# ── Build agent index ───────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def build_index(_df):
    listing = (
        _df.groupby("listing_agent")
        .agg(
            List_Units=("mls_number", "count"),
            List_Volume=("sold_price", "sum"),
            Primary_Office=("listing_office", lambda x: x.mode().iloc[0] if len(x) else "Unknown"),
        )
        .reset_index().rename(columns={"listing_agent": "Agent"})
    )
    buying = (
        _df.groupby("buying_agent")
        .agg(Buy_Units=("mls_number", "count"), Buy_Volume=("sold_price", "sum"))
        .reset_index().rename(columns={"buying_agent": "Agent"})
    )
    idx = listing.merge(buying, on="Agent", how="outer").fillna(0)
    idx["Total_Units"]  = idx["List_Units"] + idx["Buy_Units"]
    idx["Total_Volume"] = idx["List_Volume"] + idx["Buy_Volume"]
    idx["Primary_Office"] = idx["Primary_Office"].replace(0, "Unknown")
    return idx[
        (idx["Agent"] != "Unknown") & (idx["Agent"] != "") & (idx["Total_Units"] > 0)
    ].sort_values("Total_Volume", ascending=False).reset_index(drop=True)

agent_index = build_index(df)

# ── Sidebar: agent search + deal parameters ─────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Target Agent")

    search = st.text_input("Search agent name", placeholder="e.g. Smith, Jane...")
    if search and len(search.strip()) >= 2:
        matches = agent_index[agent_index["Agent"].str.lower().str.contains(search.strip().lower(), na=False)]
        if not matches.empty:
            labels = [
                f"{r['Agent']}  —  {r['Primary_Office']}"
                for _, r in matches.head(30).iterrows()
            ]
            chosen = st.selectbox("Select agent", labels)
            selected_agent = chosen.split("  —  ")[0].strip()
        else:
            st.warning("No match found.")
            selected_agent = None
    else:
        st.info("Type at least 2 characters to search.")
        selected_agent = None

    st.markdown("---")
    st.markdown("### Deal Parameters")
    st.markdown(f"<small style='color:#C9A96E'>{mb_status}</small>", unsafe_allow_html=True)

    split_pct = st.slider(
        "Agent split (agent keeps %)",
        min_value=50, max_value=95, value=80, step=5,
        help="The percentage of GCI the agent retains. SIRC keeps the remainder."
    )
    sirc_share = (100 - split_pct) / 100

    assumed_comm_rate = st.slider(
        "Assumed avg commission rate (%)",
        min_value=1.0, max_value=4.0, value=float(round(brokerage_gci_pct * 100, 2)),
        step=0.1,
        help="Applied to the agent's projected volume to estimate gross commission"
    )

    lookback_years = st.selectbox(
        "Volume lookback period",
        [1, 2, 3], index=1,
        help="How many recent years of transactions to base the projection on"
    )

    ramp_pct = st.slider(
        "Year-1 ramp-up factor (%)",
        min_value=50, max_value=100, value=75, step=5,
        help="New agents rarely hit full volume immediately — apply a ramp discount for Year 1"
    )

    signing_bonus = st.number_input(
        "Signing / transition bonus ($)",
        min_value=0, max_value=500_000, value=0, step=5_000,
        help="Any upfront cost to recruit this agent (desk setup, signing bonus, etc.)"
    )

    incremental_opex = st.number_input(
        "Incremental annual OpEx per agent ($)",
        min_value=0, max_value=100_000,
        value=int(round(opex_per_agent / 1000) * 1000),
        step=1_000,
        help="Estimated annual incremental overhead (desk, tech, support) for one new agent"
    )

    st.markdown("---")
    st.markdown("### Projection Horizon")
    years_proj = st.slider("Years to project", 1, 5, 3)

if not selected_agent:
    st.markdown(f"""
<div style="background:{SIRC_NAVY};padding:2rem;border-radius:4px;text-align:center">
  <p style="color:{SIRC_GOLD};font-size:1rem;margin:0">Search for an agent in the sidebar to begin the analysis.</p>
</div>
""", unsafe_allow_html=True)
    st.stop()

# ── Pull agent transaction history ─────────────────────────────────────────
agent_listings = df[df["listing_agent"] == selected_agent].copy()
agent_buying   = df[df["buying_agent"]  == selected_agent].copy()
all_txns = pd.concat([
    agent_listings.assign(Role="Listing"),
    agent_buying.assign(Role="Buying"),
]).dropna(subset=["sold_date"])

idx_row = agent_index[agent_index["Agent"] == selected_agent].iloc[0]
is_sirc = any(k in str(idx_row["Primary_Office"]).lower() for k in ["sotheby","sothebys","sotheby's"])

# Lookback filter
latest_date = all_txns["sold_date"].max()
cutoff = latest_date - pd.DateOffset(years=lookback_years)
recent = all_txns[all_txns["sold_date"] >= cutoff]

# Annual metrics
annual_volume = recent["sold_price"].sum() / lookback_years
annual_sides  = len(recent) / lookback_years
avg_price     = recent["sold_price"].mean() if not recent.empty else 0

# Projected gross commission (before split)
projected_gci_gross = annual_volume * (assumed_comm_rate / 100)
# SIRC's share after split
projected_gci_sirc  = projected_gci_gross * sirc_share
# GP (what stays after office overhead — using brokerage GP% as proxy)
projected_gp        = projected_gci_sirc * brokerage_gp_pct

# ── Agent profile banner ────────────────────────────────────────────────────
badge_label = "SIRC Agent" if is_sirc else "Competitor Agent"
badge_bg    = SIRC_GOLD if is_sirc else "#E8E0D5"
badge_fg    = SIRC_NAVY if is_sirc else "#8B7355"

st.markdown(f"""
<div style="background:{SIRC_NAVY};padding:1.2rem 1.8rem;border-radius:4px;margin-bottom:1.5rem;display:flex;align-items:center;justify-content:space-between">
  <div>
    <p style="color:{SIRC_GOLD};font-family:'Playfair Display',serif;font-size:1.5rem;font-weight:600;margin:0">{selected_agent}</p>
    <p style="color:#F7F3EE;font-size:0.85rem;margin:0.2rem 0 0 0">{idx_row['Primary_Office']}</p>
  </div>
  <div style="background:{badge_bg};color:{badge_fg};font-size:0.65rem;letter-spacing:0.12em;text-transform:uppercase;padding:0.25rem 0.8rem;border-radius:2px;font-weight:600">
    {badge_label}
  </div>
</div>
""", unsafe_allow_html=True)

# ── Section 1: Historical performance ──────────────────────────────────────
section("Historical Performance (Basis for Projection)")

h1, h2, h3, h4, h5 = st.columns(5)
h1.metric("Total Career Volume",    f"${idx_row['Total_Volume']/1e6:.1f}M")
h2.metric("Career Sides",           f"{int(idx_row['Total_Units']):,}")
h3.metric(f"Avg Annual Volume ({lookback_years}yr)", f"${annual_volume/1e6:.2f}M")
h4.metric(f"Avg Annual Sides ({lookback_years}yr)",  f"{annual_sides:.1f}")
h5.metric("Avg Sale Price",         f"${avg_price:,.0f}" if avg_price else "—")

# Year-by-year volume chart
yearly = all_txns.groupby(all_txns["sold_date"].dt.year)["sold_price"].agg(
    Volume="sum", Sides="count"
).reset_index().rename(columns={"sold_date": "Year"})
yearly["Year"] = yearly["Year"].astype(int)

fig = go.Figure()
fig.add_trace(go.Bar(
    x=yearly["Year"], y=yearly["Volume"],
    marker_color=SIRC_NAVY,
    text=yearly["Sides"].apply(lambda s: f"{s} sides"),
    textposition="inside", textfont=dict(color="white", size=10),
    name="Annual Volume",
))
fig.add_hline(
    y=annual_volume, line_dash="dash", line_color=SIRC_GOLD,
    annotation_text=f"  {lookback_years}yr avg: ${annual_volume/1e6:.2f}M",
    annotation_font_color=SIRC_GOLD,
)
fig.update_layout(height=300, xaxis_title="Year", yaxis_tickformat="$,.0f")
apply_plotly_theme(fig, f"{selected_agent} — Annual Volume History")
st.plotly_chart(fig, use_container_width=True)

# ── Section 2: P&L Impact Projection ───────────────────────────────────────
section("Projected P&L Impact — Annual Steady State")

p1, p2, p3, p4, p5 = st.columns(5)
p1.metric("Projected Volume / yr",  f"${annual_volume/1e6:.2f}M", help="Based on lookback average")
p2.metric("Gross Commission",       f"${projected_gci_gross:,.0f}", f"{assumed_comm_rate:.1f}% of volume")
p3.metric(f"GCI to SIRC ({100-split_pct}% share)", f"${projected_gci_sirc:,.0f}", f"Agent keeps {split_pct}%")
p4.metric("Gross Profit to SIRC",   f"${projected_gp:,.0f}", f"{brokerage_gp_pct:.1%} GP margin")
ebitda_impact = projected_gp - incremental_opex
p5.metric("Net EBITDA Impact / yr", f"${ebitda_impact:,.0f}",
          f"After ${incremental_opex:,} OpEx",
          delta_color="normal" if ebitda_impact >= 0 else "inverse")

# Vs average SIRC agent
section("Comparison vs Current SIRC Agent Average")
avg_gci_sirc_share = avg_agent_gci * sirc_share * brokerage_gp_pct
avg_ebitda = avg_gci_sirc_share - incremental_opex

c1, c2, c3 = st.columns(3)
c1.metric("This Agent — Projected GCI to SIRC", f"${projected_gci_sirc:,.0f}")
c1.metric("Avg SIRC Agent — GCI to SIRC (budget)", f"${avg_agent_gci * sirc_share:,.0f}")
c2.metric("This Agent — Projected GP", f"${projected_gp:,.0f}")
c2.metric("Avg SIRC Agent — GP", f"${avg_gci_sirc_share:,.0f}")
c3.metric("This Agent — Net EBITDA", f"${ebitda_impact:,.0f}")
c3.metric("Avg SIRC Agent — Net EBITDA", f"${avg_ebitda:,.0f}")

# ── Section 3: Multi-year projection ───────────────────────────────────────
section(f"{years_proj}-Year Financial Projection")

proj_rows = []
cumulative_ebitda = 0
for yr in range(1, years_proj + 1):
    ramp = (ramp_pct / 100) if yr == 1 else 1.0
    vol      = annual_volume * ramp
    gci_gross= vol * (assumed_comm_rate / 100)
    gci_sirc = gci_gross * sirc_share
    gp       = gci_sirc * brokerage_gp_pct
    opex     = incremental_opex
    bonus    = signing_bonus if yr == 1 else 0
    ebitda   = gp - opex - bonus
    cumulative_ebitda += ebitda
    proj_rows.append({
        "Year": f"Year {yr}",
        "Volume": vol,
        "Gross Commission": gci_gross,
        "GCI to SIRC": gci_sirc,
        "Gross Profit": gp,
        "OpEx": opex,
        "Signing Bonus": bonus,
        "Net EBITDA": ebitda,
        "Cumulative EBITDA": cumulative_ebitda,
    })

proj = pd.DataFrame(proj_rows)

# Waterfall chart for Year 1
year1 = proj.iloc[0]
wf_labels  = ["Gross Commission", f"Agent Split ({split_pct}%)", "After-Split GCI",
               "GP Margin", "Gross Profit", "OpEx", "Signing Bonus", "Net EBITDA"]
wf_values  = [
    year1["Gross Commission"],
    -(year1["Gross Commission"] - year1["GCI to SIRC"]),
    0,
    -(year1["GCI to SIRC"] - year1["Gross Profit"]),
    0,
    -year1["OpEx"],
    -year1["Signing Bonus"],
    0,
]
wf_measure = ["absolute", "relative", "total", "relative", "total", "relative", "relative", "total"]

fig = go.Figure(go.Waterfall(
    name="Year 1",
    orientation="v",
    measure=wf_measure,
    x=wf_labels,
    y=wf_values,
    textposition="outside",
    text=[f"${abs(v):,.0f}" for v in wf_values],
    connector=dict(line=dict(color="#E8E0D5")),
    increasing=dict(marker_color=SIRC_NAVY),
    decreasing=dict(marker_color="#C62828"),
    totals=dict(marker_color=SIRC_GOLD),
))
fig.update_layout(height=380, yaxis_tickformat="$,.0f", showlegend=False)
apply_plotly_theme(fig, "Year 1 — P&L Waterfall")
st.plotly_chart(fig, use_container_width=True)

# Multi-year bar chart
fig2 = go.Figure()
fig2.add_trace(go.Bar(
    x=proj["Year"], y=proj["Gross Profit"],
    name="Gross Profit", marker_color=SIRC_NAVY,
))
fig2.add_trace(go.Bar(
    x=proj["Year"], y=-(proj["OpEx"] + proj["Signing Bonus"]),
    name="Costs", marker_color="#C62828",
))
fig2.add_trace(go.Scatter(
    x=proj["Year"], y=proj["Net EBITDA"],
    name="Net EBITDA", mode="lines+markers",
    line=dict(color=SIRC_GOLD, width=3),
    marker=dict(size=10),
))
fig2.add_trace(go.Scatter(
    x=proj["Year"], y=proj["Cumulative EBITDA"],
    name="Cumulative EBITDA", mode="lines+markers",
    line=dict(color="#5A8A9F", width=2, dash="dash"),
    marker=dict(size=8),
))
fig2.update_layout(barmode="relative", height=340,
                   yaxis_tickformat="$,.0f",
                   legend=dict(orientation="h", y=1.12))
apply_plotly_theme(fig2, f"{years_proj}-Year EBITDA Projection")
st.plotly_chart(fig2, use_container_width=True)

# Break-even note
if signing_bonus > 0:
    be_year = None
    for _, r in proj.iterrows():
        if r["Cumulative EBITDA"] >= 0:
            be_year = r["Year"]
            break
    if be_year:
        st.success(f"Break-even on signing bonus reached by **{be_year}** (cumulative EBITDA turns positive).")
    else:
        st.warning(f"Signing bonus of ${signing_bonus:,} not recovered within {years_proj}-year projection at these parameters.")

# ── Section 4: Projection table ─────────────────────────────────────────────
section("Projection Detail Table")
disp = proj.copy()
for c in ["Volume", "Gross Commission", "GCI to SIRC", "Gross Profit",
          "OpEx", "Signing Bonus", "Net EBITDA", "Cumulative EBITDA"]:
    disp[c] = disp[c].apply(lambda v: f"${v:,.0f}")
st.dataframe(disp, hide_index=True, use_container_width=True)

# ── Section 5: Scenario sensitivity ─────────────────────────────────────────
section("Sensitivity Analysis — Net EBITDA by Volume & Split")

vol_range   = [annual_volume * f for f in [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]]
split_range = [70, 75, 80, 85, 90]

sensitivity_rows = []
for v in vol_range:
    row = {"Volume": f"${v/1e6:.1f}M"}
    for sp in split_range:
        sirc_sh = (100 - sp) / 100
        gp = v * (assumed_comm_rate / 100) * sirc_sh * brokerage_gp_pct
        ebitda = gp - incremental_opex
        row[f"{sp}% split"] = f"${ebitda:,.0f}"
    sensitivity_rows.append(row)

st.markdown("*Rows = agent volume scenario · Columns = agent split %*")
st.dataframe(pd.DataFrame(sensitivity_rows), hide_index=True, use_container_width=True)

# ── Section 6: Key assumptions summary ──────────────────────────────────────
section("Assumptions & Notes")
st.markdown(f"""
| Assumption | Value |
|---|---|
| Volume basis | {lookback_years}-year trailing average (${annual_volume/1e6:.2f}M/yr) |
| Commission rate | {assumed_comm_rate:.1f}% of volume |
| Agent split | Agent keeps {split_pct}% · SIRC keeps {100-split_pct}% |
| GP margin on GCI | {brokerage_gp_pct:.1%} ({"from MB report" if mb_loaded else "default estimate"}) |
| Year-1 ramp factor | {ramp_pct}% of steady-state volume |
| Incremental annual OpEx | ${incremental_opex:,}/yr |
| Signing bonus | ${signing_bonus:,} (Year 1 only) |
| Source brokerage data | {"MB Report loaded ✓" if mb_loaded else "Defaults — upload MB report on Internal Reporting page for live figures"} |
""")

st.markdown("---")
st.markdown(
    "<p style='color:#8B7355;font-size:0.7rem;text-align:center'>"
    "For internal planning purposes only. All projections are estimates based on historical MLS data and configurable assumptions.</p>",
    unsafe_allow_html=True,
)
