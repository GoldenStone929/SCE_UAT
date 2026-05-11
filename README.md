# SCE UAT R/Python Functional Test Package

## 1. Purpose

This package provides objective User Acceptance Testing (UAT) evidence for a Windows Server 2019 Statistical Computing Environment (SCE). It checks whether the environment can run basic Python and R workflows used by clinical and statistical programmers.

Windows Server 2019 is the primary target environment for this package. The package is intended for SCE qualification, onboarding, or regression testing and does not use real clinical trial data.

The package writes only within its own `outputs/` and `reports/` folders and does not modify SCE system configuration, installed software, or package libraries.

## 2. What this package tests

- Python execution and R execution.
- Relative paths from the package root.
- File and folder permissions under `outputs/`.
- CSV, TXT, JSON, HTML, and optional document generation.
- Python package and R package availability without installing anything.
- Python orchestration of R through `Rscript`.
- Fake clinical dataset processing and validation against expected results.
- Final audit-friendly reporting in a root-level Word document and supporting files under `reports/`.

## 3. Folder structure

```text
SCE_UAT_R_Python_Test_Package/
  run_uat.py
  run_uat_windows.bat
  run_uat_ssh.bat
  Final_Report.docx  (generated after each run)
  README.md
  config.json
  data/
    input/
      fake_dm.csv
      fake_ae.csv
      fake_lb.csv
    expected/
      expected_clinical_summary.csv
      expected_ae_summary.csv
      expected_lb_summary.csv
      expected_checks.json
  scripts/
    python/
    r/
  outputs/
    python/
      generated_documents/
    r/
      generated_documents/
    logs/
    test_results/
  reports/
```

## 4. How to run on Windows Server 2019

Open a terminal in the package root folder. The root folder is the folder that contains `run_uat.py`.

Do not run `run_uat.py` from inside `scripts/` or another subfolder. Run it from the folder containing `run_uat.py`, or use `run_uat_windows.bat`.

Recommended Windows commands:

Run:

```cmd
python run_uat.py
```

If the environment exposes Python through the Windows Python launcher, run:

```cmd
py run_uat.py
```

## 5. Windows double-click launcher

The main helper launcher is:

```text
run_uat_windows.bat
```

On Windows Server 2019, double-click `run_uat_windows.bat` from the package root.

The batch file:

- changes to the package folder using `cd /d "%~dp0"`;
- tries `python run_uat.py`;
- if `python` is unavailable, tries `py run_uat.py`;
- shows a clear error if neither command is available;
- pauses before closing so the user can read the console summary.

The batch launcher should support package folders with spaces in the path.

The helper launcher only starts the root-level `run_uat.py`. The audited runner remains `run_uat.py`.

The root-level launcher derives the package root from its own location and then runs all tests using relative paths.

## Remote SSH / Headless Execution

For remote Windows sessions, SSH sessions, scheduled jobs, and other headless execution, use one of:

```cmd
python run_uat.py
```

or:

```cmd
run_uat_ssh.bat
```

`run_uat_ssh.bat` is non-interactive, does not use `pause`, and returns the UAT exit code to the calling shell.

Every run writes the main reviewer report next to the root-level launchers:

```text
Final_Report.docx
```

This Word report records all tests from the run, groups them by UAT layer, and uses an XOR table format (`Check` for PASS, `X` for non-PASS). It is intended to open cleanly in Microsoft Word on Windows.

Required filesystem permissions for successful startup and execution:

- create, write, read, append, and delete under `outputs/`;
- create, write, read, append, and delete under `reports/`.

R runtime requirement for headless and interactive runs:

- `Rscript` should be available through Windows PATH, R installation registration, or R-related environment values; or
- set `SCE_UAT_RSCRIPT` to an explicit `Rscript.exe` executable path.
- if R is only easy to locate from RStudio, run `cat(file.path(R.home("bin"), "Rscript.exe"))` in RStudio and copy that path into `SCE_UAT_RSCRIPT` or `config.json` as `rscript_path`.

This package does not install Python, R, or Python/R packages.

## 6. Output reports

The primary all-in-one reviewer report is written at the package root:

- `Final_Report.docx`: final Word report grouped by UAT section with XOR row marks (`Check`/`X`).

Supporting reports are written to `reports/`:

- `uat_validation_report.html`: recommended first review artifact.
- `uat_validation_report.md`: readable Markdown reviewer summary.
- `uat_validation_report.csv`: detailed test-result table.
- `uat_validation_report.json`: machine-readable detailed report.
- `environment_report.txt`: Python, R, system, and runtime inventory.
- `permission_report.txt`: file and folder permission checks.
- `package_availability.csv`: optional Python/R package availability.
- `run_manifest.json`: run ID, timestamp, executable paths, overall status, report files, sizes, and SHA256 checksums.

Detailed evidence, logs, and generated test files are written under `outputs/`:

- `outputs/logs/`: stdout/stderr logs for executed scripts.
- `outputs/test_results/`: validation JSON/CSV evidence.
- `outputs/python/`: Python-generated test outputs, including readable Python document outputs under `outputs/python/generated_documents/`.
- `outputs/r/`: R-generated test outputs, including readable R document outputs under `outputs/r/generated_documents/`.

Each run refreshes generated artifacts under `outputs/` and `reports/` before creating new evidence, and overwrites the root-level `Final_Report.docx`, so the review artifacts reflect the latest execution.

## 7. Status definitions

- `PASS`: Required behavior completed and matched the expected result.
- `FAIL`: Required behavior ran but did not meet the expected result.
- `WARNING`: Non-blocking issue or optional concern.
- `NOT_AVAILABLE`: Optional package or optional output type is not available.
- `SKIPPED`: Test was not run because a required runtime was unavailable or disabled.
- `ERROR`: Test encountered an unexpected error.

Overall status values:

- `PASS`: all required baseline tests passed.
- `PASS_WITH_WARNINGS`: all required baseline tests passed, but optional capabilities were missing or produced warnings.
- `FAIL`: one or more required baseline tests failed.
- `ERROR`: the root runner encountered an unexpected error.

## 8. Required vs optional tests

Required tests include Python smoke, Python I/O, Python clinical validation, and final report generation. When `required_r_tests=true`, required tests also include Rscript detection, R smoke, R I/O, R clinical validation, and Python-to-R orchestration.

Optional tests include package availability checks and optional Excel, Word, PDF, and related document outputs. Missing optional packages are reported as `NOT_AVAILABLE`, not as required failures.

## 9. Fake clinical data description

The package includes three fake CSV datasets:

- `fake_dm.csv`: 10 fake subjects with site, arm, sex, age, and safety flag.
- `fake_ae.csv`: 8 fake adverse event records with deterministic severity, relationship, seriousness, and date-quality counts.
- `fake_lb.csv`: 12 fake lab records with deterministic high, missing-unit, and non-numeric result counts.

Expected results are stored in `data/expected/` and are used for exact validation.

Expected validation counts include:

- total subjects: 10
- safety subjects: 9
- total AE records: 8
- unique subjects with AE: 6
- serious AE records: 2
- treatment-related AE records: 4
- severe AE records: 1
- AE start-after-end records: 1
- total LB records: 12
- ALT high records: 2
- AST high records: 1
- missing lab unit records: 1
- non-numeric lab result records: 1
- abnormal high lab records: 3

## 10. No PHI statement

No real patient data is included. All subjects, dates, sites, events, and lab values are synthetic and non-PHI.

## 11. Windows portability rule

The package is designed to be copied to any Windows Server 2019 SCE workspace. All paths are resolved relative to the package root. The runner derives the root from its own file location and child scripts receive that root as an argument.

The package does not rely on user names, local folders, drive names, or predefined workspace locations.

Portability constraints:

- No predefined absolute path is required.
- No local username, home folder, network path, or drive letter is required.
- `run_uat.py` derives the root from `Path(__file__).resolve().parent`.
- Python child scripts are launched using `sys.executable`.
- Rscript discovery starts with `SCE_UAT_RSCRIPT` and `shutil.which("Rscript")`, then checks Windows-friendly sources such as `R_HOME`, RStudio's R executable environment, Windows R registry entries, and environment-based R installation folders.
- Rscript paths are not hardcoded.
- Python subprocess calls use list arguments rather than shell command strings to avoid Windows path and space issues.
- All input, output, report, log, and script paths are resolved relative to the package root.
- The package does not install software or packages.

## 12. Configuration

The configuration file is `config.json`.

Default configuration:

```json
{
  "project_name": "SCE_UAT_R_Python_Test_Package",
  "required_python_tests": true,
  "required_r_tests": true,
  "allow_optional_package_tests": true,
  "allow_document_generation_tests": true,
  "treat_missing_optional_packages_as_failure": false,
  "output_timezone": "local",
  "rscript_path": "",
  "rscript_search_roots": []
}
```

If `required_r_tests` is `true` and `Rscript` is not discoverable through the supported Windows R discovery methods, the overall result is `FAIL`. If `required_r_tests` is changed to `false`, unavailable R tests are reported as skipped or warnings.

## 13. Troubleshooting

If Python does not start:

- Confirm the Windows Server 2019 environment exposes either `python` or `py`.
- Confirm the command is run from the folder containing `run_uat.py`.
- If double-clicking, use `run_uat_windows.bat`.

If R tests fail:

- Confirm `Rscript` is available to the Windows Server 2019 session.
- If R works in RStudio but `Rscript` is not on the Windows PATH, run `cat(file.path(R.home("bin"), "Rscript.exe"))` in RStudio.
- Set `SCE_UAT_RSCRIPT` to that full `Rscript.exe` path, or paste it into `config.json` as `rscript_path`.
- If R is in a custom folder, add that folder to `rscript_search_roots` in `config.json`.
- Review `reports/environment_report.txt`.
- Review R logs under `outputs/logs/`.

If permission checks fail:

- Confirm the SCE allows creating, writing, reading, appending, and deleting files under the package `outputs/` and `reports/` folders.

If optional packages are missing:

- Review `reports/package_availability.csv`.
- Missing optional packages are expected in many environments and are not required failures unless configuration or local policy says otherwise.

If a clinical validation fails:

- Review `outputs/test_results/python_clinical_validation.json`.
- Review `outputs/test_results/r_clinical_validation.csv`.
- Compare the actual summary outputs against `data/expected/`.

## 14. How to interpret results

Start with:

```text
Final_Report.docx
```

Then review:

```text
reports/uat_validation_report.html
```

Recommended review order:

1. Confirm the overall status at the top of the HTML report.
2. Confirm required tests have no `FAIL` or `ERROR` status.
3. Review `reports/package_availability.csv` for optional package gaps.
4. Review the clinical validation section for metric-level PASS/FAIL evidence.
5. Review `reports/run_manifest.json` for run ID, timestamp, report list, and checksums.
6. Use `outputs/logs/` if a test needs deeper inspection.

## 15. Windows Server 2019 final review checklist

Before accepting the UAT evidence, confirm:

- The package was run from the package root on Windows Server 2019.
- The run used `python run_uat.py`, `py run_uat.py`, `run_uat_ssh.bat`, or `run_uat_windows.bat`.
- `Final_Report.docx` exists beside the root-level launcher scripts and opens in Word.
- `reports/uat_validation_report.md` exists and is readable.
- `reports/uat_validation_report.html` exists and opens.
- `reports/uat_validation_report.csv` exists and contains detailed test rows.
- `reports/uat_validation_report.json` exists and is machine-readable.
- `reports/run_manifest.json` exists.
- `outputs/logs/` contains logs for executed scripts.
- `outputs/test_results/` contains validation evidence.
- Python smoke, Python I/O, and Python clinical validation passed.
- Rscript detection, R smoke, R I/O, and R clinical validation passed when R is required.
- Python-to-R orchestration passed when R is required.
- Missing optional packages are shown as `NOT_AVAILABLE`, not `FAIL`.
- No real patient data or PHI is present.

## 16. Windows Server 2019 verification expectation

For final Windows SCE acceptance, run one of:

```cmd
python run_uat.py
```

or:

```cmd
py run_uat.py
```

Then confirm that `reports/` contains:

- `uat_validation_report.html`
- `uat_validation_report.md`
- `uat_validation_report.csv`
- `uat_validation_report.json`
- `run_manifest.json`
- `environment_report.txt`
- `permission_report.txt`
- `package_availability.csv`

Also confirm the package root contains:

- `Final_Report.docx`

## 17. GitHub distribution note

If this package is distributed through GitHub, clone or download the repository and run from the package root on Windows Server 2019.

GitHub should contain the source package, configuration, fake input data, expected results, scripts, and documentation. Generated UAT evidence under `outputs/` and `reports/` is intentionally ignored by Git because each SCE run creates fresh environment-specific evidence.

The root-level Word report `Final_Report.docx` is also ignored by Git. It appears only **on your machine** in the package root **after you run** `python run_uat.py`, `py run_uat.py`, or `run_uat_windows.bat`. You will **not** see it in the GitHub file browser unless someone commits binary evidence on purpose.

The runner creates the folder **`outputs/`** (plural name), not `output/`.

After cloning or downloading from GitHub, run one of:

```cmd
python run_uat.py
```

or:

```cmd
py run_uat.py
```

The runner recreates the required `outputs/` and `reports/` folders automatically.

## 18. Preparation workspace verification result

During package preparation, the package was executed in the available development workspace using the local Python interpreter.

Observed result:

```text
Overall status: PASS_WITH_WARNINGS
PASS: 32
FAIL: 0
WARNING: 0
NOT_AVAILABLE: 22
```

The `PASS_WITH_WARNINGS` status was expected because optional packages were not all available in the preparation environment. Required baseline tests passed.

Final Windows Server 2019 execution should be performed in the target SCE to generate environment-specific evidence under `reports/`.

## 19. Implementation consistency verification

The package implementation was checked against this README.

Verified implementation points:

- `run_uat.py` derives `ROOT` using `Path(__file__).resolve().parent`.
- Python child scripts are launched using `sys.executable`.
- Rscript discovery starts with `SCE_UAT_RSCRIPT` and `shutil.which("Rscript")`, then checks Windows-friendly R sources such as `R_HOME`, RStudio environment values, Windows registry entries, and environment-based R installation folders.
- Python subprocess calls use list arguments rather than shell command strings.
- `run_uat_windows.bat` uses `cd /d "%~dp0"` and is designed to support package folders with spaces in the path.
- Optional missing packages are reported as `NOT_AVAILABLE`, not `FAIL`.
- With `required_r_tests=true`, missing Rscript is treated as a required failure.
- The final Word reviewer report is generated at the package root as `Final_Report.docx`.
- Supporting reports are generated under `reports/`, including readable HTML and Markdown summaries.
- Runtime logs and test evidence are generated under `outputs/`.
- Python generated documents are written under `outputs/python/generated_documents/`.
- R generated documents are written under `outputs/r/generated_documents/`.
- No package installation commands are included.
- No fixed drive letters, usernames, network paths, or hardcoded Rscript paths are required.

Preparation-workspace verification produced:

```text
Overall status: PASS_WITH_WARNINGS
PASS: 32
FAIL: 0
WARNING: 0
NOT_AVAILABLE: 22
```

The preparation-workspace result confirms that the package runs successfully in the available development environment. Final acceptance evidence must still be generated by running the package in the target Windows Server 2019 SCE.
