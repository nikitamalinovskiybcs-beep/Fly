CREATE TABLE IF NOT EXISTS ohlcv
(
    ticker String,
    date Date,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume UInt64,
    adj_close Float64
)
ENGINE = MergeTree
PARTITION BY toYear(date)
ORDER BY (ticker, date);

CREATE TABLE IF NOT EXISTS backtest_results
(
    id String,
    timestamp DateTime,
    strategy String,
    tickers String,
    start_date Date,
    end_date Date,
    sharpe Float64,
    total_return Float64,
    max_drawdown Float64,
    win_rate Float64,
    total_trades UInt32,
    parameters String
)
ENGINE = MergeTree
ORDER BY (strategy, timestamp);

CREATE TABLE IF NOT EXISTS indicator_cache
(
    ticker String,
    date Date,
    indicator String,
    period UInt32,
    value Float64
)
ENGINE = MergeTree
ORDER BY (ticker, date, indicator);
