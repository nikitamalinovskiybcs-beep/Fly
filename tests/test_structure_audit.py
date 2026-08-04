from pathlib import Path

from src.structure_audit import audit_python_tree


def test_structure_audit_reports_syntax_and_broad_handlers(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text(
        "try:\n    pass\nexcept ValueError:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "broad.py").write_text(
        "try:\n    pass\nexcept:\n    pass\n",
        encoding="utf-8",
    )
    result = audit_python_tree(tmp_path)
    assert result["modules"] == 2
    assert result["broad_exception_handlers"] == 1
    assert result["passed"] is True
