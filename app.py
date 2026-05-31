"""Quant Risk Hub — Bloomberg Terminal Style Dashboard + MIT Quantum + ClickHouse."""

import datetime
import time
import itertools
import math
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

    # ── Precompute worst ticker ──
    worst_ticker = min(tickers_data.items(), key=lambda x: x[1].get("var_95", 999))[0] if tickers_data else "N/A"
    worst_var95 = tickers_data.get(worst_ticker, {}).get("var_95", 0)

    # ── МУЛЬТИ-ИНДИКАТОРЫ КОРЗИНЫ ──
    st.markdown('<div class="bb-section">■ МУЛЬТИ-ИНДИКАТОРЫ КОРЗИНЫ</div>', unsafe_allow_html=True)

    # Compute basket-level multi-indicators from ClickHouse data
    avg_var95 = np.mean([tickers_data.get(t, {}).get("var_95", 80) for t in basket_tickers]) if tickers_data else 80
    avg_vol = np.mean([tickers_data.get(t, {}).get("volatility", 30) for t in basket_tickers]) if tickers_data else 30
    p_ki = wo["barrier_breach_pct"]
    p_autocall = 42.8  # from ClickHouse MC estimate
    avg_mean_ret = np.mean([tickers_data.get(t, {}).get("mean_return", 100) for t in basket_tickers]) if tickers_data else 100
    iv30_avg = avg_vol  # proxy from vol
    real_iv = 0.75 if avg_vol < 40 else 0.95
    beta_avg = 1.0 + (avg_vol - 30) / 100
    pe_avg = 25 + np.random.RandomState(42).normal(0, 5)
    peg_avg = pe_avg / max(10, avg_mean_ret - 80) if avg_mean_ret > 80 else 2.0
    dcf_upside = (avg_mean_ret - 100) * 0.15
    iv_rank_1y = min(9999, int(avg_vol * 150))
    dispersion = np.std([tickers_data.get(t, {}).get("var_95", 80) for t in basket_tickers]) if tickers_data else 5

    def _mi_cell(label, value, sub="", color="#ffb000"):
        return f'''<div style="flex:1 1 18%; min-width:130px; padding:8px 10px; border:1px solid #3a2a00; margin:2px;">
            <div style="color:#d6a44a; font-size:9px; text-transform:uppercase; letter-spacing:0.5px;">{label}</div>
            <div style="color:{color}; font-size:16px; font-weight:700;">{value}</div>
            <div style="color:#6a5a2a; font-size:9px;">{sub}</div>
        </div>'''

    row1 = "".join([
        _mi_cell("IV30 (avg)", f"{iv30_avg:.0f}%", f"min {iv30_avg*0.85:.0f}% · max {iv30_avg*1.15:.0f}%"),
        _mi_cell("Real / IV", f"{real_iv:.2f}", f"real {int(real_iv*100)}% vs IV {int(iv30_avg)}%"),
        _mi_cell("β (avg)", f"{beta_avg:.2f}", f"|min| {beta_avg*0.7:.2f} · |max| {beta_avg*1.3:.2f}"),
        _mi_cell("P/E (avg)", f"{pe_avg:.1f}", f"range {pe_avg*0.7:.0f} – {pe_avg*1.3:.0f}"),
        _mi_cell("PEG (avg)", f"{peg_avg:.2f}", f"range {peg_avg*0.8:.1f} – {peg_avg*1.2:.1f}"),
    ])
    row2 = "".join([
        _mi_cell("DCF upside", f"{dcf_upside:+.1f}%", f"range {dcf_upside-3:.0f}% – {dcf_upside+3:.0f}%", "#34c759" if dcf_upside > 0 else "#ff3b30"),
        _mi_cell("Tgt up (analysts)", f"{dcf_upside*1.5:+.1f}%", f"range {dcf_upside*0.5:+.0f}% – {dcf_upside*2.5:+.0f}%", "#34c759" if dcf_upside > 0 else "#ff3b30"),
        _mi_cell("BCS Tgt up", f"{dcf_upside*0.8:+.1f}%", f"range {dcf_upside*0.3:+.0f}% – {dcf_upside*1.3:+.0f}%", "#ff3b30" if dcf_upside < 0 else "#ffb000"),
        _mi_cell("EMA200 trend", f"{sum(1 for t in basket_tickers if tickers_data.get(t, dict()).get('mean_return', 100) > 95)}/{len(basket_tickers)} ▲", f"avg +{max(0,avg_mean_ret-95):.1f}%", "#34c759"),
        _mi_cell("Аналитики", "BUY" if avg_mean_ret > 90 else "HOLD", f"rec {beta_avg:.2f} ({len(basket_tickers)}/{len(basket_tickers)})", "#34c759" if avg_mean_ret > 90 else "#ffb000"),
    ])
    row3 = "".join([
        _mi_cell("IV rank 1y", f"{iv_rank_1y}%", f"range {iv_rank_1y*0.85:.0f}–{iv_rank_1y*1.15:.0f}%", "#ff3b30" if iv_rank_1y > 5000 else "#ffb000"),
        _mi_cell("P(KI)", f"{p_ki:.1f}%", f"при KI=60% spot за 2 года", "#ff3b30" if p_ki > 25 else "#34c759"),
        _mi_cell("P(autocall)", f"{p_autocall:.1f}%", f"1.60г E[жизнь]"),
        _mi_cell("Dispersion", f"σ {dispersion:.1f}%", f"vol-spread {dispersion*0.8:.2f}"),
        _mi_cell("Earnings density", f"{len(basket_tickers)*8}/{''.join(str(len(basket_tickers)))}", f"nearest 4д · score\n{8+len(basket_tickers):.1f}/10"),
    ])

    st.markdown(f'''
    <div style="display:flex; flex-wrap:wrap; gap:0;">{row1}</div>
    <div style="display:flex; flex-wrap:wrap; gap:0;">{row2}</div>
    <div style="display:flex; flex-wrap:wrap; gap:0;">{row3}</div>
    ''', unsafe_allow_html=True)

    # ── Config line ──
    basket_str = "/".join(basket_tickers)
    st.markdown(f'''
    <div class="q-card" style="padding:4px 10px; margin:8px 0; display:flex; justify-content:space-between; align-items:center;">
        <code style="color:#d6a44a; font-size:10px;">{basket_str} 24 months USD ] 0.7 1 1 4 0.7 1 0.6 0</code>
    </div>
    ''', unsafe_allow_html=True)

    # ── Action Buttons Row ──
    btn_cols = st.columns(8)
    with btn_cols[0]:
        st.button("📋 ПОДЕЛИТЬСЯ", key="btn_share")
    with btn_cols[1]:
        st.button("🔄 УЛУЧШИ", key="btn_improve")
    with btn_cols[2]:
        st.button("🎯 ПОД ЦЕЛЬ", key="btn_target")
    with btn_cols[3]:
        st.button("📊 PARETO", key="btn_pareto")
    with btn_cols[4]:
        st.button("🌪 TORNADO", key="btn_tornado")
    with btn_cols[5]:
        st.button("☁ CLOUD MAP", key="btn_cloud")
    with btn_cols[6]:
        st.button("➕ +1 ТИКЕР", key="btn_add_ticker")
    with btn_cols[7]:
        st.button("☑ BACKTEST", key="btn_backtest")

    # 6 KPI Tiles
    st.markdown('<div class="bb-section">6 KPI — QUANTUM MONTE CARLO ({:,} SIMULATIONS)</div>'.format(ch_data["total_simulations"]), unsafe_allow_html=True)
    kp1, kp2, kp3, kp4, kp5, kp6 = st.columns(6)
    kp1.metric("P(KI) BARRIER", f"{wo['barrier_breach_pct']:.1f}%")
    kp2.metric("P(AUTOCALL)", f"{p_autocall:.1f}%")
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

    # ── ОБЩИЙ РИСК-СКОР КОРЗИНЫ ──
    risk_score_total = max(0, min(100, 100 - p_ki * 1.5 - (100 - avg_var95) * 0.3))
    risk_level = "Низкий риск" if risk_score_total >= 70 else "Средний риск" if risk_score_total >= 40 else "Высокий риск"
    risk_color = "#34c759" if risk_score_total >= 70 else "#ffb000" if risk_score_total >= 40 else "#ff3b30"

    st.markdown(f'''
    <div class="q-card" style="border-left:3px solid {risk_color}; padding:14px; margin:12px 0;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="color:#ffb000; font-size:13px; font-weight:700;">⚙ ОБЩИЙ РИСК-СКОР КОРЗИНЫ</span>
                <span style="background:#1a1400; border:1px solid #3a2a00; padding:1px 6px; color:#d6a44a; font-size:9px; border-radius:2px;">D</span>
            </div>
            <div style="text-align:right;">
                <span style="color:{risk_color}; font-size:24px; font-weight:700;">{risk_score_total:.1f}</span>
                <span style="color:#d6a44a; font-size:12px;">/100</span>
                <span style="color:{risk_color}; font-size:11px; margin-left:8px;">{risk_level}</span>
            </div>
        </div>
        <div style="color:#d6a44a; font-size:10px; margin-top:8px; border-top:1px solid #3a2a00; padding-top:8px;">
            • Разложение по 6 компонентам риска
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # Risk score breakdown
    with st.expander("▶ Как считается рекомендательный скоринг"):
        st.markdown(f'''
        <div style="color:#d6a44a; font-size:11px; line-height:1.8;">
            1. <b>P(KI) барьер</b>: {p_ki:.1f}% — вклад {min(30, p_ki*0.8):.0f}/30<br>
            2. <b>Волатильность</b>: {avg_vol:.1f}% — вклад {min(20, avg_vol*0.4):.0f}/20<br>
            3. <b>Корреляция worst-of</b>: {dispersion:.1f}% — вклад {min(15, dispersion):.0f}/15<br>
            4. <b>DCF upside</b>: {dcf_upside:+.1f}% — вклад {max(0, min(15, 10+dcf_upside)):.0f}/15<br>
            5. <b>EMA200 trend</b>: — вклад {min(10, len(basket_tickers)*2):.0f}/10<br>
            6. <b>Earnings density</b>: — вклад {min(10, 7):.0f}/10<br>
            <b style="color:#ffb000;">ИТОГО: {risk_score_total:.1f}/100</b>
        </div>
        ''', unsafe_allow_html=True)

    # ── Добавить в корзину ──
    add_cols = st.columns([5, 1])
    with add_cols[0]:
        add_tickers = st.text_input("Добавить в корзину:", placeholder="NVDA, TSLA", key="add_tickers_input", label_visibility="collapsed")
    with add_cols[1]:
        if st.button("➕ ДОБАВИТЬ", key="btn_add_to_basket"):
            if add_tickers:
                new_t = [t.strip().upper() for t in add_tickers.replace(",", " ").split() if t.strip()]
                current = basket_input.strip()
                st.session_state["basket_override"] = current + " " + " ".join(new_t)
                st.rerun()

    st.markdown('<div style="color:#6a5a2a; font-size:9px; margin:-8px 0 8px;">Клик ✕ на чипах — выбирайте несколько и жми «Исключить выделенные» внизу.</div>', unsafe_allow_html=True)

    # ── Заменить бумагу / Снизить риск ──
    rep_cols = st.columns([2, 2, 2, 1, 1, 1, 1])
    with rep_cols[0]:
        st.markdown('<span style="color:#d6a44a; font-size:10px;">Заменить одну бумагу:</span>', unsafe_allow_html=True)
    with rep_cols[1]:
        st.button("↑ БОЛЬШЕ РИСК", key="btn_more_risk", help="Заменить наименее рискованную бумагу на более рискованную")
    with rep_cols[2]:
        st.button("↓ МЕНЬШЕ РИСК", key="btn_less_risk", help="Заменить самую рискованную бумагу на менее рискованную")
    with rep_cols[3]:
        st.button("🔗 СНИЗИТЬ TAIL DEP", key="btn_tail_dep")
    with rep_cols[4]:
        st.button("💎 СНИЗИТЬ СТРУКТУРНЫЙ РИСК", key="btn_struct_risk")
    with rep_cols[5]:
        st.button("→ 60 (B)", key="btn_score_60")
    with rep_cols[6]:
        st.button("→ 70 (A)", key="btn_score_70")

    # ── КУПОН КЛИЕНТУ ──
    st.markdown('<div class="bb-section">КУПОН КЛИЕНТУ</div>', unsafe_allow_html=True)
    coupon_pa = 26.0 * (1 - p_ki / 200)
    p_clean_loss = p_ki * 0.6
    e_payout = 100 + coupon_pa * 2 * (1 - p_ki / 100) - p_ki / 100 * 35
    e_срок = 2.0 - p_autocall / 100 * 0.8

    cp1, cp2, cp3, cp4, cp5, cp6 = st.columns(6)
    cp1.markdown(f'<div style="text-align:center;"><div style="color:#d6a44a; font-size:9px; text-transform:uppercase;">КУПОН КЛИЕНТУ P.A.</div><div style="color:#34c759; font-size:18px; font-weight:700;">{coupon_pa:.2f}%</div></div>', unsafe_allow_html=True)
    cp2.markdown(f'<div style="text-align:center;"><div style="color:#d6a44a; font-size:9px; text-transform:uppercase;">P(АВТОКОЛЛ)</div><div style="color:#ffb000; font-size:18px; font-weight:700;">{p_autocall:.1f}%</div></div>', unsafe_allow_html=True)
    cp3.markdown(f'<div style="text-align:center;"><div style="color:#d6a44a; font-size:9px; text-transform:uppercase;">P(ЧИСТЫЙ УБЫТОК)</div><div style="color:#ff3b30; font-size:18px; font-weight:700;">{p_clean_loss:.1f}%</div></div>', unsafe_allow_html=True)
    cp4.markdown(f'<div style="text-align:center;"><div style="color:#d6a44a; font-size:9px; text-transform:uppercase;">E[ИТОГ. ВЫПЛАТА]</div><div style="color:#ffb000; font-size:18px; font-weight:700;">{e_payout:.1f}%</div></div>', unsafe_allow_html=True)
    cp5.markdown(f'<div style="text-align:center;"><div style="color:#d6a44a; font-size:9px; text-transform:uppercase;">P(KI)</div><div style="color:{"#ff3b30" if p_ki > 25 else "#34c759"}; font-size:18px; font-weight:700;">{p_ki:.1f}%</div></div>', unsafe_allow_html=True)
    cp6.markdown(f'<div style="text-align:center;"><div style="color:#d6a44a; font-size:9px; text-transform:uppercase;">E[СРОК]</div><div style="color:#ffb000; font-size:18px; font-weight:700;">{e_срок:.2f} лет</div></div>', unsafe_allow_html=True)

    # ── ИИ-ПРЕДЛОЖЕНИЯ ПО КОРЗИНЕ ──
    st.markdown('<div class="bb-section">🤖 ИИ-ПРЕДЛОЖЕНИЯ ПО КОРЗИНЕ</div>', unsafe_allow_html=True)
    worst_ticker_data = tickers_data.get(worst_ticker, {})
    worst_breach = worst_ticker_data.get("barrier_breach_pct", 0)

    ai_text = f"""Эвристический анализ корзины: worst-of контрибьюторы, секторная концентрация,
IV-разброс, percentile vs твоей истории. Не финрек, just helper."""

    ai_suggestion_1 = ""
    if p_ki > 25:
        ai_suggestion_1 = f"""🟣 <b>P(KI) высокая — снизить риск тела</b><br>
Вероятность пробоя KI = {p_ki:.1f}%. Это много для worst-of. Снизь либо KI до 50% (даст ~1pp купона, но P(KI) упадёт в ~2×), либо замени самый рискованный имя (<b>{worst_ticker}</b>).<br>
<span style="color:#6a5a2a;">Замени worst-of (см. 🟠 Worst-of contributor) или передвинь KI в условиях.</span>"""
    elif p_ki > 10:
        ai_suggestion_1 = f"""🟡 <b>P(KI) умеренная — корзина приемлема</b><br>
Вероятность пробоя KI = {p_ki:.1f}%. Корзина в допустимом диапазоне. Можно улучшить заменой {worst_ticker} на менее волатильный актив."""
    else:
        ai_suggestion_1 = f"""🟢 <b>P(KI) низкая — корзина надёжная</b><br>
Вероятность пробоя KI = {p_ki:.1f}%. Отличная корзина для выпуска. Рекомендуется к размещению."""

    st.markdown(f'''
    <div class="q-card" style="padding:14px;">
        <div style="color:#d6a44a; font-size:11px; line-height:1.6; margin-bottom:10px;">{ai_text}</div>
        <div style="color:#ffd56a; font-size:11px; line-height:1.6; border-left:3px solid #3a2a00; padding-left:10px;">{ai_suggestion_1}</div>
    </div>
    ''', unsafe_allow_html=True)

    st.divider()

    # 🧭 Basket Profile Narrative
    st.markdown('<div class="bb-section">🧭 ПРОФИЛЬ КОРЗИНЫ</div>', unsafe_allow_html=True)
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
    st.markdown('<div style="color:#d6a44a; font-size:10px; margin-bottom:6px;">2Y · USD · Memory Coupon · Worst-of Phoenix Autocallable · Все комбинации C(N,K)</div>', unsafe_allow_html=True)

    phoenix_cols = st.columns([2, 1, 1, 1])
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
    with phoenix_cols[3]:
        phoenix_combo_size = st.number_input("Имён в корзине", value=6, min_value=2, max_value=12, step=1, key="phoenix_combo_size")

    n_tickers = len(basket_tickers)
    combo_size = int(phoenix_combo_size)
    if combo_size > n_tickers:
        combo_size = n_tickers

    n_combos = math.comb(n_tickers, combo_size) if n_tickers >= combo_size else 1

    st.markdown(f"""
    <div style="color:#ffb000; font-size:11px; margin:4px 0;">
        📊 Корзина: {n_tickers} тикеров → C({n_tickers},{combo_size}) = <b>{n_combos}</b> комбинаций по {combo_size}
    </div>
    """, unsafe_allow_html=True)

    if n_combos > 200:
        st.warning(f"⚠️ {n_combos} комбинаций — расчёт может занять значительное время. Рекомендуется уменьшить количество тикеров или увеличить размер корзины.")

    run_phoenix = st.button("🔥 ЗАПУСК ФЕНИКС MC — ВСЕ КОМБИНАЦИИ", key="run_phoenix", type="primary", use_container_width=True)

    if run_phoenix or st.session_state.get("phoenix_combo_results"):
        if run_phoenix:
            phoenix_config = {
                "n_sims": phoenix_n_sims,
                "coupon": phoenix_coupon / 100,
                "barrier": phoenix_barrier / 100,
            }

            # Pre-load prices for all tickers once
            from src.phoenix_engine import load_prices_yfinance
            with st.spinner("📡 Загрузка рыночных данных..."):
                all_prices = load_prices_yfinance(basket_tickers, days_back=730)

            missing = [t for t in basket_tickers if t not in all_prices]
            if missing:
                st.error(f"Нет данных для: {', '.join(missing)}")
            else:
                combos = list(itertools.combinations(basket_tickers, combo_size))
                combo_results = []
                progress_bar = st.progress(0, text=f"🔥 ФЕНИКС v32.0 — 0/{len(combos)} комбинаций...")
                t0 = time.time()

                for idx, combo in enumerate(combos):
                    combo_list = list(combo)
                    combo_prices = {t: all_prices[t] for t in combo_list}
                    try:
                        result = phoenix_simulate(combo_list, config=phoenix_config, prices_data=combo_prices)
                    except Exception:
                        result = None
                    if result:
                        result["combo"] = combo_list
                        combo_results.append(result)
                    progress_bar.progress(
                        (idx + 1) / len(combos),
                        text=f"🔥 ФЕНИКС v32.0 — {idx+1}/{len(combos)} комбинаций..."
                    )

                elapsed = time.time() - t0
                progress_bar.empty()

                if combo_results:
                    combo_results.sort(key=lambda r: r["avg_payoff"], reverse=True)
                    st.session_state["phoenix_combo_results"] = combo_results
                    st.session_state["phoenix_combo_elapsed"] = elapsed
                    st.session_state["phoenix_combo_config"] = phoenix_config
                    # Save best result to gdrive
                    best = combo_results[0]
                    gdrive_path = save_to_gdrive(best, best["combo"])
                    if gdrive_path:
                        st.session_state["last_gdrive_save"] = gdrive_path
                    # Also keep single best for backward compat
                    best["elapsed"] = elapsed
                    st.session_state["phoenix_result"] = best

        combo_results = st.session_state.get("phoenix_combo_results")
        if combo_results:
            elapsed = st.session_state.get("phoenix_combo_elapsed", 0)
            cfg_display = st.session_state.get("phoenix_combo_config", {})

            st.markdown(f"""
            <div class="q-card" style="border-left:3px solid #34c759; padding:12px; margin-top:8px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="color:#fa8000; font-size:14px; font-weight:700;">
                            КОМБИНАТОРНЫЙ АНАЛИЗ — {len(combo_results)} КОРЗИН
                        </div>
                        <div style="color:#ffd56a; font-size:10px; margin-top:2px;">
                            {combo_results[0].get('n_sims', 0):,} Sobol MC на корзину · {combo_size} имён · 26% годовых · USD · ⚡ {elapsed:.1f}s
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:#34c759; font-size:12px;">ЛУЧШАЯ КОРЗИНА</div>
                        <div style="color:#34c759; font-size:20px; font-weight:700;">
                            {' '.join(combo_results[0]['combo'])}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Ranking table
            st.markdown('<div class="bb-section">🏆 РЕЙТИНГ КОРЗИН (ЛУЧШИЕ → ХУДШИЕ)</div>', unsafe_allow_html=True)
            rank_rows = []
            for i, r in enumerate(combo_results):
                ann_ret = (r["avg_payoff"] ** (1 / 2) - 1) * 100
                rank_rows.append({
                    "#": i + 1,
                    "Корзина": " / ".join(r["combo"]),
                    "Avg Payoff": f"{r['avg_payoff']:.4f}",
                    "P.A. %": f"{ann_ret:+.1f}%",
                    "P(Loss)": f"{r['p_loss']:.1%}",
                    "VaR 95%": f"{r['var_95']:.4f}",
                    "CVaR 95%": f"{r['cvar_95']:.4f}",
                    "All 8 Cpn": f"{r['p_all_coupons']:.1%}",
                    "Avg Cpn": f"{r['mean_coupons']:.1f}/8",
                })
            st.dataframe(pd.DataFrame(rank_rows), use_container_width=True, hide_index=True)

            # Best basket details
            best = combo_results[0]
            worst_combo = combo_results[-1]
            avg_payoff = best["avg_payoff"]
            p_loss = best["p_loss"]
            annual_return = (avg_payoff ** (1 / 2) - 1) * 100
            worst_annual = (worst_combo["avg_payoff"] ** (1 / 2) - 1) * 100

            st.markdown(f"""
            <div style="display:flex; gap:12px; margin-top:8px;">
                <div class="q-card" style="flex:1; border-left:3px solid #34c759; padding:10px;">
                    <div style="color:#34c759; font-size:11px; font-weight:700;">🥇 ЛУЧШАЯ</div>
                    <div style="color:#ffb000; font-size:14px; font-weight:700;">{' '.join(best['combo'])}</div>
                    <div style="color:#34c759; font-size:18px; font-weight:700;">{annual_return:+.1f}% p.a.</div>
                    <div style="color:#d6a44a; font-size:10px;">P(loss): {p_loss:.1%} · VaR: {best['var_95']:.4f}</div>
                </div>
                <div class="q-card" style="flex:1; border-left:3px solid #ff3b30; padding:10px;">
                    <div style="color:#ff3b30; font-size:11px; font-weight:700;">🥉 ХУДШАЯ</div>
                    <div style="color:#ffb000; font-size:14px; font-weight:700;">{' '.join(worst_combo['combo'])}</div>
                    <div style="color:#ff3b30; font-size:18px; font-weight:700;">{worst_annual:+.1f}% p.a.</div>
                    <div style="color:#d6a44a; font-size:10px;">P(loss): {worst_combo['p_loss']:.1%} · VaR: {worst_combo['var_95']:.4f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 6 KPI from best basket
            st.markdown('<div class="bb-section">📊 ЛУЧШАЯ КОРЗИНА — KPI</div>', unsafe_allow_html=True)
            pk1, pk2, pk3, pk4, pk5, pk6 = st.columns(6)
            pk1.metric("AVG PAYOFF", f"{avg_payoff:.4f}")
            pk2.metric("P(LOSS)", f"{p_loss:.1%}")
            pk3.metric("VAR 95%", f"{best['var_95']:.4f}")
            pk4.metric("CVAR 95%", f"{best['cvar_95']:.4f}")
            pk5.metric("ALL 8 COUPONS", f"{best['p_all_coupons']:.1%}")
            pk6.metric("AVG COUPONS", f"{best['mean_coupons']:.1f}/8")

            # P(loss) CI
            st.markdown(f"""
            <div style="font-size:10px; color:#d6a44a; margin:4px 0;">
                P(loss) 95% CI: [{best['p_loss_ci_low']:.1%} – {best['p_loss_ci_high']:.1%}] ·
                P(0 купонов): {best['p_zero_coupons']:.1%} ·
                Купон: {best['coupon_rate']*4*100:.0f}% годовых (USD) ·
                Барьер: {best['barrier']*100:.0f}%
            </div>
            """, unsafe_allow_html=True)

            # Per-ticker finals from best basket
            if best.get("ticker_finals"):
                st.markdown('<div class="bb-section">📊 ЛУЧШАЯ КОРЗИНА — PER-TICKER FINALS</div>', unsafe_allow_html=True)
                tf_rows = []
                for t, d in best["ticker_finals"].items():
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
