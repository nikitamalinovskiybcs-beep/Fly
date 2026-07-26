"""Worst-of Phoenix Terminal — Bloomberg-style dashboard.
Computation stays in the domain modules; this file renders the decision workflow."""

import datetime
import streamlit as st
import plotly.graph_objects as go

from src.precompute import precompute_all as _precompute_all, SECTOR_MAP
from src.phoenix_engine import GDRIVE_AVAILABLE
from src.backtest import precompute_backtest as _precompute_backtest, PhoenixAGI
from src.real_data import precompute_dealer_benchmark as _precompute_dealer
from src.calibration import run_pipeline as _run_calibration_pipeline
from src.data_module import get_data_source_status
from src.commercial_readiness import assess_commercial_readiness
from src.full_pipeline import run_full_analysis
from src.outcome_engine import (
    StructuredNoteSpec,
    load_quality_report,
    simulate_stress_suite,
)

st.set_page_config(page_title="Worst-of Phoenix | Terminal", page_icon="■", layout="wide")


@st.cache_data(ttl=300, show_spinner=False)
def cached_precompute(tickers_key: str):
    tickers = tickers_key.split(",")
    return _precompute_all(tickers)


@st.cache_data(ttl=300, show_spinner=False)
def cached_full_analysis(tickers_key: str):
    return run_full_analysis(tickers_key.split(","))


@st.cache_data(ttl=600, show_spinner=False)
def cached_backtest(tickers_key: str, p_ki: float, coupon_pa: float, e_payout: float):
    tickers = tickers_key.split(",")
    return _precompute_backtest(tickers, p_ki, coupon_pa, e_payout)


@st.cache_data(ttl=600, show_spinner=False)
def cached_dealer(tickers_key: str, coupon_pa: float, p_ki: float, score: float):
    tickers = tickers_key.split(",")
    return _precompute_dealer(tickers, coupon_pa, p_ki, score)


@st.cache_data(ttl=600, show_spinner=False)
def cached_pipeline(tickers_key: str, p_ki: float, avg_vol: float, avg_corr: float):
    tickers = tickers_key.split(",")
    agi = PhoenixAGI.load_from_clickhouse() or PhoenixAGI()
    return _run_calibration_pipeline(tickers, agi.get_params(), p_ki, avg_vol, avg_corr)


@st.cache_data(ttl=900, show_spinner=False)
def cached_outcome_stress(
    tickers_key: str,
    barrier: float,
    coupon_rate: float,
    term_months: int,
    n_paths: int,
):
    spec = StructuredNoteSpec(
        basket=tickers_key.split(","),
        barrier=barrier,
        coupon_rate=coupon_rate,
        term_months=term_months,
    )
    return simulate_stress_suite(spec, n_paths=n_paths)


def render_process_map(data: dict, pipeline: dict) -> None:
    """Render the real decision path as a status-aware neural-style graph."""
    gate_passed = bool(data.get("evidence_gate", {}).get("passed"))
    quality = load_quality_report()
    realized = int(quality.get("realized_notes", 0))
    source = data.get("data_source", "unknown").upper()
    colors = {
        "active": "#34c759",
        "blocked": "#ff3b30",
        "diagnostic": "#ffb000",
        "waiting": "#6a5a2a",
        "neutral": "#6db6ff",
    }
    stages = pipeline.get("stages", {})
    active_color = colors["active"] if gate_passed else colors["diagnostic"]
    nodes = [
        ("MARKET DATA", source, active_color, 0.5, 1.0),
        ("IV / BETA", "FEATURES", active_color, 1.7, 1.6),
        ("RETURNS", "FEATURES", active_color, 1.7, 0.4),
        ("EVIDENCE GATE", "PASSED" if gate_passed else "BLOCKED", colors["active"] if gate_passed else colors["blocked"], 3.0, 1.0),
        ("PHOENIX", stages.get("phoenix", "UNKNOWN").upper(), active_color, 4.4, 1.6),
        ("AGENTS", stages.get("agents", "UNKNOWN").upper(), active_color if gate_passed else colors["blocked"], 4.4, 0.4),
        ("PRODUCT", stages.get("product", "UNKNOWN").upper(), active_color if gate_passed else colors["blocked"], 5.8, 1.0),
        ("PAPER", "TRACKING", colors["neutral"], 7.2, 1.6),
        ("REALIZED", f"{realized} NOTES" if realized else "WAITING", colors["active"] if realized else colors["waiting"], 7.2, 0.4),
    ]
    x_values = [node[3] for node in nodes]
    y_values = [node[4] for node in nodes]
    node_colors = [node[2] for node in nodes]
    labels = [f"<b>{node[0]}</b><br><sup>{node[1]}</sup>" for node in nodes]
    edges = [
        (0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (3, 5),
        (4, 6), (5, 6), (6, 7), (6, 8),
    ]

    fig = go.Figure()
    for start, end in edges:
        edge_color = node_colors[start] if node_colors[start] == node_colors[end] else "#6a5a2a"
        fig.add_trace(go.Scatter(
            x=[x_values[start], x_values[end]],
            y=[y_values[start], y_values[end]],
            mode="lines",
            line={"color": edge_color, "width": 2},
            hoverinfo="skip",
            showlegend=False,
        ))
    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode="markers",
        marker={"size": 42, "color": node_colors, "opacity": 0.10},
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode="markers+text",
        text=labels,
        textposition="bottom center",
        textfont={"family": "JetBrains Mono, monospace", "size": 10, "color": "#d6a44a"},
        marker={"size": 18, "color": node_colors, "line": {"color": "#ffd56a", "width": 1}},
        hovertemplate="%{text}<extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(
        height=230,
        margin={"l": 10, "r": 10, "t": 8, "b": 8},
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        xaxis={"visible": False, "range": [0, 8]},
        yaxis={"visible": False, "range": [0, 2]},
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ═══════════════════════════════════════════════════════════════════
# CSS — Bloomberg Terminal
# ═══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');
:root {
    --bg:#000; --bg2:#0a0a0a; --bg3:#141414;
    --border:#3a2a00; --border2:#6a4a00;
    --text:#ffb000; --fg:#ffd56a; --muted:#d6a44a; --dim:#6a5a2a;
    --accent:#fa8000; --good:#34c759; --bad:#ff3b30; --blue:#6db6ff;
}
html,body,[class*="css"]{font-family:"JetBrains Mono",Consolas,monospace!important}
.main,.stApp{background:var(--bg)!important}
[data-testid="stSidebar"]{background:var(--bg2)!important;border-right:1px solid var(--border)!important}
[data-testid="stSidebar"] *{color:var(--text)!important}
div[data-testid="stMetric"]{background:var(--bg2)!important;border:1px solid var(--border)!important;border-radius:0!important;padding:.75rem!important}
div[data-testid="stMetric"] label{color:var(--muted)!important;font-size:.7rem!important;text-transform:uppercase!important}
div[data-testid="stMetric"] [data-testid="stMetricValue"]{color:var(--text)!important;font-weight:700!important}
.stButton>button{background:var(--accent)!important;color:#000!important;border:2px solid var(--accent)!important;border-radius:0!important;font-family:"JetBrains Mono",monospace!important;font-weight:900!important;letter-spacing:2px!important;text-transform:uppercase!important}
.stButton>button:hover{background:#ffd95a!important;border-color:#ffd95a!important;box-shadow:0 0 22px rgba(255,176,0,.7)!important}
.stSelectbox>div>div{background:var(--bg2)!important;border-color:var(--border)!important;color:var(--text)!important}
.stExpander{border:1px solid var(--border)!important;border-radius:0!important}
hr{border-color:var(--border)!important}
.up{color:var(--good)}.dn{color:var(--bad)}
.hdr{padding:8px 14px;border-bottom:1px solid var(--border);background:var(--bg2);display:flex;align-items:baseline;gap:16px}
.hdr h1{margin:0;font-size:14px;font-weight:700;letter-spacing:1px;color:var(--accent);text-transform:uppercase}.hdr h1::before{content:"■ "}.hdr .sub{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.6px}
.qc{background:var(--bg2);border:1px solid var(--border);padding:8px 12px;margin-bottom:4px}
.sec{font-size:12px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:1px;padding:8px 12px;border:1px solid var(--border);margin:16px 0 4px;background:var(--bg2);display:flex;justify-content:space-between;align-items:center}
.sbar{position:fixed;bottom:0;left:0;right:0;background:var(--bg2);border-top:1px solid var(--border);padding:4px 14px;font-size:10px;color:var(--muted);display:flex;gap:20px;z-index:9999}
.sbar .ok{color:var(--good)}.sbar .lb{color:var(--accent);font-weight:700}
.bi input{font-family:"JetBrains Mono",monospace!important;font-size:20px!important;font-weight:700!important;letter-spacing:2px!important;text-transform:uppercase!important;background:#000!important;color:#6db6ff!important;border:2px solid #6db6ff!important;border-radius:0!important;padding:12px 16px!important}
.bi input:focus{border-color:#9ad0ff!important;box-shadow:0 0 14px rgba(154,208,255,.35)!important}
.bi input::placeholder{color:#355d80!important}.bi label{display:none!important}.bi .stTextInput>div{margin:0!important}
.bar{height:14px;border-radius:1px;display:inline-block;vertical-align:middle}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════
st.markdown('<div class="hdr"><h1>WORST-OF PHOENIX</h1><span class="sub">ONE PIPELINE · 15 STEPS · ФЕНИКС v36.0 · 8 AGENTS · PRODUCT · OUTCOMES · API</span></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# BASKET INPUT
# ═══════════════════════════════════════════════════════════════════
bc = st.columns([1,5,1])
with bc[0]:
    st.markdown('<div style="padding:10px 0"><span style="color:#ffb000;font-size:14px;font-weight:700;letter-spacing:3px">PHOENIX</span></div>', unsafe_allow_html=True)
with bc[1]:
    st.markdown('<div class="bi">', unsafe_allow_html=True)
    basket_input = st.text_input(
        "basket",
        value="AAPL DELL GOOG",
        placeholder="AAPL MSFT NVDA AMD TSLA",
        label_visibility="collapsed",
        key="basket_input",
    )
    st.markdown('</div>', unsafe_allow_html=True)
requested_tickers = [
    t.strip().upper()
    for t in basket_input.replace(",", " ").split()
    if t.strip()
]
if "analysis_tickers" not in st.session_state:
    st.session_state.analysis_tickers = requested_tickers
with bc[2]:
    if st.button("▶ RUN FULL ANALYSIS", key="run_basket", type="primary", use_container_width=True):
        st.session_state.analysis_tickers = requested_tickers
        st.cache_data.clear()
        st.rerun()

basket_tickers = st.session_state.analysis_tickers
n_tickers = len(basket_tickers)

basket_label = ", ".join(basket_tickers)
st.markdown(f'<div style="color:#d6a44a;font-size:10px;padding:2px 0">КОРЗИНА: {basket_label}</div>', unsafe_allow_html=True)
if requested_tickers != basket_tickers:
    st.markdown(
        '<div style="color:#ffb000;font-size:9px;padding:2px 0">'
        'Новая корзина ожидает запуска: нажмите RUN FULL ANALYSIS.</div>',
        unsafe_allow_html=True,
    )

rc1, rc2 = st.columns([3, 1])
with rc2:
    if st.button("🔄 ОБНОВИТЬ ЦЕНЫ", key="refresh_prices", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ═══════════════════════════════════════════════════════════════════
# PRECOMPUTE ALL (Karpathy method — one call, all data)
# ═══════════════════════════════════════════════════════════════════
if basket_tickers:
    with st.spinner("⚡ Precomputing..."):
        _pipeline = cached_full_analysis(",".join(basket_tickers))
        D = _pipeline["data"]

    ch = D["ch"]
    wo = ch.get("worst_of", {})
    td = ch.get("tickers", {})
    yf = D.get("yf", {})
    corr = D.get("corr", {})
    ind = D.get("ind", {})
    score = D["score"]
    p_ki = D["p_ki"]
    p_autocall = D["p_autocall"]

    with rc1:
        data_src = D.get("data_source", "yfinance")
        st.markdown(f'<div style="color:#6a5a2a;font-size:9px;padding-top:8px">Данные: {D.get("ts", "N/A")[:19]} · {data_src} · Gen {D.get("scoring_generation", 0)}</div>', unsafe_allow_html=True)
        gate = D.get("evidence_gate", {})
        gate_label = (
            "REAL MARKET DATA · GATE PASSED"
            if gate.get("passed")
            else "DIAGNOSTIC ONLY · REAL MARKET DATA INCOMPLETE"
        )
        gate_color = "#34c759" if gate.get("passed") else "#ff3b30"
        st.markdown(
            f'<div style="color:{gate_color};font-size:9px;padding-top:2px">'
            f'{gate_label}</div>',
            unsafe_allow_html=True,
        )

    # ═══════════════════════════════════════════════════════════════
    # [1] ВЕРДИКТ — Score + Recommendation
    # ═══════════════════════════════════════════════════════════════
    with st.expander("LIVE PROCESS MAP · data → decision → outcome", expanded=True):
        render_process_map(D, _pipeline)

    with st.expander("[0] MODEL BASIS    Formula · assumptions · evidence"):
        st.markdown(
            '<div style="color:#d6a44a;font-size:10px;line-height:1.7">'
            '<b style="color:#ffb000">Phoenix score</b> = base score + '
            'diversification/fundamental/trend bonuses − P(KI)/volatility/'
            'correlation/toxicity/macro/earnings penalties. '
            'The score is a decision-support index, not a probability of profit.<br>'
            '<b style="color:#ffb000">P(KI)</b> uses a worst-of analytical '
            'barrier approximation with observed volatility, correlation and '
            'stress adjustments; it is not a dealer quote or guarantee.<br>'
            '<b style="color:#ffb000">Agents</b> are lightweight rule-based '
            'and ensemble components. They are not presented as a trained '
            'deep neural network unless realized training evidence exists.<br>'
            '<b style="color:#ffb000">Evidence rule</b>: estimated data can '
            'support diagnostics only. Live selection requires a passed evidence gate.'
            '</div>',
            unsafe_allow_html=True,
        )
        _confidence = D.get("score_confidence", 0)
        _range = D.get("score_range", [])
        st.markdown(
            f'<div style="color:#6db6ff;font-size:10px;margin-top:6px">'
            f'Confidence: {_confidence:.0f}% · score range: {_range or "not available"} · '
            f'generation: {D.get("scoring_generation", 0)}</div>',
            unsafe_allow_html=True,
        )

    rec = D.get("recommendation", {})
    rec_action = rec.get("action", "?")
    rec_color = rec.get("color", "#ffb000")
    rec_reason = rec.get("reason", "")
    rs = D["risk_score"]
    rs_color = "#34c759" if rs >= 80 else "#ffb000" if rs >= 65 else "#ff3b30"
    rs_grade = "A+" if rs >= 90 else "A" if rs >= 80 else "B" if rs >= 70 else "C" if rs >= 60 else "D"
    sl = D.get("self_learning", {})
    gen = D.get("scoring_generation", 0)

    st.markdown(f'''
    <div class="qc" style="border-left:3px solid {rec_color};padding:14px;margin:8px 0">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
                <span style="color:{rec_color};font-size:22px;font-weight:700">{rec_action}</span>
                <span style="color:#d6a44a;font-size:11px;margin-left:8px">{rec_reason}</span>
            </div>
            <div style="text-align:right">
                <span style="color:{rs_color};font-size:28px;font-weight:700">{rs:.1f}</span>
                <span style="color:#d6a44a;font-size:12px">/100</span>
                <span style="background:#1a1400;border:1px solid #3a2a00;padding:1px 6px;color:#d6a44a;font-size:9px;border-radius:2px;margin-left:6px">{rs_grade}</span>
            </div>
        </div>
        <div style="margin:6px 0;height:6px;background:#1a1400;border-radius:1px"><div style="height:100%;width:{max(0, (rs - 50) * 2)}%;background:{rs_color};border-radius:1px"></div></div>
        <div style="display:flex;justify-content:space-between;margin-top:4px">
            <span style="color:#6a5a2a;font-size:9px">Win rate: {rec.get("win_rate_expected", 0)}% · Gen {gen}</span>
            <span style="background:{rs_color}22;border:1px solid {rs_color};padding:2px 8px;color:{rs_color};font-size:10px;font-weight:700">P(KI) {p_ki:.0f}%</span>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # Score factor decomposition (inline)
    score_factors = D.get("score_factors", {})
    with st.expander("▶ Разложение скора по факторам"):
        for name, info in score_factors.items():
            impact = info["impact"] if isinstance(info, dict) else info
            raw = info.get("raw", "") if isinstance(info, dict) else ""
            impact_c = "#34c759" if impact > 0 else "#ff3b30" if impact < 0 else "#6a5a2a"
            bar_dir = "right" if impact >= 0 else "left"
            bar_w = min(100, abs(impact) * 8)
            st.markdown(f'''<div style="display:flex;align-items:center;gap:6px;margin:2px 0">
                <span style="color:#d6a44a;font-size:10px;width:90px;text-align:right">{name}</span>
                <div style="flex:1;height:8px;background:#1a1400;position:relative">
                    <div style="position:absolute;{bar_dir}:50%;width:{bar_w}%;height:100%;background:{impact_c}"></div>
                </div>
                <span style="color:{impact_c};font-size:10px;width:40px;font-weight:700">{impact:+.1f}</span>
                <span style="color:#6a5a2a;font-size:8px;width:50px">{raw}</span>
            </div>''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # КЛЮЧЕВЫЕ ИНДИКАТОРЫ (6 метрик)
    # ═══════════════════════════════════════════════════════════════
    def _mi(label, value, sub="", color="#ffb000"):
        return f'<div style="flex:1 1 30%;min-width:140px;padding:8px 10px;border:1px solid #3a2a00;margin:2px;background:#0a0a00"><div style="color:#d6a44a;font-size:9px;text-transform:uppercase">{label}</div><div style="color:{color};font-size:16px;font-weight:700">{value}</div><div style="color:#6a5a2a;font-size:9px">{sub}</div></div>'

    if ind:
        iv30 = ind.get("iv30_avg", 40)
        avg_c_val = corr.get("avg_corr", 0)
        grid = _mi("P(KI)", f"{p_ki:.1f}%", f"при KI=60% spot за 2Y", "#ff3b30" if p_ki > 25 else "#34c759")
        grid += _mi("P(autocall)", f"{p_autocall:.1f}%", f"E[жизни] {D.get('e_life',1.5):.2f}г")
        grid += _mi("IV30 (avg)", f"{iv30:.0f}%", f"min {ind.get('iv30_min',0):.0f}% · max {ind.get('iv30_max',0):.0f}%")
        grid += _mi("Avg корреляция", f"{avg_c_val:.2f}", f"sweet spot 0.45–0.65", "#34c759" if avg_c_val < 0.65 else "#ff3b30")
        grid += _mi("β (avg)", f"{ind.get('beta_avg',1):.2f}", f"min {ind.get('beta_min',0):.2f} · max {ind.get('beta_max',0):.2f}")
        grid += _mi("Dispersion", f"σ {D.get('dispersion',5):.1f}%", f"vol-spread корзины")
        st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:0">{grid}</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # КУПОН КЛИЕНТУ
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div class="sec">КУПОН КЛИЕНТУ</div>', unsafe_allow_html=True)
    cp = st.columns(6)
    cp[0].markdown(f'<div style="text-align:center"><div style="color:#d6a44a;font-size:9px;text-transform:uppercase">КУПОН P.A.</div><div style="color:#34c759;font-size:18px;font-weight:700">{D["coupon_pa"]:.2f}%</div></div>', unsafe_allow_html=True)
    cp[1].markdown(f'<div style="text-align:center"><div style="color:#d6a44a;font-size:9px;text-transform:uppercase">P(АВТОКОЛЛ)</div><div style="color:#ffb000;font-size:18px;font-weight:700">{p_autocall:.1f}%</div></div>', unsafe_allow_html=True)
    cp[2].markdown(f'<div style="text-align:center"><div style="color:#d6a44a;font-size:9px;text-transform:uppercase">P(ЧИСТЫЙ УБЫТОК)</div><div style="color:#ff3b30;font-size:18px;font-weight:700">{D["p_clean_loss"]:.1f}%</div></div>', unsafe_allow_html=True)
    cp[3].markdown(f'<div style="text-align:center"><div style="color:#d6a44a;font-size:9px;text-transform:uppercase">E[ИТОГ. ВЫПЛАТА]</div><div style="color:#ffb000;font-size:18px;font-weight:700">{D["e_payout"]:.1f}%</div></div>', unsafe_allow_html=True)
    cp[4].markdown(f'<div style="text-align:center"><div style="color:#d6a44a;font-size:9px;text-transform:uppercase">P(KI)</div><div style="color:{"#ff3b30" if p_ki>25 else "#34c759"};font-size:18px;font-weight:700">{p_ki:.1f}%</div></div>', unsafe_allow_html=True)
    cp[5].markdown(f'<div style="text-align:center"><div style="color:#d6a44a;font-size:9px;text-transform:uppercase">E[СРОК]</div><div style="color:#ffb000;font-size:18px;font-weight:700">{D["e_life"]:.2f} лет</div></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # КАЛИБРОВКА — ввод реальной ставки от брокера
    # ═══════════════════════════════════════════════════════════════
    cal_col1, cal_col2, cal_col3 = st.columns([2, 2, 4])
    with cal_col1:
        broker_rate = st.number_input("СТАВКА БРОКЕРА, % P.A.", min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="broker_rate")
    with cal_col2:
        broker_name = st.text_input("БРОКЕР", value="", placeholder="БКС, Тинькофф...", key="broker_name")
    with cal_col3:
        if broker_rate > 0:
            our_rate = D["coupon_pa"]
            delta = broker_rate - our_rate
            delta_color = "#34c759" if abs(delta) < 2 else "#ff3b30" if delta > 2 else "#ffb000"
            accuracy_pct = max(0, 100 - abs(delta) / max(our_rate, 1) * 100)
            broker_label = f" ({broker_name})" if broker_name else ""
            st.markdown(f'''<div style="padding:8px;border:1px solid #333;border-radius:6px;margin-top:18px">
                <div style="color:#d6a44a;font-size:9px;text-transform:uppercase">КАЛИБРОВКА{broker_label}</div>
                <div style="display:flex;gap:20px;align-items:center">
                    <div><span style="color:#aaa;font-size:11px">Наша модель:</span> <span style="color:#ffb000;font-size:14px;font-weight:700">{our_rate:.2f}%</span></div>
                    <div><span style="color:#aaa;font-size:11px">Брокер:</span> <span style="color:#34c759;font-size:14px;font-weight:700">{broker_rate:.2f}%</span></div>
                    <div><span style="color:#aaa;font-size:11px">Δ:</span> <span style="color:{delta_color};font-size:14px;font-weight:700">{delta:+.2f}pp</span></div>
                    <div><span style="color:#aaa;font-size:11px">Точность:</span> <span style="color:{delta_color};font-size:14px;font-weight:700">{accuracy_pct:.0f}%</span></div>
                </div>
                <div style="color:#6a5a2a;font-size:9px;margin-top:4px">{"Модель калибрована (Δ<2pp)" if abs(delta) < 2 else "Требуется калибровка — модель " + ("занижает" if delta > 0 else "завышает") + f" на {abs(delta):.1f}pp"}</div>
            </div>''', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#6a5a2a;font-size:9px;margin-top:24px">Введи ставку от брокера для калибровки модели</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [2] КОРЗИНА — Composition + Worst-of
    # ═══════════════════════════════════════════════════════════════
    n_sectors = len(set(SECTOR_MAP.get(t, "Unknown") for t in basket_tickers))
    wo_analysis = D.get("worst_of_analysis", [])
    with st.expander(f"[2] КОРЗИНА    {n_tickers} NAMES · {n_sectors} SECTORS"):
        for t in basket_tickers:
            if t in yf:
                d = yf[t]
                sector = d.get("sector", "Unknown")
                rec_label = d.get("rec_label", "buy")
                ema_sign = "▲" if d["ema200_above"] else "▼"
                ema_color = "#34c759" if d["ema200_above"] else "#ff3b30"
                st.markdown(f'''
                <div class="qc" style="border-left:3px solid #fa8000;padding:10px 14px;margin:4px 0">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <div><span style="color:#ffb000;font-size:16px;font-weight:700">{t}</span> <span style="color:#6a5a2a;font-size:10px">{sector}</span></div>
                        <span style="color:#d6a44a;font-size:10px">{rec_label}</span>
                    </div>
                    <div style="display:flex;gap:12px;font-size:11px;margin-top:4px">
                        <span style="color:#d6a44a">Spot <span style="color:#ffb000">{d["spot"]}</span></span>
                        <span style="color:#d6a44a">IV30 <span style="color:#ffb000">{d["iv30"]}%</span></span>
                        <span style="color:#d6a44a">β <span style="color:#ffb000">{d["beta"]}</span></span>
                        <span style="color:#d6a44a">P/E <span style="color:#ffb000">{d["pe"]}</span></span>
                        <span style="color:#d6a44a">EMA200 <span style="color:{ema_color}">{ema_sign} {d["ema200_pct"]:+.1f}%</span></span>
                    </div>
                </div>
                ''', unsafe_allow_html=True)

        # Worst-of analysis
        if wo_analysis:
            st.markdown('<div style="color:#ffb000;font-size:11px;font-weight:700;margin:8px 0 4px">WORST-OF RANKING</div>', unsafe_allow_html=True)
            for i, wa in enumerate(wo_analysis):
                bar_w = min(80, wa["p_worst"] * 2)
                bar_c = "#ff3b30" if i == 0 else "#ffb000"
                st.markdown(f'''<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 8px;border-bottom:1px solid #1a1400">
                    <span style="color:#ffb000;font-size:11px;font-weight:700">{wa["ticker"]}</span>
                    <div style="width:120px;height:14px;background:#1a1400"><div class="bar" style="width:{bar_w}%;background:{bar_c}"></div></div>
                    <span style="color:#ffb000;font-size:11px">{wa["p_worst"]:.1f}%</span>
                </div>''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [3] P(KI) — Main + Consensus (4 methods)
    # ═══════════════════════════════════════════════════════════════
    pki_cons = D.get("pki_consensus", D.get("buyside", {}).get("pki_consensus", {}))
    pki_per_asset = D.get("p_ki_per_asset", {})
    with st.expander(f"[3] P(KI) АНАЛИЗ    {p_ki:.1f}% · {pki_cons.get('n_methods', 0)} методов"):
        # Main P(KI) + per asset
        st.markdown(f'''<div class="qc" style="border-left:3px solid {"#ff3b30" if p_ki > 25 else "#34c759"};padding:10px">
            <span style="color:{"#ff3b30" if p_ki > 25 else "#34c759"};font-size:20px;font-weight:700">{p_ki:.1f}%</span>
            <span style="color:#d6a44a;font-size:10px;margin-left:12px">P(KI) worst-of · Analytical GBM · 7 corrections</span>
        </div>''', unsafe_allow_html=True)

        # Per-asset breakdown
        for t, pki_val in pki_per_asset.items():
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 8px;border-bottom:1px solid #1a1400"><span style="color:#d6a44a;font-size:10px">{t}</span><span style="color:#fa8000;font-size:10px;font-weight:700">{pki_val}%</span></div>', unsafe_allow_html=True)

        # Consensus
        if pki_cons and pki_cons.get("n_methods", 0) > 0:
            methods = pki_cons.get("methods", {})
            st.markdown(f'''<div class="qc" style="margin-top:8px;padding:8px">
                <div style="color:#ffb000;font-size:10px;font-weight:700;margin-bottom:4px">CONSENSUS: {pki_cons.get("median", 0)}% · σ={pki_cons.get("std", 0)}pp · {pki_cons.get("agreement", "N/A")}</div>
            </div>''', unsafe_allow_html=True)
            for method, val in methods.items():
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 8px;border-bottom:1px solid #1a1400"><span style="color:#6a5a2a;font-size:10px">{method}</span><span style="color:#fa8000;font-size:10px;font-weight:700">{val}%</span></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [4] СТРЕСС-ТЕСТ
    # ═══════════════════════════════════════════════════════════════
    stress_v2 = D.get("stress_v2", [])
    n_critical = sum(1 for s in stress_v2 if s.get("risk_level") == "CRITICAL")
    stress_c = "#ff3b30" if n_critical > 0 else "#34c759"
    with st.expander(f"[4] СТРЕСС-ТЕСТ    {'⚠ ' + str(n_critical) + ' CRITICAL' if n_critical > 0 else 'ALL OK'}"):
        if stress_v2:
            for sc in stress_v2:
                rc_c = "#ff3b30" if sc["risk_level"] == "CRITICAL" else ("#fa8000" if sc["risk_level"] == "WARNING" else "#34c759")
                ki_badge = '<span style="background:#ff3b30;color:#fff;font-size:8px;padding:1px 4px;margin-left:4px">KI BREACH</span>' if sc.get("barrier_breach_65") else ""
                st.markdown(f'''<div class="qc" style="padding:6px;margin-bottom:4px">
                    <div style="display:flex;align-items:center;gap:8px">
                        <span style="color:{rc_c};font-size:11px;font-weight:700">{sc["name"]}</span>
                        <span style="color:#6a5a2a;font-size:9px">SPX {sc["spx_drop"]:+d}%</span>{ki_badge}
                    </div>
                    <div style="display:flex;gap:12px;margin-top:2px">
                        <span style="color:#ffb000;font-size:10px">Корзина: {sc["basket_drop"]:+.1f}%</span>
                        <span style="color:#ff3b30;font-size:10px">Worst: {sc["worst_ticker_drop"]:+.1f}%</span>
                    </div>
                </div>''', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#6a5a2a;font-size:11px">Данные загружаются...</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [5] БЭКТЕСТ — Historical win rate
    # ═══════════════════════════════════════════════════════════════
    with st.spinner("⚡ Бэктест..."):
        BT = cached_backtest(",".join(basket_tickers), D["p_ki"], D["coupon_pa"], D["e_payout"])

    bt_stats = BT.get("bt_stats", {})
    with st.expander(f"[5] БЭКТЕСТ    {BT['n_backtests']} WINDOWS · WIN {bt_stats.get('win_rate',0):.0f}%"):
        if bt_stats:
            st.markdown(f'''
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px">
                <div class="qc" style="flex:1;min-width:100px;padding:8px;text-align:center"><div style="color:#d6a44a;font-size:9px">AVG PAYOFF</div><div style="color:#34c759;font-size:16px;font-weight:700">{bt_stats["avg_payoff"]:.1f}%</div></div>
                <div class="qc" style="flex:1;min-width:100px;padding:8px;text-align:center"><div style="color:#d6a44a;font-size:9px">WIN RATE</div><div style="color:#ffb000;font-size:16px;font-weight:700">{bt_stats["win_rate"]:.0f}%</div></div>
                <div class="qc" style="flex:1;min-width:100px;padding:8px;text-align:center"><div style="color:#d6a44a;font-size:9px">P(KI) ACTUAL</div><div style="color:{"#ff3b30" if bt_stats["p_ki_actual"]>25 else "#34c759"};font-size:16px;font-weight:700">{bt_stats["p_ki_actual"]:.1f}%</div></div>
                <div class="qc" style="flex:1;min-width:100px;padding:8px;text-align:center"><div style="color:#d6a44a;font-size:9px">MAX LOSS</div><div style="color:#ff3b30;font-size:16px;font-weight:700">{bt_stats["max_loss"]:.1f}%</div></div>
            </div>''', unsafe_allow_html=True)

            for bt in BT.get("backtest", [])[:10]:
                pnl_c = "#34c759" if bt["pnl_pct"] >= 0 else "#ff3b30"
                ki_badge = '<span style="color:#ff3b30;font-size:9px;margin-left:4px">KI</span>' if bt["ki_hit"] else ""
                ac_badge = '<span style="color:#34c759;font-size:9px;margin-left:4px">AC Q{}</span>'.format(bt["autocall_quarter"]) if bt["autocalled"] else ""
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 8px;border-bottom:1px solid #1a1400"><span style="color:#6a5a2a;font-size:9px">{bt["start_date"]} → {bt["end_date"]}</span>{ki_badge}{ac_badge}<span style="color:{pnl_c};font-size:10px;font-weight:700">{bt["pnl_pct"]:+.1f}%</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#6a5a2a;font-size:11px">Недостаточно данных</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [6] САМООБУЧЕНИЕ — Model accuracy + calibration
    # ═══════════════════════════════════════════════════════════════
    avg_vol_val = ind.get("iv30_avg", 35) if ind else 35
    avg_corr_val = corr.get("avg_corr", 0.5)
    with st.spinner("⚡ Калибровка..."):
        PL = cached_pipeline(",".join(basket_tickers), p_ki, avg_vol_val, avg_corr_val)

    pl_bt = PL.get("backtest", {})
    pl_cal = PL.get("calibration", {})
    cal_after = pl_cal.get("after", {})
    sl_gen = sl.get("generation", 0)
    sl_acc = sl.get("scoring_acc_after", 0)
    sl_wr = sl.get("win_rate", 0)
    sl_val = sl.get("val_acc", 0)
    sl_status = sl.get("status", "unknown")
    acc_color = "#34c759" if cal_after.get("test_acc", 0) >= 70 else "#ffb000"

    with st.expander(f"[6] САМООБУЧЕНИЕ    Gen {sl_gen} · ACC {cal_after.get('test_acc',0):.0f}% · Win {sl_wr}% · {sl_status}"):
        st.caption(
            "Metrics are historical/replay calibration only; realized-note "
            "evidence is not available yet."
        )
        if sl_status != "calibrated":
            st.markdown(
                f'<div style="color:#ff3b30;font-size:10px">Self-learning unavailable: {sl.get("error", "insufficient evidence")}</div>',
                unsafe_allow_html=True,
            )
        st.markdown(f'''
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">ACCURACY</div><div style="color:{acc_color};font-size:16px;font-weight:700">{pl_bt.get("loss_accuracy",0):.0f}%</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">WIN RATE</div><div style="color:#ffb000;font-size:16px;font-weight:700">{sl_wr}%</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">VAL ACC</div><div style="color:#6db6ff;font-size:16px;font-weight:700">{sl_val}%</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">GENERATION</div><div style="color:#fa8000;font-size:16px;font-weight:700">{sl_gen}</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">F1</div><div style="color:#ffb000;font-size:16px;font-weight:700">{pl_bt.get("f1",0):.0f}%</div></div>
        </div>''', unsafe_allow_html=True)

        # Weak/strong features
        weak = sl.get("weak_features", [])
        if weak:
            st.markdown(f'<div style="color:#ff3b30;font-size:9px;margin-top:4px">Слабые факторы (отключены): {", ".join(weak)}</div>', unsafe_allow_html=True)

        weights = sl.get("weights", {})
        if weights:
            st.markdown('<div style="color:#d6a44a;font-size:9px;margin-top:6px;font-weight:700">Веса модели:</div>', unsafe_allow_html=True)
            for k, v in sorted(weights.items(), key=lambda x: abs(x[1]) if isinstance(x[1], (int, float)) else 0, reverse=True):
                if isinstance(v, (int, float)) and k not in ("base", "generation"):
                    st.markdown(f'<div style="display:flex;justify-content:space-between;padding:1px 8px;border-bottom:1px solid #1a1400"><span style="color:#6a5a2a;font-size:9px">{k}</span><span style="color:#d6a44a;font-size:9px">{v}</span></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [7] АЛЬТЕРНАТИВЫ — Smart replacement
    # ═══════════════════════════════════════════════════════════════
    smart_alts = D.get("smart_alts", [])
    with st.expander(f"[7] АЛЬТЕРНАТИВЫ    {len(smart_alts)} вариантов"):
        if smart_alts:
            worst_replaced = smart_alts[0].get("replaced", "?")
            st.markdown(f'<div style="color:#d6a44a;font-size:10px;margin-bottom:6px">Замена <b style="color:#ff3b30">{worst_replaced}</b> на лучшие альтернативы:</div>', unsafe_allow_html=True)
            for alt in smart_alts:
                alt_score = alt["est_score"]
                alt_c = "#34c759" if alt_score > rs else "#ffb000"
                delta = alt_score - rs
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:3px 8px;border-bottom:1px solid #1a1400"><span style="color:#d6a44a;font-size:10px">{" · ".join(alt["basket"])}</span><span style="color:{alt_c};font-size:10px;font-weight:700">{alt_score:.0f} ({delta:+.0f})</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#6a5a2a;font-size:10px">Недостаточно данных</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [8] СРАВНЕНИЕ С РЫНКОМ — Toxicity + Dealer benchmark
    # ═══════════════════════════════════════════════════════════════
    DL = cached_dealer(",".join(basket_tickers), D["coupon_pa"], D["p_ki"], D["score"])
    tox_data = DL.get("toxicity", {})
    p_loss_data = DL.get("p_loss", {})
    cpn_pred = DL.get("coupon_prediction", {})
    guard = DL.get("guard_flag", False)

    with st.expander("[8] РЫНОК    Токсичность · Дилер · P(loss)"):
        if guard:
            st.markdown(f'<div style="background:#3a0000;border:1px solid #ff3b30;padding:6px;margin-bottom:6px;color:#ff3b30;font-size:11px;font-weight:700">GUARD: P(убыток) = {p_loss_data.get("p_loss_pct",0):.0f}%</div>', unsafe_allow_html=True)

        # Toxicity
        per_ticker = tox_data.get("per_ticker", {})
        tox_html = '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">'
        for ticker, info in per_ticker.items():
            label = info.get("label", "?")
            tc = "#ff3b30" if label == "TOXIC" else "#fa8000" if label == "RISKY" else "#34c759" if label == "SAFE" else "#6a5a2a"
            tox_html += f'<span style="background:#1a1400;border:1px solid {tc};padding:2px 8px;color:{tc};font-size:9px">{ticker} {info.get("tox",0.5):.2f} {label}</span>'
        tox_html += '</div>'
        st.markdown(tox_html, unsafe_allow_html=True)

        # Dealer comparison
        dealer_cpn = cpn_pred.get("predicted_coupon", 0)
        delta_cpn = DL.get("delta_coupon_vs_model", 0)
        st.markdown(f'''
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">
            <div class="qc" style="flex:1;min-width:110px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">P(УБЫТОК)</div><div style="color:{"#ff3b30" if p_loss_data.get("p_loss_pct",0)>25 else "#34c759"};font-size:14px;font-weight:700">{p_loss_data.get("p_loss_pct",0):.0f}%</div></div>
            <div class="qc" style="flex:1;min-width:110px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">КУПОН ДИЛЕР</div><div style="color:#6db6ff;font-size:14px;font-weight:700">{dealer_cpn:.1f}%</div></div>
            <div class="qc" style="flex:1;min-width:110px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">КУПОН НАШ</div><div style="color:#ffb000;font-size:14px;font-weight:700">{D["coupon_pa"]:.1f}%</div></div>
            <div class="qc" style="flex:1;min-width:110px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">Δ</div><div style="color:{"#34c759" if abs(delta_cpn)<3 else "#ff3b30"};font-size:14px;font-weight:700">{delta_cpn:+.1f}%</div></div>
        </div>''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [9] АГЕНТЫ — 8 Self-Learning Agents
    # ═══════════════════════════════════════════════════════════════
    sla = D.get("sl_agents", {})
    sla_ok = sla.get("agents_ok", 0)
    sla_total = sla.get("agents_run", 0)
    sla_decision = sla.get("decision", "N/A")
    sla_confidence = sla.get("confidence", 0)
    sla_regime = sla.get("regime", "N/A")
    sla_sentiment = sla.get("sentiment", "N/A")
    sla_adj = D.get("sl_agents_adj", 0)
    sla_dec_c = "#34c759" if sla_decision == "BUY" else "#ff3b30" if sla_decision == "AVOID" else "#ffb000"

    with st.expander(f"[9] АГЕНТЫ    {sla_ok}/{sla_total} OK · {sla_decision} · Conf {sla_confidence:.0%}"):
        # Summary metrics
        st.markdown(f'''
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">РЕШЕНИЕ</div><div style="color:{sla_dec_c};font-size:14px;font-weight:700">{sla_decision}</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">УВЕРЕННОСТЬ</div><div style="color:#ffb000;font-size:14px;font-weight:700">{sla_confidence:.0%}</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">РЕЖИМ</div><div style="color:{"#34c759" if sla_regime == "BULL" else "#ff3b30" if sla_regime == "BEAR" else "#ffb000"};font-size:14px;font-weight:700">{sla_regime}</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">SENTIMENT</div><div style="color:{"#34c759" if sla_sentiment == "BULLISH" else "#ff3b30" if sla_sentiment == "BEARISH" else "#ffb000"};font-size:14px;font-weight:700">{sla_sentiment}</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">СКОР ADJ</div><div style="color:{"#34c759" if sla_adj > 0 else "#ff3b30" if sla_adj < 0 else "#ffb000"};font-size:14px;font-weight:700">{sla_adj:+.1f}</div></div>
        </div>''', unsafe_allow_html=True)

        cascade_levels = sla.get("cascade_levels", [])
        if cascade_levels:
            st.markdown(
                '<div style="color:#d6a44a;font-size:9px;font-weight:700;'
                'margin:6px 0 3px">MULTI-LEVEL CASCADE</div>',
                unsafe_allow_html=True,
            )
            for level in cascade_levels:
                level_color = "#34c759" if level["status"] == "complete" else "#ffb000"
                st.markdown(
                    f'<div style="display:flex;gap:8px;padding:2px 8px;'
                    f'border-bottom:1px solid #1a1400;color:#d6a44a;font-size:9px">'
                    f'<span style="color:{level_color};font-weight:700">'
                    f'L{level["level"]} {level["status"].upper()}</span>'
                    f'<span>{level["name"]}: {", ".join(level["agents"])}</span></div>',
                    unsafe_allow_html=True,
                )

        # Per-agent details
        agent_results = sla.get("results", {})
        agent_labels = {
            "sentiment": "Sentiment",
            "regime": "Regime (HMM)",
            "alpha": "Alpha Discovery",
            "risk": "Risk/VaR",
            "timing": "Timing",
            "correlation": "Correlation",
            "overfit_guardian": "Overfit Guard",
            "meta": "Meta Ensemble",
        }
        for agent_key, label in agent_labels.items():
            ar = agent_results.get(agent_key, {})
            if "error" in ar:
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 8px;border-bottom:1px solid #1a1400"><span style="color:#ff3b30;font-size:9px">{label}</span><span style="color:#ff3b30;font-size:9px">ERROR</span></div>', unsafe_allow_html=True)
                continue
            adj = ar.get("scoring_adj", 0)
            adj_c = "#34c759" if adj > 0 else "#ff3b30" if adj < 0 else "#6a5a2a"
            # Extra info per agent
            extra = ""
            if agent_key == "sentiment":
                extra = ar.get("label", "")
            elif agent_key == "regime":
                extra = f"{ar.get('regime', '')} ({ar.get('confidence', 0):.0%})"
            elif agent_key == "alpha":
                extra = f"{ar.get('signals_found', 0)} signals"
            elif agent_key == "risk":
                extra = f"alloc {ar.get('final_allocation', 0):.0%}"
            elif agent_key == "timing":
                extra = ar.get("basket_signal", "")
            elif agent_key == "correlation":
                extra = f"avg {ar.get('avg_correlation', 0):.2f}"
            elif agent_key == "overfit_guardian":
                extra = ar.get("recommendation", "OK")
            elif agent_key == "meta":
                extra = f"score {ar.get('final_score', 0):.0f}"
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 8px;border-bottom:1px solid #1a1400"><span style="color:#d6a44a;font-size:9px">{label}</span><span style="color:#6a5a2a;font-size:9px">{extra}</span><span style="color:{adj_c};font-size:9px;font-weight:700">{adj:+.1f}</span></div>', unsafe_allow_html=True)

        active_agents = sla.get("agents_with_signal", [])
        active_label = " / ".join(active_agents) if active_agents else "нет"
        st.markdown(
            f'<div style="color:#6a5a2a;font-size:9px;margin-top:6px">'
            f'Агенты с измеримым вкладом: {len(active_agents)}/{max(1, sla_total - 2)}'
            f' · {active_label}</div>',
            unsafe_allow_html=True,
        )

        # Guardian status
        guardian = agent_results.get("overfit_guardian", {})
        if guardian.get("safety_ok") is False:
            st.markdown(f'<div style="background:#3a0000;border:1px solid #ff3b30;padding:6px;margin-top:6px;color:#ff3b30;font-size:10px;font-weight:700">GUARDIAN ALERT: {", ".join(guardian.get("safety_issues", []))}</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [10] BASKET SCORING — Bank-grade 8-criterion analysis
    # ═══════════════════════════════════════════════════════════════
    with st.expander("[10] BASKET SCORING    Bank-grade analysis"):
        try:
            from src.basket.scorer import SAMPLE_BASKETS, BasketScorer
            from src.basket.worst_of import WorstOfPredictor
            bs = BasketScorer()

            preset = st.selectbox(
                "Test basket", ["(current basket)"] + list(SAMPLE_BASKETS),
                key="basket_preset",
            )
            scored_tickers = (
                basket_tickers if preset == "(current basket)"
                else SAMPLE_BASKETS[preset]
            )
            st.caption("Underlyings: " + ", ".join(scored_tickers))
            report = bs.score_basket(scored_tickers)

            canonical_score = (
                float(score) if preset == "(current basket)" else report.total_score
            )
            canonical_grade = (
                "A+" if canonical_score >= 90
                else "A" if canonical_score >= 80
                else "B+" if canonical_score >= 70
                else "B" if canonical_score >= 60
                else "C" if canonical_score >= 50
                else "D"
            )
            grade_c = "#34c759" if canonical_score >= 70 else "#ffb000" if canonical_score >= 50 else "#ff3b30"
            score_label = (
                "Phoenix score (canonical)"
                if preset == "(current basket)"
                else "Diagnostic basket score"
            )
            st.markdown(f'''
            <div class="qc" style="border-left:3px solid {grade_c};padding:10px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div><span style="color:{grade_c};font-size:22px;font-weight:700">{canonical_grade}</span>
                    <span style="color:#d6a44a;font-size:11px;margin-left:8px">{score_label}</span></div>
                    <span style="color:{grade_c};font-size:20px;font-weight:700">{canonical_score:.1f}/100</span>
                </div>
            </div>''', unsafe_allow_html=True)
            if preset == "(current basket)":
                st.caption(
                    "The eight criteria below are diagnostics; the displayed "
                    "Phoenix score is the single score used by the verdict."
                )
            else:
                st.caption(report.recommendation)

            for criterion in report.criteria:
                raw_c = "#34c759" if criterion.raw_score >= 70 else "#ffb000" if criterion.raw_score >= 50 else "#ff3b30"
                bar_w = min(100, criterion.raw_score)
                st.markdown(f'''<div style="display:flex;align-items:center;gap:6px;margin:2px 0">
                    <span style="color:#d6a44a;font-size:10px;width:130px;text-align:right">{criterion.name}</span>
                    <div style="flex:1;height:8px;background:#1a1400"><div style="width:{bar_w}%;height:100%;background:{raw_c}"></div></div>
                    <span style="color:{raw_c};font-size:10px;width:30px;font-weight:700">{criterion.raw_score:.0f}</span>
                    <span style="color:#6a5a2a;font-size:8px;width:40px">w={criterion.weight:.2f}</span>
                </div>''', unsafe_allow_html=True)

            if report.red_flags:
                st.markdown(f'<div style="color:#ff3b30;font-size:10px;font-weight:700;margin-top:8px">RED FLAGS ({len(report.red_flags)})</div>', unsafe_allow_html=True)
                for flag in report.red_flags:
                    fc = "#ff3b30" if flag.severity == "critical" else "#fa8000"
                    st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 8px;border-bottom:1px solid #1a1400"><span style="color:{fc};font-size:9px">{flag.asset} — {flag.flag_type}</span><span style="color:#6a5a2a;font-size:9px">{flag.description}</span></div>', unsafe_allow_html=True)

            if report.worst_of_asset:
                st.markdown(f'<div style="color:#fa8000;font-size:10px;margin-top:6px">Worst-of: <b style="color:#ff3b30">{report.worst_of_asset}</b> — {report.worst_of_reason}</div>', unsafe_allow_html=True)

            wo_pred = WorstOfPredictor().predict(report.assets)
            if wo_pred:
                st.markdown('<div style="color:#ffb000;font-size:10px;font-weight:700;margin-top:8px">WORST-OF PROBABILITY</div>', unsafe_allow_html=True)
                for t, prob in sorted(wo_pred.items(), key=lambda x: -x[1]):
                    bar_w2 = prob * 100
                    st.markdown(f'''<div style="display:flex;align-items:center;gap:6px;margin:1px 0">
                        <span style="color:#d6a44a;font-size:10px;width:50px">{t}</span>
                        <div style="flex:1;height:10px;background:#1a1400"><div style="width:{bar_w2:.0f}%;height:100%;background:#fa8000"></div></div>
                        <span style="color:#ffb000;font-size:10px;width:40px">{prob:.1%}</span>
                    </div>''', unsafe_allow_html=True)
        except Exception as exc:
            st.markdown(f'<div style="color:#ff3b30;font-size:10px">Basket scoring error: {exc}</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [12] PAPER TRADING — Agent signals + portfolio
    # ═══════════════════════════════════════════════════════════════
    with st.expander("[11] PAPER TRADING    Agent · Portfolio · Signals"):
        try:
            from src.agents.paper_trader import PaperTradingAgent
            from src.agents.models import TradeAction

            agent = PaperTradingAgent(tickers=basket_tickers)
            portfolio = agent.get_portfolio()
            stats = agent.get_stats()

            st.markdown(f'''
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">
                <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">CASH</div><div style="color:#34c759;font-size:14px;font-weight:700">${portfolio.cash:,.0f}</div></div>
                <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">TOTAL VALUE</div><div style="color:#ffb000;font-size:14px;font-weight:700">${portfolio.total_value:,.0f}</div></div>
                <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">TRADES</div><div style="color:#ffb000;font-size:14px;font-weight:700">{stats.total_trades}</div></div>
                <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">WIN RATE</div><div style="color:{"#34c759" if stats.win_rate > 0.5 else "#ff3b30"};font-size:14px;font-weight:700">{stats.win_rate:.0%}</div></div>
                <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">SHARPE</div><div style="color:#ffb000;font-size:14px;font-weight:700">{stats.sharpe_ratio:.2f}</div></div>
            </div>''', unsafe_allow_html=True)

            st.markdown('<div style="color:#ffb000;font-size:10px;font-weight:700;margin:6px 0 4px">SIGNAL WEIGHTS</div>', unsafe_allow_html=True)
            for sig_name, sig_weight in sorted(agent._signal_weights.items(), key=lambda x: -x[1]):
                bar_w3 = sig_weight * 300
                st.markdown(f'''<div style="display:flex;align-items:center;gap:6px;margin:1px 0">
                    <span style="color:#d6a44a;font-size:9px;width:100px;text-align:right">{sig_name}</span>
                    <div style="flex:1;height:8px;background:#1a1400"><div style="width:{bar_w3:.0f}%;height:100%;background:#fa8000"></div></div>
                    <span style="color:#ffb000;font-size:9px;width:30px">{sig_weight:.0%}</span>
                </div>''', unsafe_allow_html=True)

            if portfolio.positions:
                st.markdown('<div style="color:#ffb000;font-size:10px;font-weight:700;margin:8px 0 4px">OPEN POSITIONS</div>', unsafe_allow_html=True)
                for pos in portfolio.positions:
                    pnl_c = "#34c759" if pos.unrealized_pnl >= 0 else "#ff3b30"
                    st.markdown(f'''<div style="display:flex;justify-content:space-between;padding:3px 8px;border-bottom:1px solid #1a1400">
                        <span style="color:#ffb000;font-size:10px;font-weight:700">{pos.ticker}</span>
                        <span style="color:#d6a44a;font-size:10px">Qty: {pos.quantity:.0f}</span>
                        <span style="color:#d6a44a;font-size:10px">Avg: ${pos.avg_entry_price:.2f}</span>
                        <span style="color:{pnl_c};font-size:10px;font-weight:700">P&L: ${pos.unrealized_pnl:+,.2f}</span>
                    </div>''', unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:#6a5a2a;font-size:10px">No open positions. Click "Generate Signal" to start.</div>', unsafe_allow_html=True)

            sig_col1, sig_col2 = st.columns(2)
            with sig_col1:
                if st.button("GENERATE SIGNAL", key="gen_signal", use_container_width=True):
                    for t in basket_tickers[:3]:
                        try:
                            import yfinance as _yf
                            hist = _yf.Ticker(t).history(period="3mo")
                            if not hist.empty:
                                prices = hist["Close"]
                                signals = agent._collect_signals(t, prices)
                                action, confidence = agent._make_decision(signals)
                                ac = "#34c759" if action == TradeAction.BUY else "#ff3b30" if action == TradeAction.SELL else "#ffb000"
                                st.markdown(f'<div style="padding:4px 8px;border:1px solid {ac}"><span style="color:{ac};font-size:12px;font-weight:700">{t}: {action.value.upper()}</span> <span style="color:#d6a44a;font-size:10px">conf={confidence:.2f}</span></div>', unsafe_allow_html=True)
                        except Exception:
                            st.markdown(f'<div style="color:#6a5a2a;font-size:10px">{t}: no data</div>', unsafe_allow_html=True)
        except Exception as exc:
            st.markdown(f'<div style="color:#ff3b30;font-size:10px">Paper trading error: {exc}</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [13] DATA & STORAGE — Database status + backup
    # ═══════════════════════════════════════════════════════════════
    with st.expander("[12] DATA & STORAGE    Database · Cloud · Backup"):
        try:
            from src.storage import Storage
            storage = Storage()
            status = storage.status()

            st.markdown('<div style="color:#ffb000;font-size:10px;font-weight:700;margin-bottom:4px">BACKEND STATUS</div>', unsafe_allow_html=True)
            backends = [
                ("SQLite", status.get("sqlite", False)),
                ("DuckDB", status.get("duckdb", False)),
                ("Supabase", status.get("supabase", False)),
                ("Firebase", status.get("firebase", False)),
                ("ClickHouse", status.get("clickhouse", False)),
                ("R2", status.get("r2", False)),
                ("Redis", status.get("redis", False)),
            ]
            for name, enabled in backends:
                dot = '<span style="color:#34c759">●</span>' if enabled else '<span style="color:#ff3b30">○</span>'
                st.markdown(f'<div style="display:flex;gap:8px;padding:2px 8px;border-bottom:1px solid #1a1400"><span style="font-size:10px">{dot}</span><span style="color:#d6a44a;font-size:10px">{name}</span><span style="color:#6a5a2a;font-size:10px">{"connected" if enabled else "disabled"}</span></div>', unsafe_allow_html=True)

            trade_count = len(storage.get_trades(limit=10000))
            st.markdown(f'<div style="color:#d6a44a;font-size:10px;margin-top:8px">Trades in DB: <b style="color:#ffb000">{trade_count}</b></div>', unsafe_allow_html=True)

            if st.button("BACKUP NOW", key="backup_now"):
                result = storage.backup()
                if result:
                    st.markdown('<div style="color:#34c759;font-size:10px">Backup created successfully</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="color:#ff3b30;font-size:10px">Backup failed</div>', unsafe_allow_html=True)
        except Exception as exc:
            st.markdown(f'<div style="color:#ff3b30;font-size:10px">Storage error: {exc}</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [18] BEST STRUCTURED PRODUCT — agent-driven product search
    # ═══════════════════════════════════════════════════════════════
    with st.expander("[13] BEST STRUCTURED PRODUCT    Universe search · Barrier/Tenor grid"):
        try:
            _res = _pipeline["product"]
            _universe = list(dict.fromkeys(list(basket_tickers) + [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "JPM", "XOM",
            ]))
            st.markdown(
                f'<div style="color:#d6a44a;font-size:9px;margin-bottom:4px">'
                f'Pipeline universe: {len(_universe)} tickers · basket size 3 · '
                f'barrier×tenor grid · stage: {_pipeline["stages"]["product"]}</div>',
                unsafe_allow_html=True)
            if "best" in _res:
                _b = _res["best"]
                _active_product_agents = len(_b.get("agents_with_signal", []))
                st.markdown(f'''<div style="color:#34c759;font-size:11px;padding:4px;border:1px solid #1a3a1a;border-radius:4px">
                    <b>{' / '.join(_b["basket"])}</b><br>
                    Barrier {_b["barrier"]}% · Tenor {_b["tenor_months"]}mo ·
                    Coupon ~{_b["coupon"]:.0f}% · P(loss) {_b["p_loss_pct"]:.0f}% ·
                    Tox {_b["avg_tox"]:.2f}<br>
                    Objective {_b["final_objective"]:.1f}
                    (agent adj {_b["agent_adjustment"]:+.1f}) ·
                    agents {_active_product_agents}/8 ·
                    evaluated {_res["n_evaluated"]} baskets</div>''',
                    unsafe_allow_html=True)
                st.markdown('<div style="color:#ffb000;font-size:10px;font-weight:700;margin:8px 0 4px">LEADERBOARD</div>', unsafe_allow_html=True)
                for _c in _res["leaderboard"]:
                    st.markdown(
                        f'<div style="color:#d6a44a;font-size:9px;border-bottom:1px solid #1a1400;padding:2px 0">'
                        f'{" / ".join(_c["basket"])} — obj {_c["final_objective"]:.1f} · '
                        f'{_c["barrier"]}%/{_c["tenor_months"]}mo · cpn {_c["coupon"]:.0f}%</div>',
                        unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div style="color:#ff9500;font-size:10px">No product: '
                    f'{_res.get("error", "unknown")}</div>',
                    unsafe_allow_html=True,
                )
        except Exception as exc:
            st.markdown(f'<div style="color:#ff3b30;font-size:10px">Product search error: {exc}</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [19] STRUCTURED NOTE OUTCOMES — explicit simulated/replay/realized states
    # ═══════════════════════════════════════════════════════════════
    with st.expander("[14] NOTE OUTCOMES    Simulation · Stress · Realized-only learning"):
        try:
            _quality = load_quality_report()
            _readiness = assess_commercial_readiness(
                D.get("evidence_gate", {}),
                _quality,
            )
            _readiness_color = (
                "#34c759" if _readiness["status"] == "production_review"
                else "#ffb000" if _readiness["status"] == "pilot_ready"
                else "#ff3b30"
            )
            st.markdown(
                f'<div style="border:1px solid {_readiness_color};padding:6px;margin-bottom:6px">'
                f'<div style="color:{_readiness_color};font-size:11px;font-weight:700">'
                f'COMMERCIAL STATUS: {_readiness["label"]}</div>'
                f'<div style="color:#d6a44a;font-size:9px">'
                f'{_readiness["allowed_claim"]} '
                f'Realized notes: {_readiness["realized_notes"]}; '
                f'historical windows: {_readiness["historical_windows"]}.</div>'
                f'<div style="color:#ff3b30;font-size:9px">'
                f'{_readiness["blocked_claim"]}</div></div>',
                unsafe_allow_html=True,
            )
            if _quality.get("status") != "not_available":
                st.markdown(
                    f'<div style="color:#d6a44a;font-size:9px;margin-bottom:6px">'
                    f'Quality confidence: <b>{_quality.get("confidence_pct", 0):.1f}%</b> · '
                    f'historical windows: {_quality.get("historical_windows", 0)} · '
                    f'realized notes: {_quality.get("realized_notes", 0)} · '
                    f'status: {_quality.get("status")}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                '<div style="color:#d6a44a;font-size:9px;margin-bottom:6px">'
                'Simulation is diagnostic only. It never trains agents; only '
                'a resolved paper note is marked realized.</div>',
                unsafe_allow_html=True,
            )
            _outcomes = _pipeline["stress"]
            if _outcomes:
                for _scenario, _report in _outcomes["scenarios"].items():
                    st.markdown(
                        f'<div style="color:#d6a44a;font-size:9px;border-bottom:1px solid #1a1400;padding:3px 0">'
                        f'<b>{_scenario}</b> · source={_report["source"]} · '
                        f'P(loss) {_report["p_loss"]:.1%} · '
                        f'P(KI) {_report["p_barrier_breach"]:.1%} · '
                        f'P(autocall) {_report["p_autocall"]:.1%} · '
                        f'E[return] {_report["mean_return_pct"]:+.2f}% · '
                        f'CVaR95 {_report["cvar_95"]:.3f}</div>',
                        unsafe_allow_html=True,
                    )
        except Exception as exc:
            st.markdown(f'<div style="color:#ff3b30;font-size:10px">Outcome engine error: {exc}</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [15] API & CONNECTIONS — Setup · Keys · Health Check
    # ═══════════════════════════════════════════════════════════════
    with st.expander("[15] API & CONNECTIONS    Setup · Keys · Health Check"):
        try:
            from src.api_manager import APIManager, SERVICES, mask_key
            api_mgr = APIManager(load_env=True)
            api_status = api_mgr.get_status()
            cached_probe = api_mgr.get_cached_probe()

            connected_count = api_status["connected"]
            total_count = api_status["total"]
            configured_count = api_status.get("configured", 0)
            st.markdown(f'''
            <div style="display:flex;gap:4px;margin-bottom:8px">
                <div class="qc" style="flex:1;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">LOCAL (always on)</div><div style="color:#34c759;font-size:12px;font-weight:700">SQLite + DuckDB</div></div>
                <div class="qc" style="flex:1;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">CLOUD VERIFIED</div><div style="color:#ffb000;font-size:14px;font-weight:700">{connected_count}/{total_count}</div><div style="color:#6a5a2a;font-size:8px">{configured_count} configured</div></div>
            </div>''', unsafe_allow_html=True)

            if cached_probe.get("cached"):
                probe_age = cached_probe.get("age_s")
                probe_label = (
                    "stale cache"
                    if cached_probe.get("stale")
                    else f'live probe {probe_age:.0f}s ago'
                )
                probe_color = "#ff9500" if cached_probe.get("stale") else "#34c759"
                st.markdown(
                    f'<div style="color:{probe_color};font-size:9px;margin-bottom:6px">'
                    f'Connectivity: {probe_label} · '
                    f'{cached_probe.get("connected", 0)} services reachable'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="color:#6a5a2a;font-size:9px;margin-bottom:6px">'
                    f'Connectivity: not probed yet · {configured_count} service(s) configured'
                    '</div>',
                    unsafe_allow_html=True,
                )

            for svc_id, svc_info in SERVICES.items():
                svc_status = api_status["services"][svc_id]
                has_keys = svc_status["has_keys"]
                is_connected = svc_status.get("connected", False)
                dot = '<span style="color:#34c759">●</span>' if is_connected else '<span style="color:#ffb000">○</span>' if has_keys else '<span style="color:#ff3b30">○</span>'
                status_text = (
                    "live verified" if is_connected
                    else "keys saved; not probed" if has_keys
                    else "not configured"
                )

                st.markdown(f'''<div style="display:flex;align-items:center;gap:8px;padding:4px 8px;border-bottom:1px solid #1a1400">
                    <span style="font-size:10px">{dot}</span>
                    <span style="color:#ffb000;font-size:10px;font-weight:700;width:100px">{svc_info["name"]}</span>
                    <span style="color:#6a5a2a;font-size:9px;flex:1">{svc_info["description"]}</span>
                    <span style="color:#d6a44a;font-size:9px">{status_text}</span>
                </div>''', unsafe_allow_html=True)

            st.markdown('<div style="color:#ffb000;font-size:10px;font-weight:700;margin:12px 0 6px">CONFIGURE SERVICE</div>', unsafe_allow_html=True)
            selected_svc = st.selectbox(
                "Select service to configure:",
                options=list(SERVICES.keys()),
                format_func=lambda x: f"{SERVICES[x]['name']} — {SERVICES[x]['description']}",
                key="api_service_select",
                label_visibility="collapsed",
            )

            if selected_svc:
                svc = SERVICES[selected_svc]
                st.markdown(f'<div style="color:#d6a44a;font-size:9px;margin-bottom:4px"><b>Setup:</b> <a href="{svc["signup_url"]}" target="_blank" style="color:#fa8000">{svc["signup_url"]}</a></div>', unsafe_allow_html=True)
                for step in svc["setup_steps"]:
                    st.markdown(f'<div style="color:#6a5a2a;font-size:9px;padding-left:8px">{step}</div>', unsafe_allow_html=True)

                current_keys = api_mgr.get_saved_keys(selected_svc)
                key_inputs = {}
                for key_name in svc["keys"]:
                    label = svc["key_labels"][key_name]
                    current_val = current_keys.get(key_name, "")
                    masked = mask_key(current_val) if current_val else ""
                    key_inputs[key_name] = st.text_input(
                        label,
                        value="",
                        placeholder=masked or f"Enter {key_name}",
                        key=f"api_key_{key_name}",
                        type="password",
                    )

                save_col, test_col = st.columns(2)
                with save_col:
                    if st.button("SAVE KEYS", key=f"save_{selected_svc}", use_container_width=True):
                        non_empty = {k: v for k, v in key_inputs.items() if v.strip()}
                        if non_empty:
                            if api_mgr.save_keys(selected_svc, non_empty):
                                st.markdown('<div style="color:#34c759;font-size:10px">Keys saved to .env</div>', unsafe_allow_html=True)
                            else:
                                st.markdown('<div style="color:#ff3b30;font-size:10px">Save failed</div>', unsafe_allow_html=True)
                        else:
                            st.markdown('<div style="color:#6a5a2a;font-size:10px">Enter at least one key</div>', unsafe_allow_html=True)

                with test_col:
                    if st.button("TEST CONNECTION", key=f"test_{selected_svc}", use_container_width=True):
                        test_result = api_mgr.test_connection(selected_svc)
                        if test_result["connected"]:
                            st.markdown(f'<div style="color:#34c759;font-size:10px">{test_result["message"]}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div style="color:#ff3b30;font-size:10px">{test_result["message"]}</div>', unsafe_allow_html=True)

            if st.button("TEST ALL CONNECTIONS", key="test_all_api", use_container_width=True):
                all_results = api_mgr.probe_connectivity(force=True)["results"]
                for svc_id_r, result in all_results.items():
                    c = "#34c759" if result["connected"] else "#ff3b30"
                    icon = "●" if result["connected"] else "○"
                    st.markdown(f'<div style="color:{c};font-size:10px">{icon} {SERVICES[svc_id_r]["name"]}: {result["message"]}</div>', unsafe_allow_html=True)

        except Exception as exc:
            st.markdown(f'<div style="color:#ff3b30;font-size:10px">API Manager error: {exc}</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════
    st.markdown('''
    <div style="margin-top:16px;padding:8px 14px;border-top:1px solid #3a2a00">
        <small style="color:#3a2a00;font-size:9px;line-height:1.4">
            P(KI): four model methods. Scoring: 12-factor Phoenix score + eight agents.
            Model performance is shown only when the relevant replay, paper, or realized evidence exists.
        </small>
    </div>
    ''', unsafe_allow_html=True)

now_utc = datetime.datetime.now(datetime.timezone.utc)
gdrive_st = "G-DRIVE" if GDRIVE_AVAILABLE else "LOCAL"
data_src_lbl = get_data_source_status().upper()
st.markdown(f'''
<div class="sbar">
    <span>NY {now_utc.strftime("%H:%M:%S")}</span>
    <span>ФЕНИКС <span class="ok">v36.0</span></span>
    <span>{data_src_lbl} <span class="ok">OK</span></span>
    <span>{gdrive_st} <span class="ok">OK</span></span>
    <span style="margin-left:auto"><span class="lb">PHOENIX TERMINAL</span></span>
</div>
''', unsafe_allow_html=True)
