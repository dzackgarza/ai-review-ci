"""Pydantic report models — the single validation spec for review reports.

The model selected by ``report_type`` ("general" or "slop") defines the
report contract: field semantics, semantic rejection rules, and the
hallucination checks (every cited path must exist in the reviewed checkout,
every line range must lie within the file). The reviewed checkout is the
process CWD when validation runs.

``schema_version`` and ``report_type`` are tool-owned identification fields:
``validate-report`` stamps them before validation when the candidate omits
them, and the ``Literal`` types reject any mismatching agent-supplied value.

Finding identity is also defined here: ``finding_fingerprint`` keys SARIF
alerts and PR review threads to the same tracked item across runs.
"""

import hashlib
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal, Protocol, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

LOW_SIGNAL_CATEGORIES = frozenset(
    {
        "code-style",
        "style",
        "readability",
        "import-placement",
        "import-order",
        "file-length",
        "line-length",
        "naming",
        "naming-convention",
        "duplication",
        "duplicate-code",
        "comment-style",
        "formatting",
    }
)

_INVARIANT_REJECT = [
    re.compile(p, re.IGNORECASE)
    for p in [
        "-O",
        "optimized mode",
        "clean code",
        "no violation",
        r"nothing (?:to |)report",
        r"looks? (?:good|correct|fine|right|ok)",
        r"no issues? found",
        r"appears? correct",
        r"everything (?:looks|seems|is)",
        r"i (?:don't|do not|did not|didn't) find",
    ]
]

_CLEAN_REPORT_REJECT = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bclean\b",
        r"no slop",
        r"no issues?",
        r"nothing (?:to |)report",
        r"all clear",
        r"all good",
    ]
]


def finding_fingerprint(category: str, path: str) -> str:
    """Deterministic finding identity, stable across line shifts and runs.

    Components: category + path. The agent-chosen label is deliberately
    excluded — labels are free text reinvented each run, and including
    them re-keyed the same defect into a new alert on every review.
    No line numbers, no timestamps, no commit SHAs.
    """
    raw = "|".join([category, path])
    return hashlib.sha256(raw.encode()).hexdigest()


def _path_in_checkout(path: Path) -> bool:
    """True if *path* exists in the reviewed checkout (the CWD)."""
    return (Path.cwd() / path).is_file()


def _line_count(path: Path) -> int:
    """Number of lines in *path* within the reviewed checkout."""
    return len((Path.cwd() / path).read_text(errors="replace").splitlines())


# ---------------------------------------------------------------------------
# Shared validator logic (parameterized by the per-report-type FIX guidance)
# ---------------------------------------------------------------------------


def reject_blanket_invariant(value: str, *, good_example: str) -> str:
    """Reject violated_invariant text that names nothing specific."""
    for pat in _INVARIANT_REJECT:
        if pat.search(value):
            raise ValueError(
                f"REJECTED: violated_invariant contains prohibited pattern "
                f"'{pat.pattern}'. "
                f"FIX: violated_invariant must name a specific violated contract "
                f"or behavior. Bad: 'clean code'. "
                f"Good: '{good_example}'."
            )
    return value


def reject_clean_report_language(value: str) -> str:
    """Reject slop findings that try to encode an all-clear report."""
    for pat in _CLEAN_REPORT_REJECT:
        if pat.search(value):
            raise ValueError(
                f"REJECTED: clean-report language contains prohibited pattern "
                f"'{pat.pattern}'. "
                f"FIX: slop reports must name an actual slop pattern; if no "
                f"finding can be produced, do not submit a report."
            )
    return value


def require_tier2_for_low_signal(tier: str, category: str, *, fix_examples: str) -> None:
    """Force low-signal categories to tier2."""
    if category.lower() in LOW_SIGNAL_CATEGORIES and tier == "tier1":
        raise ValueError(
            f"REJECTED: category '{category}' is low-signal, "
            f"must be tier2, not tier1. "
            f"FIX: change tier to 'tier2' or use a non-low-signal category "
            f"(e.g. {fix_examples}). "
            f"Low-signal categories: {sorted(LOW_SIGNAL_CATEGORIES)}"
        )


class ReportFinding(Protocol):
    """Read-only view of the finding fields the report-level checks need."""

    @property
    def tier(self) -> str: ...

    @property
    def category(self) -> str: ...

    @property
    def location(self) -> Location: ...

    @property
    def evidence(self) -> Sequence[Evidence]: ...


def _check_finding_paths(i: int, finding: ReportFinding) -> None:
    """Checkout-grounding checks for one finding: paths exist, lines in range."""
    loc_path = finding.location.path
    if not _path_in_checkout(loc_path):
        raise ValueError(
            f"REJECTED: findings[{i}] location path '{loc_path}' "
            f"does not exist in the reviewed checkout. "
            f"FIX: every finding path must be a real file in the "
            f"repository, relative to the repo root."
        )
    n_lines = _line_count(loc_path)
    if finding.location.end_line > n_lines:
        raise ValueError(
            f"REJECTED: findings[{i}] location lines "
            f"{finding.location.start_line}-{finding.location.end_line} "
            f"exceed the length of '{loc_path}' ({n_lines} lines). "
            f"FIX: use line numbers that exist in the file."
        )
    for j, ev in enumerate(finding.evidence):
        _check_evidence_paths(i, j, ev)


def _check_evidence_paths(i: int, j: int, ev: Evidence) -> None:
    """Checkout-grounding checks for one evidence item."""
    if not _path_in_checkout(ev.path):
        raise ValueError(
            f"REJECTED: findings[{i}].evidence[{j}] path '{ev.path}' "
            f"does not exist in the reviewed checkout. "
            f"FIX: every evidence path must be a real file in the "
            f"repository, relative to the repo root."
        )
    ev_lines = _line_count(ev.path)
    if ev.lines[1] > ev_lines:
        raise ValueError(
            f"REJECTED: findings[{i}].evidence[{j}] lines {ev.lines} exceed the length of '{ev.path}' ({ev_lines} lines). FIX: use line numbers that exist in the file."
        )


def validate_checkout_paths(review_scope: Sequence[Path], findings: Sequence[ReportFinding]) -> None:
    """Every cited path must exist in the checkout."""
    for i, p in enumerate(review_scope):
        if not _path_in_checkout(p):
            raise ValueError(
                f"REJECTED: review_scope[{i}] path '{p}' does not exist in the reviewed checkout. FIX: only list files that exist in the repository, relative to the repo root."
            )
    for i, finding in enumerate(findings):
        _check_finding_paths(i, finding)


def require_substantive_finding(findings: Sequence[ReportFinding], *, fix_tail: str) -> None:
    """At least one finding must be Tier 1 or carry a non-low-signal category."""
    if not any(f.tier == "tier1" or f.category.lower() not in LOW_SIGNAL_CATEGORIES for f in findings):
        raise ValueError(
            "REJECTED: at least one finding must be substantive "
            "(Tier 1 or non-low-signal category). "
            f"FIX: all your findings are low-signal categories at tier2. "
            f"Add at least one Tier 1 finding or use a substantive category "
            f"(not one of {sorted(LOW_SIGNAL_CATEGORIES)}). "
            f"{fix_tail}"
        )


# ---------------------------------------------------------------------------
# Shared leaf types
# ---------------------------------------------------------------------------


class Location(BaseModel):
    path: Path = Field(description="File path relative to repo root. Must exist in the reviewed checkout.")
    start_line: int = Field(ge=1, description="Finding start line (1-indexed).")
    end_line: int = Field(ge=1, description="Finding end line (1-indexed).")

    @model_validator(mode="after")
    def _ordered_lines(self) -> Self:
        if self.start_line > self.end_line:
            raise ValueError(f"REJECTED: start_line {self.start_line} > end_line {self.end_line}. FIX: start_line must not exceed end_line.")
        return self


class Evidence(BaseModel):
    kind: str = Field(description="Evidence type: file-read, diff-snippet, command-output.")
    path: Path = Field(description="Evidence file path relative to repo root. Must exist in the reviewed checkout.")
    lines: list[Annotated[int, Field(ge=1)]] = Field(
        min_length=2,
        max_length=2,
        description="Line range [start, end] this evidence covers (1-indexed).",
    )

    @model_validator(mode="after")
    def _ordered_lines(self) -> Self:
        if self.lines[0] > self.lines[1]:
            raise ValueError(f"REJECTED: evidence lines {self.lines} are not an ascending [start, end] range. FIX: start must not exceed end.")
        return self


class CheckedSurface(BaseModel):
    path: Path = Field(description="File path examined during review.")
    reason: str = Field(description="Why this surface was selected: high-churn, diff-context, dependency-graph.")
    lines_read: list[Annotated[int, Field(ge=1)]] = Field(
        min_length=2,
        max_length=2,
        description="Line range [start, end] read during review (1-indexed).",
    )
    result: str = Field(description="Outcome: finding, clean, needs-attention.")


# ---------------------------------------------------------------------------
# General review
# ---------------------------------------------------------------------------

_GENERAL_TIER_EXAMPLES = "'semantic-regression', 'test-quality'"
_GENERAL_INVARIANT_GOOD = "The CI runner silently swallows diff-retrieval failures instead of aborting"


class GeneralFinding(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "x-custom-validation": {
                "_tier_category_consistency": {
                    "rule": "Low-signal categories (see LOW_SIGNAL_CATEGORIES) require tier2",
                    "validator": "_tier_category_consistency",
                }
            }
        },
    )
    tier: Literal["tier1", "tier2"] = Field(
        description="tier1: a real semantic regression, broken invariant, or "
        "incorrect behavior that changes program output or violates a correctness "
        "property. tier2: a minor concern, code quality observation, or low-risk "
        "issue. Low-signal categories (naming, formatting, etc.) are forced to "
        "tier2 by validation.",
        json_schema_extra={
            "x-custom-validation": {
                "rule": "Low-signal categories must be tier2. See category field and _tier_category_consistency",
                "validator": "_tier_category_consistency",
            }
        },
    )
    label: str = Field(
        description="Short label describing defect shape (not severity). "
        "Ground it in what the code actually does wrong — e.g. if a function "
        "returns wrong output: INCORRECT_OUTPUT; if stderr is silenced: "
        "SUPPRESSED_ERROR; if Optional is unwrapped without guard: NULL_UNSAFE. "
        "Look at the bridge-burning-red-flags.md and runtime-control-flow-red-flags.md "
        "inventories in reviewing-llm-code for grounded pattern names.",
    )
    category: str = Field(
        description="Defect type. Ground it in known categories from policy-index "
        "and the bridge-burning rules. "
        "Examples: semantic-regression, test-quality, null-safety, "
        "missing-error-handling, logic-error, ci-pipeline, workflow.",
    )
    location: Location = Field(description="File and line range where the finding occurs.")
    violated_invariant: str = Field(
        min_length=20,
        description="A specific, verifiable contract or behavior that is violated. "
        "Must name something falsifiable — provable or disprovable via a command or "
        "code inspection. Not a blanket judgment. "
        "Rejected patterns (blanket claims that name nothing specific): -O, "
        "optimized mode, clean code, no violation, nothing to report, "
        "looks (good|correct|fine|right|ok), no issues found, appears correct, "
        "everything (looks|seems|is).",
        json_schema_extra={
            "x-custom-validation": {
                "rule": "Must name a specific falsifiable contract. "
                "Rejected against patterns: -O, optimized mode, clean code, "
                "no violation, nothing to report, looks (good|correct|fine|right|ok), "
                "no issues found, appears correct, everything (looks|seems|is)",
                "validator": "_no_empty_invariant",
            }
        },
    )
    proof_command: str = Field(
        min_length=10,
        description="Shell command or code path that proves the invariant is "
        "violated. Must be reproducible by another agent. "
        "Example: 'grep -rn get_diff src/ai_review_ci/harness.py'",
    )
    symptom: str = Field(description="Observable symptom of the defect.")
    source: str = Field(description="Root cause: what code or pattern produces the symptom.")
    consequence: str = Field(description="What breaks or degrades due to this defect.")
    evidence: list[Evidence] = Field(
        min_length=1,
        description="Supporting evidence proving the finding. At least one item required.",
    )

    @model_validator(mode="after")
    def _tier_category_consistency(self) -> Self:
        require_tier2_for_low_signal(self.tier, self.category, fix_examples=_GENERAL_TIER_EXAMPLES)
        return self

    @field_validator("violated_invariant")
    @classmethod
    def _no_empty_invariant(cls, v: str) -> str:
        return reject_blanket_invariant(v, good_example=_GENERAL_INVARIANT_GOOD)


class GeneralReport(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "x-custom-validation": {
                "_require_substantive_finding": {
                    "rule": "At least one finding must be Tier 1 or non-low-signal category",
                    "validator": "_require_substantive_finding",
                },
                "_check_paths": {
                    "rule": "Every path must exist in the reviewed checkout",
                    "validator": "_check_paths",
                },
            }
        },
    )
    schema_version: Literal[1] = Field(
        description="Report format version. Always 1. Stamped by validate-report when absent — omit it or set it to exactly 1.",
    )
    report_type: Literal["general"] = Field(
        description="Must be 'general'. Stamped by validate-report when absent. Selects the GeneralFinding model for validation.",
    )
    review_scope: list[Path] = Field(
        min_length=1,
        description="Files examined during review, relative to repo root. All must exist in the reviewed checkout. Typically drawn from the PR diff.",
    )
    findings: list[GeneralFinding] = Field(
        min_length=1,
        description="General review findings. At least one required; at least one must be substantive (Tier 1 or non-low-signal category).",
    )
    checked_surfaces: list[CheckedSurface] = Field(
        description="Surfaces inspected during review, whether findings were found or not. Documents review thoroughness.",
    )
    rejected_easy_wins: list[str] = Field(
        description="Low-signal observations the agent considered but declined to "
        "elevate to findings, with brief reason. Documents that non-trivial "
        "patterns were evaluated and dismissed, not missed.",
    )

    @model_validator(mode="after")
    def _check_paths(self) -> Self:
        validate_checkout_paths(self.review_scope, self.findings)
        return self

    @model_validator(mode="after")
    def _require_substantive_finding(self) -> Self:
        require_substantive_finding(
            self.findings,
            fix_tail="A substantive finding has a concrete 'violated_invariant' and reproducible 'proof_command'.",
        )
        return self


# ---------------------------------------------------------------------------
# Slop review
# ---------------------------------------------------------------------------

_SLOP_TIER_EXAMPLES = "'bridge-burning', 'validation-evasion'"
_SLOP_INVARIANT_GOOD = "The agent suppresses stderr to construct synthetic fallback results instead of failing on missing files"


class SlopFinding(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "x-custom-validation": {
                "_tier_category_consistency": {
                    "rule": "Low-signal categories (see LOW_SIGNAL_CATEGORIES) require tier2",
                    "validator": "_tier_category_consistency",
                }
            }
        },
    )
    tier: Literal["tier1", "tier2"] = Field(
        description="tier1: a concrete bridge-burning pattern — runtime default, "
        "fallback, suppressed error, mock-pretending-as-proof, or similar "
        "validation-evasion construct. "
        "tier2: speculative over-engineering, minor style deviation, or a pattern "
        "that could become harmful under implausible conditions. "
        "Low-signal categories are forced to tier2 by validation.",
        json_schema_extra={
            "x-custom-validation": {
                "rule": "Low-signal categories require tier2. Cross-field with category.",
                "validator": "_tier_category_consistency",
            }
        },
    )
    label: Literal["SLOP", "SLOP SUSPECT"] = Field(
        description="Finding disposition. SLOP is definite; SLOP SUSPECT is a credible slop pattern requiring human judgment. NOTE and clean-report labels are rejected."
    )
    category: str = Field(
        description="Slop pattern category from the anti-slop skill taxonomy. "
        "Look at policy-index and the bridge-burning inventory for grounded "
        "categories like: bridge-burning, runtime-control-flow, "
        "validation-evasion, defaults-and-fallbacks, proof-laundering, workflow, "
        "ci-pipeline, config.",
    )
    location: Location = Field(description="File and line range where the slop pattern occurs.")
    violated_invariant: str = Field(
        min_length=20,
        description="A specific engineering invariant that is violated by the slop "
        "pattern. Must name a concrete contract (e.g., 'every error path fails "
        "loudly, but this code suppresses stderr'). Not a blanket judgment. "
        "Rejected patterns (blanket claims that name nothing specific): -O, "
        "optimized mode, clean code, no violation, nothing to report, "
        "looks (good|correct|fine|right|ok), no issues found, appears correct, "
        "everything (looks|seems|is).",
        json_schema_extra={
            "x-custom-validation": {
                "rule": "Must name a specific falsifiable contract. "
                "Rejected against patterns: -O, optimized mode, clean code, "
                "no violation, nothing to report, looks (good|correct|fine|right|ok), "
                "no issues found, appears correct, everything (looks|seems|is)",
                "validator": "_no_empty_invariant",
            }
        },
    )
    proof_command: str = Field(
        min_length=10,
        description="Shell command or code path that reproduces the slop pattern. "
        "Must be reproducible by another agent. "
        "Example: 'rg '2>/dev/null' quality-control/', "
        "'probe search 'Optional.*Field' -- src/db/service.py'",
    )
    pattern: str = Field(
        description="Structural pattern name. Ground it in the actual code construct "
        "(is there a 2>/dev/null it's runtime-default? a mock without assertion? "
        "a try/except ImportError? a boolean mode flag?). "
        "See bridge-burning-red-flags.md and runtime-control-flow-red-flags.md "
        "for the full pattern inventory.",
    )
    task_narrative: str = Field(
        description="What the agent was supposed to build — capsulizes the task context so the reader understands the assigned goal.",
    )
    slop_narrative: str = Field(
        description="What the agent actually produced — the bridge-burning substitution. Contrast with task_narrative.",
    )
    why_it_matters: str = Field(
        description="Concrete consequence of this slop pattern: silent data loss, masked failure, untestable branch, non-deterministic behavior, etc.",
    )
    user_surprise: str = Field(
        description="What the user would observe that would trigger a 'why did this happen' reaction. Epistemic: describe the observable surprise, not the hypothetical.",
    )
    existential_justification: str = Field(
        description="Why this finding exists. The agent's rationalization for the "
        "bridge-burning choice (e.g., 'defensive coding', 'graceful degradation', "
        "'backward compatibility', 'just in case').",
    )
    failure_mode: str = Field(
        description="Which LLM failure mode this slop exploits. "
        "See the llm-failure-modes skill for the full catalog. "
        "Use the documented numbered labels (e.g. asymmetric-risk-model (#20), "
        "false-binary (#7), reward-hacking (#13), epistemic-bottleneck (#4)), "
        "not invented names.",
    )
    evidence: list[Evidence] = Field(
        min_length=1,
        description="Supporting evidence proving the slop pattern. At least one item required. Should include file-read or diff-snippet showing the offending construct.",
    )

    @model_validator(mode="after")
    def _tier_category_consistency(self) -> Self:
        require_tier2_for_low_signal(self.tier, self.category, fix_examples=_SLOP_TIER_EXAMPLES)
        return self

    @field_validator("violated_invariant")
    @classmethod
    def _no_empty_invariant(cls, v: str) -> str:
        return reject_blanket_invariant(v, good_example=_SLOP_INVARIANT_GOOD)

    @field_validator("pattern", "slop_narrative")
    @classmethod
    def _no_clean_report_language(cls, v: str) -> str:
        return reject_clean_report_language(v)


class SlopReport(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "x-custom-validation": {
                "_require_substantive_finding": {
                    "rule": "At least one finding must be Tier 1 or non-low-signal category",
                    "validator": "_require_substantive_finding",
                },
                "_check_paths": {
                    "rule": "Every path must exist in the reviewed checkout",
                    "validator": "_check_paths",
                },
            }
        },
    )
    schema_version: Literal[1] = Field(
        description="Report format version. Always 1. Stamped by validate-report when absent — omit it or set it to exactly 1.",
    )
    report_type: Literal["slop"] = Field(
        description="Must be 'slop'. Stamped by validate-report when absent. Selects the SlopFinding model for validation.",
    )
    review_scope: list[Path] = Field(
        min_length=1,
        description="Files examined during review, relative to repo root. All must exist in the reviewed checkout.",
    )
    findings: list[SlopFinding] = Field(
        min_length=1,
        description="Slop review findings. At least one required; at least one must be substantive (Tier 1 or non-low-signal category).",
    )

    @model_validator(mode="after")
    def _check_paths(self) -> Self:
        validate_checkout_paths(self.review_scope, self.findings)
        return self

    @model_validator(mode="after")
    def _require_substantive_finding(self) -> Self:
        require_substantive_finding(
            self.findings,
            fix_tail="A substantive slop finding has a concrete 'violated_invariant' and a reproducible 'proof_command' showing the bridge-burning pattern.",
        )
        return self


MODEL_BY_TYPE: dict[str, type[GeneralReport | SlopReport]] = {
    "general": GeneralReport,
    "slop": SlopReport,
}
