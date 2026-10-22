#!/usr/bin/env python3
"""Run independent development-CI diagnostics and retain every outcome.

The development phase records diagnostics; it does not decide whether an MVP
can be committed or published. Each existing QC recipe is run independently:
a compiler failure cannot prevent a test result or hide a later debt finding.
Pass --enforce only after a project has explicitly adopted a stable baseline.
"""
from __future__ import annotations

import argparse
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


def run(profile: str, tier: str, report_dir: Path, *, enforce: bool = False) -> int:
    checks = ci_checks(profile) if tier == "ci" else ambient_checks(profile)
    report_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in checks:
        logfile = report_dir / f"{spec.id}.log"
        command = spec.command()
        print(f"[{spec.category}] {spec.id}", flush=True)
        with logfile.open("w", encoding="utf-8") as stream:
            try:
                exit_code = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False).returncode
            except OSError as error:
                stream.write(f"Unable to launch check: {error}\n")
                exit_code = 127
        results.append(
            {
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
        "failed_checks": len(failures),
    }
    (report_dir / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
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
    summary += ["", "Logs and results.json are retained as CI artifacts.", "All findings enforced (stabilized phase)." if enforce else "Development findings do not block publication."]
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
