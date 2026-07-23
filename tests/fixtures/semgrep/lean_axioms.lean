-- Fixture: no axiom declarations in library roots.
-- # ruleid: lean-no-axiom
axiom torelli_statement : True

-- # ok: lean-no-axiom
theorem proved_statement : True := trivial
