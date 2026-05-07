from datetime import datetime
from pathlib import Path
import csv
import json
import os
import sys


def get_root():
    if len(sys.argv) >= 2:
        return Path(sys.argv[1]).resolve()
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "data").exists():
        return candidate
    return Path.cwd().resolve()


def read_csv(path):
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main():
    root = get_root()
    input_file = root / "data" / "input" / "fake_dm.csv"
    output_dir = root / "outputs" / "python"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_csv(input_file)
    if not rows:
        raise RuntimeError("No rows read from fake_dm.csv")

    csv_out = output_dir / "python_io_dm_copy.csv"
    txt_out = output_dir / "python_io_test.txt"
    json_out = output_dir / "python_io_test.json"
    subfolder = output_dir / "io_subfolder"
    log_file = root / "outputs" / "logs" / "python_io_append.log"
    timestamp = datetime.now().isoformat(timespec="seconds")

    subfolder.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with csv_out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    txt_out.write_text(
        "Python file I/O test PASS\n"
        f"Timestamp: {timestamp}\n"
        f"Rows read: {len(rows)}\n",
        encoding="utf-8",
    )

    json_out.write_text(
        json.dumps(
            {
                "test_name": "python_io_test",
                "timestamp": timestamp,
                "rows_read": len(rows),
                "created_subfolder": str(subfolder),
                "cwd": os.getcwd(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} - Python append test completed\n")

    copied_rows = read_csv(csv_out)
    evidence_files = [csv_out, txt_out, json_out, log_file]
    empty_files = [str(path) for path in evidence_files if not path.exists() or path.stat().st_size <= 0]
    if empty_files:
        raise RuntimeError("Generated files missing or empty: " + "; ".join(empty_files))
    if len(copied_rows) != len(rows):
        raise RuntimeError("Read-back row count did not match source row count")

    print("Python I/O test completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Python I/O test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
