"""Real Vulture runs retain dead-code detection beside framework declarations."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "vulture_frameworks"


def scan(path: Path, script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--no-project", "--python", "3.14", "--with", "vulture", "python", str(script), "--config", str(ROOT / "tool-configs" / "pyproject.toml"), str(path)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_framework_collection_and_context_protocol_are_real() -> None:
    executed = subprocess.run(
        ["uv", "run", "--no-project", "--python", "3.14", "python", "-m", "unittest", "discover", "-s", str(FIXTURES), "-p", "test_protocols.py"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert executed.returncode == 0, executed.stderr
    assert "Ran 4 tests" in executed.stderr
    result = scan(FIXTURES / "test_protocols.py", ROOT / "tool-artifacts" / "scripts" / "vulture-frameworks.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_uncollected_helpers_and_ordinary_unused_arguments_remain_findings() -> None:
    result = scan(FIXTURES / "unused.py", ROOT / "tool-artifacts" / "scripts" / "vulture-frameworks.py")
    assert result.returncode != 0
    for name in ("HiddenHelper", "_contains_", "unused_value", "kind", "error", "traceback"):
        assert f"'{name}'" in result.stdout, result.stdout


def test_sage_ideal_dispatch_is_recognized_only_on_its_declared_base() -> None:
    result = scan(FIXTURES / "sage_protocol.py", ROOT / "tool-artifacts" / "scripts" / "vulture-frameworks.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_language_recipes_scan_the_caller_and_keep_neighboring_dead_code(tmp_path: Path) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    (target / "test_protocols.py").write_text((FIXTURES / "test_protocols.py").read_text())
    subprocess.run(["git", "init", "--quiet", str(target)], check=True)
    subprocess.run(["git", "add", "test_protocols.py"], cwd=target, check=True)
    for profile in ("python", "sage"):
        command = ["just", "-f", str(ROOT / "justfiles" / f"{profile}.just"), "-d", str(target), "_vulture"]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    (target / "unused.py").write_text((FIXTURES / "unused.py").read_text())
    subprocess.run(["git", "add", "unused.py"], cwd=target, check=True)
    for profile in ("python", "sage"):
        result = subprocess.run(["just", "-f", str(ROOT / "justfiles" / f"{profile}.just"), "-d", str(target), "_vulture"], text=True, capture_output=True, check=False)
        assert result.returncode != 0
        assert "unused.py:" in result.stdout, result.stdout + result.stderr
        assert "'HiddenHelper'" in result.stdout
        assert "'surplus'" in result.stdout


def test_framework_declaration_registration_preserves_findings_inside_bodies() -> None:
    for fixture, names in (
        ("test_internal_unused.py", ("abandoned_helper", "discarded_local")),
        ("sage_internal_unused.py", ("discarded_callback_local",)),
    ):
        result = scan(FIXTURES / fixture, ROOT / "tool-artifacts" / "scripts" / "vulture-frameworks.py")
        assert result.returncode != 0
        for name in names:
            assert f"'{name}'" in result.stdout, result.stdout + result.stderr


def test_testcase_outside_discovery_sources_remains_dead_code(tmp_path: Path) -> None:
    source = tmp_path / "ordinary_module.py"
    source.write_text((FIXTURES / "test_protocols.py").read_text())
    result = scan(source, ROOT / "tool-artifacts" / "scripts" / "vulture-frameworks.py")
    assert result.returncode != 0
    assert "'Descendant'" in result.stdout
    assert "'Qualified'" in result.stdout
