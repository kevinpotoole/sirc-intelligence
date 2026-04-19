SIRC_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');

/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Top header bar ── */
.sirc-header {
    background: #002349;
    padding: 1.2rem 2rem;
    margin: -1rem -1rem 1.5rem -1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.sirc-header h1 {
    font-family: 'Playfair Display', serif;
    color: #C9A96E;
    font-size: 1.4rem;
    font-weight: 600;
    margin: 0;
    letter-spacing: 0.04em;
}
.sirc-header span {
    color: #FFFFFF;
    font-size: 0.75rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    opacity: 0.7;
}

/* ── KPI cards ── */
.kpi-card {
    background: #FFFFFF;
    border: 1px solid #E8E0D5;
    border-top: 3px solid #C9A96E;
    border-radius: 4px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.5rem;
}
.kpi-label {
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #8B7355;
    margin-bottom: 0.4rem;
}
.kpi-value {
    font-family: 'Playfair Display', serif;
    font-size: 1.8rem;
    font-weight: 700;
    color: #002349;
    line-height: 1;
}
.kpi-delta {
    font-size: 0.75rem;
    color: #5A8A5A;
    margin-top: 0.3rem;
}
.kpi-delta.neg { color: #8A3A3A; }

/* ── Section headings ── */
.section-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.2rem;
    color: #002349;
    border-bottom: 1px solid #C9A96E;
    padding-bottom: 0.4rem;
    margin: 1.5rem 0 1rem 0;
    letter-spacing: 0.02em;
}

/* ── Tables ── */
.dataframe thead th {
    background-color: #002349 !important;
    color: #C9A96E !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
}
.dataframe tbody tr:nth-child(even) {
    background-color: #F7F3EE !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #002349;
}
[data-testid="stSidebar"] .css-1d391kg,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] p {
    color: #F7F3EE !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div {
    background-color: #1A3A5C;
    color: #FFFFFF;
    border: 1px solid #C9A96E;
}

/* ── Metric overrides ── */
[data-testid="metric-container"] {
    background: #FFFFFF;
    border: 1px solid #E8E0D5;
    border-top: 3px solid #C9A96E;
    border-radius: 4px;
    padding: 1rem;
}
[data-testid="metric-container"] label {
    color: #8B7355 !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #002349 !important;
    font-family: 'Playfair Display', serif !important;
    font-size: 1.6rem !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    border-bottom: 2px solid #C9A96E;
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #002349;
    font-size: 0.8rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 0.5rem 1.2rem;
    border: none;
}
.stTabs [aria-selected="true"] {
    background: #002349 !important;
    color: #C9A96E !important;
}

/* ── Buttons ── */
.stButton > button {
    background-color: #002349;
    color: #C9A96E;
    border: 1px solid #C9A96E;
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.5rem 1.5rem;
    border-radius: 2px;
    transition: all 0.2s;
}
.stButton > button:hover {
    background-color: #C9A96E;
    color: #002349;
}

/* ── Recruitment badge ── */
.recruit-badge {
    background: #C9A96E;
    color: #002349;
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.15rem 0.5rem;
    border-radius: 2px;
    font-weight: 600;
    display: inline-block;
}
</style>
"""

PLOTLY_THEME = dict(
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#F7F3EE",
    font=dict(family="Inter, sans-serif", color="#1A1A1A"),
    colorway=["#002349", "#C9A96E", "#5A8A9F", "#8B7355", "#4A6741", "#8A3A3A"],
    title_font=dict(family="Playfair Display, serif", color="#002349"),
    xaxis=dict(gridcolor="#E8E0D5", linecolor="#E8E0D5"),
    yaxis=dict(gridcolor="#E8E0D5", linecolor="#E8E0D5"),
)

SIRC_NAVY = "#002349"
SIRC_GOLD = "#C9A96E"
SIRC_CREAM = "#F7F3EE"


def apply_plotly_theme(fig, title=None):
    fig.update_layout(**PLOTLY_THEME)
    if title:
        fig.update_layout(title=dict(text=title, font=dict(family="Playfair Display, serif", size=16, color=SIRC_NAVY)))
    return fig


def header(page_title: str, subtitle: str = ""):
    import streamlit as st
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown(f"""
    <div class="sirc-header">
        <h1>Sotheby's International Realty Canada</h1>
        <span>{page_title}{(' — ' + subtitle) if subtitle else ''}</span>
    </div>
    """, unsafe_allow_html=True)


def kpi(label: str, value: str, delta: str = "", negative: bool = False):
    delta_class = "neg" if negative else ""
    delta_html = f'<div class="kpi-delta {delta_class}">{delta}</div>' if delta else ""
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {delta_html}
    </div>
    """


def section(title: str):
    import streamlit as st
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
