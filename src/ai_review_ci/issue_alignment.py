"""Advisory alignment check for issues filed against this repository.

An issue becomes a specification the moment an implementing agent reads it, and the
proposals worth catching are well-formed: they carry symptom, evidence, and impact, and
they hand the consuming repository a switch inside a "Suggested direction" section. No
schema check reaches that, so this runs a model against CONTRIBUTING.md and the QC
authority policies and asks the one question those documents turn on.

The verdict is advisory and deliberately asymmetric in what it can express. A clean run
has no side effects at all — no label, no comment, nothing to cite. Only a suspected
inversion speaks. That keeps the check from becoming a clearance surface: absence of a
comment is not approval, because absence is also what a clean run looks like.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Literal, NoReturn, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_review_ci.harness import OpencodeConfig, load_manifest, run_opencode

VERDICT_PATH = Path(".issue-alignment.json")
RULING_LABEL = "needs-alignment-ruling"
VERDICT_MARKER = "<!-- issue-alignment-verdict -->"


def _fail(msg: str) -> NoReturn:
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


class AlignmentVerdict(BaseModel):
    """The checker's whole output surface.

    ``no-objection`` carries nothing, so the model cannot express a graded approval and a
    reader cannot mistake one for clearance. ``suspected-inversion`` must carry a verbatim
    quote, which is checked against the issue body: a finding the checker cannot ground in
    the text it was given is rejected rather than posted.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = Field(description="Verdict format version. Always 1.")
    verdict: Literal["no-objection", "suspected-inversion"] = Field(
        description="no-objection: nothing in the issue hands the consuming repository a switch. suspected-inversion: something does.",
    )
    quote: str | None = Field(
        default=None,
        min_length=1,
        description="Verbatim span from the issue body carrying the proposal. Required for suspected-inversion, forbidden otherwise.",
    )
    who_can_make_it_stand_down: str | None = Field(
        default=None,
        min_length=1,
        description="What the consuming repository would be able to do after the change. Required for suspected-inversion, forbidden otherwise.",
    )
    rationale: str | None = Field(
        default=None,
        min_length=1,
        description="Why that is a switch the repository holds. Required for suspected-inversion, forbidden otherwise.",
    )

    @model_validator(mode="after")
    def _fields_match_verdict(self) -> Self:
        carried = {
            "quote": self.quote,
            "who_can_make_it_stand_down": self.who_can_make_it_stand_down,
            "rationale": self.rationale,
        }
        if self.verdict == "no-objection":
            present = sorted(name for name, value in carried.items() if value is not None)
            if present:
                raise ValueError(f"REJECTED: a no-objection verdict must carry no finding fields; got {present}. FIX: omit them, or report 'suspected-inversion'.")
            return self
        missing = sorted(name for name, value in carried.items() if value is None)
        if missing:
            raise ValueError(f"REJECTED: a suspected-inversion verdict requires {missing}. FIX: quote the passage verbatim and state what the repository would be able to do.")
        return self

    def grounded_in(self, issue_body: str) -> Self:
        """Reject a finding whose quote is not character-for-character in the issue."""
        if self.quote is not None and self.quote not in issue_body:
            raise ValueError("REJECTED: quote does not appear in the issue body. FIX: copy the passage verbatim; a paraphrase or reconstruction is not evidence.")
        return self


def _gh(args: list[str], *, input_body: str | None = None) -> str:
    result = subprocess.run(["gh", *args], input=input_body, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        _fail(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _issue(repo: str, number: int) -> tuple[str, str]:
    payload = json.loads(_gh(["api", f"repos/{repo}/issues/{number}"]))
    body = payload["body"]
    return str(payload["title"]), "" if body is None else str(body)


def build_prompt(task: Path, manifest: Path, title: str, body: str) -> str:
    """Guides first, then the issue, then the task the issue is measured against."""
    return "\n\n".join(
        [
            load_manifest(manifest),
            "# The issue under review",
            f"## Title\n\n{title}",
            f"## Body\n\n{body}",
            task.read_text(encoding="utf-8"),
        ]
    )


def render_comment(verdict: AlignmentVerdict) -> str:
    """The posted comment. States its own standing so it cannot be cited as a ruling."""
    return "\n".join(
        [
            VERDICT_MARKER,
            "## Alignment check — suspected inversion",
            "",
            "This issue may hand a consuming repository a way to make a rule stand down.",
            "",
            "**Quoted from this issue:**",
            "",
            "> " + "\n> ".join(str(verdict.quote).splitlines()),
            "",
            f"**What the repository could then do:** {verdict.who_can_make_it_stand_down}",
            "",
            f"**Why that is a switch it holds:** {verdict.rationale}",
            "",
            "---",
            "",
            "This is a report, not a decision, and it clears nothing. It does not say the",
            "issue is wrong, and it does not block it. Per [CONTRIBUTING.md](https://github.com/dzackgarza/ai-review-ci/blob/main/CONTRIBUTING.md),",
            "relaxing a rule requires human interactive work, so this needs a ruling from the",
            "owner rather than a reply arguing it through.",
        ]
    )


def _already_reported(repo: str, number: int) -> bool:
    comments = json.loads(_gh(["api", f"repos/{repo}/issues/{number}/comments", "--paginate"]))
    return any(VERDICT_MARKER in str(comment["body"]) for comment in comments)


def check_issue_alignment(repo: str, issue: int, task: Path, manifest: Path) -> None:
    """Weigh one issue against CONTRIBUTING.md; speak only on a suspected inversion.

    Args:
        repo: owner/name of the repository owning the issue.
        issue: Issue number to weigh.
        task: Path to the alignment task prompt.
        manifest: Path to the manifest of documents inlined into the prompt.
    """
    title, body = _issue(repo, issue)
    prompt_path = Path(".issue-alignment-prompt.md")
    prompt_path.write_text(build_prompt(task, manifest, title, body), encoding="utf-8")

    config = OpencodeConfig.from_env()
    for attempt in range(1, config.max_attempts + 1):
        run_opencode(config, prompt_path, attempt)
        if VERDICT_PATH.is_file():
            break
    else:
        _fail(f"no verdict at {VERDICT_PATH} after {config.max_attempts} attempts")

    verdict = AlignmentVerdict.model_validate_json(VERDICT_PATH.read_text(encoding="utf-8")).grounded_in(body)

    if verdict.verdict == "no-objection":
        print(f"Alignment check found no objection on {repo}#{issue}; leaving no trace.")
        return

    if _already_reported(repo, issue):
        print(f"Alignment check already reported on {repo}#{issue}; not repeating.")
        return

    _gh(["api", f"repos/{repo}/issues/{issue}/labels", "--method", "POST", "-f", f"labels[]={RULING_LABEL}"])
    _gh(["api", f"repos/{repo}/issues/{issue}/comments", "--method", "POST", "-F", "body=@-"], input_body=render_comment(verdict))
    print(f"Alignment check flagged {repo}#{issue} for a ruling.")
