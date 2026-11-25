"""Exercise the real pytest compilation/cache boundary in a caller process."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_prepared_bytecode_contract(tmp_path: Path) -> None:
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "tool-artifacts" / "pytest_plugins")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-c", str(config), str(ROOT / "tests/fixtures/sage_rewrite/native_cache.py")],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 passed" in result.stdout


def test_assertion_pass_configuration_selects_current_native_bytecode(tmp_path: Path) -> None:
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "original.sage").write_text("value = 7\nassert value == 7\n")
    (tmp_path / "conftest.py").write_text(
        "from pathlib import Path\n"
        "def pytest_assertion_pass(item, lineno, orig, expl):\n"
        "    if orig == 'value == 7':\n"
        "        with Path('passed.txt').open('a') as stream:\n"
        "            stream.write('passed\\n')\n"
    )
    (tmp_path / "test_config.py").write_text(
        "from pathlib import Path\n"
        "from qc_sage_rewrite import compile_rewritten\n"
        "def test_current_configuration(request):\n"
        "    path = Path('original.sage').resolve()\n"
        "    code = compile_rewritten(path, path.read_text(), request.config, Path('compiled'))\n"
        "    exec(code, {})\n"
        "    assert code.co_filename == str(path)\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "tool-artifacts" / "pytest_plugins")
    for setting in ("false", "true"):
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-o", f"enable_assertion_pass_hook={setting}", "test_config.py"],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "1 passed" in result.stdout
    assert len(list((tmp_path / "compiled").glob("*.pyc"))) == 2
    assert (tmp_path / "passed.txt").read_text() == "passed\n"
