-- Fixture: isotropy means b(x,x) = 0, never 2-torsion.
def isIsotropicWrong (x : Nat) : Prop :=
  -- # ruleid: lean-isotropy-as-torsion
  2 • x = 0

def isIsotropic (b : Nat → Nat → Int) (x : Nat) : Prop :=
  -- # ok: lean-isotropy-as-torsion
  b x x = 0
