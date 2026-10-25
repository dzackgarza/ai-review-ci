from collections.abc import Sequence
from typing import BinaryIO, TypedDict

class Config(TypedDict):
    verbose: bool
    ignore_names: list[str]
    ignore_decorators: list[str]
    paths: list[str]
    exclude: list[str]
    min_confidence: int
    sort_by_size: bool
    make_whitelist: bool

def make_config(argv: Sequence[str] | None = ..., tomlfile: BinaryIO | None = ...) -> Config: ...
