"""Real Vulture runs retain dead-code detection beside framework declarations."""

import subprocess
from pathlib import Path

import pytest

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


FRAMEWORK_SOURCES = {
    "pydantic": {
        "base.py": """from pydantic import BaseModel as NativeModel


class Record(NativeModel):
    pass
""",
        "main.py": """from typing import ClassVar
from base import Record as Schema


class Payload(Schema):
    serialized_value: int
    unregistered_class_value: ClassVar[int] = 9

    def abandoned_member(self):
        discarded_member_local = 19
        return 1


class Ordinary:
    unregistered_value: int = 2


value = Payload.model_validate({"serialized_value": 7})
assert value.model_dump() == {"serialized_value": 7}
assert "unregistered_class_value" not in Payload.model_fields
Ordinary()
""",
    },
    "cyclopts": {
        "main.py": """from cyclopts import App as CommandApp

app = CommandApp()
seen = []


@app.command(name="consume")
def registered_callback(value: int):
    discarded_callback_local = 17
    seen.append(value)


class Ordinary:
    def command(self, function):
        return function


ordinary = Ordinary()


@ordinary.command
def unregistered_callback():
    return 5


app(["consume", "13"])
assert seen == [13]
""",
    },
    "html": {
        "main.py": """from html.parser import HTMLParser as ParserBase

seen = []


class MarkupReader(ParserBase):
    def handle_starttag(self, token, attributes):
        discarded_handler_local = 17
        seen.append(token)
        seen.extend(pair[0] for pair in attributes)


class Ordinary:
    def handle_starttag(self, tag, attrs):
        return tag, attrs


reader = MarkupReader()
reader.feed("<section id='x'></section>")
assert seen == ["section", "id"]
Ordinary()
""",
    },
}


FRAMEWORK_SOURCES["pydantic_package"] = {
    "package/base.py": FRAMEWORK_SOURCES["pydantic"]["base.py"],
    "package/__init__.py": "from .base import Record as Record\n",
    "main.py": FRAMEWORK_SOURCES["pydantic"]["main.py"].replace("from base import Record as Schema", "from package import Record as Schema"),
}


@pytest.mark.parametrize("framework", FRAMEWORK_SOURCES)
def test_real_model_fields_and_framework_callbacks_preserve_dead_neighbors(tmp_path: Path, framework: str) -> None:
    sources = FRAMEWORK_SOURCES[framework]
    target = tmp_path / framework
    target.mkdir()
    for filename, source in sources.items():
        (target / filename).parent.mkdir(parents=True, exist_ok=True)
        (target / filename).write_text(source)
    executed = subprocess.run(
        ["uv", "run", "--no-project", "--python", "3.14", "--with", "pydantic", "--with", "cyclopts", "python", str(target / "main.py")],
        cwd=target,
        text=True,
        capture_output=True,
        check=False,
    )
    assert executed.returncode == 0, executed.stdout + executed.stderr
    result = scan(target, ROOT / "tool-artifacts" / "scripts" / "vulture-frameworks.py")
    assert result.returncode != 0, result.stdout + result.stderr
    if framework.startswith("pydantic"):
        assert "'serialized_value'" not in result.stdout, result.stdout
        for name in ("unregistered_class_value", "unregistered_value", "abandoned_member", "discarded_member_local"):
            assert f"'{name}'" in result.stdout, result.stdout
    elif framework == "cyclopts":
        assert "'registered_callback'" not in result.stdout, result.stdout
        assert "'unregistered_callback'" in result.stdout, result.stdout
        assert "'discarded_callback_local'" in result.stdout, result.stdout
    else:
        source = sources["main.py"]
        registered_line = source.splitlines().index("    def handle_starttag(self, token, attributes):") + 1
        ordinary_line = source.splitlines().index("    def handle_starttag(self, tag, attrs):") + 1
        assert f"main.py:{registered_line}: unused method 'handle_starttag'" not in result.stdout, result.stdout
        assert f"main.py:{ordinary_line}: unused method 'handle_starttag'" in result.stdout, result.stdout
        assert "'discarded_handler_local'" in result.stdout, result.stdout
