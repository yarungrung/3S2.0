import ast
import json
import pathlib


NOTEBOOK = pathlib.Path(r"C:\Users\user\Downloads\3S程式運算加入Gemini版.ipynb")


def read_notebook(path: pathlib.Path) -> dict:
    """Read a notebook saved with common Jupyter or Windows encodings."""
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return json.loads(raw.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError("Could not decode notebook as JSON.")


def main() -> None:
    nb = read_notebook(NOTEBOOK)
    cells = nb.get("cells", [])
    print("cells", len(cells))
    for index, cell in enumerate(cells):
        source = "".join(cell.get("source", []))
        first = " ".join(source.strip().split())[:180]
        names = []
        if cell.get("cell_type") == "code":
            try:
                tree = ast.parse(source)
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        names.append(f"{type(node).__name__}:{node.name}")
            except Exception as exc:
                names.append(f"PARSE_ERROR:{str(exc).splitlines()[0]}")
        print(
            "CELL %02d %s lines=%d names=%s :: %s"
            % (index, cell.get("cell_type"), len(source.splitlines()), names, first)
        )


if __name__ == "__main__":
    main()
