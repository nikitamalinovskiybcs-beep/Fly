from pathlib import Path

import pytest

from src.phoenix_benchmark import run_universal_benchmark


def test_universal_benchmark_runs_research_gates():
    repository = Path(
        "/home/ubuntu/repos/phoenix-public-references/autocallable-pricer"
    )
    if not (repository / "worstof_pricer.py").exists():
        pytest.skip("public challenger checkout is not available")

    result = run_universal_benchmark(str(repository), (100, 200))
    gates = result["gates"]

    assert gates["path_fixture_completed"] is True
    assert gates["canonical_completed"] is True
    assert gates["public_challenger_completed"] is True
    assert gates["vanilla_parity_under_1e-4"] is True
    assert gates["production_promotion"] is False
