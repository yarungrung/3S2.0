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


def main() -> None:
    nb = read_notebook(NOTEBOOK)
    for cell_index in (2, 6, 10, 12, 14):
        source = "".join(nb["cells"][cell_index].get("source", []))
        print(f"\n===== CELL {cell_index:02d} =====")
        for line_no, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if (
                stripped.startswith("#")
                or "input(" in stripped
                or "print(" in stripped
                or "shortest" in stripped.lower()
                or "fare" in stripped.lower()
                or "time" in stripped.lower()
                or "weight" in stripped.lower()
                or "speed" in stripped.lower()
                or "wait" in stripped.lower()
                or "Gemini" in stripped
                or "adjusted_time" in stripped
                or "nx." in stripped
            ):
                print(f"{line_no:03d}: {line[:220]}")


if __name__ == "__main__":
    main()
