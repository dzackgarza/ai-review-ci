#!/usr/bin/env python3
"""Run independent development-CI diagnostics and retain every outcome.

The development phase records diagnostics; it does not decide whether an MVP
can be committed or published. Each existing QC recipe is run independently:
a compiler failure cannot prevent a test result or hide a later debt finding.
Pass --enforce only after a project has explicitly adopted a stable baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


INFRA = Path(__file__).resolve().parents[1]
JUSTFILES = INFRA / "justfiles"


@dataclass(frozen=True)
class Check:
    id: str
    category: str
    file: str
    recipe: str
    args: tuple[str, ...] = ()

    def command(self) -> list[str]:
        if self.file == "caller":
            return ["just", self.recipe, *self.args]
        if self.file == "infra":
            return ["just", "-f", str(INFRA / "justfile"), "-d", ".", self.recipe, *self.args]
        return ["just", "-f", str(JUSTFILES / f"{self.file}.just"), "-d", ".", self.recipe, *self.args]


def check(id: str, category: str, file: str, recipe: str, *args: str) -> Check:
    return Check(id, category, file, recipe, tuple(args))


PYTHON = (
    check("python-tests", "correctness", "python", "_pytest_with_coverage"),
    check("python-syntax", "correctness", "python", "_python-syntax"),
    check("python-types", "debt", "python", "_mypy"),
    check("python-lint", "debt", "python", "_ci-ruff-check"),
    check("python-format", "debt", "python", "_ci-ruff-format"),
    check("python-dependencies", "debt", "python", "_deptry"),
    check("python-ast-rules", "debt", "python", "_ast-grep"),
    check("python-coverage", "debt", "python", "_diff-cover"),
    check("python-imports", "debt", "python", "_import-linter"),
    check("python-duplication", "debt", "python", "_jscpd-python"),
)
BUN = (
    check("bun-tests-and-coverage", "correctness", "bun", "_coverage"),
    check("bun-types", "debt", "bun", "_tsc"),
    check("bun-dependencies", "debt", "bun", "_knip"),
    check("bun-biome", "debt", "bun", "_biome"),
    check("bun-ast-rules", "debt", "bun", "_ast-grep"),
    check("bun-eslint", "debt", "bun", "_eslint"),
    check("bun-coverage", "debt", "bun", "_diff-cover"),
    check("bun-duplication", "debt", "bun", "_jscpd-bun"),
    check("bun-complexity", "debt", "bun", "_lizard-bun"),
    check("bun-slop", "debt", "bun", "_slop-scan"),
)
SAGE = (
    check("sage-tests", "correctness", "sage", "_sage-pytest-coverage"),
    check("sage-syntax", "correctness", "sage", "_sage-syntax"),
    check("sage-types", "debt", "sage", "_sage-mypy"),
    check("sage-python-lint", "debt", "python", "_ci-ruff-check"),
    check("sage-python-format", "debt", "python", "_ci-ruff-format"),
    check("sage-dead-code", "debt", "sage", "_vulture"),
    check("sage-ast-rules", "debt", "sage", "_sage-ast-grep"),
    check("sage-file-length", "debt", "sage", "_sage-file-length"),
    check("sage-dependencies", "debt", "python", "_deptry"),
    check("sage-python-ast-rules", "debt", "python", "_ast-grep"),
    check("sage-imports", "debt", "python", "_import-linter"),
    check("sage-duplication", "debt", "python", "_jscpd-python"),
    check("sage-complexity", "debt", "python", "_lizard-python", "15"),
    check("sage-coverage", "debt", "sage", "_sage-diff-cover"),
)
RUST = (
    check("rust-tests", "correctness", "rust", "_cargo-test"),
    check("rust-clippy", "debt", "rust", "_clippy"),
    check("rust-format", "debt", "rust", "_rustfmt"),
    check("rust-duplication", "debt", "rust", "_jscpd"),
    check("rust-complexity", "debt", "rust", "_lizard"),
    check("rust-codeql", "debt", "rust", "_codeql"),
)
LEAN = (
    check("lean-build", "correctness", "lean", "_lean-build"),
    check("lean-axioms", "correctness", "lean", "lean-axiom-audit"),
    check("lean-placeholders", "debt", "lean", "lean-no-sorry"),
    check("lean-static-rules", "debt", "lean", "lean-semgrep"),
)
SHARED = (
    check("semgrep", "debt", "shared", "_semgrep"),
    check("shared-ast-rules", "debt", "shared", "_ast-grep"),
    check("vibecheck", "debt", "shared", "_vibecheck"),
    check("prose-slop", "debt", "shared", "_slop"),
    check("ai-slop", "debt", "shared", "_aislop"),
)
QC_TOOLING = (
    check("qc-config-parse", "correctness", "infra", "check"),
    check("qc-tests", "correctness", "python", "_pytest_with_coverage"),
    check("qc-types", "debt", "python", "_mypy"),
    check("qc-lint", "debt", "python", "_ci-ruff-check"),
    check("qc-format", "debt", "python", "_ci-ruff-format"),
    check("qc-coverage", "debt", "python", "_diff-cover"),
    check("qc-dependencies", "debt", "python", "_deptry"),
    check("qc-imports", "debt", "python", "_import-linter"),
)


def ci_checks(profile: str) -> tuple[Check, ...]:
    if profile == "python":
        return PYTHON + SHARED
    if profile == "sage":
        return SAGE + SHARED
    if profile == "rust":
        return RUST + SHARED
    if profile == "bun":
        return BUN + SHARED
    if profile == "bun-playwright":
        return BUN + (check("browser-app-boot", "correctness", "caller", "app-boot"),) + SHARED
    if profile == "bun-python":
        return PYTHON + BUN + SHARED
    if profile == "lean":
        return LEAN
    if profile == "docs-and-configs":
        return (check("document-links", "correctness", "docs-and-configs", "_check-links"),)
    if profile == "qc-tooling":
        return QC_TOOLING
    raise ValueError(f"Unknown profile: {profile}")


def ambient_checks(profile: str) -> tuple[Check, ...]:
    checks = []
    if profile in ("python", "sage", "bun", "bun-python", "bun-playwright", "rust"):
        checks.append(check("whole-tree-semgrep", "debt", "shared", "_ambient-semgrep"))
    if profile in ("python", "bun-python", "qc-tooling"):
        checks.append(check("python-maintenance", "debt", "python", "_ambient-python-debt"))
    if profile in ("bun", "bun-python", "bun-playwright"):
        checks.append(check("bun-maintenance", "debt", "bun", "_ambient-bun-debt"))
    return tuple(checks)


def compare_results(current: dict, previous: dict | None) -> dict:
    """Stable per-check burndown, without treating a missing baseline as zero failures."""
    now = {item["id"] for item in current["checks"] if item["status"] == "failed"}
    if previous is None or previous.get("profile") != current["profile"] or previous.get("tier") != current["tier"]:
        return {"baseline": "unavailable", "open": sorted(now), "new": [], "persistent": [], "resolved": []}
    old = {item["id"] for item in previous["checks"] if item["status"] == "failed"}
    return {
        "baseline": previous.get("generated_at", "available"),
        "open": sorted(now),
        "new": sorted(now - old),
        "persistent": sorted(now & old),
        "resolved": sorted(old - now),
    }



# Recognize common compiler/linter locations and pytest's stable test IDs.
# Tools with unrecognized output retain a check-level failure, never an empty
# result that falsely looks like no problems.
LOCATED = re.compile(
    r"^(?P<path>[^\s:]+\.(?:py|pyi|sage|lean|rs|ts|tsx|js|jsx|toml|json|ya?ml|md))"
    r":(?P<line>[0-9]+)(?::[0-9]+)?:\s*(?P<message>.+)$"
)
PYTEST = re.compile(r"^(?:FAILED|ERROR)\s+(?P<node>\S+)(?:\s+-\s+(?P<message>.*))?$")


def extract_findings(spec: Check, logfile: Path, exit_code: int) -> list[dict]:
    """Return identified failures, retaining their source location and full log."""
    if exit_code == 0:
        return []
    findings: dict[str, dict] = {}
    with logfile.open(encoding="utf-8", errors="replace") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            match = PYTEST.match(line)
            if match:
                location = match["node"]
                number = None
                message = match["message"] or "pytest case failed"
            else:
                match = LOCATED.match(line)
                if not match:
                    continue
                location = match["path"]
                number = int(match["line"])
                message = match["message"]
            # Code/check/message discriminate independent findings. Preserve
            # line numbers separately; adding lines does not reset the burndown.
            code = re.search(r"\[([a-z][a-z0-9-]+)\]$", message)
            rule = code.group(1) if code else ""
            normalized = " ".join(message.split())[:500]
            signature = "\x00".join((spec.id, location, rule, normalized))
            key = hashlib.sha256(signature.encode()).hexdigest()[:20]
            findings[key] = {
                "id": key, "check": spec.id, "category": spec.category,
                "location": location, "line": number, "rule": rule,
                "message": normalized, "log": logfile.name,
            }
    if not findings:
        key = hashlib.sha256((spec.id + "\x00unparsed-failure").encode()).hexdigest()[:20]
        findings[key] = {
            "id": key, "check": spec.id, "category": spec.category,
            "location": None, "line": None, "rule": "CHECK_FAILED",
            "message": f"Check returned {exit_code}; inspect {logfile.name}",
            "log": logfile.name,
        }
    return list(findings.values())


def compare_findings(current: dict, previous: dict | None) -> dict:
    """Findings-level debt movement; an older check-only report is not a baseline."""
    active = {item["id"] for item in current["findings"]}
    if (
        previous is None or "findings" not in previous
        or previous.get("profile") != current["profile"]
        or previous.get("tier") != current["tier"]
    ):
        return {"baseline": "unavailable", "open": sorted(active),
                "new": [], "persistent": [], "resolved": []}
    prior = {item["id"] for item in previous["findings"]}
    return {"baseline": previous.get("generated_at", "available"),
            "open": sorted(active), "new": sorted(active - prior),
            "persistent": sorted(active & prior), "resolved": sorted(prior - active)}


def run(profile: str, tier: str, report_dir: Path, *, enforce: bool = False) -> int:
    checks = ci_checks(profile) if tier == "ci" else ambient_checks(profile)
    report_dir.mkdir(parents=True, exist_ok=True)
    results = []
    findings = []
    for spec in checks:
        logfile = report_dir / f"{spec.id}.log"
        command = spec.command()
        print(f"[{spec.category}] {spec.id}", flush=True)
        with logfile.open("w", encoding="utf-8") as stream:
            try:
                # Individual diagnostic recipes must never inherit the
                # interactive/direct-repair mode. Their failure is retained in
                # this collector rather than becoming a worker instruction.
                env = {**os.environ, "AI_REVIEW_CI_FAILURE_MODE": "triage"}
                exit_code = subprocess.run(
                    command, env=env, stdout=stream,
                    stderr=subprocess.STDOUT, check=False,
                ).returncode
            except OSError as error:
                stream.write(f"Unable to launch check: {error}\n")
                exit_code = 127
        check_findings = extract_findings(spec, logfile, exit_code)
        findings.extend(check_findings)
        results.append(
            {
                "finding_count": len(check_findings),
                "id": spec.id,
                "category": spec.category,
                "status": "passed" if exit_code == 0 else "failed",
                "exit_code": exit_code,
                "command": command,
                "log": logfile.name,
            }
        )

    failures = [r for r in results if r["status"] == "failed"]
    payload = {
        "schema_version": 1,
        "phase": "development",
        "profile": profile,
        "tier": tier,
        "enforced": enforce,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": results,
        "findings": findings,
        "failed_checks": len(failures),
    }
    (report_dir / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
    baseline_path = report_dir / "previous-results.json"
    previous = None
    if baseline_path.is_file():
        try:
            previous = json.loads(baseline_path.read_text())
        except (ValueError, OSError):
            pass
    burndown = compare_results(payload, previous)
    burndown["finding_burndown"] = compare_findings(payload, previous)
    (report_dir / "burndown.json").write_text(json.dumps(burndown, indent=2) + "\n")
    summary = [
        f"## {profile} {tier} — development diagnostics",
        "",
        f"{len(results) - len(failures)} passed; {len(failures)} failed. Failures are recorded, not waived.",
        "",
        "| Check | Class | Result | Evidence |",
        "|---|---|---|---|",
    ]
    for result in results:
        summary.append(f"| {result['id']} | {result['category']} | {result['status']} | {result['log']} |")
    summary += [
        "", "### Burndown", "",
        "Previous matching CI snapshot unavailable." if burndown["baseline"] == "unavailable" else
        f"{len(burndown['new'])} newly failing; {len(burndown['persistent'])} persistent; {len(burndown['resolved'])} resolved.",
        "Open checks: " + (", ".join(burndown["open"]) if burndown["open"] else "none"),
        "",
        f"{len(findings)} individual findings retained.",
        ("Previous finding snapshot unavailable." if burndown["finding_burndown"]["baseline"] == "unavailable"
         else (f"{len(burndown['finding_burndown']['new'])} new; "
               f"{len(burndown['finding_burndown']['persistent'])} persistent; "
               f"{len(burndown['finding_burndown']['resolved'])} resolved findings.")),
        "", "Logs, results.json and burndown.json are retained as CI artifacts.",
        "All findings enforced (stabilized phase)." if enforce else "Development findings do not block publication.",
    ]
    markdown = "\n".join(summary) + "\n"
    (report_dir / "summary.md").write_text(markdown)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a", encoding="utf-8") as output:
            output.write(markdown)
    print(f"Recorded {len(results)} checks ({len(failures)} failures) in {report_dir}", flush=True)
    return 1 if enforce and failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("--tier", choices=["ci", "ambient"], default="ci")
    parser.add_argument("--report-dir", type=Path, default=Path(os.environ.get("QC_TRIAGE_DIR", ".qc-triage")))
    parser.add_argument("--enforce", action="store_true", help="Opt-in only after a project has a frozen baseline")
    args = parser.parse_args()
    try:
        return run(args.profile, args.tier, args.report_dir, enforce=args.enforce or os.getenv("QC_ENFORCE", "false").lower() == "true")
    except ValueError as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    sys.exit(main())
