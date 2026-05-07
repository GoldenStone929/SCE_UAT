from datetime import datetime
from pathlib import Path
import csv
import json
import sys


RELATED_VALUES = {"RELATED", "POSSIBLY RELATED", "PROBABLY RELATED"}


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


def write_metric_csv(path, metrics):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "actual_value"])
        writer.writeheader()
        for metric, value in metrics.items():
            writer.writerow({"metric": metric, "actual_value": value})


def read_expected(path):
    expected = {}
    for row in read_csv(path):
        expected[row["metric"]] = row["expected_value"]
    return expected


def is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def calculate_metrics(dm_rows, ae_rows, lb_rows):
    metrics = {
        "total_subjects": len(dm_rows),
        "safety_subjects": sum(1 for row in dm_rows if row.get("SAFFL", "").upper() == "Y"),
        "total_ae_records": len(ae_rows),
        "subjects_with_ae": len({row.get("USUBJID", "") for row in ae_rows if row.get("USUBJID", "")}),
        "serious_ae_records": sum(1 for row in ae_rows if row.get("AESER", "").upper() == "Y"),
        "treatment_related_ae_records": sum(
            1 for row in ae_rows if row.get("AEREL", "").upper() in RELATED_VALUES
        ),
        "severe_ae_records": sum(1 for row in ae_rows if row.get("AESEV", "").upper() == "SEVERE"),
        "ae_start_after_end_records": sum(
            1
            for row in ae_rows
            if row.get("AESTDTC", "") and row.get("AEENDTC", "") and row["AESTDTC"] > row["AEENDTC"]
        ),
        "total_lb_records": len(lb_rows),
        "alt_high_records": sum(
            1
            for row in lb_rows
            if row.get("LBTEST", "").upper() == "ALT" and row.get("LBNRIND", "").upper() == "HIGH"
        ),
        "ast_high_records": sum(
            1
            for row in lb_rows
            if row.get("LBTEST", "").upper() == "AST" and row.get("LBNRIND", "").upper() == "HIGH"
        ),
        "missing_lab_unit_records": sum(1 for row in lb_rows if row.get("LBORRESU", "").strip() == ""),
        "non_numeric_lab_result_records": sum(1 for row in lb_rows if not is_number(row.get("LBORRES", ""))),
        "abnormal_high_lab_records": sum(1 for row in lb_rows if row.get("LBNRIND", "").upper() == "HIGH"),
    }
    return metrics


def validate(metrics, expected):
    rows = []
    for metric, expected_value in expected.items():
        actual_value = str(metrics.get(metric, ""))
        rows.append(
            {
                "metric": metric,
                "expected_value": expected_value,
                "actual_value": actual_value,
                "status": "PASS" if actual_value == expected_value else "FAIL",
            }
        )
    return rows


def main():
    root = get_root()
    dm_rows = read_csv(root / "data" / "input" / "fake_dm.csv")
    ae_rows = read_csv(root / "data" / "input" / "fake_ae.csv")
    lb_rows = read_csv(root / "data" / "input" / "fake_lb.csv")
    expected = read_expected(root / "data" / "expected" / "expected_clinical_summary.csv")

    metrics = calculate_metrics(dm_rows, ae_rows, lb_rows)
    validation_rows = validate(metrics, expected)
    overall_status = "PASS" if all(row["status"] == "PASS" for row in validation_rows) else "FAIL"

    summary_file = root / "outputs" / "python" / "python_clinical_summary.csv"
    validation_file = root / "outputs" / "test_results" / "python_clinical_validation.json"
    write_metric_csv(summary_file, metrics)
    validation_file.parent.mkdir(parents=True, exist_ok=True)
    validation_file.write_text(
        json.dumps(
            {
                "test_name": "python_clinical_summary_validation",
                "status": overall_status,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "metrics": validation_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Python clinical validation status: {overall_status}")
    return 0 if overall_status == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Python clinical summary failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
