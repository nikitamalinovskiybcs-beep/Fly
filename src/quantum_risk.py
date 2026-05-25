"""IBM Quantum (Qiskit) enhanced risk analytics via local simulator."""

import numpy as np

try:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False


def quantum_var_estimation(returns: np.ndarray, confidence: float = 0.95,
                           n_qubits: int = 4, shots: int = 4096) -> dict:
    """Quantum-enhanced VaR using amplitude estimation inspired approach."""
    if not QISKIT_AVAILABLE:
        p = 1 - confidence
        var = float(np.quantile(returns, p))
        cvar = float(returns[returns <= var].mean()) if len(returns[returns <= var]) > 0 else var
        return {"var": var, "cvar": cvar, "method": "classical_fallback", "quantum": False}

    n = len(returns)
    sorted_rets = np.sort(returns)
    p = 1 - confidence
    classical_var = float(np.quantile(sorted_rets, p))

    qc = QuantumCircuit(n_qubits, n_qubits)
    n_bins = 2 ** n_qubits
    hist, bin_edges = np.histogram(returns, bins=n_bins, density=True)
    probs = hist / hist.sum()
    probs = np.sqrt(probs)
    norm = np.sqrt(np.sum(probs ** 2))
    if norm > 0:
        probs = probs / norm

    qc.initialize(probs, range(n_qubits))
    qc.measure(range(n_qubits), range(n_qubits))

    sim = AerSimulator()
    result = sim.run(qc, shots=shots).result()
    counts = result.get_counts()

    total = sum(counts.values())
    weighted_var = 0.0
    for bitstring, count in counts.items():
        idx = int(bitstring, 2) % n_bins
        bin_center = (bin_edges[idx] + bin_edges[min(idx + 1, n_bins)]) / 2
        weighted_var += bin_center * (count / total)

    tail_returns = sorted_rets[:max(1, int(n * p))]
    cvar = float(tail_returns.mean())

    quantum_adjustment = weighted_var * 0.05
    adjusted_var = classical_var + quantum_adjustment

    return {
        "var": float(adjusted_var),
        "cvar": cvar,
        "classical_var": float(classical_var),
        "quantum_adjustment": float(quantum_adjustment),
        "n_qubits": n_qubits,
        "shots": shots,
        "method": "qiskit_aer_simulator",
        "quantum": True,
    }


def quantum_monte_carlo_risk(mean_return: float, volatility: float,
                              n_paths: int = 1000, n_steps: int = 252,
                              n_qubits: int = 3, shots: int = 2048) -> dict:
    """Quantum-enhanced Monte Carlo simulation for portfolio risk."""
    if not QISKIT_AVAILABLE:
        paths = np.random.normal(mean_return / n_steps, volatility / np.sqrt(n_steps),
                                 (n_paths, n_steps))
        final_values = np.cumprod(1 + paths, axis=1)[:, -1]
        return {
            "mean_final": float(final_values.mean()),
            "std_final": float(final_values.std()),
            "var_95": float(np.quantile(final_values, 0.05)),
            "worst_case": float(final_values.min()),
            "best_case": float(final_values.max()),
            "method": "classical_fallback",
            "quantum": False,
        }

    qc = QuantumCircuit(n_qubits, n_qubits)
    for i in range(n_qubits):
        qc.h(i)
    for i in range(n_qubits - 1):
        qc.cx(i, i + 1)
    qc.measure(range(n_qubits), range(n_qubits))

    sim = AerSimulator()
    result = sim.run(qc, shots=shots).result()
    counts = result.get_counts()

    quantum_seeds = []
    for bitstring, count in counts.items():
        val = int(bitstring, 2) / (2 ** n_qubits)
        quantum_seeds.extend([val] * count)

    quantum_seeds = np.array(quantum_seeds[:n_paths])
    if len(quantum_seeds) < n_paths:
        extra = np.random.uniform(0, 1, n_paths - len(quantum_seeds))
        quantum_seeds = np.concatenate([quantum_seeds, extra])

    from scipy.stats import norm
    quantum_normals = norm.ppf(np.clip(quantum_seeds, 0.001, 0.999))

    dt = 1.0 / n_steps
    drift = (mean_return - 0.5 * volatility ** 2) * dt
    diffusion = volatility * np.sqrt(dt)

    final_values = np.zeros(n_paths)
    for i in range(n_paths):
        path_randoms = np.random.normal(0, 1, n_steps)
        path_randoms[0] = quantum_normals[i]
        log_returns = drift + diffusion * path_randoms
        final_values[i] = np.exp(np.sum(log_returns))

    return {
        "mean_final": float(final_values.mean()),
        "std_final": float(final_values.std()),
        "var_95": float(np.quantile(final_values, 0.05)),
        "var_99": float(np.quantile(final_values, 0.01)),
        "worst_case": float(final_values.min()),
        "best_case": float(final_values.max()),
        "prob_loss": float((final_values < 1.0).mean()),
        "method": "qiskit_quantum_mc",
        "quantum": True,
        "n_qubits": n_qubits,
        "shots": shots,
        "n_paths": n_paths,
    }


def get_quantum_status() -> dict:
    """Return quantum backend status info."""
    return {
        "qiskit_available": QISKIT_AVAILABLE,
        "backend": "AerSimulator (local)" if QISKIT_AVAILABLE else "classical_fallback",
        "provider": "IBM Qiskit",
    }
