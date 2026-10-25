import unittest as testing
from unittest import TestCase as Case


class Resource:
    def __enter__(self):
        return 37

    def __exit__(self, kind, error, traceback):
        return False


class Root(Case):
    def test_resource(self):
        with Resource() as value:
            self.assertEqual(value, 37)


class Descendant(Root):
    def test_arithmetic(self):
        self.assertEqual(6 * 7, 42)


class Qualified(testing.TestCase):
    def test_truth(self):
        self.assertEqual("dispatch".upper(), "DISPATCH")
