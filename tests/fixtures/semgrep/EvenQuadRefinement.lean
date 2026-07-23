-- Fixture: quadratic refinements require exact divisibility witnesses,
-- never integer truncating division.
-- # ruleid: lean-truncating-division-on-forms
def quadRefinement (n : Nat) : Nat := n / 2

-- # ok: lean-truncating-division-on-forms
def quadraticForm (n : Nat) (h : 2 ∣ n) : Nat := Nat.div n 2
