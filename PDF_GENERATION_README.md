# PDF Generation README

## Purpose of this file

Use this README as source material for generating a polished PDF summary of the `SCE_UAT_R_Python_Test_Package`.

The PDF should explain what the package is, what it tests, what each UAT layer means, what evidence is generated, and how a Windows Server 2019 SCE reviewer should interpret the results.

The intended audience is:

- SCE platform owners
- clinical/statistical programmers
- validation reviewers
- QA or audit stakeholders
- study programming leads

## Recommended PDF title

```text
SCE UAT R/Python Functional Test Package
Windows Server 2019 SCE Validation Summary
```

## Short project summary

This project is a portable User Acceptance Testing package for a Windows Server 2019 Statistical Computing Environment. It verifies that the SCE can support common clinical/statistical programming workflows using Python and R.

The package is run from the project root using:

```cmd
python run_uat.py
```

or:

```cmd
py run_uat.py
```

Windows users may also double-click:

```text
run_uat_windows.bat
```

The package uses fake, non-PHI clinical-style data only. It does not install Python or R packages.

## What the package tests

The UAT package tests:

- Python execution
- R execution through `Rscript`
- relative path handling
- file and folder permissions
- CSV/TXT/JSON/HTML output generation
- optional Excel, Word, PDF, and R Markdown-style output capability
- Python package availability
- R package availability
- Python-to-R orchestration
- fake clinical dataset processing
- validation against expected results
- final audit-friendly report generation

## UAT layer summary

### Layer 0: Environment and permission inventory

Layer 0 collects baseline environment evidence before functional tests are reviewed.

It records:

- Python version
- Python executable path
- current working directory
- project root path
- operating system and platform information
- username, if available
- whether Python can create folders and create, write, read, append, and delete files under `outputs/`
- whether `Rscript` is found
- R version
- R working directory
- R library paths
- R `sessionInfo()`
- whether R can create, write, read, append, and delete files under `outputs/`

Primary evidence:

- `reports/environment_report.txt`
- `reports/permission_report.txt`
- `outputs/test_results/environment_inventory.json`

### Layer 1: Basic execution smoke tests

Layer 1 confirms that Python and R can execute simple scripts from the uploaded package.

Python smoke test:

- runs `scripts/python/01_python_smoke_test.py`
- writes `outputs/python/python_smoke_test.txt`

R smoke test:

- runs `scripts/r/01_r_smoke_test.R`
- writes `outputs/r/r_smoke_test.txt`

The root runner captures stdout, stderr, return code, runtime, and PASS/FAIL status.

### Layer 2: Relative path and file I/O tests

Layer 2 verifies that scripts can use relative paths from the package root and perform file operations.

Python I/O test:

- reads `data/input/fake_dm.csv`
- writes CSV, TXT, and JSON outputs
- creates a subfolder
- appends to a log
- reads back generated files
- verifies file size is greater than zero

R I/O test:

- reads `data/input/fake_dm.csv`
- writes CSV and TXT outputs
- creates a subfolder
- appends to a log
- reads back generated files
- verifies generated files exist and are non-empty

### Layer 3: Package and import availability tests

Layer 3 checks whether common optional Python and R packages are already available in the SCE.

No packages are installed.

Python packages checked:

- pandas
- numpy
- openpyxl
- docx
- reportlab
- PyPDF2
- pdfplumber
- matplotlib

R packages checked:

- dplyr
- tidyr
- readxl
- openxlsx
- officer
- flextable
- rmarkdown
- knitr
- ggplot2
- haven

Statuses include:

- `AVAILABLE`
- `NOT_AVAILABLE`
- `BLOCKED`
- `ERROR`

Primary evidence:

- `outputs/test_results/python_package_availability.csv`
- `outputs/test_results/r_package_availability.csv`
- `reports/package_availability.csv`

Missing optional packages should be interpreted as capability gaps, not baseline UAT failures.

### Layer 4: Python manages Rscript

Layer 4 proves that Python can orchestrate R inside the same SCE folder.

The test:

- runs `scripts/python/06_python_call_rscript.py`
- detects `Rscript` using `SCE_UAT_RSCRIPT` (when set to a valid file path) or the system path
- calls `scripts/r/04_r_clinical_summary.R`
- passes the project root to R
- verifies that R creates `outputs/r/ae_summary_from_r.csv`
- reads the R output from Python
- compares it to `data/expected/expected_ae_summary.csv`
- writes validation evidence

Primary evidence:

- `outputs/test_results/python_calls_r_validation.json`
- `outputs/logs/python_call_rscript.log`
- `outputs/logs/python_calls_rscript_nested_r.log`

### Layer 5: Fake clinical dataset analysis

Layer 5 validates clinical/statistical-style data processing using fake data.

Input datasets:

- `data/input/fake_dm.csv`
- `data/input/fake_ae.csv`
- `data/input/fake_lb.csv`

The package calculates deterministic metrics including:

- total subjects
- safety subjects
- total AE records
- subjects with AE
- serious AE records
- treatment-related AE records
- severe AE records
- AE start-after-end records
- total lab records
- ALT high records
- AST high records
- missing lab unit records
- non-numeric lab result records
- abnormal high lab records

Expected results are stored under:

- `data/expected/expected_clinical_summary.csv`
- `data/expected/expected_ae_summary.csv`
- `data/expected/expected_lb_summary.csv`
- `data/expected/expected_checks.json`

Primary evidence:

- `outputs/python/python_clinical_summary.csv`
- `outputs/test_results/python_clinical_validation.json`
- `outputs/r/ae_summary_from_r.csv`
- `outputs/r/lb_summary_from_r.csv`
- `outputs/test_results/r_clinical_validation.csv`

### Layer 6: Document and output generation tests

Layer 6 verifies whether the SCE can produce common output artifacts.

Baseline Python outputs:

- TXT
- CSV
- JSON
- HTML

Optional Python outputs:

- XLSX if `openpyxl` is available
- DOCX if `docx` is available
- PDF if `reportlab` is available

Baseline R outputs:

- TXT
- CSV
- HTML

Optional R outputs:

- XLSX if `openxlsx` is available
- DOCX if `officer` is available
- PDF through base R PDF device where possible
- R Markdown output if `rmarkdown` is available

Primary evidence:

- `outputs/test_results/python_document_generation_results.csv`
- `outputs/test_results/r_document_generation_results.csv`
- generated files under `outputs/generated_documents/`

### Layer 7: Final UAT report generation

Layer 7 consolidates all test evidence into final reports.

Final reports:

- `reports/uat_validation_report.pdf`
- `reports/uat_validation_report.html`
- `reports/uat_validation_report.csv`
- `reports/uat_validation_report.json`
- `reports/run_manifest.json`
- `reports/environment_report.txt`
- `reports/permission_report.txt`
- `reports/package_availability.csv`

The HTML report is the recommended first review artifact.

## Status interpretation

Use these status definitions in the PDF:

- `PASS`: required behavior completed and matched the expected result.
- `FAIL`: required behavior ran but did not meet the expected result.
- `WARNING`: non-blocking issue or optional concern.
- `NOT_AVAILABLE`: optional package or optional output type is unavailable.
- `SKIPPED`: test was not run because a runtime was unavailable or disabled by configuration.
- `ERROR`: test encountered an unexpected error.

Overall status values:

- `PASS`: all required baseline tests passed.
- `PASS_WITH_WARNINGS`: required baseline tests passed, but optional packages or optional outputs were unavailable.
- `FAIL`: one or more required baseline tests failed.
- `ERROR`: the root runner encountered an unexpected error.

## Important portability points

The PDF should clearly state:

- Windows Server 2019 is the primary target environment.
- The package is portable and can be copied to an SCE workspace.
- The package does not rely on fixed folders, drive letters, usernames, or network paths.
- The root is detected from `run_uat.py`.
- Python child scripts are launched using the active Python interpreter.
- Rscript is discovered from `SCE_UAT_RSCRIPT` (if valid) or the system path.
- Rscript paths are not hardcoded.
- The package does not install Python or R packages.

## No PHI statement

Include a clear statement:

```text
This package contains no real patient data and no Protected Health Information. All datasets are synthetic and are intended only for SCE UAT evidence generation.
```

## Suggested PDF sections

Use this structure for the PDF:

1. Executive summary
2. Purpose and target environment
3. How the package is run
4. UAT layer overview
5. Detailed layer-by-layer test description
6. Fake clinical data and expected results
7. Output reports and evidence files
8. Status definitions and interpretation
9. Portability and Windows Server 2019 considerations
10. No PHI statement
11. Reviewer checklist
12. Appendix: file and folder map

## Copy/paste prompt for ChatGPT 5.5

Use the following prompt to generate the PDF narrative:

```text
You are preparing a polished PDF document for validation reviewers and clinical/statistical programming stakeholders.

Create a professional PDF-style document titled:
"SCE UAT R/Python Functional Test Package - Windows Server 2019 SCE Validation Summary"

Use the following content as source material. Explain the purpose of the package, the Windows Server 2019 target environment, what each UAT layer tests, what evidence files are generated, how to interpret statuses, and why the package is portable and non-PHI.

Audience:
- SCE platform owners
- clinical/statistical programmers
- validation reviewers
- QA or audit stakeholders

Tone:
- clear
- audit-friendly
- concise but complete
- suitable for a regulated clinical/statistical programming environment

Important constraints:
- Do not claim that the package passed on the target Windows Server 2019 SCE unless target-environment reports are provided.
- State that final Windows Server 2019 acceptance evidence should come from running the package in the target SCE.
- Do not include package installation instructions.
- Do not include real patient data.
- Emphasize that optional missing packages are reported as NOT_AVAILABLE, not as required failures.

Please produce:
1. a cover/title section,
2. an executive summary,
3. a layer-by-layer UAT explanation,
4. a table of evidence files,
5. a status interpretation section,
6. a Windows Server 2019 reviewer checklist,
7. a short conclusion.

Source material:
[Paste the contents of PDF_GENERATION_README.md and README.md here.]
```

## Suggested evidence table for the PDF

| Evidence area | Primary files |
| --- | --- |
| Environment inventory | `reports/environment_report.txt`, `outputs/test_results/environment_inventory.json` |
| Permission checks | `reports/permission_report.txt` |
| Package availability | `reports/package_availability.csv` |
| Python execution | `outputs/python/python_smoke_test.txt`, `outputs/logs/python_smoke.log` |
| R execution | `outputs/r/r_smoke_test.txt`, `outputs/logs/r_smoke.log` |
| Python I/O | `outputs/python/python_io_dm_copy.csv`, `outputs/logs/python_io.log` |
| R I/O | `outputs/r/r_io_dm_copy.csv`, `outputs/logs/r_io.log` |
| Python clinical validation | `outputs/test_results/python_clinical_validation.json` |
| R clinical validation | `outputs/test_results/r_clinical_validation.csv` |
| Python-to-R orchestration | `outputs/test_results/python_calls_r_validation.json` |
| Document generation | `outputs/test_results/python_document_generation_results.csv`, `outputs/test_results/r_document_generation_results.csv` |
| Final UAT report | `reports/uat_validation_report.pdf`, `reports/uat_validation_report.html`, `reports/uat_validation_report.csv`, `reports/uat_validation_report.json` |
| Run manifest | `reports/run_manifest.json` |

## Reviewer checklist for the PDF

Include this checklist:

- Confirm the package was run from the package root.
- Confirm the target environment is Windows Server 2019 or the intended SCE.
- Confirm `reports/uat_validation_report.pdf` exists and opens.
- Confirm `reports/uat_validation_report.html` exists and opens.
- Confirm required tests have no `FAIL` or `ERROR` status.
- Confirm optional missing packages are shown as `NOT_AVAILABLE`.
- Confirm Python-to-R orchestration passed if R is required.
- Confirm fake clinical metrics match expected results.
- Confirm logs exist under `outputs/logs/`.
- Confirm no real patient data or PHI is present.
- Confirm target-environment evidence was generated in the target SCE.
