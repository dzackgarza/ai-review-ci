# Code Verbosity and Complexity

> **Style card `CODE-VERBOSITY`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: Code that is longer, noisier, or more abstract than it needs to be — filler documentation, verbose comments that restate the obvious, unnecessary intermediate variables, verbose variable names ("currentUserAuthenticationStatusBoolean"), "just in case" dead code, excessive defensive checks on already-validated data, boilerplate explosion (one trivial operation = one file/class), and over-abstraction (interface with one implementation, factory with one product, strategy pattern that never diverges).

## Preferred construction: Delete the noise.
Every line that carries no proof or instruction burden is a liability:
- Filler docstrings: delete; let the signature and body speak.
- Verbose comments restating the obvious: delete; restructure the code if it is not self-explanatory.
- Unnecessary intermediate variables: inline; keep only if the expression genuinely needs a name.
- Verbose names that obscure intent: replace with short type-signaling names.
- "Just in case" code: delete until a real call site demonstrates the need.
- Defensive checks on already-validated data: delete; validate at the boundary, assert inside.
- Boilerplate abstraction (one-class-per-trivial-operation): inline to a free function or expression.
- Over-abstraction (interface with one impl, factory with one product): delete the abstraction layer until a second caller or implementation exists.

## Use this pattern when:
- The code carries more lines than the logic warrants.
- A reader must scan past filler to find the actual behavior.
- The abstraction exists for hypothetical future variation.

## Choose a different pattern when:
- The verbosity is required by the project's public API contract (e.g., comprehensive docstrings for a published library).
- The defensive check protects against an observed (not hypothetical) upstream invariant violation.
