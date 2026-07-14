---
name: style-guide-python
description: Load with the style guide when implementing or repairing Python. Supplies Python constructions for schema validation, explicit state, errors, and proof.
---
# Python Style Profile

Load the relevant foundation card from the [[style-guide/references/style-guide-index|style-guide index]], then apply these constructions:

- Validate owned configuration and boundary input once with Pydantic models or explicit dataclasses; construct total validated state before application logic runs.
- Represent ordinary variants with enums, dataclasses, or discriminated Pydantic models; use exhaustive `match` over domain states rather than exception-selected flow.
- Keep unexpected failures visible. Translate one specific external exception at the owned boundary only into a typed domain outcome.
- Use explicit type annotations and structured exceptions/results. Do not use `Any`, broad dictionaries, `hasattr`, or sentinel values to evade the model.
- Prove behavior through the real Python boundary with project-owned fixtures and semantic assertions; do not replace it with mocks or helper-only proof.
