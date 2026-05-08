@echo off
setlocal

cd /d "%~dp0"

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
set UAT_EXIT_CODE=1

:done
exit /b %UAT_EXIT_CODE%
