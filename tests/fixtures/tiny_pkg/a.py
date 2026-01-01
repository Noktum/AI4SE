import json

from . import b
from .b import helper as run_helper


def public_api(value):
    return run_helper(value)


async def render(value):
    formatter = b.Formatter()
    return json.dumps(formatter.format(value))
