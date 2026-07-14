# Inline Large Strings / Prompts Embedded as Code

> **Style card `INLINE-STRINGS`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: Embedding agent prompts, user-facing messages, instruction blocks, or any text longer than ~5 lines directly in source files as string literals.
This treats data (strings) as code, making the text invisible to separate review, unversioned independently, and vulnerable to ad-hoc inline edits that bypass normal review.

```python
# BAD: agent prompt embedded as a string literal in application code
PROMPT = """You are a helpful research assistant.
Analyze the following paper:
{paper_text}

Consider:
1. Main contributions
2. Methodology
3. Limitations

Provide a structured summary with citations.
"""
```

## Preferred construction: Extract all non-code strings to a standard data file (TOML, YAML, JSON) keyed by label.
Load them at runtime via a library.
The data file is the reviewed, diffable artifact; the code is a thin accessor.

```toml
# prompts.toml — reviewed artifact, independently versioned
[paper_analysis]
template = """
You are a helpful research assistant.
Analyze the following paper:
{paper_text}

Consider:
1. Main contributions
2. Methodology
3. Limitations

Provide a structured summary with citations.
"""
```

```python
# ## Preferred construction: load from config, strings are data not code
import tomllib
with open("prompts.toml", "rb") as f:
    prompts = tomllib.load(f)
prompt = prompts["paper_analysis"]["template"].format(paper_text=paper_text)
```

## Use this pattern when:
- The string is an agent prompt, instruction block, user-facing message, or any text that is primarily data rather than code logic.
- The string exceeds ~5 lines or contains structured multi-part instructions.
- The string would benefit from independent review, versioning, or editing by non-developers.

## Choose a different pattern when:
- The string is a short label, error message, or single-line log format (< 5 lines, no structured sub-instructions).
- The string is part of a test assertion where proximity to the assertion logic matters for readability.
