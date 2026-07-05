"""Behavioral tests for the standalone `python_qc_metadata` QC helper script.

#49 replaced a bespoke ordered-unique accumulator with the standard
`dict.fromkeys` idiom. These tests pin the behavior that mattered — order
preservation with duplicate removal — through the real public functions, so
the idiom swap is proven equivalent rather than asserted.

The script is stdlib-only (no `ai_review_ci` package import), so it loads and
runs directly here.
"""

import importlib.util
import pathlib
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
_SCRIPT = ROOT / "tool-artifacts" / "scripts" / "python_qc_metadata.py"


def _load_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("python_qc_metadata", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MOD = _load_module()


def test_first_party_modules_dedupes_preserving_order(tmp_path: pathlib.Path) -> None:
    (tmp_path / "src" / "alpha").mkdir(parents=True)
    (tmp_path / "src" / "alpha" / "__init__.py").write_text("")
    (tmp_path / "src" / "beta.py").write_text("")
    # hatch wheel packages re-declares src/alpha, so 'alpha' is collected twice.
    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.hatch.build.targets.wheel]",
                'packages = ["src/alpha"]',
                "",
            ]
        )
    )

    result = _MOD.first_party_modules(tmp_path)

    assert result == ["alpha", "beta"], result  # duplicate 'alpha' removed, order kept


def test_dependency_group_requirements_dedupes_preserving_order(
    tmp_path: pathlib.Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[dependency-groups]",
                'base = ["pytest", "ruff"]',
                'dev = ["pytest", {include-group = "base"}]',
                "",
            ]
        )
    )

    result = _MOD.dependency_group_requirements(tmp_path)

    # base -> [pytest, ruff]; dev -> [pytest, (include base) pytest, ruff].
    # Across both groups the duplicates collapse, first-seen order preserved.
    assert result == ["pytest", "ruff"], result


def test_pep723_requirements_dedupes_preserving_order(tmp_path: pathlib.Path) -> None:
    one = tmp_path / "one.py"
    two = tmp_path / "two.py"
    one.write_text('# /// script\n# dependencies = ["rich", "httpx"]\n# ///\n')
    two.write_text('# /// script\n# dependencies = ["httpx", "typer"]\n# ///\n')

    result = _MOD.pep723_requirements([str(one), str(two)])

    assert result == ["rich", "httpx", "typer"], result  # shared 'httpx' deduped
