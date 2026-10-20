import rules_pkg.target
import rules_pkg.target as target
from rules_pkg.target import leaf as absolute_leaf

from . import target as relative_target
from .target import Widget
from .target import leaf as run_leaf


def use_plain_import():
    return rules_pkg.target.leaf()


def use_aliased_import():
    return target.leaf()


def use_absolute_symbol():
    return absolute_leaf()


def use_from_module():
    return relative_target.leaf()


def use_from_symbol():
    return run_leaf()


def use_class():
    return Widget()
