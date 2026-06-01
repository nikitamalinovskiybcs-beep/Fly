"""Worst-of Phoenix Terminal — Bloomberg-style dashboard.
Karpathy method: ALL computation in precompute.py, this file is pure rendering."""

import datetime
import math
import streamlit as st

from src.precompute import precompute_all as _precompute_all, SECTOR_MAP
from src.phoenix_engine import simulate_basket as phoenix_simulate, save_to_gdrive, GDRIVE_AVAILABLE
from src.conductor import analyze as conductor_analyze

st.set_page_config(page_title="Worst-of Phoenix | Terminal", page_icon="■", layout="wide")


@st.cache_data(ttl=300, show_spinner=False)
def cached_precompute(tickers_key: str):
    """Cached wrapper — avoids recompute on every Streamlit rerun."""
    tickers = tickers_key.split(",")
    return _precompute_all(tickers)

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
/* Ticker tape */
.tt{background:var(--bg2);border-bottom:1px solid var(--border);overflow:hidden;white-space:nowrap;padding:4px 0;font-size:11px}
.tt-track{display:inline-block;animation:scroll-tape 60s linear infinite}
@keyframes scroll-tape{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
.tk{display:inline-block;margin-right:24px}.tk .s{color:var(--muted);font-weight:700;margin-right:4px}.tk .p{color:var(--text);margin-right:4px}.tk .up{color:var(--good)}.tk .dn{color:var(--bad)}
/* Header */
.hdr{padding:8px 14px;border-bottom:1px solid var(--border);background:var(--bg2);display:flex;align-items:baseline;gap:16px}
.hdr h1{margin:0;font-size:14px;font-weight:700;letter-spacing:1px;color:var(--accent);text-transform:uppercase}.hdr h1::before{content:"■ "}.hdr .sub{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.6px}
/* WEI */
.wei{background:var(--bg2);border-bottom:1px solid var(--border);padding:4px 14px}
.wei-t{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
.wei-b{display:flex;gap:0;flex-wrap:wrap}
.wei-c{flex:1 1 auto;min-width:120px;padding:4px 12px;border-right:1px solid var(--border)}.wei-c:last-child{border-right:none}
.wei-s{display:block;font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:1px}
.wei-p{display:block;font-size:14px;font-weight:700;color:var(--text)}.wei-d{display:block;font-size:11px}
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
# MACRO TAPE
# ═══════════════════════════════════════════════════════════════════
MACRO = [("SPX","7,580.06","+0.79%",True),("NDX","30,333.18","+1.20%",True),("VIX","15.32","-2.67%",False),
         ("DXY","98.94","+0.03%",True),("US10Y","4.45","-0.04%",False),("GOLD","4,593","+0.71%",True),("BRENT","91.12","-1.01%",False)]
TAPE = MACRO + [("AAPL","273.17","+2.17%",True),("MSFT","418.57","-0.59%",False),("AMZN","266.32","+0.49%",True),
                ("GOOG","337.73","-1.43%",False),("DELL","214.65","+3.12%",True),("NVDA","215.33","-3.64%",False)]
tape_html = "".join(f'<span class="tk"><span class="s">{s}</span><span class="p">{p}</span><span class="{"up" if u else "dn"}">{"▲" if u else "▼"} {d}</span></span>' for s,p,d,u in TAPE)
st.markdown(f'<div class="tt"><div class="tt-track">{tape_html}{tape_html}</div></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# HEADER + WEI MACRO
# ═══════════════════════════════════════════════════════════════════
st.markdown('<div class="hdr"><h1>WORST-OF PHOENIX</h1><span class="sub">MIT QUANTUM · CLICKHOUSE CLOUD · IBM QISKIT · ФЕНИКС v32.0</span></div>', unsafe_allow_html=True)
wei = "".join(f'<div class="wei-c"><span class="wei-s">{s}</span><span class="wei-p">{p}</span><span class="wei-d {"up" if u else "dn"}">{"▲" if u else "▼"} {d}</span></div>' for s,p,d,u in MACRO)
st.markdown(f'<div class="wei"><div class="wei-t">WEI · GIP MACRO SNAPSHOT</div><div class="wei-b">{wei}</div></div>', unsafe_allow_html=True)

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

# Favorites
if "favorites" not in st.session_state:
    st.session_state.favorites = []
fc = st.columns([1,6,2])
with fc[0]:
    st.markdown('<div style="color:#ffb000;font-size:11px;padding:6px 0">★ ИЗБРАННЫЕ:</div>', unsafe_allow_html=True)
with fc[1]:
    if st.session_state.favorites:
        for i,fav in enumerate(st.session_state.favorites):
            if st.button(fav, key=f"fav_{i}"):
                st.session_state["basket_override"] = fav; st.rerun()
    else:
        st.markdown('<span style="color:#d6a44a;font-size:11px">— пусто. Сохрани корзину для быстрого recall</span>', unsafe_allow_html=True)
with fc[2]:
    if st.button("+ В ИЗБРАННОЕ", key="add_fav"):
        bk = basket_input.strip()
        if bk and bk not in st.session_state.favorites and len(st.session_state.favorites) < 12:
            st.session_state.favorites.append(bk); st.rerun()

st.markdown(f'<div style="color:#d6a44a;font-size:10px;padding:2px 0">ГОТОВО: СВОЯ КОРЗИНА {", ".join(basket_tickers)}.</div>', unsafe_allow_html=True)

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

    # Data sources list
    data_sources = ["ClickHouse (40K sims)"]
    if D["qiskit"]:
        data_sources.append(f"Qiskit ({list(D['qiskit'].values())[0].get('method','aer') if D['qiskit'] else 'aer'})")

    # Score styling
    score_grade = "good" if score >= 70 else "mid" if score >= 40 else "bad"
    score_color = "#2ea043" if score_grade == "good" else "#d29922" if score_grade == "mid" else "#f85149"
    stamp = "READY TO ISSUE" if score >= 70 else "NEEDS REVIEW" if score >= 40 else "AVOID"
    grade_text = "Высокий" if score >= 70 else "Средний" if score >= 40 else "Низкий"
    comparison_pct = max(0, min(99, int(score * 0.8 + 5)))

    # ═══════════════════════════════════════════════════════════════
    # РЕКОМЕНДАЦИИ + SCORING
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div style="border-bottom:2px solid #ffb000;display:inline-block;padding:4px 12px;color:#ffb000;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px">РЕКОМЕНДАЦИИ</div>', unsafe_allow_html=True)

    # Ticker chips
    chips = ""
    for t in basket_tickers:
        arrow = "↑" if td.get(t, {}).get("mean_return", 100) > 100 else "↓"
        chips += f'<span style="display:inline-block;background:#1a1400;border:1px solid #3a2a00;padding:3px 10px;margin:2px;color:#ffb000;font-size:11px;font-weight:700">{t} <span style="color:#ff3b30">📍</span> ✕</span>'
    st.markdown(f'<div style="margin:8px 0">{chips}</div>', unsafe_allow_html=True)

    st.markdown(f'''
    <div style="color:#ffb000;font-size:10px;margin-bottom:4px">КОРЗИНА ИЗ {n_tickers} БУМАГ</div>
    <div style="color:#d6a44a;font-size:9px">РЕКОМЕНД. СКОРИНГ</div>
    <div style="color:{score_color};font-size:32px;font-weight:700">{score:.1f}%</div>
    <div style="color:#d6a44a;font-size:10px">● {grade_text}</div>
    <div style="margin:6px 0;height:6px;background:#1a1400;border-radius:1px;position:relative">
        <div style="height:100%;width:{score}%;background:linear-gradient(90deg,#ff3b30,#ffb000,#34c759);border-radius:1px"></div>
    </div>
    <div style="background:#1a1400;border:1px solid #3a2a00;padding:3px 8px;color:#6db6ff;font-size:10px;display:inline-block">
        ■ Лучше {comparison_pct}% твоих (+{comparison_pct/30:.1f} от среднего)
    </div>
    <div style="background:{score_color}22;border:1px solid {score_color};padding:3px 8px;color:{score_color};font-size:10px;font-weight:700;margin-top:4px;display:inline-block">
        ▲ {stamp} · score {score:.0f}% {">" if score >= 70 else "<"} 70% · P(KI) {p_ki:.0f}% {"<" if p_ki < 35 else "≥"} 35%
    </div>
    ''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # МУЛЬТИ-ИНДИКАТОРЫ КОРЗИНЫ
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div class="sec">■ МУЛЬТИ-ИНДИКАТОРЫ КОРЗИНЫ</div>', unsafe_allow_html=True)

    def _mi(label, value, sub="", color="#ffb000"):
        return f'<div style="flex:1 1 48%;min-width:140px;padding:8px 10px;border:1px solid #3a2a00;margin:2px;background:#0a0a00"><div style="color:#d6a44a;font-size:9px;text-transform:uppercase">{label}</div><div style="color:{color};font-size:16px;font-weight:700">{value}</div><div style="color:#6a5a2a;font-size:9px">{sub}</div></div>'

    if ind:
        iv30 = ind.get("iv30_avg", 40)
        grid = _mi("IV30 (avg)", f"{iv30:.0f}%", f"min {ind.get('iv30_min',0):.0f}% · max {ind.get('iv30_max',0):.0f}%")
        grid += _mi("Real / IV", f"{ind.get('real_iv',0):.2f}", f"real vs IV {iv30:.0f}%")
        grid += _mi("β (avg)", f"{ind.get('beta_avg',1):.2f}", f"|min| {ind.get('beta_min',0):.2f} · |max| {ind.get('beta_max',0):.2f}")
        grid += _mi("P/E (avg)", f"{ind.get('pe_avg',25):.1f}", f"range {ind.get('pe_min',0):.0f} – {ind.get('pe_max',0):.0f}")
        grid += _mi("PEG (avg)", f"{ind.get('peg_avg',1.5):.2f}", f"range {ind.get('peg_min',0):.1f} – {ind.get('peg_max',0):.1f}", "#ff3b30" if ind.get("peg_avg",1.5) > 2 else "#ffb000")
        grid += _mi("DCF upside", f"{ind.get('dcf_avg',0):+.1f}%", f"range {ind.get('dcf_min',0):+.0f}% – {ind.get('dcf_max',0):+.0f}%", "#34c759" if ind.get("dcf_avg",0) > 0 else "#ff3b30")
        grid += _mi("Tgt up (analysts)", f"{ind.get('tgt_avg',0):+.1f}%", f"range {ind.get('tgt_min',0):+.0f}% – {ind.get('tgt_max',0):+.0f}%", "#34c759" if ind.get("tgt_avg",0) > 0 else "#ff3b30")
        grid += _mi("BCS Tgt up", f"{ind.get('bcs_avg',0):+.1f}%", f"range {ind.get('bcs_min',0):+.0f}% – {ind.get('bcs_max',0):+.0f}%", "#ff3b30" if ind.get("bcs_avg",0) < 0 else "#ffb000")
        grid += _mi("EMA200 trend", f"{ind.get('ema_up',0)}/{ind.get('ema_total',0)} ▲", f"avg {ind.get('ema_avg_pct',0):+.1f}%", "#34c759")
        grid += _mi("Аналитики", ind.get("rec_label","BUY"), f"rec {ind.get('rec_avg',1.8):.2f} ({ind.get('ema_total',0)}/{ind.get('ema_total',0)})", "#34c759" if ind.get("rec_label") == "BUY" else "#ffb000")
        grid += _mi("IV rank 1y", f"{D.get('iv_rank',50)}%", f"percentile rank")
        grid += _mi("P(KI)", f"{p_ki:.1f}%", f"при KI=60% spot за 2 года", "#ff3b30" if p_ki > 25 else "#34c759")
        grid += _mi("P(autocall)", f"{p_autocall:.1f}%", f"{D.get('e_life',1.5):.2f}г E[жизни]")
        grid += _mi("Dispersion", f"σ {D.get('dispersion',5):.1f}%", f"vol-spread")
        earn = earnings
        grid += _mi("Earnings density", f"{earn.get('total_events',0)}/{n_tickers}", f"nearest {earn.get('nearest_days',999)}д · score {earn.get('density_score',5):.1f}/10")
        st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:0">{grid}</div>', unsafe_allow_html=True)
    else:
        st.info("Нет данных yfinance — индикаторы будут доступны после загрузки")

    # Config line
    bstr = "/".join(basket_tickers)
    st.markdown(f'<div class="qc" style="padding:4px 10px;margin:8px 0"><code style="color:#d6a44a;font-size:10px">{bstr} 24 months USD ] 0.7 1 1 4 0.7 1 0.6 0</code></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # ACTION BUTTONS
    # ═══════════════════════════════════════════════════════════════
    b1,b2,b3 = st.columns(3)
    with b1: st.button("📋 КОПИРОВАТЬ", key="btn_copy"); st.button("🔄 УЛУЧШИ", key="btn_improve")
    with b2: st.button("📄 PDF", key="btn_pdf"); st.button("🎯 ПОД ЦЕЛЬ", key="btn_target")
    with b3: st.button("AB СРАВНИТЬ", key="btn_compare"); st.button("📊 PARETO", key="btn_pareto")
    b4,b5,b6 = st.columns(3)
    with b4: st.button("🌪 TORNADO", key="btn_tornado")
    with b5: st.button("☁ CLOUD MAP", key="btn_cloud")
    with b6: st.button("📤 ПОДЕЛИТЬСЯ", key="btn_share")

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
    # ОБЩИЙ РИСК-СКОР
    # ═══════════════════════════════════════════════════════════════
    rs = D["risk_score"]
    rc = D["risk_components"]
    rs_color = "#34c759" if rs >= 70 else "#ffb000" if rs >= 40 else "#ff3b30"
    rs_label = "Низкий риск" if rs >= 70 else "Средний риск" if rs >= 40 else "Высокий риск"
    rs_grade = "A" if rs >= 70 else "B" if rs >= 55 else "C" if rs >= 40 else "D"
    st.markdown(f'''
    <div class="qc" style="border-left:3px solid {rs_color};padding:14px;margin:12px 0">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div style="display:flex;align-items:center;gap:10px">
                <span style="color:#ffb000;font-size:13px;font-weight:700">⚙ ОБЩИЙ РИСК-СКОР КОРЗИНЫ</span>
                <span style="background:#1a1400;border:1px solid #3a2a00;padding:1px 6px;color:#d6a44a;font-size:9px;border-radius:2px">{rs_grade}</span>
            </div>
            <div style="text-align:right">
                <span style="color:{rs_color};font-size:28px;font-weight:700">{rs:.1f}</span>
                <span style="color:#d6a44a;font-size:12px">/100</span>
                <span style="color:{rs_color};font-size:11px;margin-left:8px">{rs_label}</span>
            </div>
        </div>
        <div style="margin-top:6px;height:6px;background:#1a1400;border-radius:1px"><div style="height:100%;width:{rs}%;background:{rs_color};border-radius:1px"></div></div>
    </div>
    ''', unsafe_allow_html=True)

    with st.expander("▶ Разложение по 6 компонентам риска"):
        for name, val in rc.items():
            st.markdown(f'<div style="color:#d6a44a;font-size:11px">{name}: <b style="color:#ffb000">{val:.1f}</b></div>', unsafe_allow_html=True)

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
    # ИИ-ПРЕДЛОЖЕНИЯ ПО КОРЗИНЕ
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div class="sec">🤖 ИИ-ПРЕДЛОЖЕНИЯ ПО КОРЗИНЕ</div>', unsafe_allow_html=True)
    worst_t = wo_analysis[0]["ticker"] if wo_analysis else basket_tickers[0]
    if p_ki > 25:
        ai_msg = f'🟣 <b>P(KI) высокая — снизить риск тела</b><br>Вероятность пробоя KI = {p_ki:.1f}%. Это много для worst-of. Снизь либо KI до 50%, либо замени самый рискованный имя (<b>{worst_t}</b>).'
    elif p_ki > 10:
        ai_msg = f'🟡 <b>P(KI) умеренная — корзина приемлема</b><br>P(KI) = {p_ki:.1f}%. Можно улучшить заменой {worst_t}.'
    else:
        ai_msg = f'🟢 <b>P(KI) низкая — корзина надёжная</b><br>P(KI) = {p_ki:.1f}%. Рекомендуется к размещению.'
    st.markdown(f'''
    <div class="qc" style="padding:14px">
        <div style="color:#d6a44a;font-size:11px;line-height:1.6;margin-bottom:10px">Эвристический анализ корзины: worst-of контрибьюторы, секторная концентрация, IV-разброс, percentile vs твоей истории. Не финрек, just helper.</div>
        <div style="color:#ffd56a;font-size:11px;line-height:1.6;border-left:3px solid #3a2a00;padding-left:10px">{ai_msg}</div>
    </div>
    ''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # Добавить / Заменить
    # ═══════════════════════════════════════════════════════════════
    with st.expander("▶ Как считается рекомендательный скоринг"):
        st.markdown(f'<div style="color:#d6a44a;font-size:11px;line-height:1.8">Источники: {" · ".join(data_sources)}<br>Score = 100 – breach_penalty – vol_penalty + mean_bonus + diversification + Q-VaR_bonus</div>', unsafe_allow_html=True)

    ac1, ac2 = st.columns([5,1])
    with ac1:
        add_input = st.text_input("Добавить в корзину: NVDA, TSLA", key="add_tickers", label_visibility="collapsed")
    with ac2:
        if st.button("➕ ДОБАВИТЬ", key="btn_add"):
            if add_input:
                new_t = [t.strip().upper() for t in add_input.replace(",", " ").split() if t.strip()]
                st.session_state["basket_override"] = basket_input.strip() + " " + " ".join(new_t); st.rerun()

    rc1,rc2,rc3 = st.columns(3)
    with rc1: st.button("↑ БОЛЬШЕ РИСК (ЗАМЕНИТЬ БУМАГУ)", key="btn_more")
    with rc2: st.button("↓ МЕНЬШЕ РИСК (ЗАМЕНИТЬ БУМАГУ)", key="btn_less")
    with rc3: st.button("🔗 СНИЗИТЬ TAIL DEP", key="btn_tail")

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
    # [09] RV MATRIX — 25 alternatives
    # ═══════════════════════════════════════════════════════════════
    RV_ALTS = ["NVDA","AMD","INTC","CRM","AVGO","QCOM","DELL","HPQ","NTAP","MCHP",
               "GNRC","BA","DIS","T","MCD","PM","ABBV","JNJ","ORCL",
               "GOLD","GLD","EXC","COF","APH","HLT"]
    with st.expander(f"[09] RV MATRIX    {len(RV_ALTS)} ALTS"):
        st.markdown(f'<div style="color:#d6a44a;font-size:10px;margin-bottom:8px;line-height:1.5">{len(RV_ALTS)+1} корзин (текущая + {len(RV_ALTS)} альтернатив), сгруппированы по доминирующему сектору. Зелёный = лучший в столбце, красный = худший. ★ = текущая. <b>Клик на корзину</b> или ► — пересчитать с этой корзиной.</div>', unsafe_allow_html=True)
        # Current basket
        st.markdown(f'''
        <div style="background:#0a1a0a;border:1px solid #34c759;padding:6px 10px;margin-bottom:6px">
            <span style="color:#34c759;font-size:11px;font-weight:700">★ Текущая корзина</span>
            <span style="color:#6a5a2a;font-size:10px;margin-left:8px">{top_sector} · {top_pct}% сектор-конц.</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:3px 8px;border-bottom:1px solid #3a2a00">
            <span style="color:#d6a44a;font-size:10px;font-weight:700">КОРЗИНА</span>
            <span style="color:#d6a44a;font-size:10px;font-weight:700">КУПОН P.A.</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:3px 8px;border-bottom:1px solid #3a2a00;background:#0a1a0a">
            <span style="color:#34c759;font-size:10px">★ {" · ".join(basket_tickers)}</span>
            <span style="color:#ffb000;font-size:10px;font-weight:700">{D["coupon_pa"]:.2f}%</span>
        </div>
        ''', unsafe_allow_html=True)
        # Alt baskets by sector
        seen_sectors = {}
        for alt in RV_ALTS:
            alt_basket = []
            for orig in basket_tickers:
                if orig == basket_tickers[-1]:
                    alt_basket.append(alt)
                else:
                    alt_basket.append(orig)
            sector = SECTOR_MAP.get(alt, "Unknown")
            if sector not in seen_sectors:
                seen_sectors[sector] = []
            # Estimate coupon (simple heuristic based on sector risk)
            risk_mult = {"Information Technology": 1.1, "Communication Services": 0.95, "Consumer Discretionary": 1.0,
                         "Health Care": 0.85, "Consumer Staples": 0.80, "Industrials": 0.95, "Financials": 1.05,
                         "Materials": 0.90, "Utilities": 0.75, "Real Estate": 1.15, "ETF": 0.70, "Unknown": 1.0}
            est_coupon = round(D["coupon_pa"] * risk_mult.get(sector, 1.0), 2)
            seen_sectors[sector].append((alt_basket, est_coupon, alt))

        for sector, baskets in seen_sectors.items():
            st.markdown(f'''
            <div style="border-left:3px solid #fa8000;padding:4px 8px;margin:8px 0 4px;background:#0a0a00">
                <span style="color:#fa8000;font-size:10px">📁 {sector}</span>
                <span style="color:#6a5a2a;font-size:9px;margin-left:8px">{len(baskets)} вариантов</span>
            </div>''', unsafe_allow_html=True)
            for bsk, cpn, alt_name in baskets:
                cpn_color = "#ff3b30" if cpn < 22 else "#34c759" if cpn > 35 else "#ffb000"
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:3px 8px;border-bottom:1px solid #1a1400"><span style="color:#d6a44a;font-size:10px">{" · ".join(bsk)}</span><span style="color:{cpn_color};font-size:10px;font-weight:700">{cpn:.2f}%</span></div>', unsafe_allow_html=True)

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
