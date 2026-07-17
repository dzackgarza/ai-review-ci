# Code Within Code / Embedded Cross-Language Programs

> **Style card `CODE-WITHIN-CODE`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A program in language A assembles and executes language B as a string — Python calling `subprocess.run("bash -c '...'")`, shell scripts inlining Perl/Python with `$(python -c '...')`, or any template-like generation where one language builds another inline.
The embedded language is invisible to syntax checking, linting, static analysis, and independent debugging.

```python
# BAD: Python embedding bash as a string
subprocess.run(
    f"ffmpeg -i {input_file} -vf 'scale={width}:{height}' {output_file}",
    shell=True, check=True
)
# The bash is a string — no syntax check, no shellcheck, no debugger
```

Remediation narrative reconstruction: This pattern signals a missing abstraction layer.
Trace through three approximations to find the correct boundary:

**1st approximation — externalize the embedded language into its own file:** Extract the bash into a standalone script.
Python calls the script, not a constructed string.
The script is now syntax-checkable, lintable, and reviewable independently.

```bash
# scripts/transcode.sh — reviewed, shellcheck-passing artifact
#!/usr/bin/env bash
set -euo pipefail
ffmpeg -i "$1" -vf "scale=$2:$3" "$4"
```

```python
# Python calls the script — no string construction
subprocess.run(["scripts/transcode.sh", input_file, str(width), str(height), output_file], check=True)
```

**2nd approximation — lift to ambient workflow:** The Python and bash run sequentially in the same automation context (CI pipeline, Makefile, just recipe).
Call them as separate steps rather than nesting one inside the other.

```yaml
# CI workflow — steps are peers, not nested
steps:
  - name: Prepare metadata
    run: python prepare.py
  - name: Transcode video
    run: bash scripts/transcode.sh
  - name: Upload result
    run: python upload.py
```

**3rd approximation — eliminate the embedded language entirely:** The bash was never needed.
The CI workflow orchestration (or justfile/ Makefile) is the correct abstraction for running sequenced commands.
The Python step does Python work; the shell step does shell work; neither embeds the other.
Each tool operates at its native level, and the workflow definition provides the sequencing.

```yaml
# CI workflow — correct solution: each tool at its own level
steps:
  - run: python process_metadata.py
  - run: ffmpeg ...  # no wrapping script needed either
  - run: python upload_results.py
```

## Use this pattern when:
- Language A constructs language B as a string and executes it (subprocess with shell=True, eval, inline script).
- The embedded code could be its own file with syntax checking and linting.
- The embedding destroys debugging, stack traces, or error reporting for the inner language.

## Choose a different pattern when:
- The inner language is a genuine data query (SQL, XPath, JMESPath) where the query string is data, not control flow.
- The embedding uses a safe, non-executing template engine (Jinja2, Mustache) that produces static output files, not executed code.

* * *

<a id="remediation-existence--truthy--shape-as-proof"></a>
