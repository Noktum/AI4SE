def leaf():
    return "leaf"


class Widget:
    def method(self):
        return self.helper()

    def helper(self):
        return "helper"


def same_module():
    return leaf()


def outer():
    def inner():
        return 1

    def caller():
        return inner()

    return caller()
