---
name: style-guide
description: Load before implementing or refactoring code that reaches a governed pattern family. Routes to the canonical preferred construction, bad-pattern examples, rearchitecture, and proof obligations.
---
# Implementation Style Guide

Read the [[style-guide/references/style-guide-index|style-guide index]] first, then load only the card for the design boundary in scope.

Each card is canonical for both paths:

- Before implementation: use its preferred construction and examples.
- After a `POLICY.*` finding: use its bad-pattern analysis, rearchitecture, and proof obligation.

Do not maintain a separate remediation interpretation. [[policy-index/SKILL|policy-index]] maps findings into these cards; [[fixing-slop/SKILL|fixing-slop]] governs the repair process around them.
