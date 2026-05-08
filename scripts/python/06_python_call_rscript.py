from datetime import datetime
from pathlib import Path
import csv
import json
import os
import shutil
import subprocess
import sys


def get_root():
    if len(sys.argv) >= 2:
        return Path(sys.argv[1]).resolve()
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "data").exists():
        return candidate
    return Path.cwd().resolve()


def read_metric_csv(path, value_column):
    with path.open("r", newline="", encoding="utf-8") as handle:
        return {row["metric"]: row[value_column] for row in csv.DictReader(handle)}


def discover_rscript():
    configured_rscript = os.environ.get("SCE_UAT_RSCRIPT", "").strip()
    if configured_rscript:
        configured_path = Path(configured_rscript).expanduser()
        if configured_path.is_file():
            return str(configured_path.resolve())
    return shutil.which("Rscript")


def main():
    root = get_root()
    result_file = root / "outputs" / "test_results" / "python_calls_r_validation.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    rscript_path = discover_rscript()
    r_script = root / "scripts" / "r" / "04_r_clinical_summary.R"
    r_output = root / "outputs" / "r" / "ae_summary_from_r.csv"
    expected_file = root / "data" / "expected" / "expected_ae_summary.csv"
    nested_log = root / "outputs" / "logs" / "python_calls_rscript_nested_r.log"
    nested_log.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "test_name": "python_calls_rscript_validation",
        "status": "FAIL",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "rscript_found": bool(rscript_path),
        "rscript_path": rscript_path or "",
        "stdout": "",
        "stderr": "",
        "return_code": None,
        "metrics": [],
    }

    if not rscript_path:
        result["status"] = "FAIL"
        result["stderr"] = "Rscript was not found via SCE_UAT_RSCRIPT or on the system path."
        result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("Rscript was not found via SCE_UAT_RSCRIPT or on the system path.", file=sys.stderr)
        return 1

    completed = subprocess.run(
        [rscript_path, str(r_script), str(root)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    nested_log.write_text(
        "Command:\n"
        + " ".join([rscript_path, str(r_script), str(root)])
        + "\n\nReturn code:\n"
        + str(completed.returncode)
        + "\n\nStdout:\n"
        + completed.stdout
        + "\n\nStderr:\n"
        + completed.stderr,
        encoding="utf-8",
    )
    result["stdout"] = completed.stdout
    result["stderr"] = completed.stderr
    result["return_code"] = completed.returncode

    if completed.returncode != 0:
        result["status"] = "FAIL"
    elif not r_output.exists() or r_output.stat().st_size <= 0:
        result["status"] = "FAIL"
        result["stderr"] = result["stderr"] + "\nExpected R output file was not created or was empty."
    else:
        expected = read_metric_csv(expected_file, "expected_value")
        actual = read_metric_csv(r_output, "actual_value")
        metrics = []
        for metric, expected_value in expected.items():
            actual_value = str(actual.get(metric, ""))
            metrics.append(
                {
                    "metric": metric,
                    "expected_value": expected_value,
                    "actual_value": actual_value,
                    "status": "PASS" if actual_value == expected_value else "FAIL",
                }
            )
        result["metrics"] = metrics
        result["status"] = "PASS" if all(row["status"] == "PASS" for row in metrics) else "FAIL"

    result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Python calls Rscript validation status: {result['status']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Python calls Rscript test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
