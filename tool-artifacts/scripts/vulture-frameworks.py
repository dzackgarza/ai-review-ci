# /// script
# requires-python = ">=3.14"
# dependencies = ["vulture"]
# ///

"""Run Vulture with scope-local declarations of external framework dispatch."""

import ast
import sys

from vulture.config import make_config
from vulture.core import Vulture


class FrameworkVulture(Vulture):
    """Recognize protocol declarations without globally whitelisting their names."""

    def visit(self, node: ast.AST) -> None:
        root_node = node
        if isinstance(node, ast.Module):
            self.protocol_arguments: set[tuple[int, int]] = set()
            self.framework_classes: set[int] = set()
            self.framework_methods: set[int] = set()
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

            test_classes = {"unittest.TestCase", "unittest.case.TestCase"}
            ideal_classes = {"sage.rings.ideal.Ideal_generic"}
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                bases = {qualified(base) for base in node.bases}
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
    checker = FrameworkVulture(
        verbose=config["verbose"],
        ignore_names=config["ignore_names"],
        ignore_decorators=config["ignore_decorators"],
    )
    checker.scavenge(config["paths"], exclude=config["exclude"])
    return checker.report(
        min_confidence=config["min_confidence"],
        sort_by_size=config["sort_by_size"],
        make_whitelist=config["make_whitelist"],
    )


if __name__ == "__main__":
    sys.exit(main())
