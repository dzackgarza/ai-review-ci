from sage.all import ZZ
from sage.rings.ideal import Ideal_generic as Ideal


class DispatchedIdeal(Ideal):
    def _contains_(self, value):
        return value in self.ring().ideal(self.gens())


ideal = DispatchedIdeal(ZZ, [ZZ(3)])
assert ZZ(6) in ideal
assert ZZ(7) not in ideal
