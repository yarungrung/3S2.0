import ast
import json
import pathlib


NOTEBOOK = pathlib.Path(r"C:\Users\user\Downloads\3S程式運算加入Gemini版.ipynb")


def read_notebook(path: pathlib.Path) -> dict:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return json.loads(raw.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError("Could not decode notebook as JSON.")


def name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = name_of(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return name_of(node.func)
    if isinstance(node, ast.Subscript):
        return name_of(node.value)
    return ""


def collect_imports(tree: ast.Module) -> list[str]:
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.extend(f"{module}.{alias.name}" for alias in node.names)
    return imports


def collect_assignments(tree: ast.Module) -> list[str]:
    names = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                text = name_of(target)
                if text:
                    names.append(text)
    return names


def collect_calls(tree: ast.Module) -> list[str]:
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            text = name_of(node.func)
            if text:
                calls.append(text)
    return sorted(set(calls))


def main() -> None:
    nb = read_notebook(NOTEBOOK)
    for index, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        parse_source = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("!")
        )
        try:
            tree = ast.parse(parse_source)
        except SyntaxError as exc:
            print(f"\nCELL {index:02d}: parse error {exc}")
            continue
        funcs = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
        imports = collect_imports(tree)
        assignments = collect_assignments(tree)[:80]
        calls = collect_calls(tree)[:140]
        print(f"\nCELL {index:02d} lines={len(source.splitlines())}")
        print("FUNCTIONS:", funcs)
        print("CLASSES:", classes)
        print("IMPORTS:", imports)
        print("ASSIGNMENTS:", assignments)
        print("CALLS:", calls)


if __name__ == "__main__":
    main()
