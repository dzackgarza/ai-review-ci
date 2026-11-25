import typing

# ruleid: py-no-any-type
from typing import Any, cast
# ruleid: py-no-any-type
from typing_extensions import Any as AnyType
# ok: py-no-any-type
from typing import Anything, Protocol


# ruleid: py-no-any-type
def loose(value: typing.Any) -> int:
    return cast(int, value)


# ruleid: py-no-object-return
def opaque(value: int) -> object:
    return value


# ok: py-no-object-return
def concrete(value: int) -> int:
    return value


# ruleid: py-no-type-ignore
total: int = opaque(1)  # type: ignore
# ruleid: py-no-type-ignore
other: int = opaque(2)  #type:ignore[assignment]
# ok: py-no-type-ignore
kind = "type annotations are checked"
