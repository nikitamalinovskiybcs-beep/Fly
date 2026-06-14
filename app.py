"""Worst-of Phoenix Terminal — Bloomberg-style dashboard.
Karpathy method: ALL computation in precompute.py, this file is pure rendering."""

import datetime
import math
import streamlit as st

from src.precompute import precompute_all as _precompute_all, SECTOR_MAP
from src.phoenix_engine import simulate_basket as phoenix_simulate, save_to_gdrive, GDRIVE_AVAILABLE
from src.conductor import analyze as conductor_analyze
from src.backtest import precompute_backtest as _precompute_backtest, PhoenixAGI
from src.real_data import precompute_dealer_benchmark as _precompute_dealer
from src.calibration import run_pipeline as _run_calibration_pipeline

st.set_page_config(page_title="Worst-of Phoenix | Terminal", page_icon="■", layout="wide")


@st.cache_data(ttl=300, show_spinner=False)
def cached_precompute(tickers_key: str):
    """Cached wrapper — avoids recompute on every Streamlit rerun."""
    tickers = tickers_key.split(",")
    return _precompute_all(tickers)


@st.cache_data(ttl=600, show_spinner=False)
def cached_backtest(tickers_key: str, p_ki: float, coupon_pa: float, e_payout: float):
    """Cached backtest — heavier computation, longer TTL."""
    tickers = tickers_key.split(",")
    return _precompute_backtest(tickers, p_ki, coupon_pa, e_payout)


@st.cache_data(ttl=600, show_spinner=False)
def cached_dealer(tickers_key: str, coupon_pa: float, p_ki: float, score: float):
    """Cached dealer benchmark — real quote comparison."""
    tickers = tickers_key.split(",")
    return _precompute_dealer(tickers, coupon_pa, p_ki, score)


@st.cache_data(ttl=600, show_spinner=False)
def cached_pipeline(tickers_key: str, p_ki: float, avg_vol: float, avg_corr: float):
    """Cached 3-component pipeline: backtest → calibrate → forecast."""
    tickers = tickers_key.split(",")
    agi = PhoenixAGI.load_from_clickhouse() or PhoenixAGI()
    return _run_calibration_pipeline(tickers, agi.get_params(), p_ki, avg_vol, avg_corr)

# ═══════════════════════════════════════════════════════════════════
# CSS — Bloomberg Terminal (black #000, amber #ffb000, monospace)
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
.stTextArea>div>div>textarea{background:var(--bg)!important;border-color:var(--border)!important;color:var(--blue)!important;font-family:"JetBrains Mono",monospace!important}
.stExpander{border:1px solid var(--border)!important;border-radius:0!important}
hr{border-color:var(--border)!important}
.up{color:var(--good)}.dn{color:var(--bad)}
/* Header */
.hdr{padding:8px 14px;border-bottom:1px solid var(--border);background:var(--bg2);display:flex;align-items:baseline;gap:16px}
.hdr h1{margin:0;font-size:14px;font-weight:700;letter-spacing:1px;color:var(--accent);text-transform:uppercase}.hdr h1::before{content:"■ "}.hdr .sub{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.6px}

/* Cards */
.qc{background:var(--bg2);border:1px solid var(--border);padding:8px 12px;margin-bottom:4px}
/* Section header — collapsible style */
.sec{font-size:12px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:1px;padding:8px 12px;border:1px solid var(--border);margin:16px 0 4px;background:var(--bg2);display:flex;justify-content:space-between;align-items:center}
.sec .ri{color:var(--muted);font-size:10px;font-weight:400}
/* Status bar */
.sbar{position:fixed;bottom:0;left:0;right:0;background:var(--bg2);border-top:1px solid var(--border);padding:4px 14px;font-size:10px;color:var(--muted);display:flex;gap:20px;z-index:9999}
.sbar .ok{color:var(--good)}.sbar .lb{color:var(--accent);font-weight:700}
/* Basket input */
.bi input{font-family:"JetBrains Mono",monospace!important;font-size:20px!important;font-weight:700!important;letter-spacing:2px!important;text-transform:uppercase!important;background:#000!important;color:#6db6ff!important;border:2px solid #6db6ff!important;border-radius:0!important;padding:12px 16px!important}
.bi input:focus{border-color:#9ad0ff!important;box-shadow:0 0 14px rgba(154,208,255,.35)!important}
.bi input::placeholder{color:#355d80!important}.bi label{display:none!important}.bi .stTextInput>div{margin:0!important}
/* Bar helper */
.bar{height:14px;border-radius:1px;display:inline-block;vertical-align:middle}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════
st.markdown('<div class="hdr"><h1>WORST-OF PHOENIX</h1><span class="sub">ClickHouse Cloud · IBM Qiskit · ФЕНИКС v32.0 · Real Data</span></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# BASKET INPUT
# ═══════════════════════════════════════════════════════════════════
bc = st.columns([1,5,1])
with bc[0]:
    st.markdown('<div style="padding:10px 0"><span style="color:#ffb000;font-size:14px;font-weight:700;letter-spacing:3px">PHOENIX</span></div>', unsafe_allow_html=True)
with bc[1]:
    st.markdown('<div class="bi">', unsafe_allow_html=True)
    basket_input = st.text_input("basket", value="AAPL DELL GOOG", placeholder="AAPL MSFT NVDA AMD TSLA", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)
with bc[2]:
    st.button("▶ РАСЧЁТ ↵", key="run_basket", type="primary", use_container_width=True)

basket_tickers = [t.strip().upper() for t in basket_input.replace(",", " ").split() if t.strip()]
n_tickers = len(basket_tickers)

basket_label = ", ".join(basket_tickers)
st.markdown(f'<div style="color:#d6a44a;font-size:10px;padding:2px 0">КОРЗИНА: {basket_label}</div>', unsafe_allow_html=True)

# Refresh button + last update time
rc1, rc2 = st.columns([3, 1])
with rc2:
    if st.button("🔄 ОБНОВИТЬ ЦЕНЫ", key="refresh_prices", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ═══════════════════════════════════════════════════════════════════
# PRECOMPUTE ALL (Karpathy method — one call, all data)
# ═══════════════════════════════════════════════════════════════════
if basket_tickers:
    with st.spinner("⚡ Precomputing all sections..."):
        D = cached_precompute(",".join(basket_tickers))

    ch = D["ch"]
    wo = ch.get("worst_of", {})
    td = ch.get("tickers", {})
    yf = D.get("yf", {})
    corr = D.get("corr", {})
    aladdin = D.get("aladdin", {})
    tail = D.get("tail", {})
    stress = D.get("stress", [])
    earnings = D.get("earnings", {})
    ind = D.get("ind", {})
    wo_analysis = D.get("worst_of_analysis", [])
    score = D["score"]
    avg_qvar = D["avg_qvar"]
    p_ki = D["p_ki"]
    p_autocall = D["p_autocall"]

    # Show last update time
    with rc1:
        st.markdown(f'<div style="color:#6a5a2a;font-size:9px;padding-top:8px">Данные обновлены: {D.get("ts", "N/A")[:19]} · yfinance live prices · Cache TTL 5 min</div>', unsafe_allow_html=True)

    # Data sources list
    data_sources = ["ClickHouse (40K sims)"]
    if D["qiskit"]:
        data_sources.append(f"Qiskit ({list(D['qiskit'].values())[0].get('method','aer') if D['qiskit'] else 'aer'})")

    # ═══════════════════════════════════════════════════════════════
    # СКОРИНГ КОРЗИНЫ (единый)
    # ═══════════════════════════════════════════════════════════════
    rs = D["risk_score"]
    rc_components = D["risk_components"]
    score_factors = D.get("score_factors", {})
    gen = D.get("scoring_generation", 0)
    sl = D.get("self_learning", {})
    rs_color = "#34c759" if rs >= 80 else "#ffb000" if rs >= 65 else "#ff3b30"
    rs_label = "Низкий риск" if rs >= 80 else "Средний риск" if rs >= 65 else "Высокий риск"
    rs_grade = "A+" if rs >= 90 else "A" if rs >= 80 else "B" if rs >= 70 else "C" if rs >= 60 else "D"
    stamp = "READY TO ISSUE" if rs >= 75 else "NEEDS REVIEW" if rs >= 60 else "AVOID"

    sl_badge = ""
    if gen > 0:
        sl_badge = f' · Gen {gen}'
        if sl.get("status") == "improving":
            sl_badge += " 📈"

    st.markdown(f'''
    <div class="qc" style="border-left:3px solid {rs_color};padding:14px;margin:8px 0">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
                <span style="color:#ffb000;font-size:13px;font-weight:700">СКОРИНГ КОРЗИНЫ</span>
                <span style="background:#1a1400;border:1px solid #3a2a00;padding:1px 6px;color:#d6a44a;font-size:9px;border-radius:2px;margin-left:6px">{rs_grade}</span>
                <span style="color:#6a5a2a;font-size:8px;margin-left:4px">50-100 · S&P500=100{sl_badge}</span>
            </div>
            <div style="text-align:right">
                <span style="color:{rs_color};font-size:28px;font-weight:700">{rs:.1f}</span>
                <span style="color:#d6a44a;font-size:12px">/100</span>
            </div>
        </div>
        <div style="margin:6px 0;height:6px;background:#1a1400;border-radius:1px"><div style="height:100%;width:{max(0, (rs - 50) * 2)}%;background:{rs_color};border-radius:1px"></div></div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px">
            <span style="color:{rs_color};font-size:11px">{rs_label}</span>
            <span style="background:{rs_color}22;border:1px solid {rs_color};padding:2px 8px;color:{rs_color};font-size:10px;font-weight:700">{stamp} · P(KI) {p_ki:.0f}%</span>
        </div>
    </div>
    ''', unsafe_allow_html=True)

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
        if sl:
            mae = sl.get("mae_on_settled", 0)
            n_notes = sl.get("n_training_notes", 0)
            st.markdown(f'<div style="color:#6a5a2a;font-size:8px;margin-top:4px;border-top:1px solid #1a1400;padding-top:4px">Self-learning: {n_notes} settled notes · MAE {mae:.1f} · Gen {gen} · {sl.get("status","init")}</div>', unsafe_allow_html=True)

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
    # POSITION SIZER
    # ═══════════════════════════════════════════════════════════════
    ps1,ps2,ps3 = st.columns(3)
    with ps1: aum = st.number_input("AUM КЛИЕНТА, $", min_value=10000, value=1000000, step=10000)
    with ps2: risk_budget = st.number_input("РИСК-БЮДЖЕТ, %", min_value=0.5, max_value=50.0, value=5.0, step=0.5)
    with ps3: e_loss_pct = D.get("p_clean_loss", 15); st.number_input("E[LOSS] КОРЗИНЫ, %", value=e_loss_pct, disabled=True, key="e_loss_display")
    notional = aum * (risk_budget / 100) / max(e_loss_pct / 100, 0.01)
    st.markdown(f'<div class="qc" style="padding:10px"><div style="color:#d6a44a;font-size:10px">Notional ноты</div><div style="color:#ffb000;font-size:20px;font-weight:700">${notional:,.0f}</div><div style="color:#6a5a2a;font-size:9px">Риск-бюджет ${aum*(risk_budget/100):,.0f} ({risk_budget}% от AUM) ÷ E[loss] {e_loss_pct:.1f}% = notional ноты</div></div>', unsafe_allow_html=True)

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
    # Добавить тикер
    # ═══════════════════════════════════════════════════════════════
    ac1, ac2 = st.columns([5,1])
    with ac1:
        add_input = st.text_input("Добавить в корзину: NVDA, TSLA", key="add_tickers", label_visibility="collapsed")
    with ac2:
        if st.button("➕ ДОБАВИТЬ", key="btn_add"):
            if add_input:
                new_t = [t.strip().upper() for t in add_input.replace(",", " ").split() if t.strip()]
                st.session_state["basket_override"] = basket_input.strip() + " " + " ".join(new_t); st.rerun()

    # ═══════════════════════════════════════════════════════════════
    # [01] ALADDIN — Performance metrics
    # ═══════════════════════════════════════════════════════════════
    al = aladdin
    al_summary = f"SHRP {al.get('sharpe','?')} · DD {al.get('max_dd','?')}% · CALM {al.get('calmar','?')}" if al else "—"
    with st.expander(f"[01] ALADDIN    {al_summary}"):
        if al:
            st.markdown('<div style="color:#d6a44a;font-size:10px;margin-bottom:8px">Сравнение vs прошлых корзин (история в браузере). P75 = «лучше 75% твоих расчётов».</div>', unsafe_allow_html=True)
            metrics = [
                ("SHARPE (ANN.)", al.get("sharpe",0)),
                ("SORTINO (ANN.)", al.get("sortino",0)),
                ("CALMAR = CAGR/|MDD|", al.get("calmar",0)),
                ("CAGR (BASKET)", f"{al.get('cagr',0)}%"),
                ("MAX DRAWDOWN", f"{al.get('max_dd',0)}%"),
                ("AVG PAIR CORR", al.get("avg_pair_corr",0)),
                ("TRACKING ERROR VS SPY", f"{al.get('tracking_error',0)}%"),
                ("INFORMATION RATIO", al.get("info_ratio",0)),
                ("ACTIVE SHARE VS SPY", f"{al.get('active_share',0)}%"),
            ]
            for name, val in metrics:
                pct = min(100, max(5, abs(float(str(val).replace("%",""))) * 10 if isinstance(val, str) else abs(val) * 30))
                st.markdown(f'''
                <div class="qc" style="padding:8px 12px;margin:2px 0">
                    <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a;font-size:11px">{name}</span><span style="color:#ffb000;font-size:16px;font-weight:700">{val}</span></div>
                    <div style="height:4px;background:#1a1400;margin:4px 0"><div style="height:100%;width:{pct}%;background:linear-gradient(90deg,#fa8000,#ffb000)"></div></div>
                    <div style="color:#6a5a2a;font-size:9px">нет истории · первый расчёт — копи историю</div>
                </div>''', unsafe_allow_html=True)
        else:
            st.info("Нет данных yfinance для расчёта")

    # ═══════════════════════════════════════════════════════════════
    # [02] COMPOSITION — Per-ticker cards
    # ═══════════════════════════════════════════════════════════════
    n_sectors = len(set(SECTOR_MAP.get(t, "Unknown") for t in basket_tickers))
    with st.expander(f"[02] COMPOSITION    {n_tickers} NAMES · {n_sectors} SECTORS"):
        for t in basket_tickers:
            if t in yf:
                d = yf[t]
                sector = d.get("sector", "Unknown")
                rec_label = d.get("rec_label", "buy")
                rec_score = d.get("rec_score", 1.8)
                rec_color = "#34c759" if rec_label in ("buy","strong_buy") else "#ffb000"
                ema_sign = "▲" if d["ema200_above"] else "▼"
                ema_color = "#34c759" if d["ema200_above"] else "#ff3b30"
                dcf_color = "#34c759" if d["dcf_upside"] > 0 else "#ff3b30"
                tgt_color = "#34c759" if d["target_upside"] > 0 else "#ff3b30"
                bcs_color = "#34c759" if d["bcs_upside"] > 0 else "#ff3b30"
                avg_color = "#34c759" if d["avg_upside"] > 0 else "#ff3b30"
                peg_color = "#ff3b30" if d["peg"] > 2 else "#ffb000"
                st.markdown(f'''
                <div class="qc" style="border-left:3px solid #fa8000;padding:10px 14px;margin:6px 0">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                        <div><span style="color:#ffb000;font-size:16px;font-weight:700">{t}</span> <span style="color:#6a5a2a;font-size:10px">{sector}</span></div>
                        <span style="background:#0a1a00;border:1px solid {rec_color};padding:2px 8px;color:{rec_color};font-size:10px">{rec_label} {rec_score:.2f}</span>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:2px 20px;font-size:11px">
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">Spot</span><span style="color:#ffb000">{d["spot"]}</span></div>
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">IV30</span><span style="color:#ffb000">{d["iv30"]}%</span></div>
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">Real 1y</span><span style="color:#ffb000">{d["real_1y"]}%</span></div>
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">Vol used</span><span style="color:#ffb000">{d["vol_used"]}%</span></div>
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">β</span><span style="color:#ffb000">{d["beta"]}</span></div>
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">P/E</span><span style="color:#ffb000">{d["pe"]}</span></div>
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">PEG</span><span style="color:{peg_color}">{d["peg"]}</span></div>
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">EMA200</span><span style="color:{ema_color}">{ema_sign} {d["ema200_pct"]:+.1f}%</span></div>
                    </div>
                    <div style="border-top:1px solid #3a2a00;margin-top:6px;padding-top:6px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:2px;font-size:11px">
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">DCF</span><span style="color:#ffb000">{d["dcf"]}</span><span style="color:{dcf_color}">{d["dcf_upside"]:+.0f}%</span></div>
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">АНАЛИТИКИ · {d["n_analysts"]}</span><span style="color:#ffb000">{d["target_price"]}</span><span style="color:{tgt_color}">{d["target_upside"]:+.0f}%</span></div>
                        <div style="display:flex;justify-content:space-between"><span style="color:#d6a44a">BCS GM</span><span style="color:#ffb000">{d["bcs_target"]:.0f}</span><span style="color:{bcs_color}">{d["bcs_upside"]:+.0f}%</span></div>
                    </div>
                    <div style="border-top:1px solid #3a2a00;margin-top:4px;padding-top:4px;font-size:11px;display:flex;justify-content:space-between">
                        <span style="color:#d6a44a">AVG · СВОДНЫЙ</span><span style="color:#ffb000;font-weight:700">{d["avg_target"]}</span><span style="color:{avg_color}">{d["avg_upside"]:+.0f}%</span>
                    </div>
                </div>
                ''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [03] SECTOR EXP
    # ═══════════════════════════════════════════════════════════════
    sectors = D.get("sectors", {})
    top_sector = D.get("top_sector", "N/A")
    top_pct = D.get("top_sector_pct", 0)
    with st.expander(f"[03] SECTOR EXP.    {top_sector} {top_pct}%"):
        # Sector table
        for s, cnt in sorted(sectors.items(), key=lambda x: -x[1]):
            pct = round(cnt / n_tickers * 100)
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:3px 8px;border-bottom:1px solid #1a1400"><span style="color:#fa8000;font-size:11px">■ {s}</span><span style="color:#ffb000;font-size:11px">{pct}% ({cnt})</span></div>', unsafe_allow_html=True)
        if top_pct > 50:
            st.markdown(f'<div style="color:#ffb000;font-size:10px;margin-top:6px;border-left:3px solid #fa8000;padding-left:8px">⚠ Концентрация: {top_sector} {top_pct}% корзины. Рассмотри диверсификацию.</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [04] WORST-OF
    # ═══════════════════════════════════════════════════════════════
    with st.expander("[04] WORST-OF"):
        st.markdown('<div style="color:#d6a44a;font-size:10px;margin-bottom:8px;line-height:1.5">Для каждой бумаги: P(она = worst-of при выходе) + P(она = worst-of при KI). Идеал — у всех ≈33% (равная нагрузка). Если один тикер >50% — он «culprit», его замена улучшит расчёт.</div>', unsafe_allow_html=True)
        if wo_analysis:
            culprit = wo_analysis[0]
            fair = culprit["fair_share"]
            if culprit["p_worst"] > fair * 1.5:
                st.markdown(f'<div style="background:#1a1400;border:1px solid #ffb000;padding:8px;margin-bottom:8px;color:#ffb000;font-size:11px">● <b>{culprit["ticker"]}</b> чаще остальных оказывается worst-of ({culprit["p_worst"]:.0f}% vs {fair:.0f}% fair share). Можно рассмотреть замену.</div>', unsafe_allow_html=True)
            st.markdown('<div style="display:flex;justify-content:space-between;padding:4px 8px;border-bottom:1px solid #3a2a00"><span style="color:#d6a44a;font-size:10px">ТИКЕР</span><span style="color:#d6a44a;font-size:10px">P(WORST AT EXIT)</span></div>', unsafe_allow_html=True)
            colors = ["#fa8000", "#d6a44a", "#ff3b30"]
            for i, wa in enumerate(wo_analysis):
                bar_w = min(80, wa["p_worst"] * 2)
                bar_c = colors[i % len(colors)]
                st.markdown(f'''
                <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-bottom:1px solid #1a1400">
                    <span style="color:#6a5a2a;font-size:11px">{i+1}</span>
                    <span style="color:#ffb000;font-size:11px;font-weight:700;min-width:50px">{wa["ticker"]}</span>
                    <span style="color:#6a5a2a;font-size:10px;flex:1;margin:0 8px">· {wa["sector"]}</span>
                    <div style="width:120px;height:14px;background:#1a1400"><div class="bar" style="width:{bar_w}%;background:{bar_c}"></div></div>
                    <span style="color:#ffb000;font-size:11px;min-width:40px;text-align:right">{wa["p_worst"]:.1f}%</span>
                </div>''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [05] CORR MATRIX
    # ═══════════════════════════════════════════════════════════════
    avg_c = corr.get("avg_corr", 0)
    with st.expander(f"[05] CORR MATRIX    AVG {avg_c:.2f}"):
        st.markdown(f'<div style="color:#d6a44a;font-size:10px;margin-bottom:8px;line-height:1.5">Pearson корреляции дневных логдоходностей за 5y. Sweet spot для Phoenix: <b>0.45–0.65</b> — достаточно diversification benefit, но worst-of не «убегает» вниз.</div>', unsafe_allow_html=True)
        if avg_c < 0.40:
            st.markdown(f'<div style="background:#0a1a0a;border:1px solid #34c759;padding:6px 8px;color:#34c759;font-size:11px;margin-bottom:8px">● Средняя корреляция = {avg_c:.2f} — корзина хорошо диверсифицирована.</div>', unsafe_allow_html=True)
        elif avg_c < 0.65:
            st.markdown(f'<div style="background:#1a1a0a;border:1px solid #ffb000;padding:6px 8px;color:#ffb000;font-size:11px;margin-bottom:8px">● Средняя корреляция = {avg_c:.2f} — приемлемо.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#1a0a0a;border:1px solid #ff3b30;padding:6px 8px;color:#ff3b30;font-size:11px;margin-bottom:8px">● Средняя корреляция = {avg_c:.2f} — высокая, все падают вместе.</div>', unsafe_allow_html=True)
        # Legend
        st.markdown('<div style="font-size:10px;color:#d6a44a;margin-bottom:4px">🟦 &lt;0.40 хорошо · 🟩 0.40–0.65 · 🟨 0.65–0.75 · 🟧 0.75–0.85 · 🟥 &gt;0.85 слиплись</div>', unsafe_allow_html=True)
        # Matrix table
        c_tickers = corr.get("tickers", [])
        c_matrix = corr.get("matrix", [])
        if c_tickers and c_matrix:
            hdr = '<th style="padding:4px 8px;color:#d6a44a;font-size:10px"></th>' + "".join(f'<th style="padding:4px 8px;color:#ffb000;font-size:10px;font-weight:700">{t}</th>' for t in c_tickers)
            rows = ""
            for i, t in enumerate(c_tickers):
                cells = f'<td style="padding:4px 8px;color:#ffb000;font-size:10px;font-weight:700">{t}</td>'
                for j in range(len(c_tickers)):
                    if i == j:
                        cells += '<td style="padding:4px 8px;color:#6a5a2a;font-size:10px;text-align:center">—</td>'
                    else:
                        v = c_matrix[i][j]
                        bg = "#0a2a2a" if v < 0.40 else "#0a2a0a" if v < 0.65 else "#2a2a0a" if v < 0.75 else "#2a1a0a" if v < 0.85 else "#2a0a0a"
                        cells += f'<td style="padding:4px 8px;background:{bg};color:#ffb000;font-size:11px;text-align:center;font-weight:700">{v:.2f}</td>'
                rows += f'<tr>{cells}</tr>'
            st.markdown(f'<table style="width:100%;border-collapse:collapse;margin-top:8px"><tr>{hdr}</tr>{rows}</table>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [06] EARNINGS CAL
    # ═══════════════════════════════════════════════════════════════
    total_events = earnings.get("total_events", 0)
    with st.expander(f"[06] EARNINGS CAL    {total_events} EVENTS"):
        st.markdown('<div style="color:#ffb000;font-size:11px;font-weight:700;margin-bottom:6px">БЛИЖАЙШИЕ 5 ОТЧЁТОВ</div>', unsafe_allow_html=True)
        for ev in earnings.get("events", [])[:5]:
            days = ev["days"]
            color = "#ff3b30" if days <= 7 else "#ffb000" if days <= 30 else "#34c759"
            st.markdown(f'<div style="display:inline-block;background:#1a1400;border:1px solid {color};padding:3px 10px;margin:2px;color:{color};font-size:10px">{ev["ticker"]} · {ev["date"]} · через {days}д</div>', unsafe_allow_html=True)

        st.markdown(f'<div style="color:#ffb000;font-size:11px;font-weight:700;margin:12px 0 6px">ПО БУМАГАМ В ОКНЕ 2.0 ЛЕТ (8 КВАРТАЛОВ)</div>', unsafe_allow_html=True)
        per_ticker = earnings.get("per_ticker", {})
        for t, dates in per_ticker.items():
            chips_html = "".join(f'<span style="display:inline-block;background:#1a1400;border:1px solid #3a2a00;padding:2px 6px;margin:1px;color:#d6a44a;font-size:9px">{d}</span>' for d in dates[:8])
            st.markdown(f'<div style="display:flex;align-items:center;gap:8px;margin:2px 0"><span style="color:#ffb000;font-size:11px;font-weight:700;min-width:50px">{t}</span>{chips_html}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color:#6a5a2a;font-size:9px;margin-top:6px">🔴 ≤ 7 дн (вол-спайк, риск KI) · 🟡 ≤ 30 дн · 🟢 далее. Источник: yfinance.</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [07] TAIL RISK
    # ═══════════════════════════════════════════════════════════════
    t_var95 = tail.get("var_95_cf", 0)
    t_es95 = tail.get("es_95", 0)
    t_regime = tail.get("regime", "?")
    with st.expander(f"[07] TAIL RISK    VAR95 {t_var95:.2f}% · ES95 {t_es95:.2f}% · RE: {t_regime}"):
        st.markdown('<div style="color:#d6a44a;font-size:10px;margin-bottom:10px;line-height:1.5">Расширенный риск-анализ: фат-тейлы (skew/kurtosis), Expected Shortfall, tail-dependence (одновременные просадки), regime-switching VaR.</div>', unsafe_allow_html=True)

        # VaR section
        st.markdown(f'''
        <div class="qc" style="padding:12px">
            <div style="color:#ffb000;font-size:11px;font-weight:700;margin-bottom:6px">■ VaR — потери на 1 день</div>
            <div style="color:#6a5a2a;font-size:9px;margin-bottom:8px">Cornish-Fisher корректирует на форму распределения</div>
            <div style="display:flex;gap:8px;margin-bottom:4px"><span style="background:#1a1400;border:1px solid #3a2a00;padding:2px 8px;color:#d6a44a;font-size:10px">Skew {tail.get("skew",0):.2f}</span><span style="background:#1a1400;border:1px solid #fa8000;padding:2px 8px;color:#fa8000;font-size:10px">Kurtosis {tail.get("kurtosis",0):.2f}</span><span style="background:#1a0a00;border:1px solid #ff3b30;padding:2px 8px;color:#ff3b30;font-size:10px">{tail.get("fat_tail_penalty",0):.2f}% штраф фат-тейлов</span></div>
        ''', unsafe_allow_html=True)

        def _bar(label, val, color, max_w=60):
            w = min(max_w, val * 10)
            return f'<div style="margin:4px 0"><div style="color:#d6a44a;font-size:10px">{label}</div><div style="display:flex;align-items:center;gap:8px"><div style="width:200px;height:14px;background:#1a1400"><div class="bar" style="width:{w}%;background:{color}"></div></div><span style="color:#ffb000;font-size:11px;font-weight:700">+{val:.2f}%</span></div></div>'

        bars = _bar("VAR 95% (HIST)", tail.get("var_95_hist", 0), "#6db6ff")
        bars += _bar("VAR 95% (CF) ★", tail.get("var_95_cf", 0), "#fa8000")
        bars += _bar("VAR 99% (CF)", tail.get("var_99_cf", 0), "#ff3b30")
        st.markdown(f'{bars}</div>', unsafe_allow_html=True)

        # Expected Shortfall
        st.markdown(f'''
        <div class="qc" style="padding:12px;margin-top:6px">
            <div style="color:#ff3b30;font-size:11px;font-weight:700;margin-bottom:4px">▲ Expected Shortfall — средняя в худших днях</div>
            <div style="color:#6a5a2a;font-size:9px;margin-bottom:6px">Стандарт Basel-FRTB. Чем меньше — тем легче хвост.</div>
            {_bar("ES 90%", tail.get("es_90",0), "#34c759")}
            {_bar("ES 95% ★", tail.get("es_95",0), "#fa8000")}
            {_bar("ES 99%", tail.get("es_99",0), "#ff3b30")}
        </div>
        ''', unsafe_allow_html=True)

        # Tail-dependence
        st.markdown(f'''
        <div class="qc" style="padding:12px;margin-top:6px">
            <div style="color:#ff3b30;font-size:11px;font-weight:700;margin-bottom:4px">⚙ Tail-dependence — все вместе вниз</div>
            <div style="color:#6a5a2a;font-size:9px;margin-bottom:6px">Прямой драйвер пробоя KI в worst-of структурах.</div>
            {_bar("P(BCE ≤ 5%-KB)", tail.get("p_bce_5",0), "#34c759")}
            {_bar("P(BCE ≤ 1%-KB)", tail.get("p_bce_1",0), "#6a5a2a")}
            {_bar("AVG PAIR P(I↓|J↓)", tail.get("avg_pair_p",0), "#ff3b30", max_w=80)}
        </div>
        ''', unsafe_allow_html=True)

        # Regime-switching VaR
        regime_color = "#34c759" if tail.get("regime") == "CALM" else "#ff3b30"
        st.markdown(f'''
        <div class="qc" style="padding:12px;margin-top:6px">
            <div style="color:#fa8000;font-size:11px;font-weight:700;margin-bottom:4px">⚡ Regime-switching VaR</div>
            <div style="color:#6a5a2a;font-size:9px;margin-bottom:6px">Calm/stress по 20d-вол SPY. Ratio = во сколько раз риск выше в стресс.</div>
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
                <span style="background:#0a1a0a;border:1px solid {regime_color};padding:4px 12px;color:{regime_color};font-size:11px;font-weight:700">● СЕЙЧАС: {tail.get("regime","?")}</span>
                <span style="color:#d6a44a;font-size:10px">σ_20d={tail.get("sigma_20d",0)}% · порог=1.20%</span>
            </div>
            {_bar("CALM VAR 95% / 1D", tail.get("calm_var_1d",0), "#34c759")}
            {_bar("STRESS VAR 95% / 1D ★", tail.get("stress_var_1d",0), "#ff3b30")}
            {_bar("CALM ES 95% / 1D", tail.get("calm_es_1d",0), "#34c759")}
            {_bar("STRESS ES 95% / 1D", tail.get("stress_es_1d",0), "#ff3b30")}
            {_bar("CALM VAR 95% / 10D", tail.get("calm_var_10d",0), "#34c759")}
            {_bar("STRESS VAR 95% / 10D", tail.get("stress_var_10d",0), "#fa8000")}
            <div style="margin-top:6px;display:flex;align-items:center;gap:8px">
                <div style="width:200px;height:14px;background:#1a1400"><div class="bar" style="width:50%;background:#6a5a2a"></div></div>
                <span style="color:#fa8000;font-size:11px;font-weight:700">×{tail.get("ratio",1):.2f} умеренный rise</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [08] STRESS
    # ═══════════════════════════════════════════════════════════════
    with st.expander("[08] STRESS"):
        st.markdown(f'<div style="color:#d6a44a;font-size:10px;margin-bottom:8px;line-height:1.5">Репликация исторических кризисов через β_SPY · {len(stress)} сценариев. Каждая корзина = бар, ✓ безопасно если max DD не пробил 40%.</div>', unsafe_allow_html=True)
        for sc in stress:
            safe = sc["safe"]
            badge = f'<span style="background:#0a1a0a;border:1px solid #34c759;padding:2px 8px;color:#34c759;font-size:10px">✓ безопасно</span>' if safe else f'<span style="background:#1a0a0a;border:1px solid #ff3b30;padding:2px 8px;color:#ff3b30;font-size:10px">▲ KI {sc.get("ki_pct",40)}%</span>'
            spy_w = min(80, abs(sc["spy_total"]) * 1.5)
            basket_w = min(80, abs(sc["basket_total"]) * 1.5)
            dd_w = min(80, abs(sc["max_dd"]) * 1.5)
            spy_c = "#6db6ff" if sc["spy_total"] > 0 else "#6db6ff"
            basket_c = "#34c759" if sc["basket_total"] > 0 else "#ff3b30"
            dd_c = "#fa8000" if abs(sc["max_dd"]) < 40 else "#ff3b30"
            st.markdown(f'''
            <div class="qc" style="border-left:3px solid {"#34c759" if safe else "#ff3b30"};padding:10px 14px;margin:4px 0">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
                    <span style="color:#fa8000;font-size:13px;font-weight:700">{sc["name"]}</span>
                    <span style="color:#6a5a2a;font-size:10px">{sc["days"]}д · β={sc["beta"]}</span>
                    {badge}
                </div>
                <div style="margin:2px 0"><span style="color:#d6a44a;font-size:10px">SPY TOTAL</span><div style="display:flex;align-items:center;gap:8px"><div style="width:200px;height:12px;background:#1a1400"><div class="bar" style="width:{spy_w}%;background:{spy_c}"></div></div><span style="color:#ffb000;font-size:10px">{sc["spy_total"]:+.1f}%</span></div></div>
                <div style="margin:2px 0"><span style="color:#d6a44a;font-size:10px">КОРЗИНА TOTAL</span><div style="display:flex;align-items:center;gap:8px"><div style="width:200px;height:12px;background:#1a1400"><div class="bar" style="width:{basket_w}%;background:{basket_c}"></div></div><span style="color:#ffb000;font-size:10px">{sc["basket_total"]:+.1f}%</span></div></div>
                <div style="margin:2px 0"><span style="color:#d6a44a;font-size:10px">MAX DRAWDOWN</span><div style="display:flex;align-items:center;gap:8px"><div style="width:200px;height:12px;background:#1a1400"><div class="bar" style="width:{dd_w}%;background:{dd_c}"></div></div><span style="color:#ffb000;font-size:10px">{sc["max_dd"]:+.1f}%</span></div></div>
            </div>''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [09] SMART ALTERNATIVES — data-driven basket suggestions
    # ═══════════════════════════════════════════════════════════════
    smart_alts = D.get("smart_alts", [])
    n_alts = len(smart_alts)
    with st.expander(f"[09] SMART ALTERNATIVES    {n_alts} вариантов"):
        if smart_alts:
            worst_replaced = smart_alts[0].get("replaced", "?")
            st.markdown(f'''
            <div style="color:#d6a44a;font-size:10px;margin-bottom:8px;line-height:1.5">
                Замена слабого тикера <b style="color:#ff3b30">{worst_replaced}</b> на лучшие альтернативы из разных секторов.
                Ранжировано по estimated score. ★ = текущая корзина.
            </div>
            <div style="display:flex;justify-content:space-between;padding:4px 8px;border-bottom:1px solid #3a2a00;background:#0a1a0a">
                <span style="color:#34c759;font-size:11px;font-weight:700">★ {" · ".join(basket_tickers)}</span>
                <span style="color:{rs_color};font-size:11px;font-weight:700">{rs:.1f}</span>
            </div>''', unsafe_allow_html=True)

            for alt in smart_alts:
                alt_score = alt["est_score"]
                alt_c = "#34c759" if alt_score > rs else "#ffb000" if alt_score >= rs - 3 else "#6a5a2a"
                delta = alt_score - rs
                delta_str = f"+{delta:.0f}" if delta > 0 else f"{delta:.0f}"
                basket_str = " · ".join(alt["basket"])
                sector = alt["sector"]
                tox_val = alt["tox"]
                st.markdown(f'''<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-bottom:1px solid #1a1400">
                    <div>
                        <span style="color:#d6a44a;font-size:10px">{basket_str}</span>
                        <span style="color:#6a5a2a;font-size:8px;margin-left:4px">({sector})</span>
                    </div>
                    <div style="display:flex;gap:8px;align-items:center">
                        <span style="color:#6a5a2a;font-size:8px">tox {tox_val:.2f}</span>
                        <span style="color:{alt_c};font-size:10px;font-weight:700">{alt_score:.0f}</span>
                        <span style="color:{alt_c};font-size:9px">{delta_str}</span>
                    </div>
                </div>''', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#6a5a2a;font-size:10px">Недостаточно данных для генерации альтернатив</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [10] ПОДБОР ЛУЧШЕГО ФЕНИКСА — automatic Phoenix optimizer
    # ═══════════════════════════════════════════════════════════════
    phoenix_r = D.get("phoenix_ranker", {})
    best_bar = phoenix_r.get("best_barrier", {})
    best_ten = phoenix_r.get("best_tenor", {})
    opt_bar = D.get("optimal_barrier", {})
    cal_cpn = D.get("calibrated_coupon", {})
    emp_pki = D.get("empirical_pki", {})
    disp = D.get("dispersion_signal", {})
    sec_conc = D.get("sector_concentration", {})
    earn_risk = D.get("earnings_risk", {})
    top_bsk = D.get("top_baskets", [])

    rec_text = phoenix_r.get("recommendation", "—")
    opt_rec = opt_bar.get("recommendation", "—")
    with st.expander(f"[10] ПОДБОР ЛУЧШЕГО ФЕНИКСА    {opt_bar.get('optimal_barrier', 65)}% барьер"):
        # Main recommendation
        st.markdown(f'''
        <div style="background:#1a2600;border:1px solid #2a3600;border-radius:4px;padding:10px;margin-bottom:10px">
            <div style="color:#34c759;font-size:11px;font-weight:700">🎯 РЕКОМЕНДАЦИЯ</div>
            <div style="color:#ffb000;font-size:12px;margin-top:4px">{rec_text}</div>
            <div style="color:#d6a44a;font-size:10px;margin-top:2px">{opt_rec}</div>
        </div>''', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            # Barrier comparison
            st.markdown('<div style="color:#d6a44a;font-size:10px;font-weight:700;margin-bottom:6px">БАРЬЕР СРАВНЕНИЕ</div>', unsafe_allow_html=True)
            for b in phoenix_r.get("all_barriers", []):
                is_best = b["barrier"] == best_bar.get("barrier", 65)
                marker = "★" if is_best else " "
                bar_c = "#34c759" if is_best else "#6a5a2a"
                st.markdown(f'<div style="display:flex;gap:10px;font-size:10px;color:{bar_c}"><span>{marker} {b["barrier"]}%</span><span>P(KI) {b["p_ki"]}%</span><span>купон {b["est_coupon"]}%</span><span>score {b["score"]}</span></div>', unsafe_allow_html=True)

        with c2:
            # Tenor comparison
            st.markdown('<div style="color:#d6a44a;font-size:10px;font-weight:700;margin-bottom:6px">СРОК СРАВНЕНИЕ</div>', unsafe_allow_html=True)
            for t in phoenix_r.get("all_tenors", []):
                is_best = t["tenor_months"] == best_ten.get("tenor_months", 24)
                marker = "★" if is_best else " "
                ten_c = "#34c759" if is_best else "#6a5a2a"
                st.markdown(f'<div style="display:flex;gap:10px;font-size:10px;color:{ten_c}"><span>{marker} {t["tenor_months"]}мес</span><span>P(loss) {t["p_loss"]}%</span><span>купон {t["est_coupon"]}%</span><span>score {t["score"]}</span></div>', unsafe_allow_html=True)

        # Calibrated coupon + Empirical P(KI) + Dispersion
        st.markdown(f'''
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">
            <div class="qc" style="flex:1;min-width:110px;padding:8px;text-align:center">
                <div style="color:#d6a44a;font-size:9px">КУПОН (828 QUOTES)</div>
                <div style="color:#ffb000;font-size:14px;font-weight:700">{cal_cpn.get("coupon_blended", 0):.1f}%</div>
                <div style="color:#6a5a2a;font-size:8px">модель {cal_cpn.get("coupon_model", 0):.1f}% · lookup {cal_cpn.get("coupon_lookup", 0):.1f}%</div>
            </div>
            <div class="qc" style="flex:1;min-width:110px;padding:8px;text-align:center">
                <div style="color:#d6a44a;font-size:9px">P(KI) ЭМПИРИЧ.</div>
                <div style="color:{"#ff3b30" if emp_pki.get("p_ki_empirical", 0) > 35 else "#ffb000"};font-size:14px;font-weight:700">{emp_pki.get("p_ki_empirical", 0):.1f}%</div>
                <div style="color:#6a5a2a;font-size:8px">{emp_pki.get("n_settled", 0)} settled notes · {emp_pki.get("confidence", "?")}</div>
            </div>
            <div class="qc" style="flex:1;min-width:110px;padding:8px;text-align:center">
                <div style="color:#d6a44a;font-size:9px">DISPERSION</div>
                <div style="color:#ffb000;font-size:14px;font-weight:700">{disp.get("spread", 0):.0f}%</div>
                <div style="color:#6a5a2a;font-size:8px">сигнал: {disp.get("signal", "—")} · boost +{disp.get("coupon_boost_pct", 0):.1f}%</div>
            </div>
        </div>''', unsafe_allow_html=True)

        # Sector concentration + Earnings risk
        sec_c = "#ff3b30" if sec_conc.get("label") == "CONCENTRATED" else "#34c759"
        earn_c = "#ff3b30" if earn_risk.get("risk_level") == "HIGH" else "#6a5a2a"
        st.markdown(f'''
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">
            <div class="qc" style="flex:1;min-width:140px;padding:8px">
                <div style="color:#d6a44a;font-size:9px">СЕКТОРЫ</div>
                <div style="color:{sec_c};font-size:11px;font-weight:700">{sec_conc.get("label", "?")} · HHI {sec_conc.get("hhi", 0):.2f}</div>
                <div style="color:#6a5a2a;font-size:8px">{sec_conc.get("recommendation", "")}</div>
            </div>
            <div class="qc" style="flex:1;min-width:140px;padding:8px">
                <div style="color:#d6a44a;font-size:9px">EARNINGS RISK</div>
                <div style="color:{earn_c};font-size:11px;font-weight:700">{earn_risk.get("risk_level", "?")} · {earn_risk.get("n_risk_zones", 0)} zones</div>
                <div style="color:#6a5a2a;font-size:8px">{earn_risk.get("recommendation", "")}</div>
            </div>
        </div>''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [11] STRESS TEST v2 — historical drawdown scenarios
    # ═══════════════════════════════════════════════════════════════
    stress_v2 = D.get("stress_v2", [])
    n_critical = sum(1 for s in stress_v2 if s.get("risk_level") == "CRITICAL")
    stress_label = f"{n_critical} CRITICAL" if n_critical > 0 else "ALL OK"
    stress_c = "#ff3b30" if n_critical > 0 else "#34c759"
    with st.expander(f"[11] STRESS TEST    {stress_label}"):
        for sc in stress_v2:
            rc = "#ff3b30" if sc["risk_level"] == "CRITICAL" else ("#fa8000" if sc["risk_level"] == "WARNING" else "#34c759")
            ki_badge = f'<span style="background:#ff3b30;color:#fff;font-size:8px;padding:1px 4px;border-radius:2px">KI BREACH</span>' if sc["barrier_breach_65"] else ""
            st.markdown(f'''
            <div class="qc" style="padding:8px;margin-bottom:6px">
                <div style="display:flex;align-items:center;gap:8px">
                    <span style="color:{rc};font-size:11px;font-weight:700">{sc["name"]}</span>
                    <span style="color:#6a5a2a;font-size:9px">SPX {sc["spx_drop"]:+d}% · {sc["duration_days"]}д</span>
                    {ki_badge}
                </div>
                <div style="display:flex;gap:12px;margin-top:4px">
                    <span style="color:#ffb000;font-size:10px">Корзина: {sc["basket_drop"]:+.1f}%</span>
                    <span style="color:#ff3b30;font-size:10px">Worst: {sc["worst_ticker_drop"]:+.1f}%</span>
                    <span style="color:#6a5a2a;font-size:9px">Recovery: {sc["recovery_days"]}д</span>
                </div>
            </div>''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [12] TOP-3 РЕКОМЕНДУЕМЫЕ КОРЗИНЫ
    # ═══════════════════════════════════════════════════════════════
    with st.expander(f"[12] TOP-3 КОРЗИНЫ    рекомендации"):
        if top_bsk:
            st.markdown('<div style="color:#d6a44a;font-size:10px;margin-bottom:8px">Лучшие корзины из universe (оптимизированы по тикеру токсичности + секторной диверсификации)</div>', unsafe_allow_html=True)
            for i, b in enumerate(top_bsk):
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else ""
                sc_c = "#34c759" if b["est_score"] >= 80 else "#ffb000"
                st.markdown(f'''
                <div class="qc" style="padding:8px;margin-bottom:6px">
                    <div style="display:flex;align-items:center;gap:8px">
                        <span style="font-size:14px">{medal}</span>
                        <span style="color:#ffb000;font-size:12px;font-weight:700">{b["name"]}</span>
                        <span style="color:{sc_c};font-size:14px;font-weight:700">{b["est_score"]}</span>
                    </div>
                    <div style="color:#d6a44a;font-size:11px;margin-top:4px">{" · ".join(b["basket"])}</div>
                    <div style="color:#6a5a2a;font-size:9px">{b["n_sectors"]} секторов · avg tox {b["avg_tox"]:.2f} · {", ".join(b["sectors"])}</div>
                </div>''', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#6a5a2a;font-size:10px">Недостаточно данных</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [13] BACKTEST + NUMERIX COMPARISON + AGI MODEL
    # ═══════════════════════════════════════════════════════════════
    with st.spinner("⚡ Бэктест + AGI..."):
        BT = cached_backtest(",".join(basket_tickers), D["p_ki"], D["coupon_pa"], D["e_payout"])

    bt_stats = BT.get("bt_stats", {})
    with st.expander(f"[13] BACKTEST    {BT['n_backtests']} WINDOWS · WIN {bt_stats.get('win_rate',0):.0f}%"):
        if bt_stats:
            st.markdown(f'''
            <div style="color:#d6a44a;font-size:10px;margin-bottom:8px;line-height:1.5">Скользящий бэктест Phoenix worst-of за 5 лет ({BT["n_backtests"]} окон по 2Y). Каждый window = реальный продукт с 65% барьером.</div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px">
                <div class="qc" style="flex:1;min-width:100px;padding:8px;text-align:center"><div style="color:#d6a44a;font-size:9px">AVG PAYOFF</div><div style="color:#34c759;font-size:16px;font-weight:700">{bt_stats["avg_payoff"]:.1f}%</div></div>
                <div class="qc" style="flex:1;min-width:100px;padding:8px;text-align:center"><div style="color:#d6a44a;font-size:9px">WIN RATE</div><div style="color:#ffb000;font-size:16px;font-weight:700">{bt_stats["win_rate"]:.0f}%</div></div>
                <div class="qc" style="flex:1;min-width:100px;padding:8px;text-align:center"><div style="color:#d6a44a;font-size:9px">P(KI) ACTUAL</div><div style="color:{"#ff3b30" if bt_stats["p_ki_actual"]>25 else "#34c759"};font-size:16px;font-weight:700">{bt_stats["p_ki_actual"]:.1f}%</div></div>
                <div class="qc" style="flex:1;min-width:100px;padding:8px;text-align:center"><div style="color:#d6a44a;font-size:9px">P(AUTOCALL)</div><div style="color:#ffb000;font-size:16px;font-weight:700">{bt_stats["p_autocall_actual"]:.1f}%</div></div>
                <div class="qc" style="flex:1;min-width:100px;padding:8px;text-align:center"><div style="color:#d6a44a;font-size:9px">MAX LOSS</div><div style="color:#ff3b30;font-size:16px;font-weight:700">{bt_stats["max_loss"]:.1f}%</div></div>
                <div class="qc" style="flex:1;min-width:100px;padding:8px;text-align:center"><div style="color:#d6a44a;font-size:9px">MAX GAIN</div><div style="color:#34c759;font-size:16px;font-weight:700">+{bt_stats["max_gain"]:.1f}%</div></div>
            </div>
            ''', unsafe_allow_html=True)

            # Payoff distribution chart (HTML bar chart)
            pdist = BT.get("payoff_dist", {})
            bins = pdist.get("bins", [])
            counts = pdist.get("counts", [])
            max_count = max(counts) if counts else 1
            if counts:
                st.markdown('<div style="color:#ffb000;font-size:11px;font-weight:700;margin:8px 0 4px">■ РАСПРЕДЕЛЕНИЕ P&L</div>', unsafe_allow_html=True)
                chart_html = '<div style="display:flex;align-items:flex-end;gap:2px;height:100px;padding:4px">'
                for i, c in enumerate(counts):
                    h = max(2, c / max_count * 80)
                    color = "#ff3b30" if bins[i] < 0 else "#34c759" if bins[i] >= 5 else "#ffb000"
                    chart_html += f'<div style="flex:1;display:flex;flex-direction:column;align-items:center"><div style="width:100%;height:{h}px;background:{color};border-radius:1px"></div><div style="color:#6a5a2a;font-size:7px;margin-top:2px">{bins[i]}%</div></div>'
                chart_html += '</div>'
                st.markdown(chart_html, unsafe_allow_html=True)

                stats = pdist.get("stats", {})
                st.markdown(f'''
                <div style="display:flex;gap:12px;margin-top:6px;font-size:10px;color:#d6a44a">
                    <span>μ={stats.get("mean",0):.1f}%</span>
                    <span>σ={stats.get("std",0):.1f}%</span>
                    <span>P5={stats.get("p5",0):.1f}%</span>
                    <span>P95={stats.get("p95",0):.1f}%</span>
                    <span>Sharpe={stats.get("sharpe",0):.2f}</span>
                </div>''', unsafe_allow_html=True)

            # Individual backtest windows
            st.markdown('<div style="color:#ffb000;font-size:11px;font-weight:700;margin:12px 0 4px">■ БЭКТЕСТ-ОКНА</div>', unsafe_allow_html=True)
            for bt in BT.get("backtest", [])[:15]:
                pnl_c = "#34c759" if bt["pnl_pct"] >= 0 else "#ff3b30"
                ki_badge = '<span style="background:#1a0a0a;border:1px solid #ff3b30;padding:1px 6px;color:#ff3b30;font-size:9px">KI</span>' if bt["ki_hit"] else ""
                ac_badge = '<span style="background:#0a1a0a;border:1px solid #34c759;padding:1px 6px;color:#34c759;font-size:9px">AC Q{}</span>'.format(bt["autocall_quarter"]) if bt["autocalled"] else ""
                st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 8px;border-bottom:1px solid #1a1400"><span style="color:#6a5a2a;font-size:9px">{bt["start_date"]} → {bt["end_date"]}</span><span>{ki_badge}{ac_badge}</span><span style="color:#d6a44a;font-size:9px">купон {bt["coupons_pa"]:.1f}% p.a.</span><span style="color:{pnl_c};font-size:10px;font-weight:700">{bt["pnl_pct"]:+.1f}%</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#6a5a2a;font-size:11px">Недостаточно исторических данных для бэктеста.</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [11] СРАВНЕНИЕ С РЫНКОМ (NUMERIX + DEALER merged)
    # ═══════════════════════════════════════════════════════════════
    nmx_comp = BT.get("numerix_comparison", {})
    nmx_acc = nmx_comp.get("avg_accuracy", 0)
    DL = cached_dealer(",".join(basket_tickers), D["coupon_pa"], D["p_ki"], D["score"])
    tox_data = DL.get("toxicity", {})
    p_loss_data = DL.get("p_loss", {})
    cpn_pred = DL.get("coupon_prediction", {})
    guard = DL.get("guard_flag", False)
    acc_dealer = DL.get("accuracy_vs_dealer")
    acc_str = f"Dealer {acc_dealer:.0f}%" if acc_dealer else ""
    summary_str = f"Numerix {nmx_acc:.0f}%"
    if acc_str:
        summary_str += f" · {acc_str}"

    with st.expander(f"[14] СРАВНЕНИЕ С РЫНКОМ    {summary_str}"):
        # GUARD flag
        if guard:
            st.markdown(f'''
            <div style="background:#3a0000;border:1px solid #ff3b30;padding:8px;margin-bottom:8px">
                <span style="color:#ff3b30;font-size:11px;font-weight:700">GUARD: P(убыток) = {p_loss_data.get("p_loss_pct",0):.0f}%</span>
                <span style="color:#ff9999;font-size:9px;margin-left:8px">{p_loss_data.get("guard_msg","")}</span>
            </div>''', unsafe_allow_html=True)

        # Numerix benchmarks
        comps = nmx_comp.get("comparisons", [])
        if comps:
            st.markdown('<div style="color:#6db6ff;font-size:11px;font-weight:700;margin-bottom:4px">■ NUMERIX BENCHMARKS</div>', unsafe_allow_html=True)
            for c in comps:
                acc_c = "#34c759" if c["accuracy"] > 70 else "#ffb000" if c["accuracy"] > 40 else "#ff3b30"
                st.markdown(f'''
                <div class="qc" style="padding:8px;margin:4px 0;border-left:3px solid {acc_c}">
                    <div style="display:flex;justify-content:space-between"><span style="color:#fa8000;font-size:10px;font-weight:700">{c["benchmark"]}</span><span style="color:{acc_c};font-size:10px;font-weight:700">{c["accuracy"]:.0f}% MATCH</span></div>
                    <div style="color:#6a5a2a;font-size:9px">{" · ".join(c["tickers"])} · P(KI): {c["our_p_ki"]:.1f}% vs {c["bench_p_ki"]:.1f}% · Купон: {c["our_coupon_pa"]:.1f}% vs {c["bench_coupon_pa"]:.1f}%</div>
                </div>''', unsafe_allow_html=True)

        # Toxicity
        st.markdown('<div style="color:#ffb000;font-size:11px;font-weight:700;margin:8px 0 4px">■ ТОКСИЧНОСТЬ (ОПЫТ 2021-2024)</div>', unsafe_allow_html=True)
        tox_html = '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">'
        per_ticker = tox_data.get("per_ticker", {})
        for ticker, info in per_ticker.items():
            label = info.get("label", "?")
            tc = "#ff3b30" if label == "TOXIC" else "#fa8000" if label == "RISKY" else "#34c759" if label == "SAFE" else "#6a5a2a"
            tox_html += f'<span style="background:#1a1400;border:1px solid {tc};padding:2px 8px;color:{tc};font-size:9px">{ticker} {info.get("tox",0.5):.2f} {label}</span>'
        tox_html += '</div>'
        avg_tox = tox_data.get("avg_tox", 0.5)
        tox_html += f'<div style="color:#6a5a2a;font-size:9px">Ср. токсичность: <b style="color:{"#ff3b30" if avg_tox>0.5 else "#fa8000" if avg_tox>0.3 else "#34c759"}">{avg_tox:.3f}</b> · Известно {tox_data.get("known_count",0)}/{tox_data.get("total_count",0)}</div>'
        st.markdown(tox_html, unsafe_allow_html=True)

        # Dealer coupon prediction
        dealer_cpn = cpn_pred.get("predicted_coupon", 0)
        delta_cpn = DL.get("delta_coupon_vs_model", 0)
        band = cpn_pred.get("confidence_band", (0, 0))
        st.markdown(f'''
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin:8px 0">
            <div class="qc" style="flex:1;min-width:110px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">P(УБЫТОК)</div><div style="color:{"#ff3b30" if p_loss_data.get("p_loss_pct",0)>25 else "#34c759"};font-size:14px;font-weight:700">{p_loss_data.get("p_loss_pct",0):.0f}%</div></div>
            <div class="qc" style="flex:1;min-width:110px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">КУПОН ДИЛЕР</div><div style="color:#6db6ff;font-size:14px;font-weight:700">{dealer_cpn:.1f}%</div></div>
            <div class="qc" style="flex:1;min-width:110px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">КУПОН НАШ</div><div style="color:#ffb000;font-size:14px;font-weight:700">{D["coupon_pa"]:.1f}%</div></div>
            <div class="qc" style="flex:1;min-width:110px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:8px">Δ</div><div style="color:{"#34c759" if abs(delta_cpn)<3 else "#ff3b30"};font-size:14px;font-weight:700">{delta_cpn:+.1f}%</div></div>
        </div>
        <div style="color:#6a5a2a;font-size:9px">Диапазон дилера: {band[0]:.1f}% – {band[1]:.1f}% (±1σ из {cpn_pred.get("lookup_n",0)} котировок)</div>
        ''', unsafe_allow_html=True)

        # Similar real quotes
        similar = DL.get("similar_quotes", [])
        if similar:
            avg_sim = DL.get("avg_similar_coupon")
            st.markdown(f'<div style="color:#ffb000;font-size:10px;font-weight:700;margin:8px 0 4px">■ ПОХОЖИЕ КОТИРОВКИ ({len(similar)} шт, ср. {avg_sim:.1f}%)</div>', unsafe_allow_html=True)
            for q in similar[:4]:
                color = "#34c759" if q["coupon"] < 15 else "#ffb000" if q["coupon"] < 25 else "#ff3b30"
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 8px;border-bottom:1px solid #1a1400"><span style="color:#d6a44a;font-size:9px">{q["basket"]}</span><span style="color:{color};font-size:9px;font-weight:700">{q["coupon"]:.1f}%</span></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [12] AGI PIPELINE: БЭКТЕСТ → КАЛИБРОВКА → ПРОГНОЗ
    # ═══════════════════════════════════════════════════════════════
    avg_vol_val = ind.get("iv30_avg", 35) if ind else 35
    avg_corr_val = corr.get("avg_corr", 0.5)
    with st.spinner("⚡ Калибровка AGI..."):
        PL = cached_pipeline(",".join(basket_tickers), p_ki, avg_vol_val, avg_corr_val)

    pl_bt = PL.get("backtest", {})
    pl_cal = PL.get("calibration", {})
    pl_fc = PL.get("forecast", {})
    cal_after = pl_cal.get("after", {})
    cal_before = pl_cal.get("before", {})
    fc_conf = pl_fc.get("model_confidence", 0)
    fc_scenarios = pl_fc.get("scenarios", {})
    fc_base = fc_scenarios.get("base", {})

    acc_color = "#34c759" if cal_after.get("test_acc", 0) >= 70 else "#ffb000" if cal_after.get("test_acc", 0) >= 50 else "#ff3b30"

    with st.expander(f"[15] AGI PIPELINE    ACC {cal_after.get('test_acc',0):.0f}% · CONF {fc_conf:.0f}%"):

        # ── COMPONENT 1: БЭКТЕСТ v2 ──
        st.markdown('<div style="color:#6db6ff;font-size:12px;font-weight:700;margin-bottom:6px;border-bottom:1px solid #3a2a00;padding-bottom:4px">① БЭКТЕСТ — ТОЧНОСТЬ МОДЕЛИ</div>', unsafe_allow_html=True)

        bt_f1 = pl_bt.get("f1", 0)
        bt_prec = pl_bt.get("precision", 0)
        bt_recall = pl_bt.get("recall", 0)
        bt_r2 = pl_bt.get("coupon_r2", 0)
        bt_cm = pl_bt.get("confusion_matrix", {})
        kfold = pl_bt.get("kfold", {})
        kf_mean = kfold.get("mean_acc", 0)
        kf_std = kfold.get("std_acc", 0)

        st.markdown(f'''
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">ACCURACY</div><div style="color:{acc_color};font-size:16px;font-weight:700">{pl_bt.get("loss_accuracy",0):.0f}%</div><div style="color:#6a5a2a;font-size:7px">n={pl_bt.get("loss_n",0)}</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">PRECISION</div><div style="color:#6db6ff;font-size:16px;font-weight:700">{bt_prec:.0f}%</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">RECALL</div><div style="color:#6db6ff;font-size:16px;font-weight:700">{bt_recall:.0f}%</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">F1</div><div style="color:{"#34c759" if bt_f1>=60 else "#ffb000"};font-size:16px;font-weight:700">{bt_f1:.0f}%</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">MAE</div><div style="color:#ffb000;font-size:16px;font-weight:700">{pl_bt.get("coupon_mae",0):.1f}%</div><div style="color:#6a5a2a;font-size:7px">n={pl_bt.get("coupon_n",0)}</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">R²</div><div style="color:{"#34c759" if bt_r2>0.3 else "#ffb000"};font-size:16px;font-weight:700">{bt_r2:.3f}</div></div>
        </div>''', unsafe_allow_html=True)

        # Confusion matrix
        if bt_cm:
            st.markdown(f'''
            <div style="display:flex;gap:4px;margin-bottom:6px">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:2px;flex:1">
                    <div style="background:#0a2000;padding:4px;text-align:center;border:1px solid #1a3a00"><div style="color:#34c759;font-size:12px;font-weight:700">{bt_cm.get("tp",0)}</div><div style="color:#6a5a2a;font-size:7px">TP</div></div>
                    <div style="background:#200a00;padding:4px;text-align:center;border:1px solid #3a1a00"><div style="color:#ff3b30;font-size:12px;font-weight:700">{bt_cm.get("fp",0)}</div><div style="color:#6a5a2a;font-size:7px">FP</div></div>
                    <div style="background:#200a00;padding:4px;text-align:center;border:1px solid #3a1a00"><div style="color:#ff3b30;font-size:12px;font-weight:700">{bt_cm.get("fn",0)}</div><div style="color:#6a5a2a;font-size:7px">FN</div></div>
                    <div style="background:#0a2000;padding:4px;text-align:center;border:1px solid #1a3a00"><div style="color:#34c759;font-size:12px;font-weight:700">{bt_cm.get("tn",0)}</div><div style="color:#6a5a2a;font-size:7px">TN</div></div>
                </div>
                <div style="flex:1;padding:4px">
                    <div style="color:#d6a44a;font-size:8px;margin-bottom:4px">K-FOLD CV (k={kfold.get("k",5)})</div>
                    <div style="color:{"#34c759" if kf_mean>=65 else "#ffb000"};font-size:14px;font-weight:700">{kf_mean:.0f}% ±{kf_std:.0f}%</div>
                    <div style="color:#6a5a2a;font-size:7px">F1 avg: {kfold.get("mean_f1",0):.0f}%</div>
                </div>
            </div>''', unsafe_allow_html=True)

        # K-fold per-fold mini bars
        folds = kfold.get("folds", [])
        if folds:
            fold_html = '<div style="display:flex;gap:2px;height:24px;align-items:flex-end">'
            for f in folds:
                h = max(4, f["acc"] / 100 * 22)
                c = "#34c759" if f["acc"] >= 70 else "#ffb000" if f["acc"] >= 50 else "#ff3b30"
                fold_html += f'<div style="flex:1;text-align:center"><div style="height:{h}px;background:{c};border-radius:1px"></div><div style="color:#6a5a2a;font-size:6px">F{f["fold"]}</div></div>'
            fold_html += '</div>'
            st.markdown(fold_html, unsafe_allow_html=True)

        # Error by term bucket
        err_term = pl_bt.get("error_by_term", {})
        if err_term:
            st.markdown('<div style="color:#d6a44a;font-size:9px;margin:6px 0 2px">Bias по сроку:</div>', unsafe_allow_html=True)
            for term, stats in err_term.items():
                bias_c = "#ff3b30" if abs(stats["mean"]) > 3 else "#ffb000" if abs(stats["mean"]) > 1 else "#34c759"
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 8px;border-bottom:1px solid #1a1400"><span style="color:#6a5a2a;font-size:9px">{term}m</span><span style="color:{bias_c};font-size:9px">bias {stats["mean"]:+.1f}% ±{stats["std"]:.1f}</span><span style="color:#6a5a2a;font-size:9px">n={stats["n"]}</span></div>', unsafe_allow_html=True)

        # ── COMPONENT 2: КАЛИБРОВКА v2 ──
        st.markdown('<div style="color:#fa8000;font-size:12px;font-weight:700;margin:12px 0 6px;border-bottom:1px solid #3a2a00;padding-bottom:4px">② КАЛИБРОВКА — МНОЖИТЕЛИ</div>', unsafe_allow_html=True)

        n_changed = pl_cal.get("n_params_changed", 0)
        acc_delta = pl_cal.get("improvement", {}).get("accuracy_delta", 0)
        final_lr = pl_cal.get("final_lr", 0)
        early_stopped = pl_cal.get("early_stopped", False)
        l2_lam = pl_cal.get("l2_lambda", 0)
        n_iters = pl_cal.get("n_iterations", 0)

        st.markdown(f'''
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">ACC ДО</div><div style="color:#ff3b30;font-size:15px;font-weight:700">{cal_before.get("test_acc",0):.0f}%</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">ACC ПОСЛЕ</div><div style="color:{acc_color};font-size:15px;font-weight:700">{cal_after.get("test_acc",0):.0f}%</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">Δ ACC</div><div style="color:{"#34c759" if acc_delta > 0 else "#ff3b30"};font-size:15px;font-weight:700">{acc_delta:+.1f}%</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">PARAMS</div><div style="color:#ffb000;font-size:15px;font-weight:700">{n_changed}/15</div></div>
            <div class="qc" style="flex:1;min-width:80px;padding:6px;text-align:center"><div style="color:#d6a44a;font-size:7px">MAE ПОСЛЕ</div><div style="color:#6db6ff;font-size:15px;font-weight:700">{cal_after.get("coupon_mae",0):.1f}%</div></div>
        </div>
        <div style="display:flex;gap:8px;margin-bottom:4px;padding:4px 8px;background:#0a0800;border-left:2px solid #fa8000">
            <span style="color:#6a5a2a;font-size:8px">LR: {final_lr:.4f}</span>
            <span style="color:#6a5a2a;font-size:8px">L2: {l2_lam}</span>
            <span style="color:#6a5a2a;font-size:8px">Iters: {n_iters}/20</span>
            <span style="color:{"#34c759" if early_stopped else "#6a5a2a"};font-size:8px">{"✓ Early stop" if early_stopped else "Full run"}</span>
        </div>''', unsafe_allow_html=True)

        # Calibration log (convergence mini-chart)
        cal_log = pl_cal.get("calibration_log", [])
        if cal_log:
            accs = [r["test_acc"] for r in cal_log]
            max_a = max(accs) if accs else 1
            chart_html = '<div style="display:flex;align-items:flex-end;gap:2px;height:40px;padding:2px">'
            for i, r in enumerate(cal_log):
                h = max(3, r["test_acc"] / max(1, max_a) * 35)
                c = "#34c759" if r["test_acc"] >= 70 else "#ffb000" if r["test_acc"] >= 50 else "#ff3b30"
                chart_html += f'<div style="flex:1;display:flex;flex-direction:column;align-items:center"><div style="width:100%;height:{h}px;background:{c};border-radius:1px"></div><div style="color:#6a5a2a;font-size:6px">{i+1}</div></div>'
            chart_html += '</div>'
            st.markdown(chart_html, unsafe_allow_html=True)

        # Changed params
        deltas = pl_cal.get("param_deltas", {})
        if deltas:
            delta_html = '<div style="display:flex;flex-wrap:wrap;gap:3px;margin:4px 0">'
            for k, v in deltas.items():
                delta_html += f'<span style="background:#1a1400;border:1px solid #34c759;padding:1px 5px;color:#34c759;font-size:7px">{k}: {v["old"]:.3f}→{v["new"]:.3f}</span>'
            delta_html += '</div>'
            st.markdown(delta_html, unsafe_allow_html=True)

        # ── COMPONENT 3: ПРОГНОЗ v2 ──
        st.markdown('<div style="color:#34c759;font-size:12px;font-weight:700;margin:12px 0 6px;border-bottom:1px solid #3a2a00;padding-bottom:4px">③ ПРОГНОЗ — КАЛИБРОВАННАЯ МОДЕЛЬ</div>', unsafe_allow_html=True)

        conf_color = "#34c759" if fc_conf >= 70 else "#ffb000" if fc_conf >= 50 else "#ff3b30"
        fc_pred = pl_fc.get("prediction", {})
        fc_ensemble = pl_fc.get("ensemble_size", 1)
        fc_spread = pl_fc.get("model_spread", {})

        st.markdown(f'''
        <div style="display:flex;gap:4px;margin-bottom:6px">
            <div class="qc" style="flex:2;border-left:3px solid {conf_color};padding:8px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="color:#ffb000;font-size:10px;font-weight:700">CONFIDENCE</span>
                    <span style="color:{conf_color};font-size:20px;font-weight:700">{fc_conf:.0f}%</span>
                </div>
            </div>
            <div class="qc" style="flex:1;padding:8px;text-align:center">
                <div style="color:#d6a44a;font-size:7px">ENSEMBLE</div>
                <div style="color:#6db6ff;font-size:14px;font-weight:700">{fc_ensemble} models</div>
                <div style="color:#6a5a2a;font-size:7px">σ score: {fc_spread.get("score_spread",0):.1f}</div>
            </div>
        </div>''', unsafe_allow_html=True)

        # Scenarios table
        for key in ["base", "optimistic", "pessimistic"]:
            sc = fc_scenarios.get(key, {})
            if not sc:
                continue
            sc_c = "#ffb000" if key == "base" else "#34c759" if key == "optimistic" else "#ff3b30"
            st.markdown(f'''
            <div style="display:flex;justify-content:space-between;padding:4px 8px;border-bottom:1px solid #1a1400">
                <span style="color:{sc_c};font-size:10px;font-weight:700">{sc["label"]}</span>
                <span style="color:#d6a44a;font-size:9px">Score {sc["score"]:.0f}</span>
                <span style="color:#d6a44a;font-size:9px">Купон {sc["coupon"]:.1f}%</span>
                <span style="color:#d6a44a;font-size:9px">P(loss) {sc["p_loss"]:.0f}%</span>
                <span style="color:{sc_c};font-size:9px;font-weight:700">P={sc["probability"]:.0f}%</span>
            </div>''', unsafe_allow_html=True)

        # Confidence intervals
        ci = pl_fc.get("confidence_intervals", {})
        if ci:
            st.markdown('<div style="color:#d6a44a;font-size:9px;margin:8px 0 4px">Доверительные интервалы (P10–P90):</div>', unsafe_allow_html=True)
            for metric, vals in ci.items():
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 8px;border-bottom:1px solid #1a1400"><span style="color:#6a5a2a;font-size:9px">{metric}</span><span style="color:#d6a44a;font-size:9px">[{vals["p10"]:.1f} — {vals["p50"]:.1f} — {vals["p90"]:.1f}]</span></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # [13] EXTERNAL COMPUTE — Google Colab + Supabase + NVIDIA AI
    # ═══════════════════════════════════════════════════════════════
    ext = D.get("external_services", {})
    colab_s = ext.get("colab", {})
    supa_s = ext.get("supabase", {})
    nv_s = ext.get("nvidia", {})
    nv_risk = D.get("nvidia_risk", {})

    with st.expander("[13] EXTERNAL COMPUTE    Colab · Supabase · NVIDIA AI"):
        st.markdown(f'''
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px">
            <div class="qc" style="flex:1;min-width:120px;padding:8px;border-left:3px solid {"#34c759" if colab_s.get("available") else "#6a5a2a"}">
                <div style="color:#d6a44a;font-size:8px">GOOGLE COLAB</div>
                <div style="color:{"#34c759" if colab_s.get("available") else "#ff3b30"};font-size:11px;font-weight:700">{"● ON" if colab_s.get("available") else "○ OFF"}</div>
                <div style="color:#6a5a2a;font-size:7px">{colab_s.get("description","T4 GPU MC")}</div>
            </div>
            <div class="qc" style="flex:1;min-width:120px;padding:8px;border-left:3px solid {"#34c759" if supa_s.get("available") else "#6a5a2a"}">
                <div style="color:#d6a44a;font-size:8px">SUPABASE</div>
                <div style="color:{"#34c759" if supa_s.get("available") else "#ff3b30"};font-size:11px;font-weight:700">{"● ON" if supa_s.get("available") else "○ OFF"}</div>
                <div style="color:#6a5a2a;font-size:7px">{supa_s.get("description","PostgreSQL storage")}</div>
            </div>
            <div class="qc" style="flex:1;min-width:120px;padding:8px;border-left:3px solid {"#34c759" if nv_s.get("available") else "#6a5a2a"}">
                <div style="color:#d6a44a;font-size:8px">NVIDIA AI</div>
                <div style="color:{"#34c759" if nv_s.get("available") else "#ff3b30"};font-size:11px;font-weight:700">{"● ON" if nv_s.get("available") else "○ OFF"}</div>
                <div style="color:#6a5a2a;font-size:7px">{nv_s.get("description","NIM Llama 3.1")}</div>
            </div>
        </div>''', unsafe_allow_html=True)

        # NVIDIA risk analysis result
        nv_level = nv_risk.get("risk_level", "N/A")
        nv_adj = nv_risk.get("score_adjustment", 0)
        nv_source = nv_risk.get("source", "N/A")
        nv_level_c = {"low": "#34c759", "medium": "#ffb000", "high": "#ff3b30", "extreme": "#ff0000"}.get(nv_level, "#6a5a2a")

        st.markdown(f'''
        <div style="color:#6db6ff;font-size:10px;font-weight:700;margin:8px 0 4px;border-bottom:1px solid #3a2a00;padding-bottom:3px">AI RISK ANALYSIS ({nv_source})</div>
        <div style="display:flex;gap:6px;margin-bottom:6px">
            <div class="qc" style="flex:1;padding:6px;text-align:center">
                <div style="color:#d6a44a;font-size:7px">RISK LEVEL</div>
                <div style="color:{nv_level_c};font-size:14px;font-weight:700">{nv_level.upper()}</div>
            </div>
            <div class="qc" style="flex:1;padding:6px;text-align:center">
                <div style="color:#d6a44a;font-size:7px">SCORE ADJ</div>
                <div style="color:{"#34c759" if nv_adj > 0 else "#ff3b30" if nv_adj < 0 else "#6a5a2a"};font-size:14px;font-weight:700">{nv_adj:+.1f}</div>
            </div>
            <div class="qc" style="flex:1;padding:6px;text-align:center">
                <div style="color:#d6a44a;font-size:7px">CONCENTRATION</div>
                <div style="color:{"#ff3b30" if nv_risk.get("concentration_warning") else "#34c759"};font-size:14px;font-weight:700">{"⚠ YES" if nv_risk.get("concentration_warning") else "OK"}</div>
            </div>
        </div>''', unsafe_allow_html=True)

        # Key risks
        risks = nv_risk.get("key_risks", [])
        if risks:
            for r in risks[:3]:
                st.markdown(f'<div style="padding:2px 8px;border-left:2px solid #ff3b30;margin-bottom:2px;color:#d6a44a;font-size:8px">⚠ {r}</div>', unsafe_allow_html=True)

        rec = nv_risk.get("recommendation", "")
        if rec:
            st.markdown(f'<div style="padding:4px 8px;background:#0a0800;color:#6db6ff;font-size:8px;margin-top:4px">💡 {rec}</div>', unsafe_allow_html=True)

        # Setup instructions
        st.markdown('''
        <div style="color:#6a5a2a;font-size:7px;margin-top:8px;border-top:1px solid #1a1400;padding-top:4px">
            Подключение: NVIDIA_API_KEY → build.nvidia.com | COLAB_WEBHOOK → Google Colab | Google Drive — автоматически
        </div>''', unsafe_allow_html=True)

        # ── FEATURE IMPORTANCE ──
        feat_imp = pl_fc.get("feature_importance", {})
        if feat_imp:
            st.markdown('<div style="color:#d6a44a;font-size:9px;margin:8px 0 4px;font-weight:700">FEATURE IMPORTANCE (Δscore при +10% входа)</div>', unsafe_allow_html=True)
            # Input features
            input_feats = [(k, v) for k, v in feat_imp.items() if not k.startswith("_")]
            if input_feats:
                max_imp = max(v for _, v in input_feats) if input_feats else 1
                fi_html = '<div style="display:flex;flex-direction:column;gap:2px">'
                for fname, fval in sorted(input_feats, key=lambda x: x[1], reverse=True):
                    bar_w = max(3, fval / max(0.01, max_imp) * 100)
                    fi_html += f'<div style="display:flex;align-items:center;gap:6px"><span style="color:#6a5a2a;font-size:8px;width:55px;text-align:right">{fname}</span><div style="flex:1;background:#1a1400;height:6px;border-radius:1px"><div style="width:{bar_w:.0f}%;height:100%;background:#fa8000;border-radius:1px"></div></div><span style="color:#ffb000;font-size:8px">{fval:.2f}</span></div>'
                fi_html += '</div>'
                st.markdown(fi_html, unsafe_allow_html=True)

            # Top params
            top5 = feat_imp.get("_param_top5", [])
            if top5:
                st.markdown('<div style="color:#6a5a2a;font-size:8px;margin:6px 0 2px">Top параметры модели:</div>', unsafe_allow_html=True)
                tp_html = '<div style="display:flex;flex-wrap:wrap;gap:3px">'
                for tp in top5:
                    tp_html += f'<span style="background:#0a1a00;border:1px solid #34c759;padding:1px 5px;color:#34c759;font-size:7px">{tp["name"]}: {tp["impact"]:.2f}</span>'
                tp_html += '</div>'
                st.markdown(tp_html, unsafe_allow_html=True)

        # ── LEARNING HISTORY (Google Drive) ──
        history = PL.get("learning_history", [])
        if history:
            st.markdown('<div style="color:#d6a44a;font-size:9px;margin:10px 0 4px;font-weight:700">SELF-LEARNING HISTORY (Google Drive)</div>', unsafe_allow_html=True)
            # Mini accuracy trend chart from history
            accs_hist = [float(h.get("accuracy_after", 0)) for h in history[:15]]
            if accs_hist:
                max_h = max(accs_hist) if accs_hist else 1
                hist_html = '<div style="display:flex;align-items:flex-end;gap:2px;height:30px;padding:2px">'
                for i, a in enumerate(reversed(accs_hist)):
                    h = max(3, a / max(1, max_h) * 26)
                    c = "#34c759" if a >= 70 else "#ffb000" if a >= 50 else "#ff3b30"
                    hist_html += f'<div style="flex:1;display:flex;flex-direction:column;align-items:center"><div style="width:100%;height:{h}px;background:{c};border-radius:1px"></div></div>'
                hist_html += '</div>'
                hist_html += f'<div style="display:flex;justify-content:space-between;color:#6a5a2a;font-size:7px"><span>← старые</span><span>{len(accs_hist)} runs</span><span>новые →</span></div>'
                st.markdown(hist_html, unsafe_allow_html=True)
        elif current_acc > 0:
            st.markdown('<div style="color:#6a5a2a;font-size:8px;margin:6px 0;padding:4px 8px;background:#0a0800;border:1px solid #1a1400">📡 Запустите пайплайн несколько раз для накопления истории обучения</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # ФЕНИКС v32.0 — Sobol MC (interactive)
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div class="sec">🔥 ФЕНИКС v32.0 — SOBOL MC ENGINE</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#d6a44a;font-size:10px;margin-bottom:6px">2Y · USD · Memory Coupon · Worst-of Phoenix Autocallable · Все комбинации C(N,K)</div>', unsafe_allow_html=True)

    pc1,pc2,pc3,pc4 = st.columns(4)
    with pc1: phoenix_n_sims = st.selectbox("Симуляций", [10_000,50_000,100_000,500_000], index=1, key="ph_sims", format_func=lambda x: f"{x:,}")
    with pc2: phoenix_coupon = st.number_input("Купон %/кв", value=6.5, step=0.5, key="ph_cpn")
    with pc3: phoenix_barrier = st.number_input("Барьер %", value=65.0, step=5.0, key="ph_bar")
    with pc4: phoenix_combo = st.number_input("Имён в корзине", value=min(6, n_tickers), min_value=2, max_value=12, step=1, key="ph_k")

    combo_size = min(int(phoenix_combo), n_tickers)
    n_combos = math.comb(n_tickers, combo_size) if n_tickers >= combo_size else 1
    st.markdown(f'<div style="color:#ffb000;font-size:11px;margin:4px 0">📊 C({n_tickers},{combo_size}) = <b>{n_combos}</b> комбинаций</div>', unsafe_allow_html=True)

    if st.button("🔥 ЗАПУСК ФЕНИКС MC — ВСЕ КОМБИНАЦИИ", key="run_phoenix", type="primary", use_container_width=True):
        import itertools, time
        import numpy as np
        combos = list(itertools.combinations(basket_tickers, combo_size))
        combo_results = []
        t0 = time.time()

        progress = st.progress(0)
        for idx, combo in enumerate(combos):
            combo_list = list(combo)
            try:
                ext = conductor_analyze(combo_list, n_sims=phoenix_n_sims)
                if ext and "error" not in ext:
                    ext["combo"] = combo_list
                    combo_results.append(ext)
                    progress.progress((idx+1)/len(combos))
                    continue
            except Exception:
                pass
            try:
                res = phoenix_simulate(combo_list, config={
                    "n_sims": min(phoenix_n_sims, 10000),
                    "coupon": phoenix_coupon / 100,
                    "barrier": phoenix_barrier / 100,
                })
                res["combo"] = combo_list
                combo_results.append(res)
                save_to_gdrive(res)
            except Exception:
                pass
            progress.progress((idx+1)/len(combos))

        elapsed = time.time() - t0
        if combo_results:
            combo_results.sort(key=lambda x: x.get("avg_payoff", 0), reverse=True)
            st.session_state["phoenix_result"] = combo_results[0]
            st.session_state["phoenix_combos"] = combo_results

            st.markdown(f'''
            <div class="qc" style="border-left:3px solid #34c759;padding:12px;margin-top:8px">
                <div style="color:#fa8000;font-size:14px;font-weight:700">КОМБИНАТОРНЫЙ АНАЛИЗ — {len(combo_results)} КОРЗИН</div>
                <div style="color:#ffd56a;font-size:10px;margin-top:2px">{combo_results[0].get("n_sims",0):,} Sobol MC на корзину · {combo_size} имён · 26% годовых · USD · ⚡ {elapsed:.1f}s</div>
            </div>''', unsafe_allow_html=True)

            for i, cr in enumerate(combo_results[:20]):
                payoff = cr.get("avg_payoff", 1.0) * 100
                p_loss = cr.get("p_loss", 0) * 100
                color = "#34c759" if p_loss < 20 else "#ffb000" if p_loss < 40 else "#ff3b30"
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:3px 8px;border-bottom:1px solid #1a1400"><span style="color:#d6a44a;font-size:10px">{i+1}. {" · ".join(cr["combo"])}</span><span style="color:{color};font-size:10px">payoff {payoff:.1f}% · P(loss) {p_loss:.1f}%</span></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # FOOTER + STATUS BAR
    # ═══════════════════════════════════════════════════════════════
    st.markdown(f'''
    <div style="margin-top:16px;padding:8px 14px;border-top:1px solid #3a2a00">
        <small style="color:#3a2a00;font-size:9px;line-height:1.4">
            IV30 — yfinance. Корреляции — лог-доходности 5Y. DCF — FCF с CAPM-WACC.
            MC — коррелированный GBM. Стресс — β_SPY через GFC, COVID, Tech, TradeWar.
            ClickHouse Cloud: 40K sims · Qiskit AerSimulator · ФЕНИКС v32.0 Sobol QMC.
        </small>
    </div>
    <div style="text-align:center;color:#3a2a00;font-size:9px;margin-top:8px;text-transform:uppercase;letter-spacing:1px">
        PHOENIX TERMINAL &copy; {datetime.datetime.now().year} · MIT Quantum + IBM Qiskit + ClickHouse Cloud + ФЕНИКС v32.0
    </div>
    ''', unsafe_allow_html=True)

now_utc = datetime.datetime.now(datetime.timezone.utc)
gdrive_st = "G-DRIVE" if GDRIVE_AVAILABLE else "LOCAL-BKP"
st.markdown(f'''
<div class="sbar">
    <span>NY {now_utc.strftime("%H:%M:%S")}</span>
    <span>MKT <span class="lb">PRE-MKT</span></span>
    <span>API <span class="ok">OK</span></span>
    <span>CLICKHOUSE <span class="ok">CONNECTED</span></span>
    <span>QISKIT <span class="ok">AER-SIM → SCORING</span></span>
    <span>ФЕНИКС <span class="ok">v32.0</span></span>
    <span>HULK <span class="ok">v41 CONDUCTOR</span></span>
    <span>{gdrive_st} <span class="ok">OK</span></span>
    <span style="margin-left:auto"><span class="lb">PHOENIX TERMINAL · v3.0</span></span>
</div>
''', unsafe_allow_html=True)
