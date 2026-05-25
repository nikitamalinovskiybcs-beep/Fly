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
    # ── MIT Quantum + ClickHouse Landing Dashboard ──

    # Quantum status badge
    q_status = get_quantum_status()
    q_badge_color = "#10b981" if q_status["qiskit_available"] else "#eab308"
    st.markdown(f"""
    <div style="text-align:center; margin-bottom:1.5rem;">
        <span style="background:rgba(16,185,129,0.15); border:1px solid {q_badge_color}; border-radius:20px; padding:0.3rem 1rem; color:{q_badge_color}; font-size:0.8rem;">
            ⚛️ {q_status['provider']} — {q_status['backend']}
        </span>
        <span style="background:rgba(6,182,212,0.15); border:1px solid #06b6d4; border-radius:20px; padding:0.3rem 1rem; color:#06b6d4; font-size:0.8rem; margin-left:0.5rem;">
            🗄️ ClickHouse Cloud — Live
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Load ClickHouse data
    with st.spinner("🗄️ Загрузка данных из ClickHouse Cloud..."):
        ch_data = fetch_quantum_risk_stats()

    src_label = "ClickHouse Cloud" if ch_data["source"] == "clickhouse_cloud" else "Cache (offline)"
    st.caption(f"Источник: {src_label} · Таблица: {ch_data['table']} · Симуляций: {ch_data['total_simulations']:,}")

    # ── Top-level worst-of stats ──
    st.markdown('<div class="section-header">🌐 Worst-of Portfolio (MIT Quantum Simulation)</div>', unsafe_allow_html=True)
    wc1, wc2, wc3, wc4 = st.columns(4)
    wo = ch_data["worst_of"]
    wc1.metric("Worst-of VaR 95%", f"{wo['var_95']:.1f}%")
    wc2.metric("Worst-of VaR 99%", f"{wo['var_99']:.1f}%")
    wc3.metric("Avg Worst-of", f"{wo['mean']:.1f}%")
    wc4.metric(f"Barrier {ch_data['barrier_level']}% Breach", f"{wo['barrier_breach_pct']:.1f}%")

    st.divider()

    # ── Per-ticker quantum metrics ──
    st.markdown('<div class="section-header">⚛️ Quantum Risk Analytics — Per Ticker</div>', unsafe_allow_html=True)
    tickers_data = ch_data["tickers"]

    for ticker in ["AAPL", "MSFT", "GOOGL", "AMZN"]:
        if ticker not in tickers_data:
            continue
        d = tickers_data[ticker]
        breach_color = "#ef4444" if d["barrier_breach_pct"] > 10 else "#eab308" if d["barrier_breach_pct"] > 1 else "#22c55e"
        with st.expander(f"**{ticker}** — Mean: {d['mean_return']:.1f}% · VaR 95%: {d['var_95']:.1f}% · Barrier Breach: {d['barrier_breach_pct']:.2f}%", expanded=True):
            tc1, tc2, tc3, tc4, tc5, tc6 = st.columns(6)
            tc1.metric("VaR 95%", f"{d['var_95']:.1f}%")
            tc2.metric("VaR 99%", f"{d['var_99']:.1f}%")
            tc3.metric("Mean Return", f"{d['mean_return']:.1f}%")
            tc4.metric("Volatility", f"{d['volatility']:.1f}%")
            tc5.metric("Min", f"{d['min_return']:.1f}%")
            tc6.metric("Max", f"{d['max_return']:.1f}%")

            st.markdown(f"""
            <div style="background:rgba(15,23,42,0.5); border:1px solid #334155; border-radius:8px; padding:0.75rem; margin:0.5rem 0;">
                <span style="color:#64748b;">Barrier {ch_data['barrier_level']}% breach:</span>
                <span style="color:{breach_color}; font-weight:700;"> {d['barrier_breach_pct']:.2f}%</span>
                <span style="color:#475569;"> ({d.get('barrier_breach_count', 'N/A')} / {d['num_simulations']:,} simulations)</span>
            </div>
            """, unsafe_allow_html=True)

            # Percentile distribution chart
            if "percentiles" in d:
                p = d["percentiles"]
                fig_box = go.Figure()
                fig_box.add_trace(go.Bar(
                    x=["P5", "P25", "P50 (Median)", "P75", "P95"],
                    y=[p["p5"], p["p25"], p["p50"], p["p75"], p["p95"]],
                    marker_color=["#ef4444", "#eab308", "#06b6d4", "#10b981", "#22c55e"],
                    text=[f"{v:.1f}%" for v in [p["p5"], p["p25"], p["p50"], p["p75"], p["p95"]]],
                    textposition="outside",
                ))
                fig_box.add_hline(y=ch_data["barrier_level"], line_dash="dash", line_color="#ef4444",
                                  annotation_text=f"Barrier {ch_data['barrier_level']}%")
                fig_box.update_layout(
                    title=f"{ticker} — Return Distribution (Quantum MC)",
                    yaxis_title="Final Return %",
                    height=300,
                    **PLOT_LAYOUT,
                )
                st.plotly_chart(fig_box, use_container_width=True)

    st.divider()

    # ── Qiskit Quantum VaR Estimation ──
    st.markdown('<div class="section-header">🔬 IBM Qiskit — Live Quantum VaR Estimation</div>', unsafe_allow_html=True)
    st.caption("Quantum amplitude estimation via AerSimulator (local)")

    qiskit_cols = st.columns(4)
    for i, ticker in enumerate(["AAPL", "MSFT", "GOOGL", "AMZN"]):
        if ticker not in tickers_data:
            continue
        d = tickers_data[ticker]
        sim_returns = np.random.normal(d["mean_return"], d["volatility"], 1000)
        q_result = quantum_var_estimation(sim_returns, confidence=0.95)
        with qiskit_cols[i]:
            st.markdown(f"**{ticker}**")
            st.metric("Q-VaR 95%", f"{q_result['var']:.2f}%")
            st.metric("Q-CVaR", f"{q_result['cvar']:.2f}%")
            if q_result.get("quantum"):
                st.caption(f"⚛️ {q_result['n_qubits']}q · {q_result['shots']} shots")
            else:
                st.caption("Classical fallback")

    st.divider()

    # ── Feature cards ──
    st.markdown("""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; max-width: 900px; margin: 0 auto;">
        <div class="metric-card">
            <div style="font-size: 2rem;">⚛️</div>
            <div style="color: #e2e8f0; font-weight: 600; margin-top: 0.5rem;">IBM Quantum</div>
            <div style="color: #64748b; font-size: 0.8rem;">Qiskit AerSimulator VaR</div>
        </div>
        <div class="metric-card">
            <div style="font-size: 2rem;">🗄️</div>
            <div style="color: #e2e8f0; font-weight: 600; margin-top: 0.5rem;">ClickHouse Cloud</div>
            <div style="color: #64748b; font-size: 0.8rem;">40K quantum simulations</div>
        </div>
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
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")
    st.caption("⬅️ Для полного анализа нажмите «Запустить анализ» в боковой панели.")
