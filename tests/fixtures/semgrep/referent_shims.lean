-- Fixture: engineering shims graduated to mathematical placement
-- (lean-lattices referent audit, #309).
namespace Fixture

-- # ruleid: lean-shim-suffix-decl
structure DiscrepancyData where
  coeff : Nat

-- # ok: lean-shim-suffix-decl
structure Discrepancy where
  coeff : Nat

-- # ruleid: lean-has-wrapper
structure HasSignature (L : Type) where
  pos : Nat

-- # ok: lean-has-wrapper
def signature (n : Nat) : Nat × Nat × Nat := (n, n, n)

structure Square where
  -- # ruleid: lean-nonempty-field
  cell : Nonempty (Nat × Nat)

-- # ok: lean-nonempty-field
theorem cellUse (h : Nonempty (Fin 2)) : True := trivial

structure Properness where
  -- # ruleid: lean-bare-prop-field
  proper : Prop

structure HonestProperness where
  -- # ok: lean-bare-prop-field
  proper : ∀ n : Nat, n = n

inductive Decision where
  -- # ruleid: lean-epistemic-on-math-surface
  | unknown : Decision
  -- # ok: lean-epistemic-on-math-surface
  | refuted : Decision

end Fixture
