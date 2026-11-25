# ok: py-no-any-type
from typing import Any


class Modules:
    # ok: py-no-any-type
    def __eq__(self, other: Any) -> bool:
        return other is self

    # ok: py-no-any-type
    def __contains__(self, item: Any) -> bool:
        return item is self

    # ruleid: py-no-any-type
    def coerce(self, value: Any) -> int:
        return 0
