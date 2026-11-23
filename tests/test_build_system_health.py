import json

from scripts.build_system_health import main


def test_system_health_script_writes_report(tmp_path, monkeypatch) -> None:
    benchmark = tmp_path / "benchmark.json"
    structure = tmp_path / "structure.json"
    output = tmp_path / "health.json"
    benchmark.write_text(json.dumps({"promotion_gate": {"eligible": False}}))
    structure.write_text(json.dumps({"passed": True}))
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_system_health",
            "--benchmark",
            str(benchmark),
            "--structure",
            str(structure),
            "--output",
            str(output),
        ],
    )
    main()
    assert json.loads(output.read_text())["status"] == "attention_required"
