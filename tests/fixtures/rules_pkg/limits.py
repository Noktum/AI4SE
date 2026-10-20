from .target import Widget


class Base:
    def inherited(self):
        return 1


class Child(Base):
    def use_super(self):
        return super().inherited()

    def use_self_inherited(self):
        return self.inherited()

    def nested_self(self):
        def inner():
            return self.inherited()

        return inner()

    def use_cls(cls):
        return cls.inherited()


def use_getattr(obj):
    return getattr(obj, "inherited")


def wildcard_import():
    from .target import *

    return leaf()
