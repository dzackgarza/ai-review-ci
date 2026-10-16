from unittest import TestCase


class Collected(TestCase):
    def test_framework_dispatch(self):
        self.assertEqual(2 + 3, 5)

    def abandoned_helper(self):
        def discarded_local():
            return 91

        return 12
