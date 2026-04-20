"""
mb_report_loader.py
====================
Parsers for every sheet in the Managing Broker monthly XLSX report.

Usage
-----
    from utils.mb_report_loader import load_mb_report
    data = load_mb_report("/path/to/mb_report.xlsx")

    # Individual DataFrames
    data["scorecard_summary"]        # Monthly Scorecard-Summary
    data["scorecard_van"]            # Monthly Scorecard-Van
    data["scorecard_westvan"]        # Monthly Scorecard-West Van
    data["actual_2026_van"]          # 2026 Monthly Actual-Van
    data["actual_2026_westvan"]      # 2026 Monthly Actual-West Van
    data["actual_2025_van"]          # 2025 Monthly Actual-Van
    data["actual_2025_westvan"]      # 2025 Monthly Actual-West Van
    data["budget_2026_van"]          # 2026 Monthly Budget-Van
    data["budget_2026_westvan"]      # 2026 Monthly Budget-West Van
    data["agent_gci"]                # Agent GCI Budget v.Actual
    data["agent_aging"]              # Agent Expenses Aging report
    data["agent_ranking"]            # Ranking of Agts-Net of Office
    data["commission_cutting"]       # Commission Cutting Report-Month

Sheet Structures (0-indexed rows/cols)
---------------------------------------
SCORECARD SHEETS  ("Monthly Scorecard-Summary/Van/West Van")
    Shape ~(33–57) x 46
    Row 0   : title "2026 Monthly Scorecard"
    Row 1   : market name
    Row 2   : report date (col 1)
    Row 4   : "Final" label
    Row 6   : section group labels (Month / YTD / Full-Year Forecast …)
    Row 7   : sub-column labels (Actual | Budget | # | % …)
    Row 8   : "Summary" separator
    Row 9.. : metric rows  ← DATA STARTS HERE
    Col 0   : always NaN (spacer)
    Col 1   : metric label (row label)
    Col 2   : NaN spacer
    Col 3   : Month Actual (Mar 2026)
    Col 4   : Month Budget (Mar 2026)
    Col 5   : NaN spacer
    Col 6   : Month Actual vs Budget  (#)
    Col 7   : Month Actual vs Budget  (%)
    Col 8   : NaN spacer
    Col 9   : Month PY Actual (Mar 2025)
    Col 10  : NaN spacer
    Col 11  : Month Actual vs PY  (#)
    Col 12  : Month Actual vs PY  (%)
    Col 13  : NaN spacer
    Col 14  : YTD Actual
    Col 31  : Full-Year Forecast Actual
    Col 32  : Full-Year Forecast Budget
    Col 34  : FYF vs Budget  (#)
    Col 35  : FYF vs Budget  (%)

MONTHLY ACTUAL / BUDGET SHEETS  (4 actual + 2 budget variants)
    Shape (27) x 15
    Row 0,1 : blank
    Row 2   : column headers — col 0-1 NaN; cols 2-13 = month-end dates; col 14 = "Total"
    Row 3   : "Summary" section label (skip)
    Rows 4-26 : metric rows  ← DATA
    Col 0   : always NaN
    Col 1   : metric label
    Cols 2-13 : Jan-Dec values (NaN for future months in actuals)
    Col 14  : YTD/annual total

AGENT GCI BUDGET v. ACTUAL
    Shape (70) x 8
    Rows 0-3 : title block (row 3 col 0 = report date)
    Row 4   : blank
    Row 5   : column headers
    Rows 6-63 : Active agents
    Row 64  : Active Total (skip)
    Rows 65-67 : Inactive agents
    Row 68  : Inactive Total (skip)
    Row 69  : Grand Total (skip)
    Cols: 0=Status, 1=Agent, 2=Budget GCI (Annual), 3=Budget GCI (YTD),
          4=Actual GCI (YTD), 5=Variance (YTD), 6=Pending GCI to Dec 31,
          7=Actual + Pending Total GCI

AGENT EXPENSES AGING REPORT
    Shape (88) x 20
    Row 0   : title; col 11 = "As of" date
    Row 1   : blank
    Row 2   : headers  (col 2=Agent Name, col 3=Agent#, col 5=Terminated*,
                         col 11=Officename, col 13=Total, col 14=Current,
                         col 15=31-60, col 16=61-90, col 17=91-120, col 18=Over 120)
    Rows 3-84 : data rows
    Row 85-87 : blank / totals

RANKING OF AGENTS - NET OF OFFICE
    Shape (67) x 31
    Row 0   : title  (col 5 = heading, col 9 = date range)
    Row 1   : blank
    Row 2   : headers  (col 5=Agents#, col 7=Agent Name, col 8=Rank,
                         col 9=Ends, col 10=Sales_vol, col 11=Commission,
                         col 12=Net office, col 13=pct, col 14=totpct)
    Rows 3-65 : data rows
    Row 66  : totals (no agent name)

COMMISSION CUTTING REPORT - MONTH
    Shape (43) x 25
    Row 0   : "Commission Cutting Report" / date (col 7)
    Row 1   : market name
    Row 2   : section labels (col 5="Combined", col 11="Listing Side", col 17="Selling Side")
    Row 3   : column headers:
               col 0=Agent#, col 1=Agent Name
               --- Combined ---    col 5=Rank, col 6=Volume, col 7=Ends, col 8=Commission, col 10=Avg.%
               --- Listing Side --- col 11=Rank, col 12=Volume, col 13=Ends, col 14=Commission, col 16=Avg.%
               --- Selling Side --- col 17=Rank, col 18=Volume, col 19=Ends, col 20=Commission, col 22=Avg.%
               col 24=comm.lost
    Rows 4-30 : data rows
    Rows 31-41 : blank
    Row 42  : totals (no agent name)
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Dict

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)


# ── internal helper ──────────────────────────────────────────────────────────

def _read(path: str | Path, sheet: str) -> pd.DataFrame:
    """Read a sheet with header=None and openpyxl engine."""
    return pd.read_excel(path, sheet_name=sheet, header=None, engine="openpyxl")


# ════════════════════════════════════════════════════════════════════════════
# SCORECARD SHEETS
# ════════════════════════════════════════════════════════════════════════════

_SCORECARD_COLS = {
    "metric":               1,
    "month_actual":         3,
    "month_budget":         4,
    "month_vs_budget_$":    6,
    "month_vs_budget_pct":  7,
    "month_py_actual":      9,
    "month_vs_py_$":        11,
    "month_vs_py_pct":      12,
    "ytd_actual":           14,
    "fyf_actual":           31,
    "fyf_budget":           32,
    "fyf_vs_budget_$":      34,
    "fyf_vs_budget_pct":    35,
}


def _parse_scorecard(path: str | Path, sheet_name: str) -> pd.DataFrame:
    """
    Parse one of the three Monthly Scorecard sheets.

    skiprows : 0  (read from row 0)
    header   : None
    Data rows start at row index 9 (0-based) for rows where col 1 is not NaN.

    Returns a tidy DataFrame with columns:
        market, report_date, metric, month_actual, month_budget,
        month_vs_budget_$, month_vs_budget_pct,
        month_py_actual, month_vs_py_$, month_vs_py_pct,
        ytd_actual, fyf_actual, fyf_budget,
        fyf_vs_budget_$, fyf_vs_budget_pct
    """
    raw = _read(path, sheet_name)

    market = str(raw.iloc[1, 1]).strip()
    report_date = pd.to_datetime(raw.iloc[2, 1]).date()

    # Metric rows: index 9 onwards, keep only rows where col 1 has a value
    data_mask = raw.iloc[9:, 1].notna()
    data_rows = raw.iloc[9:][data_mask]

    rows = []
    for _, r in data_rows.iterrows():
        row: dict = {"market": market, "report_date": report_date}
        for col_name, col_idx in _SCORECARD_COLS.items():
            row[col_name] = r.iloc[col_idx] if col_idx < len(r) else None
        rows.append(row)

    df = pd.DataFrame(rows)
    df["metric"] = df["metric"].astype(str).str.strip()

    # Coerce all numeric columns
    for c in list(_SCORECARD_COLS.keys())[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


# ════════════════════════════════════════════════════════════════════════════
# MONTHLY ACTUAL / BUDGET SHEETS
# ════════════════════════════════════════════════════════════════════════════

def _parse_monthly(path: str | Path, sheet_name: str) -> pd.DataFrame:
    """
    Parse any of the six Monthly Actual / Budget sheets.

    skiprows : 0  (read from row 0)
    header   : None
    Dates    : row 2, cols 2-13  (month-end timestamps)
    Data     : rows 4-26, col 1 = metric, cols 2-14 = values

    Returns a wide DataFrame:
        metric | 2026-01 | 2026-02 | … | 2026-12 | Total
    """
    raw = _read(path, sheet_name)

    # Build month column names from row 2 (cols 2..13)
    month_cols: list[str] = []
    for val in raw.iloc[2, 2:14]:
        try:
            month_cols.append(pd.to_datetime(val).strftime("%Y-%m"))
        except Exception:
            month_cols.append(str(val))

    col_names = ["metric"] + month_cols + ["Total"]

    # Extract data: rows 4-26, cols [1, 2..14]
    data = raw.iloc[4:27, [1] + list(range(2, 15))].copy()
    data.columns = col_names
    data = data[data["metric"].notna()].copy()
    data["metric"] = data["metric"].astype(str).str.strip()
    data = data.reset_index(drop=True)

    for c in col_names[1:]:
        data[c] = pd.to_numeric(data[c], errors="coerce")

    return data


# ════════════════════════════════════════════════════════════════════════════
# AGENT GCI BUDGET v. ACTUAL
# ════════════════════════════════════════════════════════════════════════════

_SKIP_LABELS = {"Active Total", "Inactive Total", "Grand Total"}


def _parse_agent_gci(path: str | Path) -> pd.DataFrame:
    """
    Parse the 'Agent GCI Budget v.Actual' sheet.

    header row : row 5 (0-based)
    data rows  : 6 .. 69 (skip subtotal rows where col 0 in _SKIP_LABELS)

    Columns returned:
        report_date, status_group, agent,
        budget_gci_annual, budget_gci_ytd, actual_gci_ytd,
        variance_ytd, pending_gci, actual_plus_pending
    """
    raw = _read(path, "Agent GCI Budget v.Actual")
    report_date = pd.to_datetime(raw.iloc[3, 0]).date()

    col_map = {
        "agent":                1,
        "budget_gci_annual":    2,
        "budget_gci_ytd":       3,
        "actual_gci_ytd":       4,
        "variance_ytd":         5,
        "pending_gci":          6,
        "actual_plus_pending":  7,
    }

    rows = []
    current_status = "Unknown"
    for i in range(6, len(raw)):
        r = raw.iloc[i]
        label = r.iloc[0]

        if pd.notna(label):
            lstr = str(label).strip()
            if lstr in _SKIP_LABELS:
                continue
            if lstr in ("Active", "Inactive"):
                current_status = lstr
                # Don't skip — the first agent on this row is valid (col 1 has a name)
                # BUT for the "Active" row the agent col is NaN; data starts row 6.
                # We still need to record the status and fall through to agent check.

        agent_name = r.iloc[1]
        if pd.isna(agent_name):
            continue

        row: dict = {"report_date": report_date, "status_group": current_status}
        for col_name, col_idx in col_map.items():
            row[col_name] = r.iloc[col_idx]
        rows.append(row)

    df = pd.DataFrame(rows)
    numeric = [
        "budget_gci_annual", "budget_gci_ytd", "actual_gci_ytd",
        "variance_ytd", "pending_gci", "actual_plus_pending",
    ]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


# ════════════════════════════════════════════════════════════════════════════
# AGENT EXPENSES AGING REPORT
# ════════════════════════════════════════════════════════════════════════════

def _parse_agent_aging(path: str | Path) -> pd.DataFrame:
    """
    Parse the 'Agent Expenses Aging report' sheet.

    header row : row 2 (0-based)
    data rows  : 3 .. 84  (skip blank rows and the totals row 87)

    Columns returned:
        report_date, agent_name, agent_code, office,
        total, current, aging_31_60, aging_61_90, aging_91_120, over_120
    """
    raw = _read(path, "Agent Expenses Aging report")
    report_date = pd.to_datetime(raw.iloc[0, 11]).date()

    col_map = {
        "agent_name":   2,
        "agent_code":   3,
        "office":       11,
        "total":        13,
        "current":      14,
        "aging_31_60":  15,
        "aging_61_90":  16,
        "aging_91_120": 17,
        "over_120":     18,
    }

    rows = []
    for i in range(3, len(raw)):
        r = raw.iloc[i]
        name = r.iloc[2]
        if pd.isna(name) or str(name).strip() == "":
            continue

        row: dict = {"report_date": report_date}
        for col_name, col_idx in col_map.items():
            row[col_name] = r.iloc[col_idx]
        rows.append(row)

    df = pd.DataFrame(rows)
    numeric = ["total", "current", "aging_31_60", "aging_61_90", "aging_91_120", "over_120"]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


# ════════════════════════════════════════════════════════════════════════════
# RANKING OF AGENTS - NET OF OFFICE
# ════════════════════════════════════════════════════════════════════════════

def _parse_agent_ranking(path: str | Path) -> pd.DataFrame:
    """
    Parse the 'Ranking of Agts-Net of Office' sheet.

    header row : row 2 (0-based)
    data rows  : 3 .. 65  (row 66 = totals — skipped because agent_name is NaN)

    Columns returned:
        agent_code, agent_name, rank, ends,
        sales_volume, commission, net_office, pct, cum_pct
    """
    raw = _read(path, "Ranking of Agts-Net of Office")

    col_map = {
        "agent_code":   5,
        "agent_name":   7,
        "rank":         8,
        "ends":         9,
        "sales_volume": 10,
        "commission":   11,
        "net_office":   12,
        "pct":          13,
        "cum_pct":      14,
    }

    rows = []
    for i in range(3, len(raw)):
        r = raw.iloc[i]
        name = r.iloc[7]
        if pd.isna(name):
            continue  # totals row or blank

        row: dict = {}
        for col_name, col_idx in col_map.items():
            row[col_name] = r.iloc[col_idx]
        rows.append(row)

    df = pd.DataFrame(rows)
    numeric = ["rank", "ends", "sales_volume", "commission", "net_office", "pct", "cum_pct"]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["rank"] = df["rank"].astype("Int64")
    return df


# ════════════════════════════════════════════════════════════════════════════
# COMMISSION CUTTING REPORT - MONTH
# ════════════════════════════════════════════════════════════════════════════

def _parse_commission_cutting(path: str | Path) -> pd.DataFrame:
    """
    Parse the 'Commission Cutting Report-Month' sheet.

    header row : row 3 (0-based)  — three section headers in row 2
    data rows  : 4 .. 30

    Columns returned:
        report_date, agent_code, agent_name,
        combined_rank, combined_volume, combined_ends, combined_commission, combined_avg_pct,
        listing_rank,  listing_volume,  listing_ends,  listing_commission,  listing_avg_pct,
        selling_rank,  selling_volume,  selling_ends,  selling_commission,  selling_avg_pct,
        comm_lost
    """
    raw = _read(path, "Commission Cutting Report-Month")
    report_date = pd.to_datetime(raw.iloc[0, 7]).date()

    col_map = {
        "agent_code":               0,
        "agent_name":               1,
        # Combined
        "combined_rank":            5,
        "combined_volume":          6,
        "combined_ends":            7,
        "combined_commission":      8,
        "combined_avg_pct":         10,
        # Listing Side
        "listing_rank":             11,
        "listing_volume":           12,
        "listing_ends":             13,
        "listing_commission":       14,
        "listing_avg_pct":          16,
        # Selling Side
        "selling_rank":             17,
        "selling_volume":           18,
        "selling_ends":             19,
        "selling_commission":       20,
        "selling_avg_pct":          22,
        # Commission lost to competitors
        "comm_lost":                24,
    }

    rows = []
    for i in range(4, len(raw)):
        r = raw.iloc[i]
        name = r.iloc[1]
        code = r.iloc[0]
        if pd.isna(name) and pd.isna(code):
            continue

        row: dict = {"report_date": report_date}
        for col_name, col_idx in col_map.items():
            row[col_name] = r.iloc[col_idx]
        rows.append(row)

    df = pd.DataFrame(rows)
    # Keep only rows that have an agent name (excludes totals row at end)
    df = df[df["agent_name"].notna()].copy()

    numeric = [c for c in df.columns if c not in ("report_date", "agent_code", "agent_name")]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


# ════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ════════════════════════════════════════════════════════════════════════════

def load_mb_report(path: str | Path) -> Dict[str, pd.DataFrame]:
    """
    Load every sheet from the Managing Broker XLSX report and return a dict
    of clean DataFrames keyed by logical name.

    Parameters
    ----------
    path : str or Path
        Absolute path to the .xlsx file (e.g. "/tmp/mb_report.xlsx").

    Returns
    -------
    dict with keys:
        scorecard_summary     - Monthly Scorecard-Summary
        scorecard_van         - Monthly Scorecard-Van
        scorecard_westvan     - Monthly Scorecard-West Van
        actual_2026_van       - 2026 Monthly Actual-Van
        actual_2026_westvan   - 2026 Monthly Actual-West Van
        actual_2025_van       - 2025 Monthly Actual-Van
        actual_2025_westvan   - 2025 Monthly Actual-West Van
        budget_2026_van       - 2026 Monthly Budget-Van
        budget_2026_westvan   - 2026 Monthly Budget-West Van
        agent_gci             - Agent GCI Budget v.Actual
        agent_aging           - Agent Expenses Aging report
        agent_ranking         - Ranking of Agts-Net of Office
        commission_cutting    - Commission Cutting Report-Month
    """
    path = Path(path)

    return {
        # Scorecards
        "scorecard_summary": _parse_scorecard(path, "Monthly Scorecard-Summary"),
        "scorecard_van":     _parse_scorecard(path, "Monthly Scorecard-Van"),
        "scorecard_westvan": _parse_scorecard(path, "Monthly Scorecard-West Van"),

        # Monthly actuals
        "actual_2026_van":     _parse_monthly(path, "2026 Monthly Actual-Van"),
        "actual_2026_westvan": _parse_monthly(path, "2026 Monthly Actual-West Van"),
        "actual_2025_van":     _parse_monthly(path, "2025 Monthly Actual-Van"),
        "actual_2025_westvan": _parse_monthly(path, "2025 Monthly Actual-West Van"),

        # Monthly budgets
        "budget_2026_van":     _parse_monthly(path, "2026 Monthly Budget-Van"),
        "budget_2026_westvan": _parse_monthly(path, "2026 Monthly Budget-West Van"),

        # Agent-level reports
        "agent_gci":           _parse_agent_gci(path),
        "agent_aging":         _parse_agent_aging(path),
        "agent_ranking":       _parse_agent_ranking(path),
        "commission_cutting":  _parse_commission_cutting(path),
    }
