# /// script
# requires-python = ">=3.14"
# dependencies = ["vulture"]
# ///

"""Run Vulture with scope-local declarations of external framework dispatch."""

import ast
import sys

from vulture.config import make_config
from vulture.core import Vulture


class SourceModules(Vulture):
    """Collect only modules selected by Vulture's own path/exclusion rules."""

    def __init__(self) -> None:
        super().__init__()
        self.modules: dict[str, tuple[ast.Module, bool]] = {}

    def visit(self, node: ast.AST) -> None:
        if isinstance(node, ast.Module):
            path = self.filename
            parts = [] if path.stem == "__init__" else [path.stem]
            directory = path.parent
            while (directory / "__init__.py").is_file():
                parts.insert(0, directory.name)
                directory = directory.parent
            self.modules[".".join(parts)] = node, path.stem == "__init__"


def model_classes(modules: dict[str, tuple[ast.Module, bool]]) -> set[str]:
    """Resolve model inheritance through imported aliases and reexports."""
    aliases: dict[str, str] = {}
    bases: dict[str, list[str]] = {}
    for module, (tree, is_package) in modules.items():
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                package = module.split(".") if is_package else module.split(".")[:-1]
                if node.level:
                    package = package[: len(package) - node.level + 1]
                else:
                    package = []
                owner = ".".join([*package, *([node.module] if node.module else [])])
                for alias in node.names:
                    aliases[f"{module}.{alias.asname or alias.name}"] = f"{owner}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    aliases[f"{module}.{alias.asname or alias.name.split('.')[0]}"] = alias.name if alias.asname else alias.name.split(".")[0]
            elif isinstance(node, ast.ClassDef):
                bases[f"{module}.{node.name}"] = [f"{module}.{ast.unparse(base)}" for base in node.bases]

    def resolve(name: str) -> str:
        visited: set[str] = set()
        while name not in visited:
            visited.add(name)
            matching = next((alias for alias in aliases if name == alias or name.startswith(alias + ".")), None)
            if matching is None:
                break
            name = aliases[matching] + name[len(matching) :]
        return name

    recognized = {"pydantic.BaseModel", "pydantic.main.BaseModel"}
    while True:
        additions = {name for name, parents in bases.items() if any(resolve(parent) in recognized for parent in parents)}
        if additions <= recognized:
            return recognized | {name for name in aliases if resolve(name) in recognized}
        recognized.update(additions)


class FrameworkVulture(Vulture):
    """Recognize protocol declarations without globally whitelisting their names."""

    recognized_models: set[str] = set()

    def visit(self, node: ast.AST) -> None:
        root_node = node
        if isinstance(node, ast.Module):
            self.protocol_arguments: set[tuple[int, int]] = set()
            self.framework_classes: set[int] = set()
            self.framework_methods: set[int] = set()
            self.framework_fields: set[tuple[int, int]] = set()
            tree = node
            imported: dict[str, str] = {}
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported[alias.asname or alias.name] = alias.name
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported[alias.asname or alias.name] = f"{node.module}.{alias.name}"

            def qualified(node: ast.AST) -> str:
                match node:
                    case ast.Name(id=name):
                        return imported.get(name, name)
                    case ast.Attribute(value=value, attr=name):
                        return f"{qualified(value)}.{name}"
                    case _:
                        return ""

            path = self.filename
            parts = [] if path.stem == "__init__" else [path.stem]
            directory = path.parent
            while (directory / "__init__.py").is_file():
                parts.insert(0, directory.name)
                directory = directory.parent
            module = ".".join(parts)
            apps = {
                target.id
                for statement in tree.body
                if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call) and qualified(statement.value.func) in {"cyclopts.App", "cyclopts.core.App"}
                for target in statement.targets
                if isinstance(target, ast.Name)
            }
            for declaration in tree.body:
                if isinstance(declaration, ast.FunctionDef):
                    for decorator in declaration.decorator_list:
                        callback = decorator.func if isinstance(decorator, ast.Call) else decorator
                        if isinstance(callback, ast.Attribute) and callback.attr == "command" and isinstance(callback.value, ast.Name) and callback.value.id in apps:
                            self.framework_methods.add(declaration.lineno)
            html_classes = {"html.parser.HTMLParser"}
            test_classes = {"unittest.TestCase", "unittest.case.TestCase"}
            ideal_classes = {"sage.rings.ideal.Ideal_generic"}
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                bases = {qualified(base) for base in node.bases}
                if node in tree.body and f"{module}.{node.name}" in self.recognized_models:
                    for member in node.body:
                        if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name) and not member.target.id.startswith("_"):
                            annotation = member.annotation.value if isinstance(member.annotation, ast.Subscript) else member.annotation
                            if qualified(annotation) not in {"typing.ClassVar", "ClassVar"}:
                                self.framework_fields.add((member.target.lineno, member.target.col_offset))
                if bases & html_classes:
                    html_classes.add(node.name)
                    self.framework_methods.update(
                        member.lineno
                        for member in node.body
                        if isinstance(member, ast.FunctionDef)
                        and member.name
                        in {
                            "handle_starttag",
                            "handle_startendtag",
                            "handle_endtag",
                            "handle_data",
                            "handle_entityref",
                            "handle_charref",
                            "handle_comment",
                            "handle_decl",
                            "handle_pi",
                            "unknown_decl",
                        }
                    )
                excluded_test = any(
                    isinstance(member, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "__test__" for target in member.targets)
                    and isinstance(member.value, ast.Constant)
                    and member.value.value is False
                    for member in node.body
                )
                if bases & test_classes and not excluded_test and (self.filename.name.startswith("test_") or self.filename.name.endswith("_test.py")):
                    self.framework_classes.add(node.lineno)
                    test_classes.add(node.name)
                if bases & ideal_classes:
                    ideal_classes.add(node.name)
                    self.framework_methods.update(member.lineno for member in node.body if isinstance(member, ast.FunctionDef) and member.name == "_contains_")
                for member in node.body:
                    if isinstance(member, ast.FunctionDef) and member.name in {"__exit__", "__aexit__"}:
                        arguments = [*member.args.posonlyargs, *member.args.args]
                        if len(arguments) == 4:
                            self.protocol_arguments.update((arg.lineno, arg.col_offset) for arg in arguments[1:])
        super().visit(root_node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store) and (node.lineno, node.col_offset) in self.framework_fields:
            return
        super().visit_Name(node)

    def visit_arg(self, node: ast.arg) -> None:
        if (node.lineno, node.col_offset) in self.protocol_arguments:
            return
        super().visit_arg(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.lineno in self.framework_classes:
            return
        super().visit_ClassDef(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.lineno in self.framework_methods:
            return
        super().visit_FunctionDef(node)


def main() -> int:
    config = make_config()
    sources = SourceModules()
    sources.scavenge(config["paths"], exclude=config["exclude"])
    checker = FrameworkVulture(
        verbose=config["verbose"],
        ignore_names=config["ignore_names"],
        ignore_decorators=config["ignore_decorators"],
    )
    checker.recognized_models = model_classes(sources.modules)
    checker.scavenge(config["paths"], exclude=config["exclude"])
    return checker.report(
        min_confidence=config["min_confidence"],
        sort_by_size=config["sort_by_size"],
        make_whitelist=config["make_whitelist"],
    )


if __name__ == "__main__":
    sys.exit(main())
