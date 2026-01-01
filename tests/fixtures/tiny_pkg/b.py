def normalize(value):
    return value.strip().lower()


def helper(value):
    return normalize(value)


class Formatter:
    def format(self, value):
        return self._wrap(helper(value))

    def _wrap(self, value):
        return f"[{value}]"
