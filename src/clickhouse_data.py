"""ClickHouse Cloud data connector for MIT Quantum returns."""

import os

try:
    import clickhouse_connect
    CH_AVAILABLE = True
except ImportError:
    CH_AVAILABLE = False

CH_HOST = os.environ.get("CH_HOST", "mz5xp6056a.us-east1.gcp.clickhouse.cloud")
CH_PORT = int(os.environ.get("CH_PORT", "8443"))
CH_USER = os.environ.get("CH_USER", "default")
CH_PASS = os.environ.get("CH_PASS", "nSnvOjKP~2s53")


def _get_client():
    if not CH_AVAILABLE:
        return None
    try:
        return clickhouse_connect.get_client(
            host=CH_HOST, port=CH_PORT,
            username=CH_USER, password=CH_PASS,
            secure=True,
        )
    except Exception:
        return None


def fetch_quantum_risk_stats() -> dict:
    """Fetch pre-calculated quantum risk statistics from ClickHouse."""
    client = _get_client()
    if client is None:
        return _fallback_data()

    try:
        var_q = """
        SELECT
            ticker,
            quantile(0.05)(final_return) AS var_95,
            quantile(0.01)(final_return) AS var_99,
            avg(final_return) AS mean_return,
            min(final_return) AS min_return,
            max(final_return) AS max_return,
            stddevPop(final_return) AS volatility,
            count() AS num_simulations
        FROM mit_quantum_returns
        GROUP BY ticker
        ORDER BY ticker
        """
        var_result = client.query(var_q)
        ticker_stats = {}
        for row in var_result.result_rows:
            ticker_stats[row[0]] = {
                "var_95": round(float(row[1]), 2),
                "var_99": round(float(row[2]), 2),
                "mean_return": round(float(row[3]), 2),
                "min_return": round(float(row[4]), 2),
                "max_return": round(float(row[5]), 2),
                "volatility": round(float(row[6]), 2),
                "num_simulations": int(row[7]),
            }

        barrier_q = """
        SELECT
            ticker,
            countIf(final_return < 65.0) AS breach_count,
            count() AS total,
            round(countIf(final_return < 65.0) / count() * 100, 2) AS breach_pct
        FROM mit_quantum_returns
        GROUP BY ticker
        ORDER BY ticker
        """
        barrier_result = client.query(barrier_q)
        for row in barrier_result.result_rows:
            t = row[0]
            if t in ticker_stats:
                ticker_stats[t]["barrier_breach_count"] = int(row[1])
                ticker_stats[t]["barrier_breach_pct"] = float(row[3])

        worst_q = """
        SELECT
            quantile(0.05)(min_return) AS worst_of_var_95,
            quantile(0.01)(min_return) AS worst_of_var_99,
            avg(min_return) AS avg_worst_of,
            countIf(min_return < 65.0) / count() * 100 AS barrier_breach_pct
        FROM (
            SELECT simulation_id, min(final_return) AS min_return
            FROM mit_quantum_returns
            GROUP BY simulation_id
        )
        """
        worst_result = client.query(worst_q)
        wr = worst_result.result_rows[0]
        worst_of = {
            "var_95": round(float(wr[0]), 2),
            "var_99": round(float(wr[1]), 2),
            "mean": round(float(wr[2]), 2),
            "barrier_breach_pct": round(float(wr[3]), 2),
        }

        dist_q = """
        SELECT
            ticker,
            quantile(0.05)(final_return) AS p5,
            quantile(0.25)(final_return) AS p25,
            quantile(0.50)(final_return) AS p50,
            quantile(0.75)(final_return) AS p75,
            quantile(0.95)(final_return) AS p95
        FROM mit_quantum_returns
        GROUP BY ticker
        ORDER BY ticker
        """
        dist_result = client.query(dist_q)
        for row in dist_result.result_rows:
            t = row[0]
            if t in ticker_stats:
                ticker_stats[t]["percentiles"] = {
                    "p5": round(float(row[1]), 2),
                    "p25": round(float(row[2]), 2),
                    "p50": round(float(row[3]), 2),
                    "p75": round(float(row[4]), 2),
                    "p95": round(float(row[5]), 2),
                }

        return {
            "source": "clickhouse_cloud",
            "table": "mit_quantum_returns",
            "tickers": ticker_stats,
            "worst_of": worst_of,
            "total_simulations": sum(s["num_simulations"] for s in ticker_stats.values()),
            "barrier_level": 65.0,
        }

    except Exception as e:
        data = _fallback_data()
        data["error"] = str(e)
        return data


def _fallback_data() -> dict:
    """Hardcoded fallback from last successful query."""
    return {
        "source": "fallback_cache",
        "table": "mit_quantum_returns",
        "tickers": {
            "AAPL": {"var_95": 86.27, "var_99": 80.06, "mean_return": 168.88,
                     "min_return": 77.83, "max_return": 316.40, "volatility": 64.28,
                     "num_simulations": 10000, "barrier_breach_count": 0,
                     "barrier_breach_pct": 0.0,
                     "percentiles": {"p5": 86.27, "p25": 111.99, "p50": 156.83, "p75": 218.43, "p95": 285.49}},
            "AMZN": {"var_95": 48.29, "var_99": 41.70, "mean_return": 100.40,
                     "min_return": 34.93, "max_return": 249.58, "volatility": 41.41,
                     "num_simulations": 10000, "barrier_breach_count": 2422,
                     "barrier_breach_pct": 24.22,
                     "percentiles": {"p5": 48.29, "p25": 66.18, "p50": 92.30, "p75": 129.96, "p95": 177.91}},
            "GOOGL": {"var_95": 100.07, "var_99": 80.34, "mean_return": 256.19,
                      "min_return": 60.04, "max_return": 790.69, "volatility": 129.74,
                      "num_simulations": 10000, "barrier_breach_count": 2,
                      "barrier_breach_pct": 0.02,
                      "percentiles": {"p5": 100.07, "p25": 153.54, "p50": 226.11, "p75": 333.37, "p95": 512.61}},
            "MSFT": {"var_95": 58.01, "var_99": 49.06, "mean_return": 148.93,
                     "min_return": 42.58, "max_return": 402.89, "volatility": 75.93,
                     "num_simulations": 10000, "barrier_breach_count": 975,
                     "barrier_breach_pct": 9.75,
                     "percentiles": {"p5": 58.01, "p25": 85.42, "p50": 129.74, "p75": 201.39, "p95": 296.62}},
        },
        "worst_of": {"var_95": 47.60, "var_99": 41.70, "mean": 87.44, "barrier_breach_pct": 30.04},
        "total_simulations": 40000,
        "barrier_level": 65.0,
    }
