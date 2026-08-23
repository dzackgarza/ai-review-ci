"""Stubs for the panflute surface this project uses.

panflute ships no `py.typed` marker, so mypy cannot see through it. The shared
QC config sets `mypy_path = typings`, which is the place for exactly this.

These are narrow on purpose: only the constructors and functions `qualc` and
the importer call, with the signatures panflute actually declares. Nothing here
is a silencing shim — mypy checks calls against these declarations, so a wrong
argument is still an error.
"""

from typing import Any

class Element:
    content: Any
    def walk(self, action: Any, doc: Any = ...) -> Any: ...

class Inline(Element): ...
class Block(Element): ...

class Doc(Element):
    metadata: Any
    def __init__(
        self,
        *args: Block,
        metadata: dict[str, Any] = ...,
        format: str = ...,
        api_version: tuple[int, ...] = ...,
    ) -> None: ...

class Plain(Block):
    def __init__(self, *args: Inline) -> None: ...

class Para(Block):
    def __init__(self, *args: Inline) -> None: ...

class Header(Block):
    level: int
    identifier: str
    def __init__(self, *args: Inline, level: int = ..., identifier: str = ...) -> None: ...

class Div(Block):
    identifier: str
    classes: list[str]
    attributes: dict[str, str]
    def __init__(
        self,
        *args: Block,
        identifier: str = ...,
        classes: list[str] = ...,
        attributes: dict[str, str] = ...,
    ) -> None: ...

class ListItem(Element):
    def __init__(self, *args: Block) -> None: ...

class BulletList(Block):
    def __init__(self, *args: ListItem) -> None: ...

class OrderedList(Block):
    def __init__(self, *args: ListItem, start: int = ..., style: str = ..., delimiter: str = ...) -> None: ...

class Str(Inline):
    text: str
    def __init__(self, text: str) -> None: ...

class Space(Inline):
    def __init__(self) -> None: ...

class Emph(Inline):
    def __init__(self, *args: Inline) -> None: ...

class Strong(Inline):
    def __init__(self, *args: Inline) -> None: ...

class Math(Inline):
    text: str
    format: str
    def __init__(self, text: str, format: str = ...) -> None: ...

class Code(Inline):
    text: str
    def __init__(
        self,
        text: str,
        identifier: str = ...,
        classes: list[str] = ...,
        attributes: dict[str, str] = ...,
    ) -> None: ...

class Link(Inline):
    url: str
    title: str
    def __init__(self, *args: Inline, url: str = ..., title: str = ...) -> None: ...

class Image(Inline):
    url: str
    title: str
    def __init__(self, *args: Inline, url: str = ..., title: str = ...) -> None: ...

class Span(Inline):
    classes: list[str]
    attributes: dict[str, str]
    def __init__(
        self,
        *args: Inline,
        identifier: str = ...,
        classes: list[str] = ...,
        attributes: dict[str, str] = ...,
    ) -> None: ...

class Citation(Element):
    id: str
    mode: str

class Cite(Inline):
    citations: list[Citation]
    def __init__(self, *args: Inline, citations: list[Citation] = ...) -> None: ...

class Caption(Element):
    def __init__(self, *args: Block) -> None: ...

class Figure(Block):
    caption: Caption
    def __init__(
        self,
        *args: Block,
        caption: Caption = ...,
        identifier: str = ...,
        classes: list[str] = ...,
        attributes: dict[str, str] = ...,
    ) -> None: ...

class RawBlock(Block):
    text: str
    def __init__(self, text: str, format: str = ...) -> None: ...

class RawInline(Inline):
    text: str
    format: str
    def __init__(self, text: str, format: str = ...) -> None: ...

def stringify(element: Element, newlines: bool = ...) -> str: ...
def convert_text(
    text: str | Element | list[Element],
    input_format: str = ...,
    output_format: str = ...,
    standalone: bool = ...,
    extra_args: list[str] | None = ...,
    pandoc_path: str | None = ...,
) -> Any: ...
