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


def test_first_party_modules_accepts_explicit_setuptools_packages_list(tmp_path: pathlib.Path) -> None:
    # setuptools accepts packages as an explicit list of dotted package names
    # (not only the {find = {where = [...]}} table). The top-level segments are
    # the first-party modules; sub-packages collapse into their root.
    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.setuptools]",
                'package-dir = { "spam" = "." }',
                'packages = ["spam", "spam.algebra", "spam.forms"]',
                "",
            ]
        )
    )

    result = _MOD.first_party_modules(tmp_path)

    assert result == ["spam"], result


def test_dependency_group_requirements_dedupes_preserving_order(tmp_path: pathlib.Path) -> None:
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


def test_import_linter_config_skips_single_module_projects(tmp_path: pathlib.Path) -> None:
    # #249: import-linter hard-rejects single-file modules in root_packages
    # ("'score' is a module, not a package"), so a src-layout project with only
    # src/<module>.py could never pass the gate. With no first-party PACKAGES,
    # import layering is vacuous and the generator must signal a sanctioned
    # skip (None) instead of emitting a config import-linter always rejects.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "score.py").write_text("")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')

    assert _MOD.import_linter_config(tmp_path) is None


def test_import_linter_config_lints_packages_only(tmp_path: pathlib.Path) -> None:
    # Mixed shape (#249): the package is lintable; the single-file module is
    # not a valid root_packages entry and must be excluded from the config and
    # the independence contract.
    (tmp_path / "src" / "alpha").mkdir(parents=True)
    (tmp_path / "src" / "alpha" / "__init__.py").write_text("")
    (tmp_path / "src" / "beta.py").write_text("")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')

    config = _MOD.import_linter_config(tmp_path)

    assert config is not None
    assert '"alpha"' in config
    assert "beta" not in config
