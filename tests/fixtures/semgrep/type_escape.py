import typing

# ok: py-no-any-type
from typing import Any, TypeAlias, cast
# ok: py-no-any-type
from typing import Anything, Protocol

# ok: py-no-any-type
JsonValue: TypeAlias = Any
# ok: py-no-any-type
type Payload = Any


# ruleid: py-no-any-type
def untyped(value: Any) -> int:
    return cast(int, value)


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
