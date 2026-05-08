from datetime import datetime
from pathlib import Path
import csv
import json
import os
import platform
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


def valid_rscript_path(candidate):
    if not candidate:
        return None
    path = Path(candidate).expanduser()
    if path.is_file():
        return str(path.resolve())
    return None


def rscript_candidates_from_r_executable(r_executable):
    if not r_executable:
        return []
    r_path = Path(r_executable).expanduser()
    candidates = [r_path.parent / "Rscript.exe", r_path.parent / "Rscript"]
    if r_path.name.lower() in {"r.exe", "r"}:
        candidates.extend([r_path.with_name("Rscript.exe"), r_path.with_name("Rscript")])
    return candidates


def windows_registry_rscript_candidates():
    if platform.system().lower() != "windows":
        return []
    candidates = []
    try:
        import winreg
    except Exception:
        return candidates
    registry_roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    registry_keys = [
        r"Software\R-core\R",
        r"Software\R-core\R64",
        r"Software\WOW6432Node\R-core\R",
        r"Software\WOW6432Node\R-core\R64",
    ]
    for root_key in registry_roots:
        for key_name in registry_keys:
            try:
                with winreg.OpenKey(root_key, key_name) as key:
                    install_path, _ = winreg.QueryValueEx(key, "InstallPath")
                    if install_path:
                        install_root = Path(str(install_path))
                        candidates.extend(
                            [
                                install_root / "bin" / "Rscript.exe",
                                install_root / "bin" / "x64" / "Rscript.exe",
                                install_root / "bin" / "i386" / "Rscript.exe",
                            ]
                        )
            except OSError:
                continue
    return candidates


def windows_env_rscript_candidates():
    if platform.system().lower() != "windows":
        return []
    candidates = []
    for env_name in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base_value = os.environ.get(env_name, "").strip()
        if not base_value:
            continue
        base_path = Path(base_value)
        search_roots = [base_path / "R"]
        if env_name == "LOCALAPPDATA":
            search_roots.append(base_path / "Programs" / "R")
        for search_root in search_roots:
            if not search_root.exists():
                continue
            for child in search_root.glob("R-*"):
                candidates.extend(
                    [
                        child / "bin" / "Rscript.exe",
                        child / "bin" / "x64" / "Rscript.exe",
                        child / "bin" / "i386" / "Rscript.exe",
                    ]
                )
    return candidates


def discover_rscript():
    candidates = []
    configured_rscript = os.environ.get("SCE_UAT_RSCRIPT", "").strip()
    candidates.append(configured_rscript or None)
    candidates.append(shutil.which("Rscript"))

    r_home = os.environ.get("R_HOME", "").strip()
    if r_home:
        r_home_path = Path(r_home)
        candidates.extend([r_home_path / "bin" / "Rscript.exe", r_home_path / "bin" / "Rscript"])

    candidates.extend(rscript_candidates_from_r_executable(os.environ.get("RSTUDIO_WHICH_R", "").strip()))
    candidates.extend(windows_registry_rscript_candidates())
    candidates.extend(windows_env_rscript_candidates())

    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        candidate_key = str(candidate)
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        valid = valid_rscript_path(candidate)
        if valid:
            return valid
    return None


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
        result["stderr"] = (
            "Rscript was not found via SCE_UAT_RSCRIPT, PATH, R_HOME, RStudio environment, "
            "Windows registry, or environment-based R installation folders."
        )
        result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(result["stderr"], file=sys.stderr)
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
