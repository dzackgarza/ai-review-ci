from math import *


def parse(value):
    try:
        return int(value)
    except:
        return None


def add(value, items=[]):
    items.append(value)
    return items


def todo(x):
    raise NotImplementedError('TODO')
