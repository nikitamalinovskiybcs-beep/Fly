# 📊 Quant Risk Hub — Trading Strategy Risk Assessment Framework v2.3

[![Made with Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.45-red.svg)](https://streamlit.io/)
[![Deploy on Fly](https://img.shields.io/badge/Fly.io-Deploy-purple.svg)](https://fly.io)

Практичный фреймворк для оценки рисков торговых стратегий в стиле prop-трейдинговых фирм (Jane Street / Citadel).

## Принципы

- **Slavishly follow the models** — строгое следование правилам без эмоций
- Моделируем состояние рынка, а не предсказываем
- Максимальная защита от overfitting
- Математика и rigor > красивые графики
- Диверсификация, потому что неизвестно, какой рынок будет работать лучше

## Модули

| Модуль | Описание |
|--------|----------|
| **Data Module** | Загрузка данных через yfinance (OHLCV, last close) |
| **Core Metrics** | Sharpe, Sortino, Calmar, Max DD, Profit Factor, Win Rate |
| **Monte Carlo** | Permutation Test (≤ 2000 перестановок) |
| **Walk-Forward** | Анализ стабильности по фолдам |
| **Risk Metrics** | VaR / CVaR (95%, 99%), Drawdown Distribution |
| **Stress Tests** | GFC 2008, COVID 2020, Rate Hike 2022, SVB 2023 |
| **Overfitting** | Permutation test + OOS degradation |
| **Portfolio** | Корреляции, slippage impact, capacity estimation |

## Запуск

```bash
pip install -r requirements.txt
streamlit run app.py
```

Для предварительного расчёта готового snapshot (например, через cron):

```bash
python -m src.scheduler --snapshot --tickers AAPL,DELL,GOOG
```

В Streamlit после первого запуска snapshot также поддерживается фоновым
обновлением, пока процесс приложения активен.

## Self-hosted ClickHouse

Для локального режима без ClickHouse Cloud billing:

```bash
docker compose --env-file .env -f docker-compose.clickhouse.yml up -d
CLICKHOUSE_HOST=localhost CLICKHOUSE_USER=default \
CLICKHOUSE_SECURE=false python -m src.scheduler --snapshot --tickers AAPL,DELL,GOOG
```

Задайте `CLICKHOUSE_PASSWORD` в локальном `.env`; секреты не коммитятся.
Аналитические таблицы создаются автоматически при первом старте контейнера.
Self-hosted контейнер доступен только там, где запущен
Docker; для Streamlit Cloud нужен отдельно доступный сервер.

Загрузка наблюдаемой исторической OHLCV-истории в ClickHouse:

```bash
python scripts/ingest_ohlcv.py AAPL MSFT NVDA --period 3y
```

Скрипт использует рабочий Phoenix `DataManager`/yfinance provider,
пропускает уже загруженные даты и не загружает Monte Carlo или synthetic data.

## Деплой на Fly.io

```bash
fly deploy
```

## Структура

```
├── app.py                  # Streamlit dashboard
├── src/
│   ├── assessor.py         # StrategyRiskAssessor — главный класс
│   ├── data_module.py      # Загрузка данных (yfinance)
│   ├── core_metrics.py     # Метрики, Monte Carlo, Walk-Forward
│   ├── risk_metrics.py     # VaR, CVaR, Stress Tests
│   ├── overfitting.py      # Проверки на overfitting
│   └── portfolio.py        # Корреляции, slippage, capacity
├── Dockerfile
├── fly.toml
└── requirements.txt
```
