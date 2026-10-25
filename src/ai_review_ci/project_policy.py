"""Resolve owner-authorized scanner exceptions from live project metadata."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict

from ai_review_ci.doctor import _github_repo


class RepositoryTopics(BaseModel):
    model_config = ConfigDict(strict=True)
    names: list[str]


def ast_grep_arguments(target: Path) -> tuple[str, ...]:
    identity = subprocess.run(["git", "remote"], cwd=target, capture_output=True, text=True, check=False)
    if identity.returncode != 0:
        # No established repository identity can authorize a project exception.
        return ()
    remotes = identity.stdout.splitlines()
    if "origin" not in remotes:
        return ()
    remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=target, text=True).strip()
    repository = _github_repo(remote)
    if not repository:
        return ()
    request = Request(
        f"https://api.github.com/repos/{repository}/topics",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ai-review-ci"},
    )
    with urlopen(request, timeout=30) as response:
        topics = RepositoryTopics.model_validate_json(response.read())
    if "in-progress-database" in topics.names:
        print(f"Project {repository}: in-progress-database exempts no-field-default.", file=sys.stderr)
        return ("--off=no-field-default",)
    return ()


if __name__ == "__main__":
    for argument in ast_grep_arguments(Path.cwd()):
        print(argument)
