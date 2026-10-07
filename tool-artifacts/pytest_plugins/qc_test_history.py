r"""Stream one timing record per pytest run into a history directory.

Loaded by ``_sage-pytest-run`` (``-p qc_test_history --qc-history-dir DIR``).
Each run appends to its own ``DIR/<UTC start>-<commit>.jsonl``, flushing every
line as it happens:

- ``session``: commit, whether the work tree was dirty, pytest arguments;
- ``start``: a test began (so a killed run shows the test it died in);
- ``test``: a test finished, with its outcome and setup + call + teardown duration;
- ``finish``: the exit status, written only when the session ends normally.

Records are never overwritten, so durations can be compared across commits with
``pytest_history.py``.
"""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--qc-history-dir", help="directory receiving one JSONL timing record per run")


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True, text=True).stdout


class HistoryRecorder:
    def __init__(self, config: pytest.Config) -> None:
        directory = Path(config.getoption("--qc-history-dir"))
        directory.mkdir(parents=True, exist_ok=True)
        started = datetime.now(UTC)
        commit = _git(config.rootpath, "rev-parse", "HEAD").strip()
        self.handle: TextIO = (directory / f"{started:%Y%m%dT%H%M%S%fZ}-{commit[:12]}.jsonl").open("x")
        self.durations: dict[str, float] = {}
        self.outcomes: dict[str, str] = {}
        self._write(
            type="session",
            started=started.isoformat(),
            commit=commit,
            dirty=bool(_git(config.rootpath, "status", "--porcelain")),
            args=[str(argument) for argument in config.invocation_params.args],
        )

    def _write(self, **fields: object) -> None:
        self.handle.write(json.dumps(fields) + "\n")
        self.handle.flush()

    def pytest_runtest_logstart(self, nodeid: str) -> None:
        self._write(type="start", nodeid=nodeid, at=datetime.now(UTC).isoformat())

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

    def pytest_runtest_logfinish(self, nodeid: str) -> None:
        self._write(type="test", nodeid=nodeid, outcome=self.outcomes[nodeid], duration=self.durations[nodeid])

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        self._write(type="finish", finished=datetime.now(UTC).isoformat(), exitstatus=int(exitstatus))
        self.handle.close()


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--qc-history-dir") is None:
        raise pytest.UsageError("qc_test_history requires --qc-history-dir")
    config.pluginmanager.register(HistoryRecorder(config), "qc_test_history_recorder")
