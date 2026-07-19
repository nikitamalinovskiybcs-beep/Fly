"""Quant Risk Hub — Streamlit Dashboard v2.3."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import logging
from datetime import datetime

from src.assessor import StrategyRiskAssessor
from src.core_metrics import returns_from_prices
from src.risk_metrics import drawdown_series
from src.data_module import DEFAULT_TICKERS

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

st.set_page_config(
    page_title="Quant Risk Hub",
    page_icon="📊",
    layout="wide",
)

# ── Custom CSS (стиль из оригинального дизайна) ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); }
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); }
    .gradient-title {
        background: linear-gradient(135deg, #06b6d4, #10b981, #3b82f6);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .subtitle { text-align: center; color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    .metric-card {
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    .metric-value { font-size: 1.8rem; font-weight: 700; }
    .metric-label { font-size: 0.75rem; color: #64748b; margin-top: 0.25rem; }
    .section-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #e2e8f0;
        margin: 1.5rem 0 0.75rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .alert-high { background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 8px; padding: 0.75rem; color: #fca5a5; margin-bottom: 0.5rem; }
    .alert-medium { background: rgba(234, 179, 8, 0.15); border: 1px solid #eab308; border-radius: 8px; padding: 0.75rem; color: #fde047; margin-bottom: 0.5rem; }
    .alert-low { background: rgba(34, 197, 94, 0.15); border: 1px solid #22c55e; border-radius: 8px; padding: 0.75rem; color: #86efac; margin-bottom: 0.5rem; }
    div[data-testid="stMetric"] { background: rgba(15, 23, 42, 0.5); border: 1px solid #334155; border-radius: 12px; padding: 1rem; }
    .hero-panel { background: radial-gradient(circle at 80% 10%, rgba(6,182,212,.2), transparent 34%), rgba(15,23,42,.72); border: 1px solid #334155; border-radius: 20px; padding: 2rem; margin: 1rem 0 1.5rem; }
    .hero-panel h1 { color: #f8fafc; font-size: 2.4rem; margin: .25rem 0 .5rem; }
    .hero-panel p { color: #94a3b8; max-width: 760px; font-size: 1rem; line-height: 1.6; }
    .eyebrow { color: #22d3ee; font-size: .7rem; font-weight: 700; letter-spacing: .14em; }
    .insight-card, .warning-card { border-radius: 14px; padding: 1rem 1.1rem; margin-top: .75rem; }
    .insight-card { background: rgba(14,116,144,.14); border: 1px solid rgba(34,211,238,.4); }
    .warning-card { background: rgba(127,29,29,.22); border: 1px solid rgba(251,113,133,.65); }
    .insight-card strong, .warning-card strong { color: #f8fafc; }
    .insight-card p, .warning-card p { color: #cbd5e1; margin: .5rem 0 0; line-height: 1.5; }
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown('<div class="gradient-title">IMOEXF Hedge Lab</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Хедж портфеля акций через фьючерс IMOEXF · сценарный анализ, tracking error и запас ликвидности</div>', unsafe_allow_html=True)

# ── Sidebar ──
with st.sidebar:
    page_mode = st.radio(
        "Раздел",
        ["IMOEXF Hedge Lab", "Quant Risk Hub"],
        index=0,
    )
    st.markdown("### ⚙️ Настройки")
    tickers_input = st.text_area(
        "Тикеры (по одному на строку)",
        value="\n".join(DEFAULT_TICKERS),
        height=200,
    )
    tickers = [t.strip().upper() for t in tickers_input.strip().split("\n") if t.strip()]

    benchmark = st.selectbox("Бенчмарк", options=tickers if tickers else ["SPY"], index=0)
    rf_rate = st.slider("Risk-free rate", 0.0, 0.10, 0.05, 0.005, format="%.3f")
    n_perms = st.slider("Monte Carlo перестановок", 100, 2000, 500, 100)
    slippage = st.slider("Slippage (bps)", 0, 50, 5)
    commission = st.slider("Комиссия (bps)", 0, 20, 2)
    trades_day = st.slider("Сделок в день", 0.1, 10.0, 1.0, 0.1)
    period = st.selectbox("Период данных", ["1y", "2y", "3y", "5y", "10y", "max"], index=3)
    run_btn = st.button("🚀 Запустить анализ", use_container_width=True, type="primary")

# ── Plotly dark template ──
PLOT_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#e2e8f0"),
    margin=dict(l=40, r=20, t=40, b=40),
)


def color_for_level(level: str) -> str:
    return {"LOW": "#22c55e", "MEDIUM": "#eab308", "HIGH": "#ef4444"}.get(level, "#64748b")


def money(value: float) -> str:
    sign = "−" if value < 0 else "+"
    return f"{sign}{abs(value) / 1_000_000:.2f} млн ₽"


def render_hedge_lab() -> None:
    """Scenario dashboard for an equity portfolio hedged with IMOEXF."""
    st.markdown(
        """
        <div class="hero-panel">
            <div class="eyebrow">PORTFOLIO HEDGE CONSOLE</div>
            <h1>Лонг акций + шорт IMOEXF</h1>
            <p>Проверьте, что именно компенсирует фьючерс, сколько съедает tracking error
            и какой запас живых денег нужен при резком отскоке рынка.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Параметры позиции", expanded=True):
        inputs = st.columns(4)
        with inputs[0]:
            portfolio = st.number_input("Лонг портфеля, ₽", min_value=0.0, value=33_630_000.0, step=100_000.0)
            stock_move = st.number_input("Изменение лонга", value=-16.35, step=0.5, format="%.2f") / 100
        with inputs[1]:
            hedge_nominal = st.number_input("Номинал шорта IMOEXF, ₽", min_value=0.0, value=33_630_000.0, step=100_000.0)
            index_move = st.number_input("Изменение IMOEX", value=-13.0, step=0.5, format="%.2f") / 100
        with inputs[2]:
            margin_rate = st.number_input("Ориентир ГО", min_value=0.01, max_value=1.0, value=0.20, step=0.01, format="%.2f")
            carry_rate = st.number_input("Сценарий carry / базиса годовых", value=14.0, step=0.5, format="%.1f") / 100
        with inputs[3]:
            holding_months = st.number_input("Период, месяцев", min_value=0.0, value=6.0, step=1.0)
            beta = st.number_input("Beta портфеля", min_value=0.0, value=1.01, step=0.01, format="%.2f")

    long_pnl = portfolio * stock_move
    futures_pnl = -hedge_nominal * index_move
    carry_pnl = hedge_nominal * carry_rate * holding_months / 12
    net_pnl = long_pnl + futures_pnl + carry_pnl
    margin = hedge_nominal * margin_rate
    tracking_error = stock_move - index_move
    net_pct = net_pnl / portfolio if portfolio else 0.0

    st.markdown("### Результат сценария")
    cards = st.columns(4)
    cards[0].metric("Лонг", money(long_pnl), f"{stock_move:.2%}")
    cards[1].metric("Шорт IMOEXF", money(futures_pnl), f"{-index_move:.2%} к номиналу")
    cards[2].metric("Carry / базис", money(carry_pnl), "сценарная оценка")
    cards[3].metric("Итог", money(net_pnl), f"{net_pct:.2%} от лонга")

    left, right = st.columns([1.45, 1])
    with left:
        waterfall = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "relative", "total"],
            x=["Лонг", "Шорт IMOEXF", "Carry / базис", "Итог"],
            y=[long_pnl, futures_pnl, carry_pnl, net_pnl],
            text=[money(long_pnl), money(futures_pnl), money(carry_pnl), money(net_pnl)],
            textposition="outside",
            connector={"line": {"color": "#475569"}},
            increasing={"marker": {"color": "#34d399"}},
            decreasing={"marker": {"color": "#fb7185"}},
            totals={"marker": {"color": "#38bdf8"}},
        ))
        waterfall.update_layout(title="Декомпозиция P&L", **PLOT_LAYOUT)
        st.plotly_chart(waterfall, use_container_width=True)
    with right:
        st.markdown("#### Что осталось без хеджа")
        st.metric("Tracking error", f"{tracking_error:.2%}", "лонг относительно индекса")
        st.metric("Ориентир ГО", money(margin), f"{margin_rate:.0%} номинала")
        st.markdown(
            f"""
            <div class="insight-card">
                <div class="eyebrow">READOUT</div>
                <strong>Главная утечка — относительная доходность.</strong>
                <p>Если портфель падает сильнее IMOEX, индексный шорт компенсирует рынок,
                но не beta/состав корзины. В этом сценарии это {money(portfolio * tracking_error)}.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Стресс-тест: рынок отскакивает на +20%")
    stress_move = 0.20
    stress_long = portfolio * beta * stress_move
    stress_short = -hedge_nominal * stress_move
    stress_net = stress_long + stress_short + carry_pnl
    stress_cash = abs(stress_short)
    stress_cards = st.columns(4)
    stress_cards[0].metric("Лонг", money(stress_long), f"beta {beta:.2f}")
    stress_cards[1].metric("Вариационная маржа шорта", money(stress_short), "ежедневный cash outflow")
    stress_cards[2].metric("Carry / базис", money(carry_pnl), "если сценарий реализуется")
    stress_cards[3].metric("Итог сценария", money(stress_net), "экономический P&L")

    st.markdown(
        f"""
        <div class="warning-card">
            <div class="eyebrow">LIQUIDITY ALERT</div>
            <strong>Потенциальная потребность в живых деньгах: {stress_cash / 1_000_000:.2f} млн ₽.</strong>
            <p>Прибыль по акциям может быть бумажной, а убыток по фьючерсу списывается
            вариационной маржой. Это стресс-ориентир, а не гарантия брокерского требования.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["Карта рисков", "Сценарии", "Как читать расчёт"])
    with tab1:
        risk_df = pd.DataFrame([
            {"Риск": "Tracking error", "Статус": "Внимание", "Драйвер": f"{tracking_error:.2%} против IMOEX"},
            {"Риск": "Вариационная маржа", "Статус": "Критично контролировать", "Драйвер": money(stress_cash) + " при +20%"},
            {"Риск": "Carry / базис", "Статус": "Не гарантирован", "Драйвер": f"{carry_rate:.1%} годовых в модели"},
            {"Риск": "ГО", "Статус": "Динамический", "Драйвер": money(margin) + " сейчас"},
        ])
        st.dataframe(risk_df, use_container_width=True, hide_index=True)
    with tab2:
        scenario_moves = np.linspace(-0.30, 0.30, 13)
        scenario_df = pd.DataFrame({
            "IMOEX": scenario_moves,
            "Лонг": portfolio * beta * scenario_moves,
            "Шорт IMOEXF": -hedge_nominal * scenario_moves,
        })
        scenario_df["Итог без carry"] = scenario_df["Лонг"] + scenario_df["Шорт IMOEXF"]
        fig = go.Figure()
        for column, color in [("Лонг", "#34d399"), ("Шорт IMOEXF", "#fb7185"), ("Итог без carry", "#38bdf8")]:
            fig.add_trace(go.Scatter(
                x=scenario_df["IMOEX"], y=scenario_df[column] / 1_000_000,
                mode="lines+markers", name=column, line={"color": color, "width": 2},
            ))
        fig.update_layout(title="P&L при разных движениях IMOEX", xaxis_tickformat=".0%", yaxis_title="млн ₽", **PLOT_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
    with tab3:
        st.markdown(
            """
            - **Шорт IMOEXF не платит фиксированный funding.** В расчёте carry / базис — отдельный
              сценарный параметр, который может быть положительным или отрицательным.
            - **ГО — не максимальный убыток.** Биржа меняет требования, а вариационная маржа
              списывается ежедневно.
            - **Полный номинальный хедж не равен beta-хеджу.** Для портфеля с beta выше единицы
              может понадобиться больший номинал, но это увеличивает требования к ликвидности.
            """
        )
        st.caption("Модель учебная и не учитывает комиссии, налоги, дивиденды, проскальзывание и изменение базиса.")


if page_mode == "IMOEXF Hedge Lab":
    render_hedge_lab()
    st.stop()


# ── Streamlit кэширование ──
@st.cache_data(ttl=3600)
def load_and_analyze(tickers_tuple, benchmark, rf_rate, n_perms, slippage, commission, trades_day, period):
    """Кэшируем данные и анализ на 1 час."""
    try:
        assessor = StrategyRiskAssessor(
            tickers=list(tickers_tuple),
            benchmark=benchmark,
            rf_rate=rf_rate,
            n_permutations=n_perms,
            slippage_bps=slippage,
            commission_bps=commission,
            trades_per_day=trades_day,
        )
        prices = assessor.update_market_data(period=period)
        return assessor, prices
    except Exception as e:
        st.error(f"❌ Ошибка загрузки данных: {str(e)}")
        return None, None


if run_btn:
    if not tickers:
        st.error("❌ Введите хотя бы один тикер")
        st.stop()
    
    if benchmark not in tickers:
        st.error(f"❌ Бенчмарк '{benchmark}' должен быть в списке тикеров")
        st.stop()

    with st.spinner("📡 Загрузка рыночных данных..."):
        assessor, prices = load_and_analyze(
            tuple(tickers), benchmark, rf_rate, n_perms, slippage, commission, trades_day, period
        )

    if assessor is None or prices is None or prices.empty:
        st.error("❌ Не удалось загрузить данные. Проверьте тикеры и подключение.")
        st.stop()

    # ── Top Stats ──
    all_perf = assessor.get_all_performance()
    if all_perf.empty:
        st.error("❌ Недостаточно данных для анализа")
        st.stop()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📈 Тикеров", len(all_perf))
    avg_sharpe = all_perf["sharpe"].mean()
    col2.metric("⚡ Avg Sharpe", f"{avg_sharpe:.2f}")
    avg_dd = all_perf["max_drawdown"].mean()
    col3.metric("📉 Avg Max DD", f"{avg_dd:.1%}")
    col4.metric("🕐 Обновлено", assessor.last_update[:16] if assessor.last_update else "—")

    st.divider()

    # ── Performance Table ──
    st.markdown('<div class="section-header">📋 Сводка метрик по всем тикерам</div>', unsafe_allow_html=True)
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
    selected = st.selectbox("🔍 Детальный анализ тикера", tickers)

    if selected and selected in assessor.returns.columns:
        try:
            report = assessor.generate_report(selected)

            # Risk Score
            rs = report["risk_score"]
            score_color = color_for_level(rs["level"])
            st.markdown(f"""
            <div style="text-align:center; margin: 1rem 0;">
                <div style="font-size:3rem; font-weight:700; color:{score_color};">{rs['score']}</div>
                <div style="font-size:1rem; color:{score_color};">Risk Score — {rs['level']}</div>
            </div>
            """, unsafe_allow_html=True)

            # Alerts
            if report["warnings"]:
                for w in report["warnings"]:
                    alert_class = "alert-high" if "overfitting" in w.lower() or "убыточна" in w.lower() else "alert-medium"
                    st.markdown(f'<div class="{alert_class}">⚠️ {w}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="alert-low">✅ Критических предупреждений нет</div>', unsafe_allow_html=True)

            # Key Metrics row
            perf = report["performance"]
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Sharpe", f"{perf['sharpe']:.2f}")
            c2.metric("Sortino", f"{perf['sortino']:.2f}")
            c3.metric("CAGR", f"{perf['cagr']:.2%}")
            c4.metric("Max DD", f"{perf['max_drawdown']:.2%}")
            c5.metric("Profit Factor", f"{perf['profit_factor']:.2f}")

            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "📈 Equity Curve", "📊 Risk Metrics", "🧪 Monte Carlo",
                "🔄 Walk-Forward", "💥 Stress Tests", "🔗 Correlations"
            ])

            rets = assessor.returns[selected].dropna()

            # Tab 1: Equity Curve
            with tab1:
                cum = (1 + rets).cumprod()
                dd = drawdown_series(rets)
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=cum.index, y=cum.values,
                    name="Equity", line=dict(color="#06b6d4", width=2),
                    fill="tozeroy", fillcolor="rgba(6,182,212,0.1)",
                ))
                fig.update_layout(title=f"Equity Curve — {selected}", yaxis_title="Кумулятивная доходность", **PLOT_LAYOUT)
                st.plotly_chart(fig, use_container_width=True)

                fig_dd = go.Figure()
                fig_dd.add_trace(go.Scatter(
                    x=dd.index, y=dd.values,
                    name="Drawdown", line=dict(color="#ef4444", width=1.5),
                    fill="tozeroy", fillcolor="rgba(239,68,68,0.15)",
                ))
                fig_dd.update_layout(title="Drawdown", yaxis_title="Drawdown", yaxis_tickformat=".0%", **PLOT_LAYOUT)
                st.plotly_chart(fig_dd, use_container_width=True)

            # Tab 2: Risk Metrics
            with tab2:
                risk = report["risk"]
                rc1, rc2 = st.columns(2)
                with rc1:
                    st.markdown("##### VaR / CVaR")
                    risk_df = pd.DataFrame([
                        {"Метрика": "VaR 95%", "Значение": f"{risk['VaR_95']:.4f}"},
                        {"Метрика": "CVaR 95%", "Значение": f"{risk['CVaR_95']:.4f}"},
                        {"Метрика": "VaR 99%", "Значение": f"{risk['VaR_99']:.4f}"},
                        {"Метрика": "CVaR 99%", "Значение": f"{risk['CVaR_99']:.4f}"},
                    ])
                    st.dataframe(risk_df, use_container_width=True, hide_index=True)

                with rc2:
                    st.markdown("##### Drawdown Distribution")
                    dd_dist = report["drawdown_dist"]
                    dd_df = pd.DataFrame([
                        {"Метрика": "Mean DD", "Значение": f"{dd_dist['mean']:.4f}"},
                        {"Метрика": "Median DD", "Значение": f"{dd_dist['median']:.4f}"},
                        {"Метрика": "Worst DD", "Значение": f"{dd_dist['worst']:.4f}"},
                    ])
                    st.dataframe(dd_df, use_container_width=True, hide_index=True)

                # Returns distribution
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Histogram(
                    x=rets.values, nbinsx=50,
                    marker_color="#06b6d4", opacity=0.7,
                    name="Daily Returns",
                ))
                fig_hist.update_layout(title="Распределение дневных доходностей", xaxis_title="Return", **PLOT_LAYOUT)
                st.plotly_chart(fig_hist, use_container_width=True)

            # Tab 3: Monte Carlo
            with tab3:
                with st.spinner("🎲 Monte Carlo Permutation Test..."):
                    try:
                        mc = assessor.run_monte_carlo_test(selected)
                        ovf = report["overfitting"]
                        perm = ovf["permutation_test"]

                        st.markdown(f"**Observed Sharpe:** {perm['observed_sharpe']:.4f}")
                        st.markdown(f"**p-value:** {perm['p_value']:.4f}")
                        st.markdown(f"**Вердикт:** {perm['verdict']}")

                        fig_mc = go.Figure()
                        fig_mc.add_trace(go.Histogram(
                            x=mc["permuted_distribution"], nbinsx=40,
                            marker_color="#8b5cf6", opacity=0.7, name="Permuted Sharpe",
                        ))
                        fig_mc.add_vline(x=mc["observed"], line_dash="dash", line_color="#ef4444",
                                        annotation_text=f"Observed: {mc['observed']:.3f}")
                        fig_mc.update_layout(title="Monte Carlo Permutation Test", xaxis_title="Sharpe Ratio", **PLOT_LAYOUT)
                        st.plotly_chart(fig_mc, use_container_width=True)
                    except Exception as e:
                        st.warning(f"⚠️ Ошибка Monte Carlo: {str(e)}")

            # Tab 4: Walk-Forward
            with tab4:
                with st.spinner("🔄 Walk-Forward Analysis..."):
                    try:
                        wf = assessor.run_walk_forward(selected)
                        if wf:
                            wf_df = pd.DataFrame(wf)
                            st.dataframe(wf_df, use_container_width=True, hide_index=True)

                            fig_wf = go.Figure()
                            fig_wf.add_trace(go.Bar(
                                x=[f"Fold {r['fold']}" for r in wf],
                                y=[r["train_metric"] for r in wf],
                                name="Train Sharpe", marker_color="#10b981",
                            ))
                            fig_wf.add_trace(go.Bar(
                                x=[f"Fold {r['fold']}" for r in wf],
                                y=[r["test_metric"] for r in wf],
                                name="Test Sharpe", marker_color="#06b6d4",
                            ))
                            fig_wf.update_layout(title="Walk-Forward: Train vs Test Sharpe", barmode="group", **PLOT_LAYOUT)
                            st.plotly_chart(fig_wf, use_container_width=True)
                        else:
                            st.info("Недостаточно данных для Walk-Forward анализа.")
                    except Exception as e:
                        st.warning(f"⚠️ Ошибка Walk-Forward: {str(e)}")

            # Tab 5: Stress Tests
            with tab5:
                try:
                    stress = report["stress_tests"]
                    if stress:
                        stress_df = pd.DataFrame(stress)
                        for c in ["cum_return", "max_dd"]:
                            if c in stress_df.columns:
                                stress_df[c] = stress_df[c].map(lambda x: f"{x:.2%}" if not pd.isna(x) else "N/A")
                        st.dataframe(stress_df[["scenario", "period", "cum_return", "max_dd", "n_days"]],
                                    use_container_width=True, hide_index=True)
                except Exception as e:
                    st.warning(f"⚠️ Ошибка Stress Tests: {str(e)}")

            # Tab 6: Correlations
            with tab6:
                try:
                    corr = assessor.get_correlations()
                    fig_corr = px.imshow(
                        corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                        zmin=-1, zmax=1, aspect="auto",
                    )
                    fig_corr.update_layout(title="Матрица корреляций", **PLOT_LAYOUT)
                    st.plotly_chart(fig_corr, use_container_width=True)
                except Exception as e:
                    st.warning(f"⚠️ Ошибка корреляций: {str(e)}")
        
        except Exception as e:
            st.error(f"❌ Ошибка анализа: {str(e)}")

else:
    # Landing page
    st.markdown("""
    <div style="text-align: center; padding: 3rem 1rem;">
        <div style="font-size: 4rem; margin-bottom: 1rem;">📊</div>
        <h2 style="color: #e2e8f0;">Добро пожаловать в Quant Risk Hub</h2>
        <p style="color: #94a3b8; max-width: 600px; margin: 0 auto 2rem;">
            Настройте тикеры и параметры в боковой панели, затем нажмите
            <strong style="color: #06b6d4;">🚀 Запустить анализ</strong>.
        </p>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; max-width: 800px; margin: 0 auto;">
            <div class="metric-card">
                <div style="font-size: 2rem;">📈</div>
                <div style="color: #e2e8f0; font-weight: 600; margin-top: 0.5rem;">Core Metrics</div>
                <div style="color: #64748b; font-size: 0.8rem;">Sharpe, Sortino, Calmar, Max DD</div>
            </div>
            <div class="metric-card">
                <div style="font-size: 2rem;">🎲</div>
                <div style="color: #e2e8f0; font-weight: 600; margin-top: 0.5rem;">Monte Carlo</div>
                <div style="color: #64748b; font-size: 0.8rem;">Permutation Test (≤ 2000)</div>
            </div>
            <div class="metric-card">
                <div style="font-size: 2rem;">💥</div>
                <div style="color: #e2e8f0; font-weight: 600; margin-top: 0.5rem;">Stress Tests</div>
                <div style="color: #64748b; font-size: 0.8rem;">GFC 2008, COVID, Rate Hike 2022</div>
            </div>
            <div class="metric-card">
                <div style="font-size: 2rem;">🔍</div>
                <div style="color: #e2e8f0; font-weight: 600; margin-top: 0.5rem;">Overfitting</div>
                <div style="color: #64748b; font-size: 0.8rem;">OOS degradation, permutation check</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
