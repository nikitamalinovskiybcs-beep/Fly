"""Quant Risk Hub — Streamlit Dashboard v2.3 + MIT Quantum + ClickHouse."""

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

st.set_page_config(
    page_title="Quant Risk Hub | MIT Quantum",
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
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown('<div class="gradient-title">📊 Quant Risk Hub</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Trading Strategy Risk Assessment Framework v2.3 | MIT + IBM Quantum · ClickHouse Cloud</div>', unsafe_allow_html=True)

# ── Sidebar ──
with st.sidebar:
    st.markdown("### ⚙️ Настройки")
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


if run_btn:
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
                    {"Метрика": "Param VaR 95%", "Значение": f"{risk['Parametric_VaR_95']:.4f}"},
                    {"Метрика": "Param VaR 99%", "Значение": f"{risk['Parametric_VaR_99']:.4f}"},
                ])
                st.dataframe(risk_df, use_container_width=True, hide_index=True)

            with rc2:
                st.markdown("##### Drawdown Distribution")
                dd_dist = report["drawdown_dist"]
                dd_df = pd.DataFrame([
                    {"Метрика": "Mean DD", "Значение": f"{dd_dist['mean']:.4f}"},
                    {"Метрика": "Median DD", "Значение": f"{dd_dist['median']:.4f}"},
                    {"Метрика": "Worst DD", "Значение": f"{dd_dist['worst']:.4f}"},
                    {"Метрика": "DD Std", "Значение": f"{dd_dist['std']:.4f}"},
                    {"Метрика": "5th percentile", "Значение": f"{dd_dist['percentile_5']:.4f}"},
                ])
                st.dataframe(dd_df, use_container_width=True, hide_index=True)

            # Returns distribution
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Histogram(
                x=rets.values, nbinsx=80,
                marker_color="#06b6d4", opacity=0.7,
                name="Daily Returns",
            ))
            fig_hist.update_layout(title="Распределение дневных доходностей", xaxis_title="Return", **PLOT_LAYOUT)
            st.plotly_chart(fig_hist, use_container_width=True)

            # Stability
            st.markdown("##### Стабильность Sharpe по периодам")
            stab = report["stability"]
            stab_df = pd.DataFrame([{"Период": k, "Sharpe": f"{v:.2f}" if not pd.isna(v) else "N/A"} for k, v in stab.items()])
            st.dataframe(stab_df, use_container_width=True, hide_index=True)

        # Tab 3: Monte Carlo
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
                marker_color="#8b5cf6", opacity=0.7, name="Permuted Sharpe",
            ))
            fig_mc.add_vline(x=mc["observed"], line_dash="dash", line_color="#ef4444",
                             annotation_text=f"Observed: {mc['observed']:.3f}")
            fig_mc.update_layout(title="Monte Carlo Permutation Test", xaxis_title="Sharpe Ratio", **PLOT_LAYOUT)
            st.plotly_chart(fig_mc, use_container_width=True)

            # OOS degradation
            st.markdown("##### Out-of-Sample Degradation")
            oos = ovf["oos_degradation"]
            oc1, oc2, oc3 = st.columns(3)
            oc1.metric("Train Sharpe", f"{oos['train_sharpe']:.2f}")
            oc2.metric("Test Sharpe", f"{oos['test_sharpe']:.2f}")
            oc3.metric("Деградация", f"{oos['sharpe_degradation']:.2f}")
            st.markdown(f"**Вердикт:** {oos['verdict']}")

        # Tab 4: Walk-Forward
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

        # Tab 5: Stress Tests
        with tab5:
            stress = report["stress_tests"]
            stress_df = pd.DataFrame(stress)
            for c in ["cum_return", "max_dd"]:
                if c in stress_df.columns:
                    stress_df[c] = stress_df[c].map(lambda x: f"{x:.2%}" if not pd.isna(x) else "N/A")
            st.dataframe(stress_df[["scenario", "period", "cum_return", "max_dd", "n_days", "warning"]],
                         use_container_width=True, hide_index=True)

            # Slippage impact
            st.markdown("##### Влияние Slippage на результат")
            slip_df = assessor.get_slippage_impact(selected)
            for c in ["total_return", "cagr"]:
                slip_df[c] = slip_df[c].map(lambda x: f"{x:.2%}")
            slip_df["sharpe"] = slip_df["sharpe"].map(lambda x: f"{x:.2f}")
            st.dataframe(slip_df, use_container_width=True, hide_index=True)

        # Tab 6: Correlations
        with tab6:
            corr = assessor.get_correlations()
            fig_corr = px.imshow(
                corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                zmin=-1, zmax=1, aspect="auto",
            )
            fig_corr.update_layout(title="Матрица корреляций", **PLOT_LAYOUT)
            st.plotly_chart(fig_corr, use_container_width=True)

else:
    # ── Landing Dashboard — Original Quant Risk Hub Style + Quantum Enhancements ──

    # Load ClickHouse data
    with st.spinner("🗄️ Загрузка данных из ClickHouse Cloud..."):
        ch_data = fetch_quantum_risk_stats()
    q_status = get_quantum_status()
    tickers_data = ch_data["tickers"]
    wo = ch_data["worst_of"]
    src_label = "ClickHouse Cloud" if ch_data["source"] == "clickhouse_cloud" else "Cache (offline)"

    # ── Top Stats Grid (original 2x2 style + quantum) ──
    st.markdown(f"""
    <div style="display:grid; grid-template-columns:repeat(2,1fr); gap:0.75rem; margin-bottom:1.5rem;">
        <div style="background:rgba(15,23,42,0.5); border:1px solid #334155; border-radius:12px; padding:1rem; text-align:center;">
            <div style="font-size:2rem; font-weight:700; color:#06b6d4;">{ch_data['total_simulations']:,}</div>
            <div style="font-size:0.75rem; color:#64748b;">Квантовых симуляций</div>
        </div>
        <div style="background:rgba(15,23,42,0.5); border:1px solid #334155; border-radius:12px; padding:1rem; text-align:center;">
            <div style="font-size:2rem; font-weight:700; color:#10b981;">{len(tickers_data)}</div>
            <div style="font-size:0.75rem; color:#64748b;">Активов</div>
        </div>
        <div style="background:rgba(15,23,42,0.5); border:1px solid #334155; border-radius:12px; padding:1rem; text-align:center;">
            <div style="font-size:2rem; font-weight:700; color:#eab308;">{wo['barrier_breach_pct']:.1f}%</div>
            <div style="font-size:0.75rem; color:#64748b;">Worst-of Barrier Breach</div>
        </div>
        <div style="background:rgba(15,23,42,0.5); border:1px solid #334155; border-radius:12px; padding:1rem; text-align:center;">
            <div style="font-size:2rem; font-weight:700; color:#a78bfa;">{wo['var_95']:.1f}%</div>
            <div style="font-size:0.75rem; color:#64748b;">Worst-of VaR 95%</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Quantum Risk Section (card-based like original GitHub section) ──
    st.markdown(f"""
    <div style="background:rgba(15,23,42,0.3); border:1px solid #334155; border-radius:12px; padding:1rem; margin-bottom:0.75rem;">
        <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.75rem;">
            <div style="width:32px; height:32px; background:rgba(6,182,212,0.2); border-radius:8px; display:flex; align-items:center; justify-content:center;">
                <span style="font-size:1rem;">⚛️</span>
            </div>
            <h2 style="font-size:1.1rem; font-weight:700; color:white; margin:0;">⚛️ MIT Quantum Risk Analytics</h2>
        </div>
        <div style="font-size:0.8rem; color:#94a3b8; margin-bottom:0.75rem;">
            Источник: {src_label} · Таблица: {ch_data['table']} · Barrier: {ch_data['barrier_level']}%
        </div>
    """, unsafe_allow_html=True)

    # Per-ticker cards (styled like original GitHub repo cards)
    for ticker in ["AAPL", "MSFT", "GOOGL", "AMZN"]:
        if ticker not in tickers_data:
            continue
        d = tickers_data[ticker]
        breach_color = "#ef4444" if d["barrier_breach_pct"] > 10 else "#eab308" if d["barrier_breach_pct"] > 1 else "#22c55e"
        st.markdown(f"""
        <div style="background:rgba(15,23,42,0.5); border:1px solid #334155; border-radius:8px; padding:0.75rem; margin-bottom:0.5rem;">
            <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:0.5rem;">
                <span style="font-weight:700; color:#10b981; font-size:0.95rem;">{ticker}</span>
                <div style="display:flex; gap:0.75rem; align-items:center;">
                    <span style="color:#06b6d4; font-size:0.8rem;">VaR 95%: {d['var_95']:.1f}%</span>
                    <span style="color:{breach_color}; font-size:0.8rem;">Breach: {d['barrier_breach_pct']:.2f}%</span>
                </div>
            </div>
            <div style="color:#94a3b8; font-size:0.8rem; margin-bottom:0.4rem;">
                Mean: {d['mean_return']:.1f}% · Vol: {d['volatility']:.1f}% · Range: [{d['min_return']:.1f}%, {d['max_return']:.1f}%]
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.75rem;">
                <span style="color:#475569;">📊 {d['num_simulations']:,} simulations</span>
                <span style="color:#475569;">VaR 99%: {d['var_99']:.1f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Qiskit Live VaR Section (card-based like X.com tweets) ──
    st.markdown(f"""
    <div style="background:rgba(15,23,42,0.3); border:1px solid #334155; border-radius:12px; padding:1rem; margin-bottom:0.75rem;">
        <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.75rem;">
            <div style="width:32px; height:32px; background:rgba(168,85,247,0.2); border-radius:8px; display:flex; align-items:center; justify-content:center;">
                <span style="font-size:1rem;">🔬</span>
            </div>
            <h2 style="font-size:1.1rem; font-weight:700; color:white; margin:0;">🔬 IBM Qiskit — Live Q-VaR</h2>
        </div>
        <div style="font-size:0.8rem; color:#94a3b8; margin-bottom:0.75rem;">
            {'⚛️ ' + q_status['provider'] + ' — ' + q_status['backend']}
        </div>
    """, unsafe_allow_html=True)

    for ticker in ["AAPL", "MSFT", "GOOGL", "AMZN"]:
        if ticker not in tickers_data:
            continue
        d = tickers_data[ticker]
        sim_returns = np.random.normal(d["mean_return"], d["volatility"], 1000)
        q_result = quantum_var_estimation(sim_returns, confidence=0.95)
        q_label = f"⚛️ {q_result['n_qubits']}q · {q_result['shots']} shots" if q_result.get("quantum") else "Classical"
        st.markdown(f"""
        <div style="background:rgba(15,23,42,0.5); border:1px solid #334155; border-radius:8px; padding:0.75rem; margin-bottom:0.5rem;">
            <div style="display:flex; gap:0.5rem;">
                <div style="width:32px; height:32px; background:rgba(168,85,247,0.2); border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                    <span style="font-size:0.8rem;">⚛️</span>
                </div>
                <div style="flex:1;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:0.25rem;">
                        <span style="font-weight:700; color:#a78bfa;">{ticker}</span>
                        <span style="color:#475569; font-size:0.75rem;">{q_label}</span>
                    </div>
                    <div style="color:#e2e8f0; font-size:0.85rem;">
                        Q-VaR 95%: <strong style="color:#06b6d4;">{q_result['var']:.2f}%</strong> ·
                        Q-CVaR: <strong style="color:#eab308;">{q_result['cvar']:.2f}%</strong>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── GitHub Section (original style) ──
    st.markdown("""
    <div style="background:rgba(15,23,42,0.3); border:1px solid #334155; border-radius:12px; padding:1rem; margin-bottom:0.75rem;">
        <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.75rem;">
            <div style="width:32px; height:32px; background:rgba(16,185,129,0.2); border-radius:8px; display:flex; align-items:center; justify-content:center;">
                <svg style="width:16px; height:16px; fill:#10b981;" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.108-.775.418-1.305.762-1.604-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
            </div>
            <h2 style="font-size:1.1rem; font-weight:700; color:white; margin:0;">💻 GitHub Новинки</h2>
        </div>
    """, unsafe_allow_html=True)

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
                st.markdown(f"""
                <div style="background:rgba(15,23,42,0.5); border:1px solid #334155; border-radius:8px; padding:0.75rem; margin-bottom:0.5rem;">
                    <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:0.25rem;">
                        <a href="{repo['html_url']}" target="_blank" style="font-weight:700; color:#10b981; font-size:0.9rem; text-decoration:none;">{repo['name']}</a>
                        <div style="display:flex; align-items:center; gap:0.25rem; font-size:0.8rem;">
                            <span style="color:#eab308;">⭐</span>
                            <span style="color:#e2e8f0;">{repo['stargazers_count']}</span>
                        </div>
                    </div>
                    <div style="color:#94a3b8; font-size:0.8rem; margin-bottom:0.25rem;">{repo.get('description', '') or 'Нет описания'}</div>
                    <div style="display:flex; justify-content:space-between; font-size:0.75rem;">
                        <span style="color:#475569;">📝 {repo.get('language', 'N/A')}</span>
                        <span style="color:#475569;">👤 {repo['owner']['login']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div style="text-align:center; color:#64748b; padding:1rem;">GitHub API недоступен</div>', unsafe_allow_html=True)
    except Exception:
        st.markdown('<div style="text-align:center; color:#64748b; padding:1rem;">Не удалось загрузить данные GitHub</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── X.com Section (original style with quantum tweets) ──
    quantum_tweets = [
        "Quantum computing is revolutionizing risk management in finance! New algorithms show 40% better prediction accuracy. #Quant #RiskManagement",
        "Just released an open-source portfolio optimization tool using reinforcement learning. Check it out on GitHub! 🚀",
        "The future of trading is quantum. Traditional models can't keep up with the complexity of modern markets. #QuantTrading",
        "Excited to share our new research on AI-driven risk assessment for crypto portfolios. Paper coming soon! 📄",
        "Machine learning vs Quantum computing for portfolio optimization. Which one will win? Thread 🧵",
    ]

    st.markdown("""
    <div style="background:rgba(15,23,42,0.3); border:1px solid #334155; border-radius:12px; padding:1rem; margin-bottom:0.75rem;">
        <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.75rem;">
            <div style="width:32px; height:32px; background:rgba(6,182,212,0.2); border-radius:8px; display:flex; align-items:center; justify-content:center;">
                <svg style="width:16px; height:16px; fill:#06b6d4;" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231z"/></svg>
            </div>
            <h2 style="font-size:1.1rem; font-weight:700; color:white; margin:0;">𝕏 Актуальные твиты</h2>
        </div>
    """, unsafe_allow_html=True)

    for tweet in quantum_tweets:
        st.markdown(f"""
        <div style="background:rgba(15,23,42,0.5); border:1px solid #334155; border-radius:8px; padding:0.75rem; margin-bottom:0.5rem;">
            <div style="display:flex; gap:0.5rem;">
                <div style="width:32px; height:32px; background:rgba(6,182,212,0.2); border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                    <svg style="width:14px; height:14px; fill:#06b6d4;" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231z"/></svg>
                </div>
                <p style="color:#e2e8f0; font-size:0.85rem; flex:1; margin:0;">{tweet}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Footer (original style) ──
    import datetime
    st.markdown(f"""
    <div style="text-align:center; color:#475569; font-size:0.75rem; margin-top:1.5rem; padding-top:1rem; border-top:1px solid #1e293b;">
        <p>Quant Risk Hub © {datetime.datetime.now().year} | MIT Quantum + IBM Qiskit + ClickHouse Cloud</p>
        <p style="color:#374151; margin-top:0.25rem;">Обновлено: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M UTC')}</p>
    </div>
    """, unsafe_allow_html=True)
