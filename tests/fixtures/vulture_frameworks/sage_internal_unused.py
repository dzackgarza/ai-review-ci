from sage.rings.ideal import Ideal_generic


class SpecializedIdeal(Ideal_generic):
    def _contains_(self, value):
        def discarded_callback_local():
            return 17

        return value in self.ring().ideal(self.gens())


SpecializedIdeal
