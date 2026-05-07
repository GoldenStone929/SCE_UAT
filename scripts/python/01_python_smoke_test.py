from datetime import datetime
from pathlib import Path
import sys


def get_root():
    if len(sys.argv) >= 2:
        return Path(sys.argv[1]).resolve()
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "data").exists():
        return candidate
    return Path.cwd().resolve()


def main():
    root = get_root()
    output_dir = root / "outputs" / "python"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "python_smoke_test.txt"
    timestamp = datetime.now().isoformat(timespec="seconds")

    output_file.write_text(
        "Python smoke test PASS\n"
        f"Timestamp: {timestamp}\n"
        f"Root: {root}\n",
        encoding="utf-8",
    )

    print("Python smoke test completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Python smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
