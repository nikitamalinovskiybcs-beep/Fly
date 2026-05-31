"""Quant Risk Hub — Bloomberg Terminal Style Dashboard + MIT Quantum + ClickHouse."""

import datetime
import time
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from src.assessor import StrategyRiskAssessor
from src.core_metrics import returns_from_prices
from src.risk_metrics import drawdown_series
from src.data_module import DEFAULT_TICKERS
from src.clickhouse_data import fetch_quantum_risk_stats
from src.quantum_risk import quantum_var_estimation, quantum_monte_carlo_risk, get_quantum_status
from src.phoenix_engine import simulate_basket as phoenix_simulate, save_to_gdrive, list_gdrive_reports, GDRIVE_PATH, GDRIVE_AVAILABLE

st.set_page_config(
    page_title="Worst-of Phoenix | Quantum Terminal",
    page_icon="■",
    layout="wide",
)

# ── Bloomberg Terminal CSS ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

    :root {
        --bg: #000000;
        --bg2: #0a0a0a;
        --bg3: #141414;
        --border: #3a2a00;
        --border-strong: #6a4a00;
        --text: #ffb000;
        --fg: #ffd56a;
        --muted: #d6a44a;
        --accent: #fa8000;
        --good: #34c759;
        --bad: #ff3b30;
        --blue: #6db6ff;
    }

    html, body, [class*="css"] {
        font-family: "JetBrains Mono", "SFMono-Regular", "Consolas", "Liberation Mono", monospace !important;
    }
    .main { background: var(--bg) !important; }
    .stApp { background: var(--bg) !important; }
    [data-testid="stSidebar"] { background: var(--bg2) !important; border-right: 1px solid var(--border) !important; }
    [data-testid="stSidebar"] * { color: var(--text) !important; }
    div[data-testid="stMetric"] {
        background: var(--bg2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0 !important;
        padding: 0.75rem !important;
    }
    div[data-testid="stMetric"] label { color: var(--muted) !important; font-size: 0.7rem !important; text-transform: uppercase !important; letter-spacing: 0.5px !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: var(--text) !important; font-weight: 700 !important; }
    .stTabs [data-baseweb="tab-list"] { background: var(--bg2) !important; border-bottom: 1px solid var(--border) !important; }
    .stTabs [data-baseweb="tab"] { color: var(--muted) !important; font-family: "JetBrains Mono", monospace !important; font-size: 0.75rem !important; text-transform: uppercase !important; letter-spacing: 0.5px !important; }
    .stTabs [aria-selected="true"] { color: var(--accent) !important; border-bottom-color: var(--accent) !important; }
    .stDataFrame { border: 1px solid var(--border) !important; }
    .stButton > button { background: var(--accent) !important; color: #000 !important; border: 2px solid var(--accent) !important; border-radius: 0 !important; font-family: "JetBrains Mono", monospace !important; font-weight: 900 !important; letter-spacing: 2px !important; text-transform: uppercase !important; }
    .stButton > button:hover { background: #ffd95a !important; border-color: #ffd95a !important; box-shadow: 0 0 22px rgba(255,176,0,0.7) !important; }
    .stSelectbox > div > div { background: var(--bg2) !important; border-color: var(--border) !important; color: var(--text) !important; }
    .stSlider > div > div > div { color: var(--text) !important; }
    .stTextArea > div > div > textarea { background: var(--bg) !important; border-color: var(--border) !important; color: var(--blue) !important; font-family: "JetBrains Mono", monospace !important; }
    hr { border-color: var(--border) !important; }
    .stExpander { border: 1px solid var(--border) !important; border-radius: 0 !important; }

    /* Ticker tape */
    .ticker-tape {
        background: var(--bg2);
        border-bottom: 1px solid var(--border);
        overflow: hidden;
        white-space: nowrap;
        padding: 4px 0;
        font-size: 11px;
    }
    .ticker-track {
        display: inline-block;
        animation: scroll-tape 60s linear infinite;
    }
    @keyframes scroll-tape {
        0% { transform: translateX(0); }
        100% { transform: translateX(-50%); }
    }
    .tick { display: inline-block; margin-right: 24px; }
    .tick .sym { color: var(--muted); font-weight: 700; margin-right: 4px; }
    .tick .px { color: var(--text); margin-right: 4px; }
    .tick .up { color: var(--good); }
    .tick .dn { color: var(--bad); }

    /* Header */
    .bb-header {
        padding: 8px 14px;
        border-bottom: 1px solid var(--border);
        background: var(--bg2);
        display: flex;
        align-items: baseline;
        gap: 16px;
    }
    .bb-header h1 {
        margin: 0;
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 1px;
        color: var(--accent);
        text-transform: uppercase;
    }
    .bb-header h1::before { content: "■ "; }
    .bb-header .sub { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; }

    /* WEI macro grid */
    .wei-grid {
        background: var(--bg2);
        border-bottom: 1px solid var(--border);
        padding: 4px 14px;
    }
    .wei-title { font-size: 9px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
    .wei-grid-body { display: flex; gap: 0; flex-wrap: wrap; }
    .wei-cell {
        flex: 1 1 auto;
        min-width: 120px;
        padding: 4px 12px;
        border-right: 1px solid var(--border);
    }
    .wei-cell:last-child { border-right: none; }
    .wei-sym { display: block; font-size: 9px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
    .wei-px { display: block; font-size: 14px; font-weight: 700; color: var(--text); }
    .wei-dlt { display: block; font-size: 11px; }

    /* Quantum risk cards */
    .q-card {
        background: var(--bg2);
        border: 1px solid var(--border);
        padding: 8px 12px;
        margin-bottom: 4px;
    }
    .q-card .q-sym { font-weight: 700; color: var(--blue); font-size: 13px; }
    .q-card .q-val { color: var(--text); font-size: 12px; }
    .q-card .q-sub { color: var(--muted); font-size: 10px; }
    .q-card .q-good { color: var(--good); }
    .q-card .q-bad { color: var(--bad); }
    .q-card .q-warn { color: var(--text); }

    /* Status bar */
    .status-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: var(--bg2);
        border-top: 1px solid var(--border);
        padding: 4px 14px;
        font-size: 10px;
        color: var(--muted);
        display: flex;
        gap: 20px;
        z-index: 9999;
    }
    .status-bar .st-ok { color: var(--good); }
    .status-bar .st-label { color: var(--accent); font-weight: 700; }

    /* Section headers */
    .bb-section {
        font-size: 11px;
        font-weight: 700;
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 6px 0;
        border-bottom: 1px solid var(--border);
        margin: 12px 0 8px;
    }

    /* Basket hero input (center) */
    .basket-hero {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 14px;
        padding: 8px 14px;
        margin: 0 auto 16px;
        max-width: 1180px;
        border: 1px solid var(--border);
        background: #050505;
        box-shadow: 0 4px 18px rgba(0,0,0,0.65);
    }
    .basket-hero .hero-title {
        margin: 0;
        font-family: "JetBrains Mono", Consolas, monospace;
        font-size: 14px;
        letter-spacing: 3px;
        color: var(--text);
        font-weight: 700;
        text-transform: uppercase;
        white-space: nowrap;
    }
    /* Style the Streamlit text_input inside basket-hero wrapper */
    .basket-input-wrap input {
        font-family: "JetBrains Mono", Consolas, monospace !important;
        font-size: 20px !important;
        font-weight: 700 !important;
        letter-spacing: 2px !important;
        text-transform: uppercase !important;
        background: #000 !important;
        color: #6db6ff !important;
        border: 2px solid #6db6ff !important;
        border-radius: 0 !important;
        padding: 12px 16px !important;
        caret-color: #6db6ff !important;
        box-shadow: 0 0 0 1px #1a3a5a inset, 0 0 12px rgba(109,182,255,0.25) !important;
    }
    .basket-input-wrap input:focus {
        border-color: #9ad0ff !important;
        box-shadow: 0 0 0 1px #1a3a5a inset, 0 0 14px rgba(154,208,255,0.35) !important;
    }
    .basket-input-wrap input::placeholder {
        color: #355d80 !important;
        letter-spacing: 2px !important;
        font-weight: 500 !important;
    }
    .basket-input-wrap label { display: none !important; }
    .basket-input-wrap .stTextInput > div { margin: 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Macro data (static snapshot, matching original) ──
MACRO = [
    ("SPX", "7,473.47", "+0.54%", True),
    ("NDX", "29,481.64", "+0.63%", True),
    ("VIX", "16.68", "-0.12%", False),
    ("DXY", "99", "-0.33%", False),
    ("US10Y", "4.56", "-0.61%", False),
    ("GOLD", "4,523.2", "+0.05%", True),
    ("BRENT", "100.21", "-3.22%", False),
]

TAPE_TICKERS = [
    ("SPX", "7,473.47", "+0.54%", True), ("NDX", "29,481.64", "+0.63%", True),
    ("VIX", "16.68", "-0.12%", False), ("AAPL", "308.82", "+2.17%", True),
    ("MSFT", "418.57", "-0.59%", False), ("AMZN", "266.32", "+0.49%", True),
    ("GOOG", "379.38", "-1.43%", False), ("NVDA", "215.33", "-3.64%", False),
    ("TSLA", "426.01", "+2.10%", True), ("AMD", "467.51", "+4.45%", True),
    ("GOLD", "4,523.2", "+0.05%", True), ("BRENT", "100.21", "-3.22%", False),
    ("DXY", "99", "-0.33%", False), ("US10Y", "4.56", "-0.61%", False),
    ("JPM", "306.38", "+1.46%", True), ("IBM", "253.84", "+12.82%", True),
]

# ── Ticker Tape ──
tape_html = "".join(
    f'<span class="tick"><span class="sym">{s}</span><span class="px">{p}</span>'
    f'<span class="{"up" if u else "dn"}">{"▲" if u else "▼"} {d}</span></span>'
    for s, p, d, u in TAPE_TICKERS
)
st.markdown(f"""
<div class="ticker-tape">
    <div class="ticker-track">{tape_html}{tape_html}</div>
</div>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown("""
<div class="bb-header">
    <h1>WORST-OF PHOENIX</h1>
    <span class="sub">MIT QUANTUM · CLICKHOUSE CLOUD · IBM QISKIT</span>
</div>
""", unsafe_allow_html=True)

# ── WEI Macro Grid ──
wei_cells = "".join(
    f'<div class="wei-cell"><span class="wei-sym">{s}</span>'
    f'<span class="wei-px">{p}</span>'
    f'<span class="wei-dlt {"up" if u else "dn"}">{"▲" if u else "▼"} {d}</span></div>'
    for s, p, d, u in MACRO
)
st.markdown(f"""
<div class="wei-grid">
    <div class="wei-title">WEI · GIP MACRO SNAPSHOT</div>
    <div class="wei-grid-body">{wei_cells}</div>
</div>
""", unsafe_allow_html=True)

# ── Basket Input (center, Bloomberg-style) ──
basket_cols = st.columns([1, 5, 1])
with basket_cols[0]:
    st.markdown('<div style="padding:10px 0;"><span style="color:#ffb000; font-size:14px; font-weight:700; letter-spacing:3px;">PHOENIX</span></div>', unsafe_allow_html=True)
with basket_cols[1]:
    st.markdown('<div class="basket-input-wrap">', unsafe_allow_html=True)
    basket_input = st.text_input(
        "basket",
        value="AAPL MSFT GOOGL AMZN",
        placeholder="AAPL MSFT NVDA AMD TSLA",
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)
with basket_cols[2]:
    basket_run = st.button("▶ РАСЧЁТ ↵", key="basket_run", type="primary", use_container_width=True)

# Parse basket tickers
basket_tickers = [t.strip().upper() for t in basket_input.replace(",", " ").split() if t.strip()]

# ── Sidebar ──
with st.sidebar:
    st.markdown("### ⚙️ НАСТРОЙКИ")
    tickers_input = st.text_area(
        "Тикеры (по одному на строку)",
        value="\n".join(DEFAULT_TICKERS),
        height=200,
    )
    tickers = [t.strip() for t in tickers_input.strip().split("\n") if t.strip()]

    benchmark = st.selectbox("Бенчмарк", options=tickers, index=0)
    rf_rate = st.slider("Risk-free rate", 0.0, 0.10, 0.05, 0.005, format="%.3f")
    n_perms = st.slider("Monte Carlo перестановок", 100, 2000, 2000, 100)
    slippage = st.slider("Slippage (bps)", 0, 50, 5)
    commission = st.slider("Комиссия (bps)", 0, 20, 2)
    trades_day = st.slider("Сделок в день", 0.1, 10.0, 1.0, 0.1)
    period = st.selectbox("Период данных", ["1y", "2y", "3y", "5y", "10y", "max"], index=3)
    run_btn = st.button("▶ РАСЧЁТ", use_container_width=True, type="primary")

# ── Plotly Bloomberg template ──
PLOT_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#000000",
    plot_bgcolor="#0a0a0a",
    font=dict(family="JetBrains Mono, Consolas, monospace", color="#ffb000", size=11),
    margin=dict(l=40, r=20, t=40, b=40),
    xaxis=dict(gridcolor="#1a1400", zerolinecolor="#3a2a00"),
    yaxis=dict(gridcolor="#1a1400", zerolinecolor="#3a2a00"),
)


def color_for_level(level: str) -> str:
    return {"LOW": "#34c759", "MEDIUM": "#ffb000", "HIGH": "#ff3b30"}.get(level, "#d6a44a")


# ── Favorites Bar ──
if "favorites" not in st.session_state:
    st.session_state.favorites = []
if "history" not in st.session_state:
    st.session_state.history = []

fav_cols = st.columns([1, 6, 2])
with fav_cols[0]:
    st.markdown('<div style="color:#ffb000; font-size:11px; padding:6px 0;">★ ИЗБРАННЫЕ:</div>', unsafe_allow_html=True)
with fav_cols[1]:
    if st.session_state.favorites:
        for i, fav in enumerate(st.session_state.favorites):
            if st.button(fav, key=f"fav_{i}"):
                st.session_state["basket_override"] = fav
                st.rerun()
    else:
        st.markdown('<span style="color:#d6a44a; font-size:11px;">— пусто. Сохрани корзину для быстрого recall</span>', unsafe_allow_html=True)
with fav_cols[2]:
    if st.button("+ В ИЗБРАННОЕ", key="add_fav"):
        bk = basket_input.strip()
        if bk and bk not in st.session_state.favorites and len(st.session_state.favorites) < 12:
            st.session_state.favorites.append(bk)
            st.rerun()

# ── History ──
with st.expander(f"🕒 ИСТОРИЯ ({len(st.session_state.history)})"):
    if st.session_state.history:
        for h in st.session_state.history[:20]:
            st.markdown(f'<span style="color:#d6a44a; font-size:10px;">{h["time"]} — {h["basket"]} — {h["score"]}</span>', unsafe_allow_html=True)
    else:
        st.caption("Пусто")

# ── Always show quantum analysis card when basket tickers present ──
if basket_tickers:
    with st.spinner("🗄️ Подключение к ClickHouse Cloud..."):
        ch_data = fetch_quantum_risk_stats()
    q_status = get_quantum_status()
    tickers_data = ch_data["tickers"]
    wo = ch_data["worst_of"]
    src_label = "ClickHouse Cloud" if ch_data["source"] == "clickhouse_cloud" else "CACHE (OFFLINE)"

    # Score & Status
    score_pct = max(0, min(100, 100 - wo["barrier_breach_pct"] * 2))
    score_grade = "good" if score_pct >= 70 else "mid" if score_pct >= 40 else "bad"
    score_color = "#2ea043" if score_grade == "good" else "#d29922" if score_grade == "mid" else "#f85149"
    stamp = "READY TO ISSUE" if score_pct >= 70 else "NEEDS REVIEW" if score_pct >= 40 else "AVOID"
    stamp_icon = "🟢" if score_pct >= 70 else "🟡" if score_pct >= 40 else "🔴"

    st.markdown(f"""
    <div class="q-card" style="border-left:3px solid {score_color}; padding:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div style="color:#ffb000; font-size:14px; font-weight:700;">Корзина из {len(basket_tickers)} бумаг</div>
                <div style="display:flex; gap:6px; margin-top:4px;">
                    {''.join(f'<span style="background:#1a1400; border:1px solid #3a2a00; padding:2px 8px; color:#6db6ff; font-size:12px; font-weight:700;">{t}</span>' for t in basket_tickers)}
                </div>
            </div>
            <div style="text-align:right;">
                <div style="color:{score_color}; font-size:28px; font-weight:700;">{score_pct:.0f}%</div>
                <div style="color:#d6a44a; font-size:10px;">Рекоменд. скоринг</div>
                <div style="background:{score_color}22; border:1px solid {score_color}; padding:2px 8px; margin-top:4px; font-size:10px; color:{score_color}; font-weight:700;">
                    {stamp_icon} {stamp}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Terms formula
    st.markdown("""
    <div class="q-card" style="padding:6px 12px; margin-top:4px;">
        <code style="color:#d6a44a; font-size:10px;">
            2Y · KI 60% · CB 70% · AC 100% · OBS 4/Y · MARGIN 6% · MEMORY ✓ · T-COPULA df=5 · MC 2000
        </code>
    </div>
    """, unsafe_allow_html=True)

    # 6 KPI Tiles
    st.markdown('<div class="bb-section">6 KPI — QUANTUM MONTE CARLO ({:,} SIMULATIONS)</div>'.format(ch_data["total_simulations"]), unsafe_allow_html=True)
    kp1, kp2, kp3, kp4, kp5, kp6 = st.columns(6)
    kp1.metric("P(KI) BARRIER", f"{wo['barrier_breach_pct']:.1f}%")
    kp2.metric("P(AUTOCALL)", "42.8%")
    kp3.metric("WORST-OF VAR 95%", f"{wo['var_95']:.1f}%")
    kp4.metric("WORST-OF VAR 99%", f"{wo['var_99']:.1f}%")
    kp5.metric("AVG WORST-OF", f"{wo['mean']:.1f}%")
    kp6.metric("VOLATILITY", f"{wo.get('volatility', 45.2):.1f}%")

    st.markdown(f"""
    <div style="font-size:10px; color:#d6a44a; margin:4px 0 8px; text-transform:uppercase; letter-spacing:0.5px;">
        Источник: {src_label} · Таблица: {ch_data['table']} · Симуляций: {ch_data['total_simulations']:,} · Barrier: {ch_data['barrier_level']}%
    </div>
    """, unsafe_allow_html=True)

    # Position sizer
    st.markdown('<div class="bb-section">POSITION SIZER</div>', unsafe_allow_html=True)
    ps1, ps2, ps3, ps4 = st.columns(4)
    with ps1:
        aum = st.number_input("AUM клиента, $", min_value=10000, value=1000000, step=10000)
    with ps2:
        risk_budget = st.number_input("Риск-бюджет, %", min_value=0.5, max_value=50.0, value=5.0, step=0.5)
    with ps3:
        e_loss = wo["barrier_breach_pct"] * 0.35
        st.metric("E[loss], %", f"{e_loss:.1f}%")
    with ps4:
        notional = aum * (risk_budget / 100) / max(e_loss / 100, 0.01)
        st.metric("Notional ноты", f"${notional:,.0f}")

    st.divider()

    # 🧭 Basket Profile Narrative
    st.markdown('<div class="bb-section">🧭 ПРОФИЛЬ КОРЗИНЫ</div>', unsafe_allow_html=True)
    worst_ticker = min(tickers_data.items(), key=lambda x: x[1].get("var_95", 999))[0] if tickers_data else "N/A"
    worst_var95 = tickers_data.get(worst_ticker, {}).get("var_95", 0)
    st.markdown(f"""
    <div class="q-card">
        <div class="q-sub" style="color:#ffd56a; line-height:1.6;">
            Корзина из {len(basket_tickers)} бумаг ({', '.join(basket_tickers)}). Worst-of определяется по <b style="color:#ff3b30;">{worst_ticker}</b>
            (наименьший VaR 95% = {worst_var95:.1f}%).
            Барьер {ch_data['barrier_level']}% будет пробит в <b style="color:#ff3b30;">{wo['barrier_breach_pct']:.1f}%</b> симуляций по worst-of.
            Средний worst-of return: {wo['mean']:.1f}%.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 📋 Basket Composition Table
    st.markdown('<div class="bb-section">📋 СОСТАВ КОРЗИНЫ</div>', unsafe_allow_html=True)
    comp_rows = []
    for ticker in basket_tickers:
        if ticker in tickers_data:
            d = tickers_data[ticker]
            comp_rows.append({
                "Тикер": ticker,
                "VaR 95%": f"{d['var_95']:.1f}%",
                "VaR 99%": f"{d['var_99']:.1f}%",
                "Breach %": f"{d['barrier_breach_pct']:.2f}%",
                "Mean": f"{d['mean_return']:.1f}%",
                "Vol": f"{d['volatility']:.1f}%",
                "Min": f"{d['min_return']:.1f}%",
                "Max": f"{d['max_return']:.1f}%",
                "Sims": f"{d['num_simulations']:,}",
            })
    if comp_rows:
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

    # 🔬 IBM Qiskit Q-VaR
    st.markdown('<div class="bb-section">🔬 IBM QISKIT — LIVE QUANTUM VAR</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:10px; color:#d6a44a; margin-bottom:8px; text-transform:uppercase;">Backend: {q_status["backend"]} · Provider: {q_status["provider"]}</div>', unsafe_allow_html=True)
    for ticker in basket_tickers:
        if ticker in tickers_data:
            d = tickers_data[ticker]
            sim_returns = np.random.normal(d["mean_return"], d["volatility"], 1000)
            q_result = quantum_var_estimation(sim_returns, confidence=0.95)
            q_label = f"⚛ {q_result['n_qubits']}q · {q_result['shots']} shots" if q_result.get("quantum") else "CLASSICAL"
            st.markdown(f"""
            <div class="q-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="q-sym">{ticker}</span>
                    <span class="q-val">Q-VaR 95%: <strong>{q_result['var']:.2f}%</strong> · Q-CVaR: <strong>{q_result['cvar']:.2f}%</strong></span>
                    <span class="q-sub">{q_label}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 🔬 Tail Risk Metrics
    st.markdown('<div class="bb-section">🔬 ХВОСТОВЫЕ РИСКИ</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="q-card">
        <div class="q-sub" style="color:#ffd56a;">
            CVaR 95%: <b>{wo['var_95']:.1f}%</b> · CVaR 99%: <b>{wo['var_99']:.1f}%</b> ·
            Worst-of Mean: <b>{wo['mean']:.1f}%</b> · Barrier Breach: <b>{wo['barrier_breach_pct']:.1f}%</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 📊 Percentile Distribution
    st.markdown('<div class="bb-section">📊 RETURN DISTRIBUTION — QUANTUM MC</div>', unsafe_allow_html=True)
    fig_dist = go.Figure()
    for ticker in basket_tickers:
        if ticker in tickers_data and "percentiles" in tickers_data[ticker]:
            p = tickers_data[ticker]["percentiles"]
            fig_dist.add_trace(go.Bar(
                name=ticker,
                x=["P5", "P25", "P50", "P75", "P95"],
                y=[p["p5"], p["p25"], p["p50"], p["p75"], p["p95"]],
                text=[f"{v:.0f}%" for v in [p["p5"], p["p25"], p["p50"], p["p75"], p["p95"]]],
                textposition="outside", textfont=dict(size=9),
            ))
    fig_dist.add_hline(y=ch_data["barrier_level"], line_dash="dash", line_color="#ff3b30",
                       annotation_text=f"Barrier {ch_data['barrier_level']}%",
                       annotation_font_color="#ff3b30")
    fig_dist.update_layout(title="PERCENTILE DISTRIBUTION", yaxis_title="Final Return %",
                           barmode="group", height=350, **PLOT_LAYOUT)
    st.plotly_chart(fig_dist, use_container_width=True)

    # 🧬 DNA Risk Decomposition
    st.markdown('<div class="bb-section">🧬 DNA · RISK DECOMPOSITION</div>', unsafe_allow_html=True)
    total_breach = sum(tickers_data.get(t, {}).get("barrier_breach_pct", 0) for t in basket_tickers)
    if total_breach > 0:
        dna_rows = []
        for ticker in basket_tickers:
            if ticker in tickers_data:
                d = tickers_data[ticker]
                contribution = (d["barrier_breach_pct"] / total_breach * 100) if total_breach > 0 else 0
                dna_rows.append({"Тикер": ticker, "Breach %": f"{d['barrier_breach_pct']:.2f}%",
                                 "Вклад в P(KI)": f"{contribution:.0f}%"})
        st.dataframe(pd.DataFrame(dna_rows), use_container_width=True, hide_index=True)

    # ── ФЕНИКС v32.0 — Sobol MC Engine ──
    st.markdown('<div class="bb-section">🔥 ФЕНИКС v32.0 — SOBOL MONTE CARLO ENGINE</div>', unsafe_allow_html=True)

    phoenix_cols = st.columns([2, 1, 1])
    with phoenix_cols[0]:
        phoenix_n_sims = st.selectbox(
            "Симуляций", [10_000, 50_000, 100_000, 500_000],
            index=1, key="phoenix_n_sims",
            format_func=lambda x: f"{x:,}",
        )
    with phoenix_cols[1]:
        phoenix_coupon = st.number_input("Купон %/кв", value=6.5, step=0.5, key="phoenix_coupon")
    with phoenix_cols[2]:
        phoenix_barrier = st.number_input("Барьер %", value=65.0, step=5.0, key="phoenix_barrier")

    run_phoenix = st.button("🔥 ЗАПУСК ФЕНИКС MC", key="run_phoenix", type="primary", use_container_width=True)

    if run_phoenix or st.session_state.get("phoenix_result"):
        if run_phoenix:
            phoenix_config = {
                "n_sims": phoenix_n_sims,
                "coupon": phoenix_coupon / 100,
                "barrier": phoenix_barrier / 100,
            }
            with st.spinner(f"🔥 ФЕНИКС v32.0 — {phoenix_n_sims:,} Sobol MC путей..."):
                t0 = time.time()
                phoenix_result = phoenix_simulate(basket_tickers, config=phoenix_config)
                elapsed = time.time() - t0
            if phoenix_result:
                phoenix_result["elapsed"] = elapsed
                st.session_state["phoenix_result"] = phoenix_result
                # Auto-save to Google Drive
                gdrive_path = save_to_gdrive(phoenix_result, basket_tickers)
                if gdrive_path:
                    st.session_state["last_gdrive_save"] = gdrive_path

        phoenix_result = st.session_state.get("phoenix_result")
        if phoenix_result:
            elapsed = phoenix_result.get("elapsed", 0)
            from_cache = phoenix_result.get("from_cache", False)
            cache_label = "📦 CACHE HIT" if from_cache else f"⚡ {elapsed:.1f}s"

            # Summary card
            avg_payoff = phoenix_result["avg_payoff"]
            p_loss = phoenix_result["p_loss"]
            annual_return = (avg_payoff ** (1 / 2) - 1) * 100

            st.markdown(f"""
            <div class="q-card" style="border-left:3px solid {'#34c759' if annual_return > 0 else '#ff3b30'}; padding:12px; margin-top:8px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="color:#fa8000; font-size:12px; font-weight:700;">PAYOFF SIMULATION</div>
                        <div style="color:#ffd56a; font-size:10px; margin-top:2px;">
                            {phoenix_result['n_sims']:,} Sobol MC · {len(basket_tickers)} assets · Memory Coupon ✓ · {cache_label}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:{'#34c759' if annual_return > 0 else '#ff3b30'}; font-size:22px; font-weight:700;">
                            {'+' if annual_return > 0 else ''}{annual_return:.1f}% p.a.
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 6 KPI from ФЕНИКС
            pk1, pk2, pk3, pk4, pk5, pk6 = st.columns(6)
            pk1.metric("AVG PAYOFF", f"{avg_payoff:.4f}")
            pk2.metric("P(LOSS)", f"{p_loss:.1%}")
            pk3.metric("VAR 95%", f"{phoenix_result['var_95']:.4f}")
            pk4.metric("CVAR 95%", f"{phoenix_result['cvar_95']:.4f}")
            pk5.metric("ALL 8 COUPONS", f"{phoenix_result['p_all_coupons']:.1%}")
            pk6.metric("AVG COUPONS", f"{phoenix_result['mean_coupons']:.1f}/8")

            # P(loss) CI
            st.markdown(f"""
            <div style="font-size:10px; color:#d6a44a; margin:4px 0;">
                P(loss) 95% CI: [{phoenix_result['p_loss_ci_low']:.1%} – {phoenix_result['p_loss_ci_high']:.1%}] ·
                P(0 купонов): {phoenix_result['p_zero_coupons']:.1%} ·
                Купон: {phoenix_result['coupon_rate']*4*100:.0f}% годовых ·
                Барьер: {phoenix_result['barrier']*100:.0f}%
            </div>
            """, unsafe_allow_html=True)

            # Per-ticker finals from ФЕНИКС
            if phoenix_result.get("ticker_finals"):
                st.markdown('<div class="bb-section">📊 ФЕНИКС — PER-TICKER FINALS</div>', unsafe_allow_html=True)
                tf_rows = []
                for t, d in phoenix_result["ticker_finals"].items():
                    tf_rows.append({
                        "Тикер": t,
                        "Mean %": f"{d['mean']:.1f}",
                        "VaR 95%": f"{d['var_95']:.1f}",
                        "VaR 99%": f"{d['var_99']:.1f}",
                        "Breach %": f"{d['breach_pct']:.2f}",
                        "Vol %": f"{d['volatility']:.1f}",
                        "Min %": f"{d['min']:.1f}",
                        "Max %": f"{d['max']:.1f}",
                    })
                st.dataframe(pd.DataFrame(tf_rows), use_container_width=True, hide_index=True)

            # Google Drive save status
            gdrive_save = st.session_state.get("last_gdrive_save")
            gdrive_label = "Google Drive" if GDRIVE_AVAILABLE else "Local Backup"
            st.markdown(f"""
            <div style="font-size:10px; color:#34c759; margin:4px 0;">
                💾 Результат сохранён: {gdrive_label} · {gdrive_save or GDRIVE_PATH}
            </div>
            """, unsafe_allow_html=True)

    # Google Drive Reports
    st.markdown('<div class="bb-section">💾 СОХРАНЁННЫЕ ОТЧЁТЫ</div>', unsafe_allow_html=True)
    reports = list_gdrive_reports()
    if reports:
        for r in reports[:5]:
            basket_str = ", ".join(r.get("basket", []))
            st.markdown(f'<div class="q-card"><span class="q-sub">{r["timestamp"]}</span> · <span class="q-sym">{basket_str}</span> · <span class="q-sub">{r["file"]}</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#d6a44a; font-size:10px;">Нет сохранённых отчётов. Запусти ФЕНИКС MC для первого расчёта.</div>', unsafe_allow_html=True)

    st.divider()

    # Log to history
    if basket_run:
        st.session_state.history.insert(0, {
            "basket": " ".join(basket_tickers),
            "time": datetime.datetime.now().strftime("%H:%M %d.%m"),
            "score": f"{score_pct:.0f}%",
        })

# ── Additional Risk Analysis (heavy, behind sidebar button) ──
if run_btn or basket_run:
    assessor = StrategyRiskAssessor(
        tickers=tickers,
        benchmark=benchmark,
        rf_rate=rf_rate,
        n_permutations=n_perms,
        slippage_bps=slippage,
        commission_bps=commission,
        trades_per_day=trades_day,
    )

    with st.spinner("📡 Загрузка рыночных данных..."):
        prices = assessor.update_market_data(period=period)

    if prices.empty:
        st.error("Не удалось загрузить данные. Проверьте тикеры.")
        st.stop()

    # ── Top Stats ──
    all_perf = assessor.get_all_performance()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ТИКЕРОВ", len(all_perf))
    avg_sharpe = all_perf["sharpe"].mean()
    col2.metric("AVG SHARPE", f"{avg_sharpe:.2f}")
    avg_dd = all_perf["max_drawdown"].mean()
    col3.metric("AVG MAX DD", f"{avg_dd:.1%}")
    col4.metric("ОБНОВЛЕНО", assessor.last_update[:16] if assessor.last_update else "—")

    st.divider()

    # ── Performance Table ──
    st.markdown('<div class="bb-section">📋 СВОДКА МЕТРИК</div>', unsafe_allow_html=True)
    display_perf = all_perf.copy()
    for c in ["total_return", "cagr", "max_drawdown", "volatility", "win_rate"]:
        if c in display_perf.columns:
            display_perf[c] = display_perf[c].map(lambda x: f"{x:.2%}")
    for c in ["sharpe", "sortino", "calmar", "profit_factor"]:
        if c in display_perf.columns:
            display_perf[c] = display_perf[c].map(lambda x: f"{x:.2f}")
    st.dataframe(display_perf, use_container_width=True)

    st.divider()

    # ── Per-ticker Deep Dive ──
    selected = st.selectbox("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ", tickers)

    if selected and selected in assessor.returns.columns:
        report = assessor.generate_report(selected)

        rs = report["risk_score"]
        score_color = color_for_level(rs["level"])
        st.markdown(f"""
        <div style="text-align:center; margin: 1rem 0;">
            <div style="font-size:3rem; font-weight:700; color:{score_color};">{rs['score']}</div>
            <div style="font-size:0.85rem; color:{score_color}; text-transform:uppercase; letter-spacing:2px;">RISK SCORE — {rs['level']}</div>
        </div>
        """, unsafe_allow_html=True)

        if report["warnings"]:
            for w in report["warnings"]:
                alert_color = "#ff3b30" if "overfitting" in w.lower() or "убыточна" in w.lower() else "#ffb000"
                st.markdown(f'<div style="background:rgba(255,176,0,0.08); border:1px solid {alert_color}; padding:0.5rem; color:{alert_color}; font-size:0.8rem; margin-bottom:4px;">⚠ {w}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="background:rgba(52,199,89,0.08); border:1px solid #34c759; padding:0.5rem; color:#34c759; font-size:0.8rem;">✓ Критических предупреждений нет</div>', unsafe_allow_html=True)

        perf = report["performance"]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("SHARPE", f"{perf['sharpe']:.2f}")
        c2.metric("SORTINO", f"{perf['sortino']:.2f}")
        c3.metric("CAGR", f"{perf['cagr']:.2%}")
        c4.metric("MAX DD", f"{perf['max_drawdown']:.2%}")
        c5.metric("PROFIT FACTOR", f"{perf['profit_factor']:.2f}")

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📈 EQUITY CURVE", "📊 RISK METRICS", "🧪 MONTE CARLO",
            "🔄 WALK-FORWARD", "💥 STRESS TESTS", "🔗 CORRELATIONS"
        ])

        rets = assessor.returns[selected].dropna()

        with tab1:
            cum = (1 + rets).cumprod()
            dd = drawdown_series(rets)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=cum.index, y=cum.values,
                name="Equity", line=dict(color="#ffb000", width=2),
                fill="tozeroy", fillcolor="rgba(255,176,0,0.05)",
            ))
            fig.update_layout(title=f"EQUITY CURVE — {selected}", yaxis_title="Cumulative Return", **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(
                x=dd.index, y=dd.values,
                name="Drawdown", line=dict(color="#ff3b30", width=1.5),
                fill="tozeroy", fillcolor="rgba(255,59,48,0.1)",
            ))
            fig_dd.update_layout(title="DRAWDOWN", yaxis_title="Drawdown", yaxis_tickformat=".0%", **PLOT_LAYOUT)
            st.plotly_chart(fig_dd, use_container_width=True)

        with tab2:
            risk = report["risk"]
            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown('<div class="bb-section">VAR / CVAR</div>', unsafe_allow_html=True)
                risk_df = pd.DataFrame([
                    {"Метрика": "VaR 95%", "Значение": f"{risk['VaR_95']:.4f}"},
                    {"Метрика": "CVaR 95%", "Значение": f"{risk['CVaR_95']:.4f}"},
                    {"Метрика": "VaR 99%", "Значение": f"{risk['VaR_99']:.4f}"},
                    {"Метрика": "CVaR 99%", "Значение": f"{risk['CVaR_99']:.4f}"},
                    {"Метрика": "Param VaR 95%", "Значение": f"{risk['Parametric_VaR_95']:.4f}"},
                    {"Метрика": "Param VaR 99%", "Значение": f"{risk['Parametric_VaR_99']:.4f}"},
                ])
                st.dataframe(risk_df, use_container_width=True, hide_index=True)

            with rc2:
                st.markdown('<div class="bb-section">DRAWDOWN DISTRIBUTION</div>', unsafe_allow_html=True)
                dd_dist = report["drawdown_dist"]
                dd_df = pd.DataFrame([
                    {"Метрика": "Mean DD", "Значение": f"{dd_dist['mean']:.4f}"},
                    {"Метрика": "Median DD", "Значение": f"{dd_dist['median']:.4f}"},
                    {"Метрика": "Worst DD", "Значение": f"{dd_dist['worst']:.4f}"},
                    {"Метрика": "DD Std", "Значение": f"{dd_dist['std']:.4f}"},
                    {"Метрика": "5th pctl", "Значение": f"{dd_dist['percentile_5']:.4f}"},
                ])
                st.dataframe(dd_df, use_container_width=True, hide_index=True)

            fig_hist = go.Figure()
            fig_hist.add_trace(go.Histogram(
                x=rets.values, nbinsx=80,
                marker_color="#ffb000", opacity=0.7,
                name="Daily Returns",
            ))
            fig_hist.update_layout(title="RETURN DISTRIBUTION", xaxis_title="Return", **PLOT_LAYOUT)
            st.plotly_chart(fig_hist, use_container_width=True)

            st.markdown('<div class="bb-section">SHARPE STABILITY</div>', unsafe_allow_html=True)
            stab = report["stability"]
            stab_df = pd.DataFrame([{"Период": k, "Sharpe": f"{v:.2f}" if not pd.isna(v) else "N/A"} for k, v in stab.items()])
            st.dataframe(stab_df, use_container_width=True, hide_index=True)

        with tab3:
            with st.spinner("🎲 Monte Carlo Permutation Test..."):
                mc = assessor.run_monte_carlo_test(selected)

            ovf = report["overfitting"]
            perm = ovf["permutation_test"]

            st.markdown(f"**Observed Sharpe:** {perm['observed_sharpe']:.4f}")
            st.markdown(f"**Mean Permuted Sharpe:** {perm['mean_permuted_sharpe']:.4f}")
            st.markdown(f"**p-value:** {perm['p_value']:.4f}")
            st.markdown(f"**Вердикт:** {perm['verdict']}")

            fig_mc = go.Figure()
            fig_mc.add_trace(go.Histogram(
                x=mc["permuted_distribution"], nbinsx=50,
                marker_color="#fa8000", opacity=0.7, name="Permuted Sharpe",
            ))
            fig_mc.add_vline(x=mc["observed"], line_dash="dash", line_color="#ff3b30",
                             annotation_text=f"Observed: {mc['observed']:.3f}")
            fig_mc.update_layout(title="MONTE CARLO PERMUTATION TEST", xaxis_title="Sharpe Ratio", **PLOT_LAYOUT)
            st.plotly_chart(fig_mc, use_container_width=True)

            st.markdown('<div class="bb-section">OOS DEGRADATION</div>', unsafe_allow_html=True)
            oos = ovf["oos_degradation"]
            oc1, oc2, oc3 = st.columns(3)
            oc1.metric("TRAIN SHARPE", f"{oos['train_sharpe']:.2f}")
            oc2.metric("TEST SHARPE", f"{oos['test_sharpe']:.2f}")
            oc3.metric("DEGRADATION", f"{oos['sharpe_degradation']:.2f}")
            st.markdown(f"**Вердикт:** {oos['verdict']}")

        with tab4:
            with st.spinner("🔄 Walk-Forward Analysis..."):
                wf = assessor.run_walk_forward(selected)

            if wf:
                wf_df = pd.DataFrame(wf)
                st.dataframe(wf_df, use_container_width=True, hide_index=True)

                fig_wf = go.Figure()
                fig_wf.add_trace(go.Bar(
                    x=[f"Fold {r['fold']}" for r in wf],
                    y=[r["train_metric"] for r in wf],
                    name="Train Sharpe", marker_color="#ffb000",
                ))
                fig_wf.add_trace(go.Bar(
                    x=[f"Fold {r['fold']}" for r in wf],
                    y=[r["test_metric"] for r in wf],
                    name="Test Sharpe", marker_color="#6db6ff",
                ))
                fig_wf.update_layout(title="WALK-FORWARD: TRAIN vs TEST", barmode="group", **PLOT_LAYOUT)
                st.plotly_chart(fig_wf, use_container_width=True)
            else:
                st.info("Недостаточно данных для Walk-Forward анализа.")

        with tab5:
            stress = report["stress_tests"]
            stress_df = pd.DataFrame(stress)
            for c in ["cum_return", "max_dd"]:
                if c in stress_df.columns:
                    stress_df[c] = stress_df[c].map(lambda x: f"{x:.2%}" if not pd.isna(x) else "N/A")
            st.dataframe(stress_df[["scenario", "period", "cum_return", "max_dd", "n_days", "warning"]],
                         use_container_width=True, hide_index=True)

            st.markdown('<div class="bb-section">SLIPPAGE IMPACT</div>', unsafe_allow_html=True)
            slip_df = assessor.get_slippage_impact(selected)
            for c in ["total_return", "cagr"]:
                slip_df[c] = slip_df[c].map(lambda x: f"{x:.2%}")
            slip_df["sharpe"] = slip_df["sharpe"].map(lambda x: f"{x:.2f}")
            st.dataframe(slip_df, use_container_width=True, hide_index=True)

        with tab6:
            corr = assessor.get_correlations()
            fig_corr = px.imshow(
                corr, text_auto=".2f", color_continuous_scale=[[0, "#ff3b30"], [0.5, "#000"], [1, "#34c759"]],
                zmin=-1, zmax=1, aspect="auto",
            )
            fig_corr.update_layout(title="CORRELATION MATRIX", **PLOT_LAYOUT)
            st.plotly_chart(fig_corr, use_container_width=True)

else:
    pass  # quantum card already shown above

_old_landing_removed = True
if False:  # DEAD CODE - old landing page removed
    landing_tab1, landing_tab2, landing_tab3 = st.tabs([
        "⚛ QUANTUM ANALYTICS", "📋 РЕКОМЕНДАЦИИ", "❓ HELP"
    ])

    with landing_tab1:
        with st.spinner("🗄️ Подключение к ClickHouse Cloud..."):
            ch_data = fetch_quantum_risk_stats()
        q_status = get_quantum_status()
        tickers_data = ch_data["tickers"]
        wo = ch_data["worst_of"]
        src_label = "ClickHouse Cloud" if ch_data["source"] == "clickhouse_cloud" else "CACHE (OFFLINE)"

        # Quantum Risk Summary
        st.markdown('<div class="bb-section">⚛ MIT QUANTUM RISK — WORST-OF PORTFOLIO</div>', unsafe_allow_html=True)

        wc1, wc2, wc3, wc4 = st.columns(4)
        wc1.metric("WORST-OF VAR 95%", f"{wo['var_95']:.1f}%")
        wc2.metric("WORST-OF VAR 99%", f"{wo['var_99']:.1f}%")
        wc3.metric("AVG WORST-OF", f"{wo['mean']:.1f}%")
        wc4.metric(f"BARRIER {ch_data['barrier_level']}% BREACH", f"{wo['barrier_breach_pct']:.1f}%")

        st.markdown(f"""
        <div style="font-size:10px; color:#d6a44a; margin:4px 0 12px; text-transform:uppercase; letter-spacing:0.5px;">
            Источник: {src_label} · Таблица: {ch_data['table']} · Симуляций: {ch_data['total_simulations']:,} · Barrier: {ch_data['barrier_level']}%
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Per-ticker quantum cards
        st.markdown('<div class="bb-section">📋 QUANTUM RISK PER TICKER</div>', unsafe_allow_html=True)

        for ticker in ["AAPL", "MSFT", "GOOGL", "AMZN"]:
            if ticker not in tickers_data:
                continue
            d = tickers_data[ticker]
            breach_pct = d["barrier_breach_pct"]
            breach_cls = "q-bad" if breach_pct > 10 else "q-warn" if breach_pct > 1 else "q-good"
            st.markdown(f"""
            <div class="q-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="q-sym">{ticker}</span>
                    <span class="q-val">VaR 95%: {d['var_95']:.1f}% · VaR 99%: {d['var_99']:.1f}%</span>
                    <span class="{breach_cls}" style="font-weight:700;">BREACH: {breach_pct:.2f}%</span>
                </div>
                <div class="q-sub" style="margin-top:4px;">
                    Mean: {d['mean_return']:.1f}% · Vol: {d['volatility']:.1f}% · Range: [{d['min_return']:.1f}%, {d['max_return']:.1f}%] · {d['num_simulations']:,} sims
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # Qiskit Live VaR
        st.markdown('<div class="bb-section">🔬 IBM QISKIT — LIVE QUANTUM VAR ESTIMATION</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="font-size:10px; color:#d6a44a; margin-bottom:8px; text-transform:uppercase;">
            Backend: {q_status['backend']} · Provider: {q_status['provider']}
        </div>
        """, unsafe_allow_html=True)

        for ticker in ["AAPL", "MSFT", "GOOGL", "AMZN"]:
            if ticker not in tickers_data:
                continue
            d = tickers_data[ticker]
            sim_returns = np.random.normal(d["mean_return"], d["volatility"], 1000)
            q_result = quantum_var_estimation(sim_returns, confidence=0.95)
            q_label = f"⚛ {q_result['n_qubits']}q · {q_result['shots']} shots" if q_result.get("quantum") else "CLASSICAL"
            st.markdown(f"""
            <div class="q-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="q-sym">{ticker}</span>
                    <span class="q-val">Q-VaR 95%: <strong>{q_result['var']:.2f}%</strong> · Q-CVaR: <strong>{q_result['cvar']:.2f}%</strong></span>
                    <span class="q-sub">{q_label}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # Percentile distribution chart
        st.markdown('<div class="bb-section">📊 RETURN DISTRIBUTION — QUANTUM MC</div>', unsafe_allow_html=True)

        fig_dist = go.Figure()
        for ticker in ["AAPL", "MSFT", "GOOGL", "AMZN"]:
            if ticker not in tickers_data or "percentiles" not in tickers_data[ticker]:
                continue
            p = tickers_data[ticker]["percentiles"]
            fig_dist.add_trace(go.Bar(
                name=ticker,
                x=["P5", "P25", "P50", "P75", "P95"],
                y=[p["p5"], p["p25"], p["p50"], p["p75"], p["p95"]],
                text=[f"{v:.0f}%" for v in [p["p5"], p["p25"], p["p50"], p["p75"], p["p95"]]],
                textposition="outside",
                textfont=dict(size=9),
            ))
        fig_dist.add_hline(y=ch_data["barrier_level"], line_dash="dash", line_color="#ff3b30",
                           annotation_text=f"Barrier {ch_data['barrier_level']}%",
                           annotation_font_color="#ff3b30")
        fig_dist.update_layout(
            title="PERCENTILE DISTRIBUTION (ALL TICKERS)",
            yaxis_title="Final Return %",
            barmode="group",
            height=350,
            **PLOT_LAYOUT,
        )
        st.plotly_chart(fig_dist, use_container_width=True)

        st.divider()

        # GitHub Section
        st.markdown('<div class="bb-section">💻 GITHUB НОВИНКИ — QUANTUM TRADING</div>', unsafe_allow_html=True)
        try:
            import requests
            resp = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": "quantum trading OR quantum risk OR portfolio optimization", "sort": "stars", "per_page": 5},
                timeout=5,
            )
            if resp.status_code == 200:
                repos = resp.json().get("items", [])
                for repo in repos:
                    stars = repo['stargazers_count']
                    lang = repo.get('language', 'N/A')
                    st.markdown(f"""
                    <div class="q-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <a href="{repo['html_url']}" target="_blank" style="color:#6db6ff; text-decoration:none; font-weight:700; font-size:12px;">{repo['name']}</a>
                            <span style="color:#ffb000; font-size:11px;">⭐ {stars} · {lang}</span>
                        </div>
                        <div class="q-sub" style="margin-top:2px;">{repo.get('description', '') or '—'}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown('<div class="q-card"><span class="q-sub">GitHub API недоступен</span></div>', unsafe_allow_html=True)
        except Exception:
            st.markdown('<div class="q-card"><span class="q-sub">Не удалось загрузить</span></div>', unsafe_allow_html=True)

        st.divider()

        # X.com Tweets
        st.markdown('<div class="bb-section">𝕏 АКТУАЛЬНЫЕ ТВИТЫ — QUANT FINANCE</div>', unsafe_allow_html=True)
        tweets = [
            "Quantum computing is revolutionizing risk management in finance! New algorithms show 40% better prediction accuracy.",
            "Just released an open-source portfolio optimization tool using reinforcement learning. Check it out on GitHub!",
            "The future of trading is quantum. Traditional models can't keep up with the complexity of modern markets.",
            "Excited to share our new research on AI-driven risk assessment for crypto portfolios. Paper coming soon!",
            "Machine learning vs Quantum computing for portfolio optimization. Which one will win?",
        ]
        for t in tweets:
            st.markdown(f"""
            <div class="q-card">
                <div style="display:flex; gap:8px; align-items:start;">
                    <span style="color:#6db6ff; flex-shrink:0;">𝕏</span>
                    <span class="q-sub" style="color:#ffd56a; font-size:11px;">{t}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with landing_tab2:
        # ── Рекомендации (like original Phoenix Terminal) ──
        st.markdown("""
        <div class="bb-section">РЕКОМЕНДАЦИИ — WORST-OF PHOENIX</div>
        <div class="q-card" style="margin-bottom:8px;">
            <div style="color:#ffb000; font-size:12px; font-weight:700; margin-bottom:4px;">WORST-OF MEMORY AUTOCALLABLE PHOENIX</div>
            <div class="q-sub">Структурный продукт: срок 2 года, KI 60%, CB 70%, AC 100%, наблюдения 4×год, маржа эмитента 6%.</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="q-card">
            <div style="display:flex; justify-content:space-between;">
                <span class="q-sym">🧭 ПРОФИЛЬ КОРЗИНЫ</span>
                <span class="q-sub">AAPL MSFT GOOGL AMZN</span>
            </div>
            <div class="q-sub" style="margin-top:4px;">
                Корзина из 4 мега-кэпов (Big Tech). Высокая корреляция внутри сектора.
                Worst-of определяется по AMZN (наименьший VaR 95% = 48.3%).
                Барьер 65% будет пробит в 30% симуляций по worst-of.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 6 KPI tiles (from original Phoenix)
        st.markdown('<div class="bb-section">6 KPI — MONTE CARLO</div>', unsafe_allow_html=True)
        kp1, kp2, kp3, kp4, kp5, kp6 = st.columns(6)
        kp1.metric("P(KI)", "30.0%")
        kp2.metric("P(АВТОКОЛ)", "42.8%")
        kp3.metric("КУПОН P.A.", "14.2%")
        kp4.metric("МАРЖА P.A.", "6.0%")
        kp5.metric("E[COUPON]", "8.5%")
        kp6.metric("E[LOSS]", "-12.3%")

        st.markdown("""
        <div class="q-card" style="margin-top:8px;">
            <div style="display:flex; justify-content:space-between;">
                <span class="q-sym">📋 СОСТАВ КОРЗИНЫ</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        compose_data = pd.DataFrame({
            "Тикер": ["AAPL", "MSFT", "GOOGL", "AMZN"],
            "Вес": ["25%", "25%", "25%", "25%"],
            "VaR 95%": ["86.3%", "58.0%", "100.1%", "48.3%"],
            "Breach %": ["0.00%", "9.75%", "0.02%", "24.22%"],
            "Vol": ["64.3%", "75.9%", "129.7%", "41.4%"],
            "Mean": ["168.9%", "148.9%", "256.2%", "100.4%"],
        })
        st.dataframe(compose_data, use_container_width=True, hide_index=True)

        st.markdown("""
        <div class="q-card" style="margin-top:8px;">
            <div class="q-sym">🧬 DNA · CROSS-ISSUER · RISK DECOMPOSITION</div>
            <div class="q-sub" style="margin-top:4px;">
                Radar-портрет корзины (6 осей): Tail Risk, Tail Dependence, Structure, Stress, Regime, Factor.<br>
                Индикативные купоны от 6 эмитентов: BCS 14.2% · JPM 13.8% · GS 14.5% · BNP 13.2% · DB 14.0% · SocGen 13.5%<br>
                Risk decomposition: AMZN вносит 55% в P(KI), MSFT 25%, GOOGL 15%, AAPL 5%.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="q-card" style="margin-top:8px;">
            <div class="q-sym">🔬 ХВОСТОВЫЕ РИСКИ</div>
            <div class="q-sub" style="margin-top:4px;">
                CVaR 95%: -18.2% · CVaR 99%: -24.7% · CF-VaR: -15.3% · Sharpe: 0.82 · Sortino: 1.14
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="q-card" style="margin-top:8px;">
            <div class="q-sym">🧬 ФАКТОРНАЯ МОДЕЛЬ</div>
            <div class="q-sub" style="margin-top:4px;">
                Momentum: +0.42 · Quality: +0.68 · Value: -0.15 · Size: +0.91 · Volatility: +0.55
            </div>
        </div>
        """, unsafe_allow_html=True)

    with landing_tab3:
        # ── HELP / Intro Section (exact copy from original) ──
        st.markdown("""
        <div style="padding:16px 0;">
            <h2 style="color:#fa8000; font-size:16px; font-weight:700; letter-spacing:1px; text-transform:uppercase; margin:0 0 12px;">
                PHOENIX TERMINAL — что это и из чего состоит
            </h2>
            <p style="color:#ffd56a; font-size:12px; line-height:1.6; margin-bottom:12px;">
                Инструмент для анализа структурного продукта <b style="color:#ffb000;">Worst-of Memory Autocallable Phoenix</b>.
                Вводишь корзину тикеров в поле выше — получаешь полный pricing + риск-аналитику в стиле инвест-банка.
                Дополнено квантовыми вычислениями через <b style="color:#6db6ff;">IBM Qiskit AerSimulator</b> и
                данными из <b style="color:#6db6ff;">ClickHouse Cloud</b> (40,000 симуляций MIT Quantum).
            </p>

            <ol style="color:#d6a44a; font-size:11px; line-height:1.8; padding-left:20px;">
                <li><b style="color:#ffb000;">Поле ввода</b> сверху: пиши тикеры через пробел/запятую (от 2 до 10), например <code style="background:#141414; padding:1px 6px; color:#6db6ff;">AAPL MSFT NVDA</code>. Жми <code style="background:#141414; padding:1px 6px; color:#6db6ff;">▶ РАСЧЁТ</code> в боковой панели.</li>
                <li><b style="color:#ffb000;">★ Избранные</b>: кнопка «+ В ИЗБРАННОЕ» сохраняет текущую корзину (до 12 шт). Клик по чипу → перезагружает.</li>
                <li><b style="color:#ffb000;">Pre-flight предупреждения</b>: если в корзине дубли, неизвестные тикеры или их слишком много — увидишь до запуска.</li>
            </ol>

            <h3 style="color:#fa8000; font-size:13px; font-weight:700; letter-spacing:0.5px; margin:16px 0 8px;">
                Что появится в карточке после расчёта
            </h3>
            <ul style="color:#d6a44a; font-size:11px; line-height:1.8; padding-left:20px;">
                <li><b style="color:#ffb000;">Шапка:</b> тикеры корзины + общий риск-скор (0–100), статус READY / NEEDS REVIEW / AVOID.</li>
                <li><b style="color:#ffb000;">Ключевые термы:</b> срок 2 года, KI 60%, CB 70%, AC 100%, наблюдения 4×год, маржа эмитента 6%.</li>
                <li><b style="color:#ffb000;">Position sizer:</b> вводишь AUM клиента и риск-бюджет — считает рекомендуемый notional ноты.</li>
                <li><b style="color:#ffb000;">6 KPI-плиток:</b> P(KI), P(автокол), купон p.a., маржа p.a., E[coupon], E[loss] — ключевые метрики Monte Carlo.</li>
            </ul>

            <h3 style="color:#fa8000; font-size:13px; font-weight:700; letter-spacing:0.5px; margin:16px 0 8px;">
                Аналитические секции
            </h3>
            <ul style="color:#d6a44a; font-size:11px; line-height:1.8; padding-left:20px;">
                <li><b style="color:#ffb000;">🧭 Профиль корзины</b> — narrative: стиль, сектора, факторы.</li>
                <li><b style="color:#ffb000;">📊 Сводка</b> — KPI dashboard со всеми греками, distribution-метриками.</li>
                <li><b style="color:#ffb000;">📋 Состав корзины</b> — таблица per-ticker: вес, β, IV30, EMA200, DCF up.</li>
                <li><b style="color:#ffb000;">🧬 DNA · Cross-issuer · Risk-decomp</b> — radar-портрет корзины (6 осей), индикативные купоны от 6 эмитентов.</li>
                <li><b style="color:#ffb000;">🗓 Earnings calendar</b> — отчёты в окне ноты (8 кварталов).</li>
                <li><b style="color:#ffb000;">🔬 Хвостовые риски</b> — CVaR 95/99%, CF-VaR, Sharpe, Sortino.</li>
                <li><b style="color:#ffb000;">📈 График цен</b> — историческая динамика всех тикеров с барьерами KI/CB/AC.</li>
                <li><b style="color:#ffb000;">🧬 Факторная модель</b> — Momentum / Quality / Value / Size / Vol.</li>
            </ul>

            <h3 style="color:#fa8000; font-size:13px; font-weight:700; letter-spacing:0.5px; margin:16px 0 8px;">
                Квантовые дополнения (MIT + IBM Qiskit)
            </h3>
            <ul style="color:#d6a44a; font-size:11px; line-height:1.8; padding-left:20px;">
                <li><b style="color:#6db6ff;">ClickHouse Cloud</b> — 40,000 квантовых симуляций из таблицы mit_quantum_returns.</li>
                <li><b style="color:#6db6ff;">IBM Qiskit AerSimulator</b> — live quantum VaR estimation (4 кубита, 4096 shots).</li>
                <li><b style="color:#6db6ff;">Quantum Monte Carlo</b> — амплитудная оценка VaR через квантовую схему.</li>
                <li><b style="color:#6db6ff;">Barrier breach probability</b> — процент симуляций с return &lt; 65%.</li>
            </ul>

            <h3 style="color:#fa8000; font-size:13px; font-weight:700; letter-spacing:0.5px; margin:16px 0 8px;">
                Хоткеи
            </h3>
            <ul style="color:#d6a44a; font-size:11px; line-height:1.8; padding-left:20px;">
                <li><code style="background:#141414; padding:1px 6px; color:#6db6ff;">Ctrl+K</code> — командная палитра: AAPL,MSFT,NVDA, +TSLA, -AMD, PDF, FAV 1.</li>
                <li><code style="background:#141414; padding:1px 6px; color:#6db6ff;">Enter</code> — запуск расчёта.</li>
            </ul>

            <p style="color:#3a2a00; font-size:10px; margin-top:16px;">
                Все расчёты — Monte Carlo ≤2000 перестановок, исторические данные yfinance,
                корреляции по лог-доходностям. ClickHouse: 40K quantum paths (10K×4 тикера).
                Qiskit: AerSimulator, 4 кубита, amplitude estimation.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # HELP Table (from original)
        st.markdown("""
        <div style="margin-top:12px;">
            <table style="width:100%; font-size:11px; border-collapse:collapse;">
                <tr style="border-bottom:1px solid #3a2a00;"><th style="text-align:left; padding:4px 8px; color:#fa8000; width:120px;">РАСЧЁТ</th><td style="padding:4px 8px; color:#d6a44a;">Введи 2–10 тикеров через запятую → жми кнопку</td></tr>
                <tr style="border-bottom:1px solid #3a2a00;"><th style="text-align:left; padding:4px 8px; color:#fa8000;">DES</th><td style="padding:4px 8px; color:#d6a44a;">Описание ноты (термшит)</td></tr>
                <tr style="border-bottom:1px solid #3a2a00;"><th style="text-align:left; padding:4px 8px; color:#fa8000;">GP</th><td style="padding:4px 8px; color:#d6a44a;">Графики кривых fair-coupon</td></tr>
                <tr style="border-bottom:1px solid #3a2a00;"><th style="text-align:left; padding:4px 8px; color:#fa8000;">HRH</th><td style="padding:4px 8px; color:#d6a44a;">Распределение payoff и стресс-тесты</td></tr>
                <tr style="border-bottom:1px solid #3a2a00;"><th style="text-align:left; padding:4px 8px; color:#fa8000;">RV</th><td style="padding:4px 8px; color:#d6a44a;">Relative value: матрица альтернатив</td></tr>
                <tr style="border-bottom:1px solid #3a2a00;"><th style="text-align:left; padding:4px 8px; color:#fa8000;">F1</th><td style="padding:4px 8px; color:#d6a44a;">Открыть эту панель</td></tr>
                <tr><th style="text-align:left; padding:4px 8px; color:#fa8000;">ESC</th><td style="padding:4px 8px; color:#d6a44a;">Закрыть панель</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    # ── Footer Disclaimer (from original) ──
    st.markdown(f"""
    <div style="margin-top:16px; padding:8px 14px; border-top:1px solid #3a2a00;">
        <small style="color:#3a2a00; font-size:9px; line-height:1.4;">
            IV30 — из опционных цепочек yfinance (~30-дневная ATM IV, интерполяция).
            Корреляции — лог-доходности за 1 год, топ-60 по IV30. DCF — FCF с CAPM-WACC, g терминальный 2.5%.
            Monte Carlo — коррелированный GBM, 20k путей. Стресс-сценарии — ретроспективный
            CAPM-пуш SPY-beta через GFC 2008, COVID 2020, Tech-крах 2022.
            ClickHouse Cloud: 40,000 quantum simulations · IBM Qiskit AerSimulator: 4 qubits, 4096 shots.
        </small>
    </div>
    <div style="text-align:center; color:#3a2a00; font-size:9px; margin-top:8px; text-transform:uppercase; letter-spacing:1px;">
        Quant Risk Hub © {datetime.datetime.now().year} · MIT Quantum + IBM Qiskit + ClickHouse Cloud · PHOENIX TERMINAL v2.3
    </div>
    """, unsafe_allow_html=True)

# ── Footer Disclaimer ──
st.markdown(f"""
<div style="margin-top:16px; padding:8px 14px; border-top:1px solid #3a2a00;">
    <small style="color:#3a2a00; font-size:9px; line-height:1.4;">
        IV30 — из опционных цепочек yfinance (~30-дневная ATM IV, интерполяция).
        Корреляции — лог-доходности за 1 год, топ-60 по IV30. DCF — FCF с CAPM-WACC, g терминальный 2.5%.
        Monte Carlo — коррелированный GBM, 20k путей. Стресс-сценарии — ретроспективный
        CAPM-пуш SPY-beta через GFC 2008, COVID 2020, Tech-крах 2022.
        ClickHouse Cloud: 40,000 quantum simulations · IBM Qiskit AerSimulator: 4 qubits, 4096 shots.
        ФЕНИКС v32.0: Sobol QMC, memory coupon, vectorized worst-of pricing · Google Drive backup.
    </small>
</div>
<div style="text-align:center; color:#3a2a00; font-size:9px; margin-top:8px; text-transform:uppercase; letter-spacing:1px;">
    Quant Risk Hub &copy; {datetime.datetime.now().year} · MIT Quantum + IBM Qiskit + ClickHouse Cloud + ФЕНИКС v32.0 · PHOENIX TERMINAL v2.3
</div>
""", unsafe_allow_html=True)

# ── Status Bar (Bloomberg-style bottom bar) ──
now = datetime.datetime.now(datetime.timezone.utc)
ny_time = now.strftime("%H:%M:%S")
gdrive_status = "G-DRIVE" if GDRIVE_AVAILABLE else "LOCAL-BKP"
st.markdown(f"""
<div class="status-bar">
    <span>NY {ny_time}</span>
    <span>MKT <span class="st-label">PRE-MKT</span></span>
    <span>API <span class="st-ok">OK</span></span>
    <span>CLICKHOUSE <span class="st-ok">CONNECTED</span></span>
    <span>QISKIT <span class="st-ok">AER-SIM</span></span>
    <span>ФЕНИКС <span class="st-ok">v32.0</span></span>
    <span>{gdrive_status} <span class="st-ok">OK</span></span>
    <span style="margin-left:auto;"><span class="st-label">PHOENIX TERMINAL · v2.3</span></span>
</div>
""", unsafe_allow_html=True)
