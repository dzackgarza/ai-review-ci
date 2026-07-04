import re
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def iter_skill_markdown_files() -> list[Path]:
    return sorted((ROOT / "skills").rglob("*.md")) + [ROOT / ".github" / "pull_request_template.md"]


def iter_links(path: Path) -> list[tuple[int, str]]:
    links: list[tuple[int, str]] = []
    in_fenced_block = False
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        if line.startswith("```"):
            in_fenced_block = not in_fenced_block
            continue
        if in_fenced_block:
            continue
        links.extend((lineno, match.group(1)) for match in MARKDOWN_LINK.finditer(line))
    return links


def test_skill_markdown_links_are_checkout_relative() -> None:
    failures: list[str] = []

    for path in iter_skill_markdown_files():
        for lineno, href in iter_links(path):
            if href.startswith("#"):
                continue
            parsed = urlparse(href)
            if parsed.scheme == "file":
                failures.append(f"{path.relative_to(ROOT)}:{lineno}: machine-local file URL: {href}")
                continue
            if parsed.scheme:
                continue
            target_path = href.split("#", maxsplit=1)[0]
            if not target_path:
                continue
            if target_path.startswith("/"):
                failures.append(f"{path.relative_to(ROOT)}:{lineno}: absolute local path link: {href}")
                continue
            target = (path.parent / unquote(target_path)).resolve(strict=False)
            if not target.exists():
                failures.append(f"{path.relative_to(ROOT)}:{lineno}: broken relative link: {href}")

    assert not failures, "\n".join(failures)
