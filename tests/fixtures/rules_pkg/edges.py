from .target import leaf


def deco(function):
    return function


@deco
def decorated():
    return leaf()


@deco()
def decorated_with_call():
    return leaf()


async def async_function():
    return leaf()


if True:

    def branch():
        return leaf()

else:

    def branch():
        return leaf()
