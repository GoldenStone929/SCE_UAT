@echo off
setlocal

cd /d "%~dp0"

echo Running SCE UAT R/Python Functional Test Package...
echo.

where python >nul 2>nul
if errorlevel 1 goto try_py

python run_uat.py
set UAT_EXIT_CODE=%ERRORLEVEL%
goto done

:try_py
where py >nul 2>nul
if errorlevel 1 goto no_python

py run_uat.py
set UAT_EXIT_CODE=%ERRORLEVEL%
goto done

:no_python
echo ERROR: Could not find python or py on PATH.
echo Please start this package from a Windows Server 2019 environment with Python available.
set UAT_EXIT_CODE=1

:done
echo.
echo UAT finished with exit code %UAT_EXIT_CODE%.
echo Review Final_Report.docx in this folder for the main reviewer report.
echo If Windows hides file extensions, this appears as Final_Report with Type Microsoft Word Document.
echo A matching Word copy is also written to reports\Final_Report.docx.
echo Review the reports folder for supporting CSV, JSON, HTML, Markdown, and manifest results.
echo.
pause
exit /b %UAT_EXIT_CODE%
