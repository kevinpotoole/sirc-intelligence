import streamlit as st

st.set_page_config(
    page_title="SIRC Intelligence Platform",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("pages/0_Command_Centre.py",           title="Command Centre",          icon="🏠"),
    st.Page("pages/1_Agent_Performance.py",         title="Agent Performance",       icon="👤"),
    st.Page("pages/2_Brokerage_Intelligence.py",    title="Brokerage Intelligence",  icon="📊"),
    st.Page("pages/3_Market_Research.py",           title="Market Research",         icon="🔍"),
    st.Page("pages/4_Recruitment_Radar.py",         title="Recruitment Radar",       icon="🎯"),
    st.Page("pages/5_Generate_Report.py",           title="Generate Report",         icon="📄"),
    st.Page("pages/6_AI_Assistant.py",              title="AI Assistant",            icon="🤖"),
    st.Page("pages/7_Agent_Search.py",              title="Agent Search",            icon="🔎"),
    st.Page("pages/8_Internal_Reporting.py",        title="Internal Reporting",      icon="📈"),
    st.Page("pages/9_Recruitment_Impact.py",        title="Recruitment Impact",      icon="💼"),
    st.Page("pages/10_Neighbourhood_DrillDown.py",  title="Neighbourhood DrillDown", icon="🏘️"),
    st.Page("pages/11_Active_Listings.py",          title="Active Listings",         icon="🏡"),
    st.Page("pages/12_List_vs_Sold.py",             title="List vs Sold",            icon="⚖️"),
    st.Page("pages/13_Pipeline_Tracker.py",         title="Pipeline Tracker",        icon="🔄"),
    st.Page("pages/14_Market_Absorption.py",        title="Market Absorption",       icon="📉"),
], position="sidebar")

pg.run()
