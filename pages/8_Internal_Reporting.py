"""
Internal Company Reporting Dashboard
Reads the Managing Broker monthly XLSX from Google Drive and displays:
  • Brokerage P&L scorecard (combined, Vancouver, West Vancouver)
  • Monthly actual vs budget time-series charts
  • Agent GCI tracker (budget vs actual vs pending)
  • Agent ranking (net of office)
  • Commission cutting report
  • Expense receivables aging
"""
import io
import os
import base64

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from utils.mb_report_loader import load_mb_report
from utils.styles import (
    apply_plotly_theme, header, section,
    SIRC_CSS, SIRC_NAVY, SIRC_GOLD, SIRC_CREAM,
)

st.set_page_config(page_title="Internal Reporting | SIRC", layout="wide")
header("Internal Reporting", "Managing Broker Dashboard — Vancouver & West Vancouver")

MB_REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "mb_report.xlsx"
)

# ── Load report ────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Loading Managing Broker report…", ttl=1800)
def get_report(path):
    return load_mb_report(path)


def _pct(val):
    if pd.isna(val) or val == 0:
        return "—"
    return f"{val:.1%}"

def _dollar(val, unit=""):
    if pd.isna(val):
        return "—"
    if unit == "M":
        return f"${val/1e6:.2f}M"
    if unit == "K":
        return f"${val/1e3:.0f}K"
    return f"${val:,.0f}"

def _delta_color(val):
    if pd.isna(val) or val == 0:
        return "#8B7355"
    return "#2E7D32" if val > 0 else "#C62828"


# ── Sidebar: file upload or Drive download ─────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Report Source")

    uploaded = st.file_uploader(
        "Upload Managing Broker XLSX",
        type=["xlsx"],
        help="Upload the monthly Managing Broker Report XLSX",
    )
    if uploaded:
        report_bytes = uploaded.read()
        with open(MB_REPORT_PATH, "wb") as f:
            f.write(report_bytes)
        st.cache_data.clear()
        st.success("Report uploaded and cached.")

    if os.path.exists(MB_REPORT_PATH):
        mtime = os.path.getmtime(MB_REPORT_PATH)
        mdate = pd.Timestamp(mtime, unit="s").strftime("%b %d, %Y %H:%M")
        st.markdown(f"<small style='color:#C9A96E'>Loaded: {mdate}</small>", unsafe_allow_html=True)
    else:
        st.warning("No report found. Upload the XLSX above.")

if not os.path.exists(MB_REPORT_PATH):
    st.info("Upload the Managing Broker XLSX using the sidebar to get started.")
    st.stop()

data = get_report(MB_REPORT_PATH)
sc_sum = data["scorecard_summary"]
report_date = sc_sum["report_date"].iloc[0] if not sc_sum.empty else "—"

# ── Page header with report date ───────────────────────────────────────────
st.markdown(f"""
<div style="background:{SIRC_NAVY};padding:1rem 1.5rem;border-radius:4px;margin-bottom:1.5rem;display:flex;align-items:center;justify-content:space-between">
  <div>
    <p style="color:{SIRC_GOLD};font-size:0.75rem;letter-spacing:0.1em;text-transform:uppercase;margin:0 0 0.2rem 0">Managing Broker Report</p>
    <p style="color:#F7F3EE;font-size:0.85rem;margin:0">Vancouver & West Vancouver — {report_date}</p>
  </div>
  <p style="color:#F7F3EE;font-size:0.75rem;margin:0;opacity:0.7">INTERNAL USE ONLY</p>
</div>
""", unsafe_allow_html=True)

# ── Tab layout ──────────────────────────────────────────────────────────────
tab_scorecard, tab_trend, tab_gci, tab_ranking, tab_commission, tab_aging = st.tabs([
    "📊 Scorecard",
    "📈 Monthly Trends",
    "🎯 Agent GCI Tracker",
    "🏆 Agent Ranking",
    "💰 Commission Report",
    "⚠️ Aging Receivables",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — SCORECARD
# ════════════════════════════════════════════════════════════════════════════
with tab_scorecard:
    section("Monthly Scorecard — Combined Vancouver & West Van")

    def get_metric(df, name):
        row = df[df["metric"].str.contains(name, case=False, na=False)]
        return row.iloc[0] if not row.empty else None

    def scorecard_kpi(col, label, metric_row, field_actual, field_budget, prefix="$", unit=""):
        if metric_row is None:
            col.metric(label, "—")
            return
        actual = metric_row[field_actual]
        budget = metric_row[field_budget] if field_budget else None
        if pd.isna(actual):
            col.metric(label, "—")
            return
        if unit == "M":
            val_str = f"${actual/1e6:.2f}M"
        elif unit == "int":
            val_str = f"{int(actual):,}"
        elif unit == "pct":
            val_str = f"{actual:.1%}"
        else:
            val_str = f"${actual:,.0f}"
        delta_str = None
        if budget and not pd.isna(budget) and budget != 0:
            diff_pct = (actual - budget) / abs(budget)
            delta_str = f"{diff_pct:+.1%} vs budget"
        col.metric(label, val_str, delta_str)

    office_choice = st.radio("Office", ["Combined", "Vancouver", "West Vancouver"], horizontal=True)
    sc = {"Combined": sc_sum, "Vancouver": data["scorecard_van"], "West Vancouver": data["scorecard_westvan"]}[office_choice]

    k1, k2, k3, k4, k5 = st.columns(5)
    scorecard_kpi(k1, "Sides (Month)", get_metric(sc, "^Sides$"), "month_actual", "month_budget", unit="int")
    scorecard_kpi(k2, "Volume (Month)", get_metric(sc, "^Volume$"), "month_actual", "month_budget", unit="M")
    scorecard_kpi(k3, "GCI (Month)", get_metric(sc, "^GCI$"), "month_actual", "month_budget", unit="M")
    scorecard_kpi(k4, "Agent Count", get_metric(sc, "Agent Count"), "month_actual", "month_budget", unit="int")
    scorecard_kpi(k5, "Avg Sale Price", get_metric(sc, "ASP"), "month_actual", "month_budget", unit="M")

    k6, k7, k8, k9, k10 = st.columns(5)
    scorecard_kpi(k6, "Gross Profit", get_metric(sc, "^GP$"), "month_actual", "month_budget", unit="M")
    gp_row = get_metric(sc, r"GP \(%\)|GP%")
    if gp_row is not None:
        k7.metric("GP %", _pct(gp_row["month_actual"]))
    ebitda_row = get_metric(sc, "EBITDA")
    if ebitda_row is not None:
        actual_ebitda = ebitda_row["month_actual"]
        color = "#2E7D32" if (actual_ebitda or 0) >= 0 else "#C62828"
        k8.metric("Brokerage EBITDA", _dollar(actual_ebitda))
    scorecard_kpi(k9, "YTD Volume", get_metric(sc, "^Volume$"), "ytd_actual", None, unit="M")
    scorecard_kpi(k10, "YTD GCI", get_metric(sc, "^GCI$"), "ytd_actual", None, unit="M")

    # P&L waterfall table
    section("P&L Detail — Month vs Budget vs Prior Year")
    PL_METRICS = [
        "Sides", "Volume", "ASP", "Agent Count", "GCI", "GCI %", "GP", "GP (%)",
        "Equipment Rental", "Rent & Occupancy", "Insurance", "Selling",
        "Franchise fees", "Labour", "Bank charges", "Communication",
        "Travel", "Food and entertainment", "Office Expenses",
        "Professional Fees - Legal", "Professional Fees - Marketing",
        "Managment fees", "Total Opex", "Brokerage EBITDA",
    ]
    rows_out = []
    for _, r in sc.iterrows():
        rows_out.append({
            "Metric": r["metric"],
            "Month Actual": _dollar(r["month_actual"]) if "Volume" in r["metric"] or "GCI" in r["metric"] or "EBITDA" in r["metric"] or "GP" in r["metric"] or "Sides" not in r["metric"] else f"{int(r['month_actual']):,}" if not pd.isna(r['month_actual']) else "—",
            "Month Budget": _dollar(r["month_budget"]) if not pd.isna(r["month_budget"]) else "—",
            "vs Budget": f"{r['month_vs_budget_pct']:+.1%}" if not pd.isna(r.get("month_vs_budget_pct")) else "—",
            "Prior Year": _dollar(r["month_py_actual"]) if not pd.isna(r["month_py_actual"]) else "—",
            "vs PY": f"{r['month_vs_py_pct']:+.1%}" if not pd.isna(r.get("month_vs_py_pct")) else "—",
            "YTD Actual": _dollar(r["ytd_actual"]) if not pd.isna(r["ytd_actual"]) else "—",
            "FYF": _dollar(r["fyf_actual"]) if not pd.isna(r["fyf_actual"]) else "—",
        })
    pl_df = pd.DataFrame(rows_out)
    st.dataframe(pl_df, hide_index=True, use_container_width=True, height=600)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — MONTHLY TRENDS
# ════════════════════════════════════════════════════════════════════════════
with tab_trend:
    section("Monthly Trends — Actual vs Budget")

    trend_office = st.radio("Office", ["Vancouver", "West Vancouver"], horizontal=True, key="trend_office")
    if trend_office == "Vancouver":
        actual_25 = data["actual_2025_van"]
        actual_26 = data["actual_2026_van"]
        budget_26 = data["budget_2026_van"]
    else:
        actual_25 = data["actual_2025_westvan"]
        actual_26 = data["actual_2026_westvan"]
        budget_26 = data["budget_2026_westvan"]

    metric_opts = actual_26["metric"].tolist()
    sel_metric = st.selectbox("Metric", metric_opts, index=metric_opts.index("Volume") if "Volume" in metric_opts else 0)

    def get_monthly_series(df, metric):
        row = df[df["metric"] == metric]
        if row.empty:
            return pd.Series(dtype=float)
        r = row.iloc[0]
        month_cols = [c for c in df.columns if c != "metric" and c != "Total"]
        return pd.Series({c: r[c] for c in month_cols})

    s25 = get_monthly_series(actual_25, sel_metric)
    s26_act = get_monthly_series(actual_26, sel_metric)
    s26_bud = get_monthly_series(budget_26, sel_metric)

    fig = go.Figure()
    if not s25.empty:
        fig.add_trace(go.Scatter(x=s25.index, y=s25.values, name="2025 Actual",
                                  line=dict(color="#8B7355", dash="dot"), mode="lines+markers"))
    if not s26_bud.empty:
        fig.add_trace(go.Scatter(x=s26_bud.index, y=s26_bud.values, name="2026 Budget",
                                  line=dict(color=SIRC_GOLD, dash="dash"), mode="lines"))
    if not s26_act.empty:
        act_vals = s26_act.dropna()
        act_vals = act_vals[act_vals != 0]
        fig.add_trace(go.Bar(x=act_vals.index, y=act_vals.values, name="2026 Actual",
                              marker_color=SIRC_NAVY, opacity=0.85))

    fig.update_layout(height=380, xaxis_title="Month", yaxis_tickformat="$,.0f",
                      legend=dict(orientation="h", y=1.1))
    apply_plotly_theme(fig, f"{sel_metric} — {trend_office} Monthly Trend")
    st.plotly_chart(fig, use_container_width=True)

    # Show full year table
    with st.expander("Full year data table"):
        tbl = pd.DataFrame({
            "Month": s26_act.index,
            "2025 Actual": s25.reindex(s26_act.index).values,
            "2026 Budget": s26_bud.reindex(s26_act.index).values,
            "2026 Actual": s26_act.values,
        })
        tbl["vs Budget"] = ((tbl["2026 Actual"] - tbl["2026 Budget"]) / tbl["2026 Budget"].abs()).map(
            lambda v: f"{v:+.1%}" if pd.notna(v) and v != 0 else "—"
        )
        tbl["vs 2025"] = ((tbl["2026 Actual"] - tbl["2025 Actual"]) / tbl["2025 Actual"].abs()).map(
            lambda v: f"{v:+.1%}" if pd.notna(v) and v != 0 else "—"
        )
        for c in ["2025 Actual", "2026 Budget", "2026 Actual"]:
            tbl[c] = tbl[c].apply(lambda v: f"${v:,.0f}" if pd.notna(v) and v != 0 else "—")
        st.dataframe(tbl, hide_index=True, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — AGENT GCI TRACKER
# ════════════════════════════════════════════════════════════════════════════
with tab_gci:
    section("Agent GCI — Budget vs Actual vs Pending")

    gci = data["agent_gci"].copy()
    gci = gci[gci["agent"].notna() & (gci["agent"] != "")].copy()
    gci["attainment"] = (gci["actual_gci_ytd"] / gci["budget_gci_ytd"]).clip(0, 5)
    gci["attainment_pct"] = gci["attainment"].apply(_pct)
    gci["projected_attainment"] = (gci["actual_plus_pending"] / gci["budget_gci_annual"]).clip(0, 5)
    gci = gci.sort_values("actual_gci_ytd", ascending=False).reset_index(drop=True)

    # Summary KPIs
    k1, k2, k3, k4 = st.columns(4)
    on_track = gci[gci["attainment"] >= 1.0]
    behind = gci[gci["attainment"] < 1.0]
    k1.metric("Agents On/Above Target", f"{len(on_track)}")
    k2.metric("Agents Behind Target", f"{len(behind)}")
    k3.metric("Total Actual GCI (YTD)", _dollar(gci["actual_gci_ytd"].sum(), "M"))
    k4.metric("Total GCI incl. Pending", _dollar(gci["actual_plus_pending"].sum(), "M"))

    # Chart — horizontal bar showing actual vs budget
    gci_chart = gci.head(30).copy()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=gci_chart["agent"], x=gci_chart["budget_gci_ytd"],
        name="YTD Budget", orientation="h",
        marker_color="#E8E0D5",
    ))
    fig.add_trace(go.Bar(
        y=gci_chart["agent"], x=gci_chart["actual_gci_ytd"],
        name="YTD Actual", orientation="h",
        marker_color=SIRC_NAVY,
    ))
    fig.add_trace(go.Bar(
        y=gci_chart["agent"], x=gci_chart["pending_gci"].fillna(0),
        name="Pending GCI", orientation="h",
        marker_color=SIRC_GOLD, opacity=0.7,
    ))
    fig.update_layout(barmode="overlay", height=max(400, len(gci_chart) * 22),
                      xaxis_tickformat="$,.0f", yaxis_autorange="reversed")
    apply_plotly_theme(fig, "Agent GCI — YTD Actual vs Budget (top 30)")
    st.plotly_chart(fig, use_container_width=True)

    section("Full Agent GCI Table")
    gci_disp = gci[[
        "agent", "status_group", "budget_gci_annual", "budget_gci_ytd",
        "actual_gci_ytd", "variance_ytd", "pending_gci", "actual_plus_pending", "attainment_pct",
    ]].copy()
    for c in ["budget_gci_annual", "budget_gci_ytd", "actual_gci_ytd",
              "variance_ytd", "pending_gci", "actual_plus_pending"]:
        gci_disp[c] = gci_disp[c].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    st.dataframe(gci_disp.rename(columns={
        "agent": "Agent", "status_group": "Status",
        "budget_gci_annual": "Annual Budget", "budget_gci_ytd": "YTD Budget",
        "actual_gci_ytd": "YTD Actual", "variance_ytd": "Variance",
        "pending_gci": "Pending GCI", "actual_plus_pending": "Actual + Pending",
        "attainment_pct": "YTD Attainment",
    }), hide_index=True, use_container_width=True, height=500)


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — AGENT RANKING
# ════════════════════════════════════════════════════════════════════════════
with tab_ranking:
    section("Agent Ranking — Net of Office (YTD)")

    ranking = data["agent_ranking"].copy()
    ranking = ranking[ranking["agent_name"].notna()].sort_values("rank").reset_index(drop=True)

    k1, k2, k3 = st.columns(3)
    k1.metric("Agents Ranked", f"{len(ranking)}")
    k2.metric("Total YTD Volume", _dollar(ranking["sales_volume"].sum(), "M"))
    k3.metric("Total Commission", _dollar(ranking["commission"].sum(), "M"))

    # Treemap of volume by agent
    fig = px.treemap(
        ranking.head(30), path=["agent_name"], values="sales_volume",
        color="commission",
        color_continuous_scale=[[0, SIRC_CREAM], [1, SIRC_NAVY]],
        hover_data={"ends": True, "net_office": True},
    )
    fig.update_layout(height=380)
    apply_plotly_theme(fig, "Agent Volume Share (top 30)")
    st.plotly_chart(fig, use_container_width=True)

    section("Full Rankings Table")
    rank_disp = ranking.copy()
    for c in ["sales_volume", "commission", "net_office"]:
        rank_disp[c] = rank_disp[c].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    rank_disp["ends"] = rank_disp["ends"].apply(lambda v: f"{v:.1f}" if pd.notna(v) else "—")
    rank_disp["pct"] = rank_disp["pct"].apply(_pct)
    rank_disp["cum_pct"] = rank_disp["cum_pct"].apply(_pct)
    st.dataframe(rank_disp.rename(columns={
        "rank": "Rank", "agent_code": "Code", "agent_name": "Agent",
        "ends": "Ends", "sales_volume": "Volume", "commission": "Commission",
        "net_office": "Net Office", "pct": "% Share", "cum_pct": "Cumulative %",
    }), hide_index=True, use_container_width=True, height=500)


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — COMMISSION CUTTING REPORT
# ════════════════════════════════════════════════════════════════════════════
with tab_commission:
    section("Commission Cutting Report — Month")

    cc = data["commission_cutting"].copy()
    cc = cc[cc["agent_name"].notna()].sort_values("combined_rank").reset_index(drop=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Active Agents", f"{len(cc)}")
    k2.metric("Total Volume", _dollar(cc["combined_volume"].sum(), "M"))
    k3.metric("Total Commission", _dollar(cc["combined_commission"].sum()))
    avg_pct = cc["combined_avg_pct"].mean()
    k4.metric("Avg Commission %", _pct(avg_pct / 100) if pd.notna(avg_pct) else "—")

    # Commission % scatter
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cc["combined_volume"],
        y=cc["combined_avg_pct"],
        mode="markers+text",
        text=cc["agent_name"].str.split(",").str[0],
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(
            size=cc["combined_ends"].fillna(0) * 8 + 8,
            color=cc["combined_commission"],
            colorscale=[[0, SIRC_CREAM], [1, SIRC_NAVY]],
            showscale=True,
            colorbar=dict(title="Commission $"),
        ),
        hovertemplate="<b>%{text}</b><br>Volume: $%{x:,.0f}<br>Avg Comm%: %{y:.2f}%<extra></extra>",
    ))
    fig.update_layout(height=420, xaxis_title="Volume ($)", yaxis_title="Avg Commission %",
                      xaxis_tickformat="$,.0f")
    apply_plotly_theme(fig, "Commission % vs Volume (bubble size = ends)")
    st.plotly_chart(fig, use_container_width=True)

    section("Detail Table")
    cc_disp = cc.copy()
    for c in ["combined_volume", "combined_commission", "listing_volume",
              "listing_commission", "selling_volume", "selling_commission", "comm_lost"]:
        cc_disp[c] = cc_disp[c].apply(lambda v: f"${v:,.0f}" if pd.notna(v) and v != 0 else "—")
    for c in ["combined_avg_pct", "listing_avg_pct", "selling_avg_pct"]:
        cc_disp[c] = cc_disp[c].apply(lambda v: f"{v:.2f}%" if pd.notna(v) and v != 0 else "—")

    st.dataframe(cc_disp[[
        "combined_rank", "agent_name", "combined_volume", "combined_ends",
        "combined_commission", "combined_avg_pct",
        "listing_commission", "listing_avg_pct",
        "selling_commission", "selling_avg_pct",
        "comm_lost",
    ]].rename(columns={
        "combined_rank": "Rank", "agent_name": "Agent",
        "combined_volume": "Volume", "combined_ends": "Ends",
        "combined_commission": "Commission", "combined_avg_pct": "Avg %",
        "listing_commission": "List Commission", "listing_avg_pct": "List %",
        "selling_commission": "Sell Commission", "selling_avg_pct": "Sell %",
        "comm_lost": "Comm Lost",
    }), hide_index=True, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — AGING RECEIVABLES
# ════════════════════════════════════════════════════════════════════════════
with tab_aging:
    section("Agent Expense Receivables Aging")

    aging = data["agent_aging"].copy()
    aging = aging[aging["agent_name"].notna()].copy()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Outstanding", _dollar(aging["total"].sum()))
    k2.metric("Current (0–30 days)", _dollar(aging["current"].sum()))
    overdue = aging[["aging_31_60", "aging_61_90", "aging_91_120", "over_120"]].sum().sum()
    k3.metric("Overdue (31+ days)", _dollar(overdue))
    seriously_overdue = aging["over_120"].sum()
    k4.metric("Over 120 Days", _dollar(seriously_overdue))

    # Stacked bar by agent (top 20 by total)
    top_aging = aging.sort_values("total", ascending=False).head(20)
    fig = go.Figure()
    buckets = [
        ("Current", "current", "#C8E6C9"),
        ("31–60 days", "aging_31_60", SIRC_GOLD),
        ("61–90 days", "aging_61_90", "#FF9800"),
        ("91–120 days", "aging_91_120", "#F44336"),
        ("Over 120 days", "over_120", "#B71C1C"),
    ]
    for label, col, color in buckets:
        fig.add_trace(go.Bar(
            y=top_aging["agent_name"],
            x=top_aging[col].fillna(0),
            name=label,
            orientation="h",
            marker_color=color,
        ))
    fig.update_layout(barmode="stack", height=max(350, len(top_aging) * 24),
                      xaxis_tickformat="$,.0f", yaxis_autorange="reversed")
    apply_plotly_theme(fig, "Receivables Aging by Agent (top 20)")
    st.plotly_chart(fig, use_container_width=True)

    section("Aging Detail Table")
    # Highlight rows with over-120 balances
    aging_disp = aging.copy()
    for c in ["total", "current", "aging_31_60", "aging_61_90", "aging_91_120", "over_120"]:
        aging_disp[c] = aging_disp[c].apply(lambda v: f"${v:,.2f}" if pd.notna(v) and v != 0 else "—")

    st.dataframe(aging_disp[[
        "agent_name", "office", "total", "current",
        "aging_31_60", "aging_61_90", "aging_91_120", "over_120",
    ]].rename(columns={
        "agent_name": "Agent", "office": "Office", "total": "Total",
        "current": "Current", "aging_31_60": "31–60", "aging_61_90": "61–90",
        "aging_91_120": "91–120", "over_120": "Over 120",
    }).sort_values("Total", ascending=False),
    hide_index=True, use_container_width=True)

    # Flag seriously overdue
    serious = aging[aging["over_120"] > 0].sort_values("over_120", ascending=False)
    if not serious.empty:
        st.markdown(f"""
<div style="background:#FFEBEE;border-left:4px solid #C62828;padding:0.8rem 1rem;border-radius:2px;margin-top:1rem">
<strong style="color:#C62828">⚠ {len(serious)} agent{'s' if len(serious)!=1 else ''} with balances over 120 days</strong><br>
<small>{', '.join(serious['agent_name'].tolist())}</small>
</div>
""", unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='color:#8B7355;font-size:0.7rem;text-align:center'>"
    "Internal use only — Sotheby's International Realty Canada. Do not distribute."
    "</p>",
    unsafe_allow_html=True,
)
