"""Direct boolean parameters are findings; nested boolean types are clean."""

import builtins
from collections.abc import Callable
import typing
from typing import Optional, Union


# ruleid: no-boolean-param
def annotated(flag: bool) -> None:
    pass


# ruleid: no-boolean-param
def qualified(flag: builtins.bool) -> None:
    pass


# ruleid: no-boolean-param
def forward(flag: "bool") -> None:
    pass


# ruleid: no-boolean-param
def annotated_default(flag: bool = False) -> None:
    pass


# ruleid: no-boolean-param
def qualified_default(flag: builtins.bool = False) -> None:
    pass


# ruleid: no-boolean-param
def forward_default(flag: "bool" = False) -> None:
    pass


# ruleid: no-boolean-param
def optional(flag: bool | None) -> None:
    pass


# ruleid: no-boolean-param
def optional_default(flag: bool | None = None) -> None:
    pass


# ruleid: no-boolean-param
def union_member(flag: str | bool | None) -> None:
    pass


# ruleid: no-boolean-param
def qualified_optional(flag: builtins.bool | None) -> None:
    pass


# ruleid: no-boolean-param
def forward_optional(flag: "bool" | None) -> None:
    pass


# ruleid: no-boolean-param
def generic_optional(flag: Optional[bool]) -> None:
    pass


# ruleid: no-boolean-param
def qualified_generic_optional(flag: typing.Optional[bool] = None) -> None:
    pass


# ruleid: no-boolean-param
def generic_union(flag: Union[str, bool, None]) -> None:
    pass


# ruleid: no-boolean-param
def qualified_generic_union(flag: typing.Union[None, bool]) -> None:
    pass


# ruleid: no-boolean-param
def forward_union(flag: "bool | None") -> None:
    pass


# ruleid: no-boolean-param
def parenthesized(flag: (bool)) -> None:
    pass


# ruleid: no-boolean-param
def inferred_true(flag=True) -> None:
    pass


# ruleid: no-boolean-param
def inferred_false(flag=False) -> None:
    pass


# ok: no-boolean-param
def callable_result(thunk: Callable[[], tuple[bool, str]]) -> None:
    pass


# ok: no-boolean-param
def tuple_items(values: tuple[bool, str]) -> None:
    pass


# ok: no-boolean-param
def callable_optional_result(thunk: Callable[[], bool | None]) -> None:
    pass


# ok: no-boolean-param
def tuple_optional_items(values: tuple[bool | None, str]) -> None:
    pass


# ok: no-boolean-param
def generic_optional_callable(thunk: Optional[Callable[[], bool]]) -> None:
    pass


# ok: no-boolean-param
def generic_union_tuple(values: Union[tuple[bool, str], None]) -> None:
    pass


# ok: no-boolean-param
def return_only() -> bool:
    return True


# ok: no-boolean-param
def boolean_constructor(thunk: Callable[[], bool] = bool) -> None:
    pass
