from unittest import TestCase


class HiddenHelper(TestCase):
    __test__ = False


class Ordinary:
    def _contains_(self, unused_value):
        return True


def ordinary_callback(kind, error, traceback):
    return 19


ordinary_callback(1, 2, 3)
Ordinary()


class InvalidContext:
    def __exit__(self, kind, error, traceback, surplus):
        return False


InvalidContext()
