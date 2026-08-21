"""Direct boolean parameters are findings; nested boolean types are clean."""

import builtins
from collections.abc import Callable


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
def return_only() -> bool:
    return True


# ok: no-boolean-param
def boolean_constructor(thunk: Callable[[], bool] = bool) -> None:
    pass
