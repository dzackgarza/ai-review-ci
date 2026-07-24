-- Fixture: the vacuous existential-implication misformalisation
-- (`∃ x, P x → Q` instead of `∃ x, P x ∧ Q`).
namespace Fixture

-- # ruleid: lean-exists-implication
theorem bad : ∃ n : Nat, 0 < n → n = n := ⟨0, fun _ => rfl⟩

-- # ok: lean-exists-implication
theorem honest : ∃ n : Nat, 0 < n ∧ n = n := ⟨1, by omega, rfl⟩

-- # ok: lean-exists-implication
theorem functionBinder : ∃ f : Nat → Nat, f 0 = 0 := ⟨id, rfl⟩

-- # ok: lean-exists-implication
theorem plainForall : ∀ n : Nat, 0 < n → 0 ≤ n := fun _ _ => Nat.zero_le _

-- # ok: lean-exists-implication
theorem boundedExists : ∃ n ∈ ({1} : Set Nat), n = 1 := ⟨1, rfl, rfl⟩

end Fixture
