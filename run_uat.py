from __future__ import annotations

from datetime import datetime
from getpass import getuser
from pathlib import Path
import csv
import hashlib
import html
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import textwrap
import traceback
import zipfile


ROOT = Path(__file__).resolve().parent

GENERATED_ROOT_DIRS = [
    ROOT / "outputs",
    ROOT / "reports",
]

OUTPUT_DIRS = [
    ROOT / "outputs" / "python",
    ROOT / "outputs" / "python" / "generated_documents",
    ROOT / "outputs" / "r",
    ROOT / "outputs" / "r" / "generated_documents",
    ROOT / "outputs" / "logs",
    ROOT / "outputs" / "test_results",
    ROOT / "reports",
]

REPORT_FIELDNAMES = [
    "test_id",
    "layer",
    "language",
    "test_name",
    "status",
    "expected_result",
    "actual_result",
    "output_file",
    "error_message",
    "timestamp",
    "runtime_seconds",
]

ALLOWED_STATUSES = {"PASS", "FAIL", "WARNING", "NOT_AVAILABLE", "SKIPPED", "ERROR"}
RUN_LOCK_FILE = ROOT / "outputs" / ".sce_uat_run.lock"
STARTUP_ERROR_FILE = ROOT / "reports" / "startup_error.txt"
ROOT_FINAL_WORD_REPORT = ROOT / "SCE_UAT_Final_Report.docx"


class RunLockError(RuntimeError):
    pass


class StartupCleanupPermissionError(PermissionError):
    pass


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_rel(path: Path | str | None) -> str:
    if not path:
        return ""
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return str(path)


def ensure_directories() -> None:
    for directory in GENERATED_ROOT_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
    for directory in OUTPUT_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


def _valid_rscript_path(candidate: Path | str | None) -> str | None:
    if not candidate:
        return None
    path = Path(candidate).expanduser()
    if path.is_file():
        return str(path.resolve())
    return None


def _rscript_candidates_from_r_executable(r_executable: str | None) -> list[Path]:
    if not r_executable:
        return []
    r_path = Path(r_executable).expanduser()
    candidates = [r_path.parent / "Rscript.exe", r_path.parent / "Rscript"]
    if r_path.name.lower() in {"r.exe", "r"}:
        candidates.extend([r_path.with_name("Rscript.exe"), r_path.with_name("Rscript")])
    return candidates


def _windows_registry_rscript_candidates() -> list[Path]:
    if platform.system().lower() != "windows":
        return []
    candidates: list[Path] = []
    try:
        import winreg  # type: ignore
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


def _rscript_candidates_from_search_roots(search_roots: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for search_root in search_roots:
        if not search_root.exists():
            continue
        candidates.extend(
            [
                search_root / "Rscript.exe",
                search_root / "Rscript",
                search_root / "bin" / "Rscript.exe",
                search_root / "bin" / "Rscript",
                search_root / "bin" / "x64" / "Rscript.exe",
                search_root / "bin" / "i386" / "Rscript.exe",
            ]
        )
        try:
            candidates.extend(search_root.glob("R-*/bin/Rscript.exe"))
            candidates.extend(search_root.glob("R-*/bin/x64/Rscript.exe"))
            candidates.extend(search_root.glob("R-*/bin/i386/Rscript.exe"))
        except OSError:
            continue
    return candidates


def _configured_rscript_candidates(config: dict | None = None) -> list[Path | str | None]:
    config = config or {}
    candidates: list[Path | str | None] = []
    candidates.append(config.get("rscript_path") or None)

    search_roots: list[Path] = []
    config_roots = config.get("rscript_search_roots", [])
    if isinstance(config_roots, str):
        config_roots = [config_roots]
    if isinstance(config_roots, list):
        search_roots.extend(Path(str(item)).expanduser() for item in config_roots if str(item).strip())

    env_roots = os.environ.get("SCE_UAT_RSCRIPT_SEARCH_ROOTS", "").strip()
    if env_roots:
        search_roots.extend(Path(item).expanduser() for item in env_roots.split(os.pathsep) if item.strip())

    candidates.extend(_rscript_candidates_from_search_roots(search_roots))
    return candidates


def _windows_env_rscript_candidates() -> list[Path]:
    if platform.system().lower() != "windows":
        return []
    search_roots: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base_value = os.environ.get(env_name, "").strip()
        if not base_value:
            continue
        base_path = Path(base_value)
        env_search_roots = [base_path / "R"]
        if env_name == "LOCALAPPDATA":
            env_search_roots.append(base_path / "Programs" / "R")
        search_roots.extend(env_search_roots)
    return _rscript_candidates_from_search_roots(search_roots)


def discover_rscript(config: dict | None = None) -> str | None:
    candidates: list[Path | str | None] = []

    configured_rscript = os.environ.get("SCE_UAT_RSCRIPT", "").strip()
    candidates.append(configured_rscript or None)
    candidates.extend(_configured_rscript_candidates(config))
    candidates.append(shutil.which("Rscript"))

    r_home = os.environ.get("R_HOME", "").strip()
    if r_home:
        r_home_path = Path(r_home)
        candidates.extend([r_home_path / "bin" / "Rscript.exe", r_home_path / "bin" / "Rscript"])

    candidates.extend(_rscript_candidates_from_r_executable(os.environ.get("RSTUDIO_WHICH_R", "").strip()))
    candidates.extend(_windows_registry_rscript_candidates())
    candidates.extend(_windows_env_rscript_candidates())

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        candidate_key = str(candidate)
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        valid = _valid_rscript_path(candidate)
        if valid:
            return valid
    return None


def _assert_within_root(path: Path) -> None:
    path.resolve().relative_to(ROOT.resolve())


def acquire_run_lock() -> None:
    RUN_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with RUN_LOCK_FILE.open("x", encoding="utf-8") as handle:
            handle.write(
                f"pid={os.getpid()}\n"
                f"timestamp={now_iso()}\n"
                f"python={sys.executable}\n"
            )
    except FileExistsError as exc:
        raise RunLockError(
            f"SCE UAT run lock already exists at {safe_rel(RUN_LOCK_FILE)}; another run may be active."
        ) from exc


def release_run_lock() -> None:
    try:
        RUN_LOCK_FILE.unlink()
    except FileNotFoundError:
        return
    except Exception as exc:
        print(f"WARNING: Failed to remove run lock file {RUN_LOCK_FILE}: {exc}", file=sys.stderr)


def write_startup_error_file(message: str, exc: Exception) -> None:
    payload = "\n".join(
        [
            "SCE UAT startup permission failure",
            f"Timestamp: {now_iso()}",
            f"Project root: {ROOT}",
            "",
            message,
            "",
            f"Error: {exc}",
        ]
    )
    try:
        STARTUP_ERROR_FILE.parent.mkdir(parents=True, exist_ok=True)
        STARTUP_ERROR_FILE.write_text(payload, encoding="utf-8")
    except Exception as report_exc:
        print(
            f"WARNING: Could not write startup error report to {STARTUP_ERROR_FILE}: {report_exc}",
            file=sys.stderr,
        )


def clean_generated_artifacts(root: Path) -> dict:
    summary = {
        "cleanup_performed": True,
        "targets": [safe_rel(path) for path in GENERATED_ROOT_DIRS],
        "removed_files": 0,
        "removed_directories": 0,
        "recreated_directories": [],
    }

    for directory in GENERATED_ROOT_DIRS:
        _assert_within_root(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for child in directory.iterdir():
            _assert_within_root(child)
            if child == RUN_LOCK_FILE:
                continue
            if child.is_dir():
                shutil.rmtree(child)
                summary["removed_directories"] += 1
            else:
                child.unlink()
                summary["removed_files"] += 1

    ensure_directories()
    if ROOT_FINAL_WORD_REPORT.exists():
        ROOT_FINAL_WORD_REPORT.unlink()
    summary["recreated_directories"] = [safe_rel(path) for path in OUTPUT_DIRS]
    return summary


def load_config() -> dict:
    config_file = ROOT / "config.json"
    if not config_file.exists():
        return {}
    with config_file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_record(
    test_id: str,
    layer: str,
    language: str,
    test_name: str,
    status: str,
    expected_result: str,
    actual_result: str,
    output_file: str = "",
    error_message: str = "",
    runtime_seconds: float = 0.0,
) -> dict:
    if status not in ALLOWED_STATUSES:
        status = "ERROR"
    return {
        "test_id": test_id,
        "layer": layer,
        "language": language,
        "test_name": test_name,
        "status": status,
        "expected_result": expected_result,
        "actual_result": actual_result,
        "output_file": output_file,
        "error_message": error_message,
        "timestamp": now_iso(),
        "runtime_seconds": f"{runtime_seconds:.3f}",
    }


def command_log_file(test_id: str) -> Path:
    safe_name = "".join(char if char.isalnum() or char in "-_" else "_" for char in test_id)
    return ROOT / "outputs" / "logs" / f"{safe_name}.log"


def run_command(
    test_id: str,
    layer: str,
    language: str,
    test_name: str,
    command: list[str],
    expected_result: str,
    required: bool,
    output_file: Path | str | None = None,
) -> dict:
    start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    runtime = time.perf_counter() - start
    log_file = command_log_file(test_id)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(
        "Command:\n"
        + " ".join(command)
        + "\n\nReturn code:\n"
        + str(completed.returncode)
        + "\n\nStdout:\n"
        + completed.stdout
        + "\n\nStderr:\n"
        + completed.stderr,
        encoding="utf-8",
    )

    if completed.returncode == 0:
        status = "PASS"
        actual_result = "Command completed successfully."
    else:
        status = "FAIL" if required else "WARNING"
        actual_result = f"Command returned code {completed.returncode}."

    return make_record(
        test_id=test_id,
        layer=layer,
        language=language,
        test_name=test_name,
        status=status,
        expected_result=expected_result,
        actual_result=actual_result,
        output_file=safe_rel(output_file) if output_file else safe_rel(log_file),
        error_message=completed.stderr.strip(),
        runtime_seconds=runtime,
    )


def python_permission_check() -> dict:
    result = {
        "can_create_folder": False,
        "can_create_file": False,
        "can_write_file": False,
        "can_read_file": False,
        "can_append_file": False,
        "can_delete_file": False,
        "errors": [],
    }
    probe_dir = ROOT / "outputs" / "permission_python_probe"
    probe_file = probe_dir / "permission_check.txt"
    try:
        probe_dir.mkdir(parents=True, exist_ok=True)
        result["can_create_folder"] = probe_dir.exists()
        probe_file.write_text("write\n", encoding="utf-8")
        result["can_create_file"] = probe_file.exists()
        result["can_write_file"] = probe_file.stat().st_size > 0
        result["can_read_file"] = probe_file.read_text(encoding="utf-8") == "write\n"
        with probe_file.open("a", encoding="utf-8") as handle:
            handle.write("append\n")
        result["can_append_file"] = "append" in probe_file.read_text(encoding="utf-8")
        probe_file.unlink()
        result["can_delete_file"] = not probe_file.exists()
        try:
            probe_dir.rmdir()
        except OSError:
            pass
    except Exception as exc:
        result["errors"].append(str(exc))
    return result


def create_r_environment_probe() -> Path:
    probe_file = ROOT / "outputs" / "test_results" / "r_environment_probe.R"
    probe_file.write_text(
        """args <- commandArgs(trailingOnly = TRUE)
if (length(args) >= 1) {
  ROOT <- normalizePath(args[1], winslash = "/", mustWork = TRUE)
} else {
  ROOT <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

probe_dir <- file.path(ROOT, "outputs", "permission_r_probe")
probe_file <- file.path(probe_dir, "permission_check.txt")
errors <- character()
can_create_folder <- FALSE
can_create_file <- FALSE
can_write_file <- FALSE
can_read_file <- FALSE
can_append_file <- FALSE
can_delete_file <- FALSE

tryCatch({
  dir.create(probe_dir, recursive = TRUE, showWarnings = FALSE)
  can_create_folder <- dir.exists(probe_dir)
  writeLines("write", probe_file)
  can_create_file <- file.exists(probe_file)
  can_write_file <- file.info(probe_file)$size > 0
  can_read_file <- identical(readLines(probe_file, warn = FALSE), "write")
  cat("append\\n", file = probe_file, append = TRUE)
  can_append_file <- any(grepl("append", readLines(probe_file, warn = FALSE)))
  unlink(probe_file)
  can_delete_file <- !file.exists(probe_file)
  unlink(probe_dir, recursive = TRUE)
}, error = function(e) {
  errors <<- c(errors, conditionMessage(e))
})

cat("R_VERSION|", paste(R.version$major, R.version$minor, sep = "."), "\\n", sep = "")
cat("R_WORKING_DIRECTORY|", getwd(), "\\n", sep = "")
cat("R_LIB_PATHS|", paste(.libPaths(), collapse = ";"), "\\n", sep = "")
cat("R_CAN_CREATE_FOLDER|", can_create_folder, "\\n", sep = "")
cat("R_CAN_CREATE_FILE|", can_create_file, "\\n", sep = "")
cat("R_CAN_WRITE_FILE|", can_write_file, "\\n", sep = "")
cat("R_CAN_READ_FILE|", can_read_file, "\\n", sep = "")
cat("R_CAN_APPEND_FILE|", can_append_file, "\\n", sep = "")
cat("R_CAN_DELETE_FILE|", can_delete_file, "\\n", sep = "")
cat("R_ERRORS|", paste(errors, collapse = "; "), "\\n", sep = "")
cat("R_SESSION_INFO_BEGIN\\n")
cat(capture.output(sessionInfo()), sep = "\\n")
cat("\\nR_SESSION_INFO_END\\n")
""",
        encoding="utf-8",
    )
    return probe_file


def parse_r_probe(stdout: str) -> dict:
    data = {
        "r_version": "",
        "r_working_directory": "",
        "r_lib_paths": [],
        "r_session_info": "",
        "permission_results": {},
        "errors": [],
    }
    session_lines = []
    in_session = False
    for line in stdout.splitlines():
        if line == "R_SESSION_INFO_BEGIN":
            in_session = True
            continue
        if line == "R_SESSION_INFO_END":
            in_session = False
            continue
        if in_session:
            session_lines.append(line)
            continue
        if "|" not in line:
            continue
        key, value = line.split("|", 1)
        value = value.strip()
        if key == "R_VERSION":
            data["r_version"] = value
        elif key == "R_WORKING_DIRECTORY":
            data["r_working_directory"] = value
        elif key == "R_LIB_PATHS":
            data["r_lib_paths"] = [item for item in value.split(";") if item]
        elif key.startswith("R_CAN_"):
            data["permission_results"][key.lower().replace("r_", "")] = value.upper() == "TRUE"
        elif key == "R_ERRORS" and value:
            data["errors"].append(value)
    data["r_session_info"] = "\n".join(session_lines)
    return data


def collect_environment_inventory(rscript_path: str | None) -> dict:
    python_permissions = python_permission_check()
    inventory = {
        "timestamp": now_iso(),
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "current_working_directory": os.getcwd(),
            "project_root": str(ROOT),
            "platform": platform.platform(),
            "username": "",
            "permission_results": python_permissions,
        },
        "r": {
            "rscript_found": bool(rscript_path),
            "rscript_path": rscript_path or "",
            "r_version": "",
            "r_working_directory": "",
            "r_lib_paths": [],
            "r_session_info": "",
            "permission_results": {},
            "errors": [],
        },
        "system": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "directory_existence": {
                safe_rel(directory): directory.exists() for directory in OUTPUT_DIRS
            },
            "errors": [],
        },
    }
    try:
        inventory["python"]["username"] = getuser()
    except Exception as exc:
        inventory["system"]["errors"].append(f"Username unavailable: {exc}")

    if rscript_path:
        probe_file = create_r_environment_probe()
        start = time.perf_counter()
        completed = subprocess.run(
            [rscript_path, str(probe_file), str(ROOT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        runtime = time.perf_counter() - start
        log_file = command_log_file("layer0_r_environment_permission_probe")
        log_file.write_text(
            "Command:\n"
            + " ".join([rscript_path, str(probe_file), str(ROOT)])
            + "\n\nReturn code:\n"
            + str(completed.returncode)
            + "\n\nRuntime seconds:\n"
            + f"{runtime:.3f}"
            + "\n\nStdout:\n"
            + completed.stdout
            + "\n\nStderr:\n"
            + completed.stderr,
            encoding="utf-8",
        )
        if completed.returncode == 0:
            parsed = parse_r_probe(completed.stdout)
            inventory["r"].update(parsed)
        else:
            inventory["r"]["errors"].append(completed.stderr.strip() or "R environment probe failed.")

    write_json(ROOT / "outputs" / "test_results" / "environment_inventory.json", inventory)
    write_environment_reports(inventory)
    return inventory


def permission_status(permission_results: dict) -> str:
    if not permission_results:
        return "No permission results available."
    checks = []
    for key, value in permission_results.items():
        if key == "errors":
            continue
        checks.append(f"{key}: {value}")
    errors = permission_results.get("errors", [])
    if errors:
        checks.append("errors: " + "; ".join(errors))
    return "\n".join(checks)


def write_environment_reports(inventory: dict) -> None:
    env_report = ROOT / "reports" / "environment_report.txt"
    permission_report = ROOT / "reports" / "permission_report.txt"
    env_report.write_text(
        "\n".join(
            [
                "SCE UAT Environment Report",
                f"Timestamp: {inventory['timestamp']}",
                "",
                "Python",
                f"Version: {inventory['python']['version']}",
                f"Executable: {inventory['python']['executable']}",
                f"Current working directory: {inventory['python']['current_working_directory']}",
                f"Project root: {inventory['python']['project_root']}",
                f"Platform: {inventory['python']['platform']}",
                f"Username: {inventory['python']['username']}",
                "",
                "R",
                f"Rscript found: {inventory['r']['rscript_found']}",
                f"Rscript path: {inventory['r']['rscript_path']}",
                f"R version: {inventory['r']['r_version']}",
                f"R working directory: {inventory['r']['r_working_directory']}",
                f"R library paths: {'; '.join(inventory['r']['r_lib_paths'])}",
                "",
                "R sessionInfo()",
                inventory["r"]["r_session_info"],
                "",
                "System",
                f"Platform: {inventory['system']['platform']}",
                f"System: {inventory['system']['system']}",
                f"Release: {inventory['system']['release']}",
                f"Machine: {inventory['system']['machine']}",
                f"Processor: {inventory['system']['processor']}",
                "",
                "Directory Existence",
                *[
                    f"{directory}: {exists}"
                    for directory, exists in inventory["system"]["directory_existence"].items()
                ],
                "",
                "Detected Errors",
                "; ".join(inventory["system"]["errors"] + inventory["r"]["errors"]) or "None",
            ]
        ),
        encoding="utf-8",
    )
    permission_report.write_text(
        "\n".join(
            [
                "SCE UAT Permission Report",
                f"Timestamp: {inventory['timestamp']}",
                "",
                "Python permission results",
                permission_status(inventory["python"]["permission_results"]),
                "",
                "R permission results",
                permission_status(inventory["r"]["permission_results"]),
            ]
        ),
        encoding="utf-8",
    )


def merge_package_availability() -> list[dict]:
    python_rows = read_csv_rows(ROOT / "outputs" / "test_results" / "python_package_availability.csv")
    r_rows = read_csv_rows(ROOT / "outputs" / "test_results" / "r_package_availability.csv")
    rows = python_rows + r_rows
    write_csv(
        ROOT / "reports" / "package_availability.csv",
        rows,
        ["language", "package", "status", "version", "error_message"],
    )
    return rows


def add_package_records(records: list[dict], package_rows: list[dict]) -> None:
    for index, row in enumerate(package_rows, start=1):
        original_status = row.get("status", "")
        if original_status == "AVAILABLE":
            status = "PASS"
        elif original_status == "NOT_AVAILABLE":
            status = "NOT_AVAILABLE"
        elif original_status == "BLOCKED":
            status = "WARNING"
        else:
            status = "WARNING"
        records.append(
            make_record(
                test_id=f"package_availability_{index:03d}",
                layer="Layer 3",
                language=row.get("language", ""),
                test_name=f"Package availability: {row.get('package', '')}",
                status=status,
                expected_result="Package availability classified without installing packages.",
                actual_result=original_status,
                output_file="reports/package_availability.csv",
                error_message=row.get("error_message", ""),
            )
        )


def load_python_clinical_validation() -> list[dict]:
    path = ROOT / "outputs" / "test_results" / "python_clinical_validation.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    rows = data.get("metrics", [])
    for row in rows:
        row["language"] = "Python"
        row["source"] = safe_rel(path)
    return rows


def load_python_calls_r_validation() -> list[dict]:
    path = ROOT / "outputs" / "test_results" / "python_calls_r_validation.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    rows = data.get("metrics", [])
    for row in rows:
        row["language"] = "Python calls R"
        row["source"] = safe_rel(path)
    return rows


def load_r_clinical_validation() -> list[dict]:
    path = ROOT / "outputs" / "test_results" / "r_clinical_validation.csv"
    rows = read_csv_rows(path)
    for row in rows:
        row["language"] = "R"
        row["source"] = safe_rel(path)
    return rows


def clinical_validation_rows() -> list[dict]:
    return load_python_clinical_validation() + load_r_clinical_validation() + load_python_calls_r_validation()


def document_generation_rows() -> list[dict]:
    return read_csv_rows(ROOT / "outputs" / "test_results" / "python_document_generation_results.csv") + read_csv_rows(
        ROOT / "outputs" / "test_results" / "r_document_generation_results.csv"
    )


def add_document_records(records: list[dict], rows: list[dict]) -> None:
    for index, row in enumerate(rows, start=1):
        source_status = row.get("status", "")
        if source_status == "PASS":
            status = "PASS"
        elif source_status == "NOT_AVAILABLE":
            status = "NOT_AVAILABLE"
        else:
            status = "WARNING"
        records.append(
            make_record(
                test_id=f"document_generation_{index:03d}",
                layer="Layer 6",
                language=row.get("language", ""),
                test_name=f"Document generation: {row.get('output_type', '')}",
                status=status,
                expected_result="Output generated or optional capability classified.",
                actual_result=source_status,
                output_file=safe_rel(row.get("file_path", "")),
                error_message=row.get("error_message", ""),
            )
        )


def count_statuses(records: list[dict]) -> dict:
    counts = {status: 0 for status in ["PASS", "FAIL", "WARNING", "NOT_AVAILABLE", "SKIPPED", "ERROR"]}
    for record in records:
        counts[record.get("status", "")] = counts.get(record.get("status", ""), 0) + 1
    return counts


def overall_status(records: list[dict], required_test_ids: set[str]) -> str:
    required_failures = [
        record
        for record in records
        if record["test_id"] in required_test_ids and record["status"] in {"FAIL", "ERROR", "SKIPPED"}
    ]
    if required_failures:
        return "FAIL"
    if any(record["status"] in {"WARNING", "NOT_AVAILABLE"} for record in records):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def html_table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "<p>No records available.</p>"
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def layer_sort_key(layer_name: str) -> tuple[int, str]:
    if layer_name.startswith("Layer "):
        suffix = layer_name.split(" ", 1)[1]
        numeric_part = "".join(char for char in suffix if char.isdigit())
        if numeric_part:
            return int(numeric_part), layer_name
    return 999, layer_name


def grouped_records_by_layer(records: list[dict]) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = {}
    for record in records:
        layer = str(record.get("layer", "Uncategorized")) or "Uncategorized"
        grouped.setdefault(layer, []).append(record)
    output: list[tuple[str, list[dict]]] = []
    for layer in sorted(grouped.keys(), key=layer_sort_key):
        ordered_records = sorted(grouped[layer], key=lambda item: str(item.get("test_id", "")))
        output.append((layer, ordered_records))
    return output


def wrap_pdf_text(text: str, width: int = 116) -> list[str]:
    cleaned = str(text).replace("\r\n", "\n").replace("\r", "\n")
    wrapped: list[str] = []
    for raw_line in cleaned.split("\n"):
        chunks = textwrap.wrap(
            raw_line,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        )
        wrapped.extend(chunks or [""])
    return wrapped


def pdf_safe_text(text: str) -> str:
    latin_text = str(text).encode("latin-1", "replace").decode("latin-1")
    return latin_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_markdown_report(run_timestamp: str, status: str, inventory: dict, records: list[dict]) -> str:
    counts = count_statuses(records)
    lines = [
        "# SCE UAT Validation Report",
        "",
        "## Run Summary",
        "",
        f"- Target environment: Windows Server 2019 SCE",
        f"- Run timestamp: {run_timestamp}",
        f"- Overall status: {status}",
        f"- Project root: {inventory.get('python', {}).get('project_root', str(ROOT))}",
        "- Root runner: run_uat.py",
        "",
        "## Status Counts",
        "",
        f"- PASS: {counts.get('PASS', 0)}",
        f"- FAIL: {counts.get('FAIL', 0)}",
        f"- WARNING: {counts.get('WARNING', 0)}",
        f"- NOT_AVAILABLE: {counts.get('NOT_AVAILABLE', 0)}",
        f"- SKIPPED: {counts.get('SKIPPED', 0)}",
        f"- ERROR: {counts.get('ERROR', 0)}",
        "",
        "## Environment Summary",
        "",
        f"- Python executable: {inventory.get('python', {}).get('executable', '')}",
        f"- Rscript found: {inventory.get('r', {}).get('rscript_found', '')}",
        f"- Rscript path: {inventory.get('r', {}).get('rscript_path', '')}",
        f"- R version: {inventory.get('r', {}).get('r_version', '')}",
        f"- Platform: {inventory.get('system', {}).get('platform', '')}",
        "",
        "## Detailed Test Results",
        "",
    ]

    for layer_name, layer_records in grouped_records_by_layer(records):
        section_counts = count_statuses(layer_records)
        lines.extend(
            [
                f"### {layer_name}",
                "",
                (
                    f"Layer counts: PASS={section_counts.get('PASS', 0)}, "
                    f"FAIL={section_counts.get('FAIL', 0)}, "
                    f"WARNING={section_counts.get('WARNING', 0)}, "
                    f"NOT_AVAILABLE={section_counts.get('NOT_AVAILABLE', 0)}, "
                    f"SKIPPED={section_counts.get('SKIPPED', 0)}, "
                    f"ERROR={section_counts.get('ERROR', 0)}"
                ),
                "",
            ]
        )

        for record in layer_records:
            lines.append(
                f"- **{record.get('status', '')}** `{record.get('test_id', '')}`: "
                f"{record.get('test_name', '')}"
            )
            lines.append(f"  - Language: {record.get('language', '')}")
            lines.append(f"  - Expected: {record.get('expected_result', '')}")
            actual_result = str(record.get("actual_result", "")).strip()
            if actual_result:
                lines.append(f"  - Actual: {actual_result}")
            output_file = str(record.get("output_file", "")).strip()
            if output_file:
                lines.append(f"  - Output: `{output_file}`")
            error_message = str(record.get("error_message", "")).strip()
            if error_message:
                lines.append(f"  - Error: {error_message}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_markdown_report(report_file: Path, markdown_text: str) -> None:
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(markdown_text, encoding="utf-8")


def docx_text(text: object) -> str:
    return html.escape(str(text), quote=True)


def docx_paragraph(text: object = "", bold: bool = False, size: int = 20) -> str:
    run_properties = f"<w:rPr>{'<w:b/>' if bold else ''}<w:sz w:val=\"{size}\"/></w:rPr>"
    return f"<w:p><w:r>{run_properties}<w:t xml:space=\"preserve\">{docx_text(text)}</w:t></w:r></w:p>"


def docx_cell(value: object, width: int = 1800, bold: bool = False) -> str:
    values = value if isinstance(value, list) else [value]
    paragraphs = "".join(docx_paragraph(item, bold=bold, size=18) for item in values)
    return (
        f"<w:tc><w:tcPr><w:tcW w:w=\"{width}\" w:type=\"dxa\"/>"
        f"<w:tcMar><w:top w:w=\"80\" w:type=\"dxa\"/><w:left w:w=\"80\" w:type=\"dxa\"/>"
        f"<w:bottom w:w=\"80\" w:type=\"dxa\"/><w:right w:w=\"80\" w:type=\"dxa\"/></w:tcMar>"
        f"</w:tcPr>{paragraphs}</w:tc>"
    )


def docx_table(rows: list[list[object]], widths: list[int], header_rows: int = 1) -> str:
    border = '<w:top w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
    border += '<w:left w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
    border += '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
    border += '<w:right w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
    border += '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
    border += '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
    table_rows = []
    for row_index, row in enumerate(rows):
        cells = []
        for cell_index, value in enumerate(row):
            width = widths[cell_index] if cell_index < len(widths) else 1800
            cells.append(docx_cell(value, width=width, bold=row_index < header_rows))
        table_rows.append("<w:tr>" + "".join(cells) + "</w:tr>")
    return (
        "<w:tbl><w:tblPr><w:tblW w:w=\"0\" w:type=\"auto\"/>"
        f"<w:tblBorders>{border}</w:tblBorders></w:tblPr>"
        + "".join(table_rows)
        + "</w:tbl>"
    )


def status_xor_marks(status: str) -> tuple[str, str]:
    return ("", chr(10003)) if status == "PASS" else ("X", "")


def evidence_cell(record: dict) -> list[str]:
    lines: list[str] = []
    actual = str(record.get("actual_result", "")).strip()
    output_file = str(record.get("output_file", "")).strip()
    error_message = str(record.get("error_message", "")).strip()
    if actual:
        lines.append(f"Actual: {actual}")
    if output_file:
        lines.append(f"Output: {output_file}")
    if error_message:
        lines.append(f"Error: {error_message}")
    return lines or [""]


def build_docx_document(run_timestamp: str, status: str, inventory: dict, records: list[dict]) -> str:
    counts = count_statuses(records)
    body_parts = [
        docx_paragraph("SCE UAT Final All-in-One Test Report", bold=True, size=32),
        docx_paragraph("Windows-based SCE UAT evidence generated from the project root.", size=20),
        docx_table(
            [
                ["Item", "Value"],
                ["Run timestamp", run_timestamp],
                ["Overall status", status],
                ["Project root", inventory.get("python", {}).get("project_root", str(ROOT))],
                ["Root runner", "run_uat.py"],
                ["Rscript found", inventory.get("r", {}).get("rscript_found", "")],
                ["Rscript path", inventory.get("r", {}).get("rscript_path", "")],
            ],
            [2200, 6800],
        ),
        docx_paragraph("Status Counts", bold=True, size=26),
        docx_table(
            [
                ["PASS", "FAIL", "WARNING", "NOT_AVAILABLE", "SKIPPED", "ERROR"],
                [
                    counts.get("PASS", 0),
                    counts.get("FAIL", 0),
                    counts.get("WARNING", 0),
                    counts.get("NOT_AVAILABLE", 0),
                    counts.get("SKIPPED", 0),
                    counts.get("ERROR", 0),
                ],
            ],
            [1200, 1200, 1600, 2200, 1400, 1200],
        ),
        docx_paragraph("XOR table rule: PASS rows are marked with a check mark; every non-PASS row is marked with X.", size=18),
    ]

    for layer_name, layer_records in grouped_records_by_layer(records):
        section_counts = count_statuses(layer_records)
        body_parts.append(docx_paragraph(layer_name, bold=True, size=26))
        body_parts.append(
            docx_paragraph(
                "Layer counts: "
                f"PASS={section_counts.get('PASS', 0)}, "
                f"FAIL={section_counts.get('FAIL', 0)}, "
                f"WARNING={section_counts.get('WARNING', 0)}, "
                f"NOT_AVAILABLE={section_counts.get('NOT_AVAILABLE', 0)}, "
                f"SKIPPED={section_counts.get('SKIPPED', 0)}, "
                f"ERROR={section_counts.get('ERROR', 0)}",
                size=18,
            )
        )
        rows: list[list[object]] = [["X", "Check", "Status", "Test ID", "Language", "Test Name", "Evidence / Result"]]
        for record in layer_records:
            x_mark, check_mark = status_xor_marks(str(record.get("status", "")))
            rows.append(
                [
                    x_mark,
                    check_mark,
                    record.get("status", ""),
                    record.get("test_id", ""),
                    record.get("language", ""),
                    record.get("test_name", ""),
                    evidence_cell(record),
                ]
            )
        body_parts.append(docx_table(rows, [500, 700, 1200, 1900, 1300, 2500, 4200]))

    body_parts.append(
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="720" w:right="720" '
        'w:bottom="720" w:left="720" w:header="360" w:footer="360" w:gutter="0"/></w:sectPr>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(body_parts)
        + "</w:body></w:document>"
    )


def write_docx_report(report_file: Path, run_timestamp: str, status: str, inventory: dict, records: list[dict]) -> None:
    document_xml = build_docx_document(run_timestamp, status, inventory, records)
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )

    report_file.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(report_file, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", document_xml)


def write_text_pdf(report_file: Path, lines: list[str]) -> None:
    report_file.parent.mkdir(parents=True, exist_ok=True)

    page_width = 612
    page_height = 792
    margin_left = 40
    start_y = 760
    font_size = 9
    line_height = 12
    lines_per_page = 58

    if not lines:
        lines = [""]
    pages = [lines[index : index + lines_per_page] for index in range(0, len(lines), lines_per_page)]

    objects: dict[int, bytes] = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    page_ids: list[int] = []
    first_page_object_id = 4
    for page_index, page_lines in enumerate(pages):
        page_obj_id = first_page_object_id + page_index * 2
        content_obj_id = page_obj_id + 1
        page_ids.append(page_obj_id)

        content_commands = [
            "BT",
            f"/F1 {font_size} Tf",
            f"{line_height} TL",
            f"{margin_left} {start_y} Td",
        ]
        for line in page_lines:
            content_commands.append(f"({pdf_safe_text(line)}) Tj")
            content_commands.append("T*")
        content_commands.append("ET")
        stream_data = "\n".join(content_commands).encode("latin-1", "replace")

        objects[page_obj_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj_id} 0 R >>"
        ).encode("ascii")
        objects[content_obj_id] = (
            b"<< /Length "
            + str(len(stream_data)).encode("ascii")
            + b" >>\nstream\n"
            + stream_data
            + b"\nendstream"
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

    max_obj_id = max(objects)
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max_obj_id + 1)
    for obj_id in range(1, max_obj_id + 1):
        offsets[obj_id] = len(output)
        output.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        output.extend(objects[obj_id])
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {max_obj_id + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for obj_id in range(1, max_obj_id + 1):
        output.extend(f"{offsets[obj_id]:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {max_obj_id + 1} /Root 1 0 R >>\n".encode("ascii"))
    output.extend(f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    report_file.write_bytes(bytes(output))


def generate_pdf_report(report_file: Path, markdown_text: str) -> None:
    lines: list[str] = []
    for line in markdown_text.splitlines():
        lines.extend(wrap_pdf_text(line, width=96))
    write_text_pdf(report_file, lines)


def generate_html_report(
    report_file: Path,
    run_timestamp: str,
    status: str,
    inventory: dict,
    records: list[dict],
    package_rows: list[dict],
    clinical_rows: list[dict],
    document_rows: list[dict],
) -> None:
    counts = count_statuses(records)
    error_rows = [row for row in records if row.get("status") in {"FAIL", "ERROR", "WARNING"} and row.get("error_message")]
    environment_summary = [
        {"item": "Python version", "value": inventory["python"]["version"]},
        {"item": "Python executable", "value": inventory["python"]["executable"]},
        {"item": "Project root", "value": inventory["python"]["project_root"]},
        {"item": "Rscript found", "value": inventory["r"]["rscript_found"]},
        {"item": "Rscript path", "value": inventory["r"]["rscript_path"]},
        {"item": "R version", "value": inventory["r"]["r_version"]},
        {"item": "Platform", "value": inventory["system"]["platform"]},
    ]
    permission_summary = []
    for language_key, label in (("python", "Python"), ("r", "R")):
        for check, value in inventory[language_key].get("permission_results", {}).items():
            permission_summary.append({"language": label, "check": check, "value": value})
    summary_counts = [{"status": key, "count": value} for key, value in counts.items()]

    report_file.write_text(
        f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>SCE UAT Validation Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    h1, h2 {{ color: #102a43; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; font-size: 13px; }}
    th, td {{ border: 1px solid #bcccdc; padding: 6px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f0f4f8; }}
    .status {{ display: inline-block; padding: 6px 10px; border-radius: 4px; background: #e6f6ff; font-weight: bold; }}
    .meta {{ color: #52606d; }}
  </style>
</head>
<body>
  <h1>SCE UAT Validation Report</h1>
  <p class="meta">Run timestamp: {html.escape(run_timestamp)}</p>
  <p>Overall status: <span class="status">{html.escape(status)}</span></p>

  <h2>Environment Summary</h2>
  {html_table(environment_summary, ["item", "value"])}

  <h2>Permission Summary</h2>
  {html_table(permission_summary, ["language", "check", "value"])}

  <h2>Test Summary Counts</h2>
  {html_table(summary_counts, ["status", "count"])}

  <h2>Detailed Test Results</h2>
  {html_table(records, REPORT_FIELDNAMES)}

  <h2>Package Availability</h2>
  {html_table(package_rows, ["language", "package", "status", "version", "error_message"])}

  <h2>Clinical Validation</h2>
  {html_table(clinical_rows, ["language", "metric", "expected_value", "actual_value", "status", "source"])}

  <h2>Document Generation</h2>
  {html_table(document_rows, ["language", "output_type", "file_path", "status", "package_used", "error_message"])}

  <h2>Error Section</h2>
  {html_table(error_rows, ["test_id", "layer", "language", "test_name", "status", "error_message"])}
</body>
</html>
""",
        encoding="utf-8",
    )


def write_final_reports(
    records: list[dict],
    inventory: dict,
    package_rows: list[dict],
    clinical_rows: list[dict],
    document_rows: list[dict],
    status: str,
    run_id: str,
    run_timestamp: str,
    cleanup_summary: dict,
) -> None:
    csv_report = ROOT / "reports" / "uat_validation_report.csv"
    json_report = ROOT / "reports" / "uat_validation_report.json"
    html_report = ROOT / "reports" / "uat_validation_report.html"
    markdown_report = ROOT / "reports" / "uat_validation_report.md"
    word_report = ROOT_FINAL_WORD_REPORT
    manifest_report = ROOT / "reports" / "run_manifest.json"

    write_csv(csv_report, records, REPORT_FIELDNAMES)
    write_json(
        json_report,
        {
            "run_id": run_id,
            "timestamp": run_timestamp,
            "overall_status": status,
            "cleanup_summary": cleanup_summary,
            "status_counts": count_statuses(records),
            "test_results": records,
            "environment_summary": inventory,
            "package_availability": package_rows,
            "clinical_validation": clinical_rows,
            "document_generation": document_rows,
        },
    )
    generate_html_report(html_report, run_timestamp, status, inventory, records, package_rows, clinical_rows, document_rows)
    markdown_text = build_markdown_report(run_timestamp, status, inventory, records)
    write_markdown_report(markdown_report, markdown_text)
    write_docx_report(word_report, run_timestamp, status, inventory, records)

    report_files = [
        word_report,
        ROOT / "reports" / "environment_report.txt",
        ROOT / "reports" / "permission_report.txt",
        ROOT / "reports" / "package_availability.csv",
        csv_report,
        json_report,
        html_report,
        markdown_report,
    ]
    details = []
    for path in report_files:
        if path.exists():
            details.append(
                {
                    "file_path": safe_rel(path),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "run_id": run_id,
        "timestamp": run_timestamp,
        "root_path": str(ROOT),
        "python_executable": sys.executable,
        "rscript_path": inventory["r"]["rscript_path"],
        "overall_status": status,
        "cleanup_summary": cleanup_summary,
        "report_files": [item["file_path"] for item in details] + [safe_rel(manifest_report)],
        "report_file_details": details,
    }
    write_json(manifest_report, manifest)


def file_evidence_status(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "File does not exist."
    if path.stat().st_size <= 0:
        return False, "File exists but is empty."
    return True, f"File exists with {path.stat().st_size} bytes."


def add_file_evidence_record(records: list[dict], test_id: str, layer: str, language: str, test_name: str, path: Path) -> None:
    ok, message = file_evidence_status(path)
    records.append(
        make_record(
            test_id=test_id,
            layer=layer,
            language=language,
            test_name=test_name,
            status="PASS" if ok else "FAIL",
            expected_result="Generated file exists and has size greater than zero.",
            actual_result=message,
            output_file=safe_rel(path),
        )
    )


def skip_r_records(records: list[dict], required_r_tests: bool) -> None:
    status = "FAIL" if required_r_tests else "SKIPPED"
    expected = "Rscript is available for required R tests." if required_r_tests else "R tests skipped when R is unavailable."
    actual = (
        "Rscript was not found via SCE_UAT_RSCRIPT, PATH, R_HOME, RStudio environment, "
        "Windows registry, or environment-based R installation folders."
    )
    r_tests = [
        ("r_smoke", "Layer 1", "R smoke test"),
        ("r_io", "Layer 2", "R file I/O test"),
        ("r_package_availability", "Layer 3", "R package availability test"),
        ("r_clinical", "Layer 5", "R clinical summary validation"),
        ("python_call_rscript", "Layer 4", "Python calls Rscript validation"),
        ("r_document_generation", "Layer 6", "R document generation test"),
    ]
    for test_id, layer, test_name in r_tests:
        records.append(
            make_record(
                test_id=test_id,
                layer=layer,
                language="R" if test_id != "python_call_rscript" else "Python/R",
                test_name=test_name,
                status=status,
                expected_result=expected,
                actual_result=actual,
            )
        )


def run_uat() -> tuple[str, list[dict]]:
    try:
        cleanup_summary = clean_generated_artifacts(ROOT)
    except PermissionError as exc:
        raise StartupCleanupPermissionError(str(exc)) from exc
    config = load_config()
    required_r_tests = bool(config.get("required_r_tests", True))
    allow_optional_package_tests = bool(config.get("allow_optional_package_tests", True))
    allow_document_generation_tests = bool(config.get("allow_document_generation_tests", True))
    records: list[dict] = []
    run_timestamp = now_iso()
    run_id = "SCE_UAT_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    rscript_path = discover_rscript(config)
    if rscript_path:
        os.environ["SCE_UAT_RSCRIPT"] = rscript_path
    inventory = collect_environment_inventory(rscript_path)

    records.append(
        make_record(
            test_id="generated_artifact_cleanup",
            layer="Layer 0",
            language="Python",
            test_name="Generated artifact cleanup",
            status="PASS",
            expected_result="Previously generated files under outputs/ and reports/ are cleared before the run.",
            actual_result=(
                f"Removed {cleanup_summary['removed_files']} files and "
                f"{cleanup_summary['removed_directories']} directories; recreated run folders."
            ),
            output_file="outputs/; reports/",
        )
    )

    records.append(
        make_record(
            test_id="environment_inventory",
            layer="Layer 0",
            language="Python/R/System",
            test_name="Environment and permission inventory",
            status="PASS",
            expected_result="Environment inventory and permission reports generated.",
            actual_result="Inventory completed.",
            output_file="outputs/test_results/environment_inventory.json",
        )
    )

    r_detection_status = "PASS" if rscript_path else ("FAIL" if required_r_tests else "WARNING")
    records.append(
        make_record(
            test_id="rscript_detection",
            layer="Layer 0",
            language="R",
            test_name="Rscript detection",
            status=r_detection_status,
            expected_result=(
                "Rscript is discoverable via SCE_UAT_RSCRIPT, PATH, R_HOME, RStudio environment, "
                "Windows registry, or environment-based R installation folders."
            ),
            actual_result=rscript_path or "Rscript was not found.",
            error_message=""
            if rscript_path
            else (
                "Rscript was not found via SCE_UAT_RSCRIPT, PATH, R_HOME, RStudio environment, "
                "Windows registry, or environment-based R installation folders."
            ),
        )
    )

    records.append(
        run_command(
            "python_smoke",
            "Layer 1",
            "Python",
            "Python smoke test",
            [sys.executable, str(ROOT / "scripts" / "python" / "01_python_smoke_test.py"), str(ROOT)],
            "Python script runs and creates smoke-test evidence.",
            True,
            ROOT / "outputs" / "python" / "python_smoke_test.txt",
        )
    )

    if rscript_path:
        records.append(
            run_command(
                "r_smoke",
                "Layer 1",
                "R",
                "R smoke test",
                [rscript_path, str(ROOT / "scripts" / "r" / "01_r_smoke_test.R"), str(ROOT)],
                "R script runs and creates smoke-test evidence.",
                required_r_tests,
                ROOT / "outputs" / "r" / "r_smoke_test.txt",
            )
        )

    records.append(
        run_command(
            "python_io",
            "Layer 2",
            "Python",
            "Python file I/O test",
            [sys.executable, str(ROOT / "scripts" / "python" / "02_python_io_test.py"), str(ROOT)],
            "Python reads input and writes/reads generated files.",
            True,
            ROOT / "outputs" / "python" / "python_io_dm_copy.csv",
        )
    )

    if rscript_path:
        records.append(
            run_command(
                "r_io",
                "Layer 2",
                "R",
                "R file I/O test",
                [rscript_path, str(ROOT / "scripts" / "r" / "02_r_io_test.R"), str(ROOT)],
                "R reads input and writes/reads generated files.",
                required_r_tests,
                ROOT / "outputs" / "r" / "r_io_dm_copy.csv",
            )
        )

    if allow_optional_package_tests:
        records.append(
            run_command(
                "python_package_availability",
                "Layer 3",
                "Python",
                "Python package availability test",
                [sys.executable, str(ROOT / "scripts" / "python" / "03_python_import_test.py"), str(ROOT)],
                "Python package availability is classified without installation.",
                False,
                ROOT / "outputs" / "test_results" / "python_package_availability.csv",
            )
        )
        if rscript_path:
            records.append(
                run_command(
                    "r_package_availability",
                    "Layer 3",
                    "R",
                    "R package availability test",
                    [rscript_path, str(ROOT / "scripts" / "r" / "03_r_package_test.R"), str(ROOT)],
                    "R package availability is classified without installation.",
                    False,
                    ROOT / "outputs" / "test_results" / "r_package_availability.csv",
                )
            )
    else:
        records.append(
            make_record(
                "package_availability_skipped",
                "Layer 3",
                "Python/R",
                "Package availability tests",
                "SKIPPED",
                "Package tests are enabled in config.",
                "Package tests disabled by config.",
            )
        )

    records.append(
        run_command(
            "python_clinical",
            "Layer 5",
            "Python",
            "Python clinical summary validation",
            [sys.executable, str(ROOT / "scripts" / "python" / "04_python_clinical_summary.py"), str(ROOT)],
            "Python clinical metrics exactly match expected results.",
            True,
            ROOT / "outputs" / "test_results" / "python_clinical_validation.json",
        )
    )

    if rscript_path:
        records.append(
            run_command(
                "r_clinical",
                "Layer 5",
                "R",
                "R clinical summary validation",
                [rscript_path, str(ROOT / "scripts" / "r" / "04_r_clinical_summary.R"), str(ROOT)],
                "R clinical metrics exactly match expected AE and LB results.",
                required_r_tests,
                ROOT / "outputs" / "test_results" / "r_clinical_validation.csv",
            )
        )
        records.append(
            run_command(
                "python_call_rscript",
                "Layer 4",
                "Python/R",
                "Python calls Rscript validation",
                [sys.executable, str(ROOT / "scripts" / "python" / "06_python_call_rscript.py"), str(ROOT)],
                "Python calls R, R writes AE output, and Python validates it.",
                required_r_tests,
                ROOT / "outputs" / "test_results" / "python_calls_r_validation.json",
            )
        )
    else:
        skip_r_records(records, required_r_tests)

    if allow_document_generation_tests:
        records.append(
            run_command(
                "python_document_generation",
                "Layer 6",
                "Python",
                "Python document generation test",
                [sys.executable, str(ROOT / "scripts" / "python" / "05_python_document_generation.py"), str(ROOT)],
                "Python baseline documents generated and optional outputs classified.",
                False,
                ROOT / "outputs" / "test_results" / "python_document_generation_results.csv",
            )
        )
        if rscript_path:
            records.append(
                run_command(
                    "r_document_generation",
                    "Layer 6",
                    "R",
                    "R document generation test",
                    [rscript_path, str(ROOT / "scripts" / "r" / "05_r_document_generation.R"), str(ROOT)],
                    "R baseline documents generated and optional outputs classified.",
                    False,
                    ROOT / "outputs" / "test_results" / "r_document_generation_results.csv",
                )
            )
    else:
        records.append(
            make_record(
                "document_generation_skipped",
                "Layer 6",
                "Python/R",
                "Document generation tests",
                "SKIPPED",
                "Document generation tests are enabled in config.",
                "Document generation tests disabled by config.",
            )
        )

    package_rows = merge_package_availability()
    add_package_records(records, package_rows)
    clinical_rows = clinical_validation_rows()
    document_rows = document_generation_rows()
    add_document_records(records, document_rows)

    add_file_evidence_record(
        records,
        "python_smoke_file_evidence",
        "Layer 1",
        "Python",
        "Python smoke-test output file evidence",
        ROOT / "outputs" / "python" / "python_smoke_test.txt",
    )
    if rscript_path:
        add_file_evidence_record(
            records,
            "r_smoke_file_evidence",
            "Layer 1",
            "R",
            "R smoke-test output file evidence",
            ROOT / "outputs" / "r" / "r_smoke_test.txt",
        )
    add_file_evidence_record(
        records,
        "python_clinical_summary_file_evidence",
        "Layer 5",
        "Python",
        "Python clinical summary file evidence",
        ROOT / "outputs" / "python" / "python_clinical_summary.csv",
    )
    if rscript_path:
        add_file_evidence_record(
            records,
            "r_ae_summary_file_evidence",
            "Layer 5",
            "R",
            "R AE summary file evidence",
            ROOT / "outputs" / "r" / "ae_summary_from_r.csv",
        )
        add_file_evidence_record(
            records,
            "r_lb_summary_file_evidence",
            "Layer 5",
            "R",
            "R LB summary file evidence",
            ROOT / "outputs" / "r" / "lb_summary_from_r.csv",
        )

    required_ids = {
        "python_smoke",
        "python_io",
        "rscript_detection",
        "r_smoke",
        "r_io",
        "python_clinical",
        "r_clinical",
        "python_call_rscript",
        "final_report_generation",
    }
    if not required_r_tests:
        required_ids = required_ids - {"rscript_detection", "r_smoke", "r_io", "r_clinical", "python_call_rscript"}

    final_status = overall_status(records, required_ids - {"final_report_generation"})
    final_report_files = [
        ROOT_FINAL_WORD_REPORT,
        ROOT / "reports" / "uat_validation_report.csv",
        ROOT / "reports" / "uat_validation_report.json",
        ROOT / "reports" / "uat_validation_report.html",
        ROOT / "reports" / "uat_validation_report.md",
        ROOT / "reports" / "run_manifest.json",
    ]
    records.append(
        make_record(
            "final_report_generation",
            "Layer 7",
            "Python",
            "Final UAT report generation",
            "PASS",
            "Final root-level Word, CSV, JSON, HTML, Markdown, and manifest reports generated.",
            "Final report generation completed.",
            output_file="; ".join(safe_rel(path) for path in final_report_files),
        )
    )
    final_status = overall_status(records, required_ids)
    write_final_reports(
        records,
        inventory,
        package_rows,
        clinical_rows,
        document_rows,
        final_status,
        run_id,
        run_timestamp,
        cleanup_summary,
    )
    return final_status, records


def write_emergency_error_report(exc: Exception) -> None:
    ensure_directories()
    error_record = make_record(
        "run_uat_unexpected_error",
        "Layer 7",
        "Python",
        "run_uat.py unexpected error",
        "ERROR",
        "Runner completes without crashing.",
        "Runner encountered an unexpected error.",
        error_message=traceback.format_exc(),
    )
    inventory = {
        "timestamp": now_iso(),
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "current_working_directory": os.getcwd(),
            "project_root": str(ROOT),
            "platform": platform.platform(),
            "username": "",
            "permission_results": {},
        },
        "r": {
            "rscript_found": False,
            "rscript_path": "",
            "r_version": "",
            "r_working_directory": "",
            "r_lib_paths": [],
            "r_session_info": "",
            "permission_results": {},
            "errors": [str(exc)],
        },
        "system": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "directory_existence": {},
            "errors": [str(exc)],
        },
    }
    write_environment_reports(inventory)
    write_csv(ROOT / "reports" / "uat_validation_report.csv", [error_record], REPORT_FIELDNAMES)
    write_json(
        ROOT / "reports" / "uat_validation_report.json",
        {"overall_status": "ERROR", "test_results": [error_record], "error": traceback.format_exc()},
    )
    generate_html_report(
        ROOT / "reports" / "uat_validation_report.html",
        now_iso(),
        "ERROR",
        inventory,
        [error_record],
        [],
        [],
        [],
    )
    markdown_text = build_markdown_report(now_iso(), "ERROR", inventory, [error_record])
    write_markdown_report(ROOT / "reports" / "uat_validation_report.md", markdown_text)
    write_docx_report(ROOT_FINAL_WORD_REPORT, now_iso(), "ERROR", inventory, [error_record])
    write_json(
        ROOT / "reports" / "run_manifest.json",
        {
            "run_id": "SCE_UAT_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
            "timestamp": now_iso(),
            "root_path": str(ROOT),
            "python_executable": sys.executable,
            "rscript_path": discover_rscript(load_config()) or "",
            "overall_status": "ERROR",
            "report_files": [
                safe_rel(ROOT_FINAL_WORD_REPORT),
                "reports/environment_report.txt",
                "reports/permission_report.txt",
                "reports/uat_validation_report.csv",
                "reports/uat_validation_report.json",
                "reports/uat_validation_report.html",
                "reports/uat_validation_report.md",
                "reports/run_manifest.json",
            ],
        },
    )


def print_summary(status: str, records: list[dict]) -> None:
    counts = count_statuses(records)
    print("")
    print("SCE UAT run complete")
    print(f"Overall status: {status}")
    print(f"PASS: {counts.get('PASS', 0)}")
    print(f"FAIL: {counts.get('FAIL', 0)}")
    print(f"WARNING: {counts.get('WARNING', 0)}")
    print(f"NOT_AVAILABLE: {counts.get('NOT_AVAILABLE', 0)}")
    print("")
    print("Final report paths:")
    print(f"- {ROOT_FINAL_WORD_REPORT}")
    print(f"- {ROOT / 'reports' / 'uat_validation_report.csv'}")
    print(f"- {ROOT / 'reports' / 'uat_validation_report.json'}")
    print(f"- {ROOT / 'reports' / 'uat_validation_report.html'}")
    print(f"- {ROOT / 'reports' / 'uat_validation_report.md'}")
    print(f"- {ROOT / 'reports' / 'run_manifest.json'}")


def main() -> int:
    lock_acquired = False
    try:
        acquire_run_lock()
        lock_acquired = True
        status, records = run_uat()
        print_summary(status, records)
        return 0 if status in {"PASS", "PASS_WITH_WARNINGS"} else 1
    except RunLockError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except StartupCleanupPermissionError as exc:
        message = (
            "SCE UAT startup failed due to permission errors while cleaning outputs/ and reports/. "
            "The runner requires create, write, read, append, and delete permissions in both folders."
        )
        print(message, file=sys.stderr)
        print(str(exc), file=sys.stderr)
        write_startup_error_file(message, exc)
        return 1
    except Exception as exc:
        write_emergency_error_report(exc)
        print("SCE UAT runner encountered an unexpected error.", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if lock_acquired:
            release_run_lock()


if __name__ == "__main__":
    raise SystemExit(main())
