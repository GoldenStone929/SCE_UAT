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
echo Review the reports folder for results.
echo.
pause
exit /b %UAT_EXIT_CODE%
