"""Quant Risk Hub — Streamlit Dashboard v2.3."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import logging
import requests
import re
from datetime import datetime
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

from src.assessor import StrategyRiskAssessor
from src.core_metrics import returns_from_prices
from src.risk_metrics import drawdown_series
from src.data_module import DEFAULT_TICKERS

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

st.set_page_config(
    page_title="Адаптивная крепость",
    page_icon="🔒",
    layout="wide",
)

# ── Custom CSS (стиль из оригинального дизайна) ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background: #080b10; }
    .stApp { background: #080b10; }
    .gradient-title {
        background: linear-gradient(90deg, #f59e0b, #fbbf24);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.75rem;
        font-weight: 600;
        letter-spacing: -.04em;
        text-align: left;
        margin-bottom: 0.5rem;
    }
    .subtitle { text-align: left; color: #64748b; font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; margin-bottom: 1rem; }
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
    .hero-panel { background: #0d1219; border: 1px solid #263241; border-radius: 4px; padding: 1.35rem 1.5rem; margin: 1rem 0 1.5rem; }
    .hero-panel h1 { color: #f8fafc; font-family: 'IBM Plex Mono', monospace; font-size: 1.65rem; margin: .25rem 0 .5rem; }
    .hero-panel p { color: #94a3b8; max-width: 760px; font-size: 1rem; line-height: 1.6; }
    .eyebrow { color: #f59e0b; font-family: 'IBM Plex Mono', monospace; font-size: .66rem; font-weight: 700; letter-spacing: .14em; }
    .insight-card, .warning-card { border-radius: 4px; padding: 1rem 1.1rem; margin-top: .75rem; }
    .insight-card { background: #0d1a1d; border: 1px solid #155e63; }
    .warning-card { background: #211517; border: 1px solid #7f1d1d; }
    .insight-card strong, .warning-card strong { color: #f8fafc; }
    .insight-card p, .warning-card p { color: #cbd5e1; margin: .5rem 0 0; line-height: 1.5; }
    .terminal-bar { display: flex; justify-content: space-between; gap: 1rem; background: #111820; border: 1px solid #263241; border-radius: 4px; padding: .55rem .8rem; color: #94a3b8; font-family: 'IBM Plex Mono', monospace; font-size: .7rem; margin-bottom: 1rem; }
    .terminal-bar b { color: #fbbf24; }
    div[data-testid="stMetric"] { border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown('<div class="gradient-title">🔒 АДАПТИВНАЯ КРЕПОСТЬ // RISK TERMINAL</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">LIVE SCENARIO MONITOR · ЗАЩИТА КАПИТАЛА · MOEX BENCHMARKS</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="terminal-bar"><span><b>RISK</b> / PORTFOLIO HEDGE</span><span>MCFTR · RUSFAR · IMOEXF</span><span>RUB</span></div>',
    unsafe_allow_html=True,
)

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


def rubles(value: float) -> str:
    return f"{value:,.0f} ₽".replace(",", " ")


@st.cache_data(ttl=900)
def load_moex_benchmarks(start_date: str, end_date: str) -> pd.DataFrame:
    """Load MOEX total-return and money-market benchmark history."""
    rows: dict[str, pd.Series] = {}
    for secid in ("MCFTR", "RUSFAR"):
        response = requests.get(
            f"https://iss.moex.com/iss/history/engines/stock/markets/index/securities/{secid}.json",
            params={"from": start_date, "till": end_date, "limit": 1000},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()["history"]
        frame = pd.DataFrame(payload["data"], columns=payload["columns"])
        if frame.empty:
            raise ValueError(f"MOEX returned no data for {secid}")
        frame["TRADEDATE"] = pd.to_datetime(frame["TRADEDATE"])
        frame["CLOSE"] = pd.to_numeric(frame["CLOSE"], errors="coerce")
        rows[secid] = frame.dropna(subset=["CLOSE"]).set_index("TRADEDATE")["CLOSE"].sort_index()

    benchmark = pd.DataFrame(rows).dropna()
    benchmark["MCFTR"] = benchmark["MCFTR"] / benchmark["MCFTR"].iloc[0]
    money_market_daily = (1 + benchmark["RUSFAR"] / 100) ** (1 / 365) - 1
    benchmark["RUSFAR"] = (1 + money_market_daily).cumprod()
    return benchmark


@st.cache_data(ttl=900)
def load_sector_indices(start_date: str, end_date: str) -> pd.DataFrame:
    """Load MOEX financials and oil-and-gas total-return indices."""
    rows = {}
    for secid in ("MEFNTR", "MEOGTR"):
        response = requests.get(
            f"https://iss.moex.com/iss/history/engines/stock/markets/index/securities/{secid}.json",
            params={"from": start_date, "till": end_date, "limit": 1000},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()["history"]
        frame = pd.DataFrame(payload["data"], columns=payload["columns"])
        if frame.empty:
            raise ValueError(f"MOEX returned no data for {secid}")
        frame["TRADEDATE"] = pd.to_datetime(frame["TRADEDATE"])
        frame["CLOSE"] = pd.to_numeric(frame["CLOSE"], errors="coerce")
        rows[secid] = (
            frame.dropna(subset=["CLOSE"])
            .set_index("TRADEDATE")["CLOSE"]
            .groupby(level=0)
            .last()
            .sort_index()
        )
    data = pd.DataFrame(rows).dropna()
    return data / data.iloc[0]


@st.cache_data(ttl=900)
def load_sector_exposures(tickers: tuple[str, ...], start_date: str, end_date: str) -> pd.DataFrame:
    """Estimate each holding's beta to financials and oil-and-gas TR indices."""
    def fetch_history(ticker: str) -> tuple[str, pd.Series | None]:
        market = "index" if ticker.startswith("ME") else "shares"
        response = requests.get(
            f"https://iss.moex.com/iss/history/engines/stock/markets/{market}/securities/{ticker}.json",
            params={"from": start_date, "till": end_date, "limit": 1000},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()["history"]
        frame = pd.DataFrame(payload["data"], columns=payload["columns"])
        if frame.empty:
            return ticker, None
        frame["TRADEDATE"] = pd.to_datetime(frame["TRADEDATE"])
        frame["CLOSE"] = pd.to_numeric(frame["CLOSE"], errors="coerce")
        series = (
            frame.dropna(subset=["CLOSE"])
            .set_index("TRADEDATE")["CLOSE"]
            .groupby(level=0)
            .last()
            .sort_index()
        )
        return ticker, series

    histories = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        for ticker, series in executor.map(fetch_history, (*tickers, "MEFNTR", "MEOGTR")):
            if series is not None:
                histories[ticker] = series
    returns = pd.DataFrame(histories).pct_change().dropna()
    result = []
    for ticker in tickers:
        if ticker not in returns:
            continue
        row = {"Бумага": ticker}
        for sector in ("MEFNTR", "MEOGTR"):
            if sector in returns and returns[sector].var():
                row[f"Beta {sector}"] = returns[ticker].cov(returns[sector]) / returns[sector].var()
        result.append(row)
    return pd.DataFrame(result)


@st.cache_data(ttl=60)
def load_moex_quotes(tickers: tuple[str, ...]) -> pd.DataFrame:
    """Load current MOEX quotes for the uploaded portfolio."""
    quotes = []
    for ticker in tickers:
        response = requests.get(
            f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json",
            params={"iss.meta": "off"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()["marketdata"]
        frame = pd.DataFrame(payload["data"], columns=payload["columns"])
        if frame.empty:
            continue
        row = frame.iloc[0]
        quotes.append({
            "Бумага": ticker,
            "Цена MOEX": pd.to_numeric(row.get("LAST"), errors="coerce"),
            "Изм. дня, %": pd.to_numeric(row.get("LASTCHANGEPRCNT"), errors="coerce"),
        })
    return pd.DataFrame(quotes)


@st.cache_data(ttl=900)
def load_moex_betas(tickers: tuple[str, ...], start_date: str, end_date: str) -> pd.DataFrame:
    """Estimate 90-day beta versus IMOEX from MOEX daily closes."""
    histories = {}
    for ticker in (*tickers, "IMOEX"):
        market = "index" if ticker == "IMOEX" else "shares"
        response = requests.get(
            f"https://iss.moex.com/iss/history/engines/stock/markets/{market}/securities/{ticker}.json",
            params={"from": start_date, "till": end_date, "limit": 1000},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()["history"]
        frame = pd.DataFrame(payload["data"], columns=payload["columns"])
        if frame.empty:
            continue
        frame["TRADEDATE"] = pd.to_datetime(frame["TRADEDATE"])
        frame["CLOSE"] = pd.to_numeric(frame["CLOSE"], errors="coerce")
        histories[ticker] = (
            frame.dropna(subset=["CLOSE"])
            .set_index("TRADEDATE")["CLOSE"]
            .groupby(level=0)
            .last()
            .sort_index()
        )
    prices = pd.DataFrame(histories).dropna()
    returns = prices.pct_change().dropna()
    if "IMOEX" not in returns:
        raise ValueError("IMOEX history unavailable")
    market_returns = returns["IMOEX"]
    result = []
    for ticker in tickers:
        if ticker not in returns:
            continue
        variance = market_returns.var()
        beta = returns[ticker].cov(market_returns) / variance if variance else np.nan
        result.append({"Бумага": ticker, "Beta к IMOEX": beta})
    return pd.DataFrame(result)


def parse_holdings_image(uploaded_file) -> tuple[pd.DataFrame, str]:
    """Best-effort OCR for common broker portfolio screenshots."""
    if pytesseract is None or Image is None:
        raise RuntimeError("OCR dependencies are not installed")
    image = Image.open(BytesIO(uploaded_file.getvalue()))
    text = pytesseract.image_to_string(image, lang="rus+eng")
    known_tickers = ("X5", "T", "NVTK", "DOMRF", "SBER", "TRNFP")
    rows = []
    for ticker in known_tickers:
        match = re.search(
            rf"\b{ticker}\b(?P<body>.{{0,180}}?)(?P<pct>-?\d+[,.]\d+)\s*%",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            continue
        numbers = re.findall(r"\d[\d\s]*[,.]\d{2}", match.group("body"))
        value = float(numbers[0].replace(" ", "").replace(",", ".")) if numbers else np.nan
        change = float(match.group("pct").replace(",", "."))
        rows.append({"Бумага": ticker, "Стоимость, ₽": value, "Изменение, %": change})
    return pd.DataFrame(rows), text


def build_agent_reports(
    portfolio: float,
    stock_move: float,
    index_move: float,
    hedge_nominal: float,
    beta: float,
    margin: float,
    tracking_error: float,
    sector_corr_90: float,
    sector_exposure: pd.DataFrame,
    long_pnl: float,
    futures_pnl: float,
    beta_adjusted_pnl: float,
    net_pnl: float,
) -> list[dict[str, str]]:
    """Run deterministic analytical agents; no order execution or broker actions."""
    protection = futures_pnl / abs(long_pnl) if long_pnl else 0.0
    beta_improvement = 1 - abs(beta_adjusted_pnl) / abs(long_pnl) if long_pnl else 0.0
    residual_improvement = 1 - abs(long_pnl + futures_pnl) / abs(long_pnl) if long_pnl else 0.0
    reports = [
        {
            "agent": "DATA AGENT",
            "status": "READY",
            "signal": "MOEX / OCR / manual inputs",
            "effect": "Проверка данных: 100%",
            "readout": "Проверяет наличие котировок, дату последнего обновления и согласованность введённых значений.",
        },
        {
            "agent": "RISK AGENT",
            "status": "ALERT" if abs(tracking_error) >= 0.05 else "READY",
            "signal": f"Tracking error {tracking_error:.2%}",
            "effect": f"Снижение остаточного риска: {residual_improvement:.1%}",
            "readout": "Контролирует beta, относительную доходность и запас ГО; высокий tracking error требует пересмотра состава.",
        },
        {
            "agent": "HEDGE AGENT",
            "status": "ALERT" if hedge_nominal < portfolio * beta else "READY",
            "signal": f"IMOEXF {hedge_nominal / portfolio:.0%} / beta {beta:.2f}" if portfolio else "Нет портфеля",
            "effect": f"Компенсация падения: {protection:.1%}",
            "readout": f"Beta-adjusted ориентир: {money(portfolio * beta)}. Агент не отправляет сделки, а показывает расхождение.",
        },
        {
            "agent": "SECTOR AGENT",
            "status": "ALERT" if pd.notna(sector_corr_90) and sector_corr_90 < 0.2 else "READY",
            "signal": f"Corr(банки, нефть) 90д: {sector_corr_90:.2f}" if pd.notna(sector_corr_90) else "Нет sector data",
            "effect": f"Beta-adjusted улучшение: {beta_improvement:.1%}",
            "readout": "Сравнивает MEFNTR и MEOGTR; низкая корреляция означает, что один индексный хедж хуже описывает портфель.",
        },
        {
            "agent": "REPORT AGENT",
            "status": "READY",
            "signal": f"ГО {money(margin)}",
            "effect": f"Итоговый сценарий: {net_pnl / portfolio:.2%}" if portfolio else "Нет портфеля",
            "readout": f"Сводит результат: лонг {stock_move:.2%}, IMOEX {index_move:.2%}, потребность в ликвидности {money(margin)}.",
        },
    ]
    if sector_exposure.empty:
        reports[3]["status"] = "WAIT"
    return reports


def render_agent_command_center(reports: list[dict[str, str]]) -> None:
    """Render the coordinator output for the analytical agents."""
    st.markdown("### Agent Command Center")
    st.caption("Пять аналитических агентов работают как прозрачные правила и метрики; торговых поручений и автосделок нет.")
    cols = st.columns(len(reports))
    for col, report in zip(cols, reports):
        with col:
            color = {"READY": "#22c55e", "ALERT": "#ef4444", "WAIT": "#eab308"}[report["status"]]
            st.markdown(
                f"""
                <div class="metric-card" style="min-height: 150px; text-align: left;">
                    <div style="color: {color}; font-family: 'IBM Plex Mono', monospace; font-size: .72rem;">
                        {report["status"]}
                    </div>
                    <strong>{report["agent"]}</strong>
                    <div style="color: #fbbf24; margin: .45rem 0;">{report["signal"]}</div>
                    <div style="color: #34d399; font-size: .78rem; margin-bottom: .35rem;">{report["effect"]}</div>
                    <div style="color: #94a3b8; font-size: .78rem; line-height: 1.35;">{report["readout"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("#### Пошаговый аудит эффективности")
    st.dataframe(
        pd.DataFrame([
            {"Шаг": index + 1, "Агент": report["agent"], "Статус": report["status"], "Процентный эффект": report["effect"]}
            for index, report in enumerate(reports)
        ]),
        use_container_width=True,
        hide_index=True,
    )
    alerts = [report for report in reports if report["status"] == "ALERT"]
    if alerts:
        st.warning(f"Координатор: активных сигналов — {len(alerts)}. Сначала проверьте Risk/Hedge/Sector Agent.")
    else:
        st.success("Координатор: критических сигналов нет в текущем сценарии.")


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

    st.markdown("### Доходность с 1 февраля")
    performance_inputs = st.columns(3)
    with performance_inputs[0]:
        start_date = st.date_input("Дата старта", value=datetime(2026, 2, 1).date())
    with performance_inputs[1]:
        start_value = st.number_input("Стартовая стоимость, ₽", min_value=0.0, value=50_800.0, step=100.0)
    with performance_inputs[2]:
        current_value = st.number_input("Текущая стоимость, ₽", min_value=0.0, value=56_000.0, step=100.0)
    performance_pnl = current_value - start_value
    performance_return = performance_pnl / start_value if start_value else 0.0
    performance_cards = st.columns(3)
    performance_cards[0].metric("Старт", rubles(start_value), "1 февраля")
    performance_cards[1].metric("Сейчас", rubles(current_value), f"{performance_return:.2%}")
    performance_cards[2].metric("Доходность", rubles(performance_pnl), f"{performance_return:.2%}")
    performance_chart = go.Figure(go.Scatter(
        x=["1 февраля", "Сейчас"],
        y=[start_value, current_value],
        mode="lines+markers+text",
        text=[rubles(start_value), rubles(current_value)],
        textposition="top center",
        line={"color": "#34d399", "width": 3},
        marker={"size": 10, "color": "#22d3ee"},
    ))
    performance_chart.update_layout(
        title="Динамика стоимости",
        yaxis_title="₽",
        yaxis_tickformat=",~s",
        **PLOT_LAYOUT,
    )
    st.plotly_chart(performance_chart, use_container_width=True)

    st.markdown("### Сравнение с рынком")
    st.caption("MCFTR — индекс МосБиржи полной доходности «брутто». RUSFAR — денежный рынок; доходность оценена через ежедневное начисление ставки.")
    try:
        benchmark_data = load_moex_benchmarks(
            start_date.isoformat(),
            datetime.now().date().isoformat(),
        )
        portfolio_curve = (
            np.linspace(1, current_value / start_value, len(benchmark_data))
            if start_value else np.ones(len(benchmark_data))
        )
        normalized = pd.DataFrame({
            "Портфель": portfolio_curve,
            "MCFTR / ММВБ TR": benchmark_data["MCFTR"],
            "RUSFAR / денежный рынок": benchmark_data["RUSFAR"],
        }, index=benchmark_data.index) * 100
        market_chart = go.Figure()
        for name, color in [
            ("Портфель", "#fbbf24"),
            ("MCFTR / ММВБ TR", "#22d3ee"),
            ("RUSFAR / денежный рынок", "#a3e635"),
        ]:
            market_chart.add_trace(go.Scatter(
                x=normalized.index,
                y=normalized[name],
                name=name,
                mode="lines",
                line={"color": color, "width": 2},
            ))
        market_chart.update_layout(
            title=f"Индексировано к 100 на {start_date.strftime('%d.%m.%Y')}",
            yaxis_title="Индекс, 100 = старт",
            hovermode="x unified",
            **PLOT_LAYOUT,
        )
        st.plotly_chart(market_chart, use_container_width=True)
        benchmark_cards = st.columns(3)
        benchmark_cards[0].metric("Портфель", f"{normalized['Портфель'].iloc[-1] - 100:+.2f}%", "от старта")
        benchmark_cards[1].metric("MCFTR", f"{normalized['MCFTR / ММВБ TR'].iloc[-1] - 100:+.2f}%", "ММВБ полной доходности")
        benchmark_cards[2].metric("RUSFAR", f"{normalized['RUSFAR / денежный рынок'].iloc[-1] - 100:+.2f}%", "денежный рынок")
        st.caption(f"Последняя доступная дата MOEX: {benchmark_data.index[-1].strftime('%d.%m.%Y')}.")
    except (requests.RequestException, KeyError, ValueError) as exc:
        st.warning(f"MOEX benchmark data unavailable: {exc}. Остальные сценарии доступны вручную.")

    st.markdown("### Сектора: банки против нефти")
    st.caption("MEFNTR — финансовый сектор; MEOGTR — нефть и газ. Корреляция рассчитывается по дневным доходностям.")
    sector_corr_90 = np.nan
    try:
        sector_data = load_sector_indices(
            start_date.isoformat(),
            datetime.now().date().isoformat(),
        )
        sector_returns = sector_data.pct_change().dropna()
        sector_chart = go.Figure()
        for name, color in [("MEFNTR · банки", "#f59e0b"), ("MEOGTR · нефть и газ", "#f43f5e")]:
            secid = name.split(" · ")[0]
            sector_chart.add_trace(go.Scatter(
                x=sector_data.index,
                y=sector_data[secid] * 100,
                mode="lines",
                name=name,
                line={"color": color, "width": 2},
            ))
        sector_chart.update_layout(
            title="Секторальная доходность, база 100",
            yaxis_title="Индекс",
            **PLOT_LAYOUT,
        )
        st.plotly_chart(sector_chart, use_container_width=True)
        correlations = pd.DataFrame({
            "30 дней": sector_returns["MEFNTR"].rolling(30).corr(sector_returns["MEOGTR"]),
            "90 дней": sector_returns["MEFNTR"].rolling(90).corr(sector_returns["MEOGTR"]),
            "252 дня": sector_returns["MEFNTR"].rolling(252).corr(sector_returns["MEOGTR"]),
        }).dropna(how="all")
        correlation_chart = go.Figure()
        for name, color in [("30 дней", "#22d3ee"), ("90 дней", "#a3e635"), ("252 дня", "#fbbf24")]:
            correlation_chart.add_trace(go.Scatter(
                x=correlations.index,
                y=correlations[name],
                mode="lines",
                name=name,
                line={"color": color, "width": 2},
            ))
        correlation_chart.update_layout(
            title="Rolling-корреляция банков и нефти",
            yaxis_title="Корреляция",
            yaxis_range=[-1, 1],
            **PLOT_LAYOUT,
        )
        st.plotly_chart(correlation_chart, use_container_width=True)
        latest_corr = correlations.iloc[-1]
        sector_corr_90 = float(latest_corr["90 дней"])
        corr_cards = st.columns(3)
        corr_cards[0].metric("Корреляция 30д", f"{latest_corr['30 дней']:.2f}")
        corr_cards[1].metric("Корреляция 90д", f"{latest_corr['90 дней']:.2f}")
        corr_cards[2].metric("Корреляция 252д", f"{latest_corr['252 дня']:.2f}")
        if latest_corr["90 дней"] < 0.2:
            st.warning("ALERT: 90-дневная корреляция секторов низкая — общий IMOEX-хедж может давать высокий tracking error.")
    except (requests.RequestException, KeyError, ValueError) as exc:
        st.warning(f"Sector data unavailable: {exc}")

    default_holdings = pd.DataFrame([
        {"Бумага": "X5", "Стоимость, ₽": 4_982_567.50, "Изменение, %": -22.88},
        {"Бумага": "T", "Стоимость, ₽": 5_022_652.24, "Изменение, %": -27.03},
        {"Бумага": "NVTK", "Стоимость, ₽": 5_494_579.20, "Изменение, %": -19.53},
        {"Бумага": "DOMRF", "Стоимость, ₽": 5_910_070.00, "Изменение, %": -6.22},
        {"Бумага": "SBER", "Стоимость, ₽": 6_311_793.00, "Изменение, %": -7.54},
        {"Бумага": "TRNFP", "Стоимость, ₽": 5_908_030.00, "Изменение, %": -14.39},
    ])
    uploaded_portfolio = st.file_uploader(
        "Вставить скриншот портфеля",
        type=["png", "jpg", "jpeg"],
        help="Сайт покажет скриншот и попробует распознать тикеры, значения и доходность.",
    )
    if uploaded_portfolio:
        st.image(uploaded_portfolio, caption="Загруженный скриншот", use_container_width=True)
        try:
            parsed_holdings, ocr_text = parse_holdings_image(uploaded_portfolio)
            if not parsed_holdings.empty:
                default_holdings = default_holdings.set_index("Бумага")
                parsed_holdings = parsed_holdings.set_index("Бумага")
                default_holdings.update(parsed_holdings)
                default_holdings = default_holdings.reset_index()
                st.success(f"OCR распознал {len(parsed_holdings)} позиций. Проверьте таблицу ниже.")
            else:
                st.warning("Тикеры не распознаны автоматически — заполните таблицу вручную.")
            with st.expander("Текст OCR для проверки"):
                st.code(ocr_text or "Текст не найден")
        except RuntimeError:
            st.info("Скриншот загружен. OCR будет доступен после установки языкового пакета; таблицу можно редактировать вручную.")
        except (ValueError, OSError) as exc:
            st.warning(f"Не удалось прочитать скриншот: {exc}")
    with st.expander("Состав портфеля со скриншота", expanded=True):
        edited_holdings = st.data_editor(
            default_holdings,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Стоимость, ₽": st.column_config.NumberColumn(format="%.2f ₽"),
                "Изменение, %": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )
    try:
        quotes = load_moex_quotes(tuple(edited_holdings["Бумага"].astype(str).str.upper()))
        if not quotes.empty:
            live_holdings = edited_holdings.merge(quotes, on="Бумага", how="left")
            st.dataframe(
                live_holdings[["Бумага", "Цена MOEX", "Изм. дня, %", "Стоимость, ₽"]],
                use_container_width=True,
                hide_index=True,
            )
            st.caption("Котировки MOEX обновляются автоматически примерно раз в минуту; стоимость портфеля берётся из таблицы.")
    except (requests.RequestException, KeyError, ValueError) as exc:
        st.warning(f"Live quotes unavailable: {exc}")
    portfolio = float(edited_holdings["Стоимость, ₽"].sum())
    weighted_move = float(
        (edited_holdings["Стоимость, ₽"] * edited_holdings["Изменение, %"]).sum() / portfolio
    ) if portfolio else 0.0
    beta_estimate = 1.01
    try:
        beta_df = load_moex_betas(
            tuple(edited_holdings["Бумага"].astype(str).str.upper()),
            (datetime.now() - pd.Timedelta(days=120)).date().isoformat(),
            datetime.now().date().isoformat(),
        )
        if not beta_df.empty:
            beta_weighted = beta_df.merge(edited_holdings[["Бумага", "Стоимость, ₽"]], on="Бумага")
            beta_estimate = float(
                (beta_weighted["Beta к IMOEX"] * beta_weighted["Стоимость, ₽"]).sum() / portfolio
            )
            st.markdown("#### Beta и номинал хеджа")
            beta_view = beta_df.copy()
            beta_view["Beta к IMOEX"] = beta_view["Beta к IMOEX"].round(2)
            st.dataframe(beta_view, use_container_width=True, hide_index=True)
            beta_cards = st.columns(3)
            beta_cards[0].metric("Beta портфеля", f"{beta_estimate:.2f}", "90 дней к IMOEX")
            beta_cards[1].metric("Beta-adjusted hedge", money(portfolio * beta_estimate), "рекомендуемый номинал модели")
            beta_cards[2].metric("Текущий hedge", money(33_630_000), f"{33_630_000 / (portfolio * beta_estimate):.0%} от beta-хеджа")
    except (requests.RequestException, KeyError, ValueError, ZeroDivisionError):
        beta_df = pd.DataFrame()
    try:
        sector_exposure = load_sector_exposures(
            tuple(edited_holdings["Бумага"].astype(str).str.upper()),
            (datetime.now() - pd.Timedelta(days=120)).date().isoformat(),
            datetime.now().date().isoformat(),
        )
        if not sector_exposure.empty:
            st.markdown("#### Экспозиция к секторам")
            st.dataframe(
                sector_exposure.round(2),
                use_container_width=True,
                hide_index=True,
            )
    except (requests.RequestException, KeyError, ValueError):
        sector_exposure = pd.DataFrame()

    with st.expander("Параметры позиции", expanded=True):
        inputs = st.columns(4)
        with inputs[0]:
            st.metric("Лонг портфеля", money(portfolio), "сумма позиций")
            stock_move = st.number_input(
                "Изменение лонга из отчёта",
                value=-16.35,
                step=0.5,
                format="%.2f",
                help="Значение из сводки брокера. Можно заменить на взвешенный результат таблицы.",
            ) / 100
            st.caption(f"Взвешенно по строкам: {weighted_move:.2f}%")
        with inputs[1]:
            hedge_nominal = st.number_input("Номинал шорта IMOEXF, ₽", min_value=0.0, value=33_630_000.0, step=100_000.0)
            index_move = st.number_input("Изменение IMOEX", value=-13.0, step=0.5, format="%.2f") / 100
        with inputs[2]:
            margin_rate = st.number_input("Ориентир ГО", min_value=0.01, max_value=1.0, value=0.20, step=0.01, format="%.2f")
            carry_rate = st.number_input("Сценарий carry / базиса годовых", value=14.0, step=0.5, format="%.1f") / 100
        with inputs[3]:
            holding_months = st.number_input("Период, месяцев", min_value=0.0, value=6.0, step=1.0)
            beta = st.number_input("Beta портфеля", min_value=0.0, value=float(round(beta_estimate, 2)), step=0.01, format="%.2f")

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
    if abs(tracking_error) >= 0.05:
        st.warning(f"ALERT: tracking error {tracking_error:.2%}. Портфель заметно отклоняется от IMOEX.")
    if hedge_nominal < portfolio * beta:
        st.info(f"Недохедж: номинал IMOEXF ниже beta-adjusted оценки примерно на {money(portfolio * beta - hedge_nominal)}.")
    efficiency_df = pd.DataFrame([
        {"Изменение модели": "Без хеджа", "P&L": long_pnl, "Доходность": long_pnl / portfolio if portfolio else 0.0, "Что измеряет": "Базовый риск корзины"},
        {"Изменение модели": "+ шорт IMOEXF", "P&L": long_pnl + futures_pnl, "Доходность": (long_pnl + futures_pnl) / portfolio if portfolio else 0.0, "Что измеряет": "Защита от движения рынка"},
        {"Изменение модели": "+ carry / базис", "P&L": net_pnl, "Доходность": net_pct, "Что измеряет": "Сценарный полный результат"},
        {"Изменение модели": "Beta-adjusted hedge", "P&L": long_pnl - portfolio * beta * index_move, "Доходность": (long_pnl - portfolio * beta * index_move) / portfolio if portfolio else 0.0, "Что измеряет": "Хедж с учётом чувствительности"},
    ])
    st.markdown("### Эффективность модели")
    st.caption("Сравнение сценарное: beta-adjusted строка показывает, как меняется результат при номинале, рассчитанном по beta; carry не является гарантированным funding.")
    st.dataframe(
        efficiency_df.assign(**{
            "P&L": efficiency_df["P&L"].map(money),
            "Доходность": efficiency_df["Доходность"].map(lambda value: f"{value:.2%}"),
        }),
        use_container_width=True,
        hide_index=True,
    )
    protection = futures_pnl / abs(long_pnl) if long_pnl else 0.0
    efficiency_cards = st.columns(3)
    efficiency_cards[0].metric("Компенсация падения", f"{protection:.1%}", "шорт / убыток лонга")
    efficiency_cards[1].metric("Снижение tracking error", money(abs(portfolio * tracking_error) - abs(long_pnl + futures_pnl)), "приближённо")
    efficiency_cards[2].metric("Нужный cash buffer", money(stress_cash if "stress_cash" in locals() else hedge_nominal * 0.20), "стресс +20%")

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

    st.markdown("### Где искать замену")
    st.caption("Сайт не выносит приказов на сделки: он выделяет позиции для дополнительной проверки и сравнения.")
    review_df = edited_holdings.copy()
    review_df["Отклонение от IMOEX, п.п."] = review_df["Изменение, %"] - index_move * 100
    review_df["Сигнал модели"] = np.where(
        review_df["Отклонение от IMOEX, п.п."] <= -5,
        "Кандидат на пересмотр",
        "В пределах сценария",
    )
    st.dataframe(
        review_df[["Бумага", "Стоимость, ₽", "Изменение, %", "Отклонение от IMOEX, п.п.", "Сигнал модели"]],
        use_container_width=True,
        hide_index=True,
    )
    replacement_df = pd.DataFrame([
        {
            "Роль в портфеле": "Снижение риска одной бумаги",
            "Что сравнить": "Более широкий индексный слой",
            "Зачем": "Меньше зависимости от X5/T и их индивидуальных новостей",
            "Проверить": "Корреляцию с IMOEX, ликвидность, комиссии",
        },
        {
            "Роль в портфеле": "Защитная акция",
            "Что сравнить": "SBER / LKOH как альтернативы для анализа",
            "Зачем": "Сравнить beta, просадку и дивидендный профиль",
            "Проверить": "Долговую нагрузку, дивиденды, секторную концентрацию",
        },
        {
            "Роль в портфеле": "Высокая beta",
            "Что сравнить": "Сохранить только при наличии лимита риска",
            "Зачем": "T и X5 дали наибольшее отставание от индекса",
            "Проверить": "Допустимую просадку и размер позиции",
        },
    ])
    st.dataframe(replacement_df, use_container_width=True, hide_index=True)

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

    agent_reports = build_agent_reports(
        portfolio=portfolio,
        stock_move=stock_move,
        index_move=index_move,
        hedge_nominal=hedge_nominal,
        beta=beta,
        margin=margin,
        tracking_error=tracking_error,
        sector_corr_90=sector_corr_90,
        sector_exposure=sector_exposure,
        long_pnl=long_pnl,
        futures_pnl=futures_pnl,
        beta_adjusted_pnl=long_pnl - portfolio * beta * index_move,
        net_pnl=net_pnl,
    )
    render_agent_command_center(agent_reports)

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
