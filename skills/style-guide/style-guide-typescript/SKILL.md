---
name: style-guide-typescript
description: Load with the style guide when implementing or repairing TypeScript or Bun. Supplies TypeScript constructions for schemas, discriminated variants, errors, and proof.
---
# TypeScript and Bun Style Profile

Load the relevant foundation card from the [[style-guide/references/style-guide-index|style-guide index]], then apply these constructions:

- Parse owned configuration and boundary input once with Zod schemas into total typed values before application logic runs.
- Model ordinary variants as discriminated unions and dispatch exhaustively with `switch` or an exhaustive match helper; do not let thrown failures select normal behavior.
- Keep unexpected failures visible. Translate a specific external failure at the owned boundary only into an explicit typed result/outcome.
- Do not use `any`, broad `unknown` escapes, stringly error channels, optional core state, or boolean mode flags where the domain has named variants.
- Prove behavior through the real TypeScript/Bun boundary with semantic assertions and real project fixtures; mocks do not discharge boundary proof.
