from pathlib import Path
import csv
import importlib
import importlib.metadata
import importlib.util
import sys


PACKAGES = [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("openpyxl", "openpyxl"),
    ("docx", "python-docx"),
    ("reportlab", "reportlab"),
    ("PyPDF2", "PyPDF2"),
    ("pdfplumber", "pdfplumber"),
    ("matplotlib", "matplotlib"),
]


def get_root():
    if len(sys.argv) >= 2:
        return Path(sys.argv[1]).resolve()
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "data").exists():
        return candidate
    return Path.cwd().resolve()


def package_version(distribution_name, module_name):
    for name in (distribution_name, module_name):
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    module = sys.modules.get(module_name)
    return str(getattr(module, "__version__", ""))


def check_package(module_name, distribution_name):
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            return {
                "language": "Python",
                "package": module_name,
                "status": "NOT_AVAILABLE",
                "version": "",
                "error_message": "",
            }

        module = importlib.import_module(module_name)
        version = package_version(distribution_name, module_name)
        if not version:
            version = str(getattr(module, "__version__", ""))
        return {
            "language": "Python",
            "package": module_name,
            "status": "AVAILABLE",
            "version": version,
            "error_message": "",
        }
    except PermissionError as exc:
        return {
            "language": "Python",
            "package": module_name,
            "status": "BLOCKED",
            "version": "",
            "error_message": str(exc),
        }
    except Exception as exc:
        return {
            "language": "Python",
            "package": module_name,
            "status": "ERROR",
            "version": "",
            "error_message": str(exc),
        }


def main():
    root = get_root()
    output_file = root / "outputs" / "test_results" / "python_package_availability.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    rows = [check_package(module_name, distribution_name) for module_name, distribution_name in PACKAGES]

    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["language", "package", "status", "version", "error_message"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Python package availability written to {output_file}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Python import test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
