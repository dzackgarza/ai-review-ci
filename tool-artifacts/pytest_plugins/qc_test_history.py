r"""Append one timing record per pytest run to a history directory.

Loaded by ``_sage-pytest-run`` (``-p qc_test_history --qc-history-dir DIR``).
Each run writes ``DIR/<UTC start>-<commit>.json`` holding the commit, whether the
work tree was dirty, the pytest arguments, the exit status, and every test's
outcome and duration (setup + call + teardown). Records are never overwritten,
so durations can be compared across commits with ``pytest_history.py``.
"""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

SCHEMA_VERSION = 1


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--qc-history-dir", help="directory receiving one JSON timing record per run")


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True, text=True).stdout


class HistoryRecorder:
    def __init__(self, config: pytest.Config) -> None:
        self.directory = Path(config.getoption("--qc-history-dir"))
        self.arguments = [str(argument) for argument in config.invocation_params.args]
        self.started = datetime.now(UTC)
        self.commit = _git(config.rootpath, "rev-parse", "HEAD").strip()
        self.dirty = bool(_git(config.rootpath, "status", "--porcelain"))
        self.durations: dict[str, float] = {}
        self.outcomes: dict[str, str] = {}

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self.durations[report.nodeid] = self.durations.get(report.nodeid, 0.0) + report.duration
        match (report.when, report.outcome):
            case ("call", "failed"):
                self.outcomes[report.nodeid] = "failed"
            case (_, "failed"):
                self.outcomes[report.nodeid] = "error"
            case (_, "skipped"):
                self.outcomes[report.nodeid] = "skipped"
            case (_, "passed"):
                self.outcomes.setdefault(report.nodeid, "passed")

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        record = {
            "schema_version": SCHEMA_VERSION,
            "started": self.started.isoformat(),
            "finished": datetime.now(UTC).isoformat(),
            "commit": self.commit,
            "dirty": self.dirty,
            "args": self.arguments,
            "exitstatus": int(exitstatus),
            "tests": [
                {"nodeid": nodeid, "outcome": self.outcomes[nodeid], "duration": duration}
                for nodeid, duration in self.durations.items()
            ],
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{self.started:%Y%m%dT%H%M%S%fZ}-{self.commit[:12]}.json"
        with path.open("x") as handle:
            json.dump(record, handle, indent=1)
            handle.write("\n")


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--qc-history-dir") is None:
        raise pytest.UsageError("qc_test_history requires --qc-history-dir")
    config.pluginmanager.register(HistoryRecorder(config), "qc_test_history_recorder")
