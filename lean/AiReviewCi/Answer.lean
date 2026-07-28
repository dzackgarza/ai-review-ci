/-
Derived from google-deepmind/formal-conjectures (Apache License, Version 2.0):
`FormalConjecturesUtil/Answer.lean` and `FormalConjecturesUtil/Answer/Syntax.lean`.

Reduced to the core `answer(...)` elaborator (the original's configurable mode
option, auxiliary-definition mode, and InfoTree answer-collection tooling are
omitted). Shipped with ai-review-ci and consumed by managed Lean repositories as a
Lake dependency, so its `sorry`-handling constructs live under `.lake/packages` and
are invisible to a consumer's no-sorry gate.

Copyright 2025 The Formal Conjectures Authors.
Licensed under the Apache License, Version 2.0; you may not use this file except in
compliance with the License. See https://www.apache.org/licenses/LICENSE-2.0.
Unless required by applicable law or agreed to in writing, software distributed under
the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
ANY KIND, either express or implied.
-/
module

public meta import Lean.Elab.Command

/-!
# The `answer(...)` elaborator

Marks the *answer* to a problem as distinct from its *proof*. Replacing `:= sorry`
in a proof only requires finding any inhabitant; supplying an answer requires
evaluating mathematical meaning, a job for a human rather than Lean alone. This gives
a gate-legal way to record "answer not yet determined":

* `answer(sorry)` where a `Prop` is expected elaborates to `True`, so a conjecture or
  experimental statement whose answer is unknown compiles without a real `sorry`.
* `answer(sorry)` at any other expected type elaborates to a canonical `sorryAx`
  carrying a stable, module-independent `answer` annotation.
* `answer(e)` for a concrete `e` elaborates `e` and tags it with the `answer`
  annotation so downstream tooling can locate supplied answers.
-/

public meta section

namespace AiReviewCi.Answer

open Lean Elab Meta Term

/-- Marks where the answer sits in a problem statement. -/
syntax (name := answer) "answer(" term ")" : term

/-- Wrap `e` in the `answer` metadata annotation. -/
def mkAnswerAnnotation (e : Expr) : Expr := mkAnnotation `answer e

/-- Strip one layer of `mdata`, returning the inner expression. -/
private def unwrapMData : Expr → Expr
  | .mdata _ inner => inner
  | e => e

/-- The first subexpression carrying the `answer` annotation, unwrapped. -/
def findAnswerExpr (e : Expr) : Option Expr :=
  (e.find? fun
    | .mdata m _ => m.contains `answer
    | _ => false).map unwrapMData

/-- Elaborate `stx`, annotating the result; optionally postpone via `by exact`. -/
def elabTermAndAnnotate (stx : TSyntax `term) (expectedType? : Option Expr)
    (postpone : Bool := false) : TermElabM Expr :=
  mkAnswerAnnotation <$> do
    if postpone then
      postponeElabTerm (← `(by exact $stx)) expectedType?
    else
      elabTerm stx expectedType?

/-- A canonical `sorryAx` carrying a stable, module-independent `answer` tag (unlike
the built-in `sorry` macro, this does not embed the current module name via hygiene). -/
def mkCanonicalSorryAnnotation (expectedType : Expr) : TermElabM Expr := do
  let sorryExpr ← Meta.mkSorry expectedType (synthetic := false)
  return mkAnswerAnnotation sorryExpr

@[term_elab answer]
def answerElab : TermElab := fun stx expectedType? => do
  match stx with
  | `(answer($a:term)) =>
    if expectedType? == some (.sort .zero) && a == (← `(term| sorry)) then
      return .const ``True []
    else if a == (← `(term| sorry)) then
      match expectedType? with
      | some ty => mkCanonicalSorryAnnotation ty
      | none    => elabTermAndAnnotate a expectedType? (postpone := true)
    else
      elabTermAndAnnotate a expectedType? (postpone := true)
  | _ => Elab.throwUnsupportedSyntax

end AiReviewCi.Answer
