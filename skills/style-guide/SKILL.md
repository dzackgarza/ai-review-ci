---
name: style-guide
description: Load before implementing or refactoring code that reaches a governed pattern family. Routes by language and concern to the canonical preferred construction, bad-pattern examples, rearchitecture, and proof obligations.
---
# Implementation Style Guide

Start by selecting the implementation language, then load only the relevant foundation card from the [[style-guide/references/style-guide-index|style-guide index]].

- [[style-guide/style-guide-python/SKILL|Python]]
- [[style-guide/style-guide-typescript/SKILL|TypeScript and Bun]]
- [[style-guide/style-guide-bash/SKILL|Bash]]
- [[style-guide/style-guide-sage/SKILL|SageMath stub]]

Each card is canonical for both paths:

- Before implementation: use its preferred construction and language profile.
- After a `POLICY.*` finding: use its bad-pattern analysis, language-specific rearchitecture, and proof obligation.

Do not maintain a separate remediation interpretation. [[policy-index/SKILL|policy-index]] maps findings into these cards; [[fixing-slop/SKILL|fixing-slop]] governs the repair process around them.
