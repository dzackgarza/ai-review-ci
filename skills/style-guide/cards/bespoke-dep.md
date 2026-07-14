# Bespoke Dependency Reinvention

> **Style card `BESPOKE-DEP`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: Application code reimplements what an existing, installed dependency already provides — custom React components when a UI library has them, hand-rolled YAML generation when a YAML library is installed, bespoke string parsing when a parser exists, custom pagination when a framework provides it.
The model perceives the generic, tested solution as "abstraction layer bloat" and the bespoke reinvention as "clean, minimal code."

Examples:
- Custom `AcademicCard.tsx` (~60 LOC) when `card.tsx` exists in the UI inventory.
- Custom `FilterControls.tsx` with hand-rolled popover logic when `select.tsx`, `dropdown-menu.tsx`, and `scroll-area.tsx` already exist.
- Custom `PaginatedScroller.tsx` with bespoke scroll logic when `scroll-area.tsx` + `pagination.tsx` already exist.
- Custom string-concatenated YAML generation when a YAML library is installed.
- Custom hand-rolled AST stringifier when the parser library already provides stringification.

## Preferred construction: REFINE, REPLACE, REFACTOR — migrate the bespoke implementation to use the dependency.
For every custom function or component, ask: "Is there a standard library or installed dependency that already solves this?"
If yes, the custom code is technical debt.
Do not delete the dependency because it is "unused" — it was unused because the bespoke code was written instead of using it.

## Use this pattern when:
- A dependency provides exactly the functionality reimplemented in custom code.
- The custom code is larger, less tested, or less maintainable than the library alternative.
- The library is already installed (the import is missing, not the package).

## Choose a different pattern when:
- The dependency does not exist in the project and adding it would be disproportionate for the use case.
- The custom code has genuinely different requirements that the library does not support.
- The library is deprecated, unmaintained, or has known security issues.

* * *

> **Agent-resistant codebases should be designed so that the easiest code to write is also the hardest code to fake.**

Defaults, fallbacks, mocks, skips, helper proofs, string errors, and local QC gates all make faking easier.
The bridge-burning policies remove those moves from the game.
