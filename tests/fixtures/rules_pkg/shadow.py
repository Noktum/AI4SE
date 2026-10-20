from .target import leaf


def parameter_shadow(leaf):
    return leaf()


def assignment_shadow():
    leaf = lambda: None
    return leaf()


def attribute_shadow(obj):
    return obj.method()
