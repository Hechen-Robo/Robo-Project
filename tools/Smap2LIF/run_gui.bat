@echo off
setlocal
cd /d "%~dp0"

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo ERROR: Project virtual environment was not found.
    echo Run build.bat or create .venv and install the project first.
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m smap2lif --gui
if errorlevel 1 (
    echo.
    echo Smap2LIF exited with an error.
    pause
    exit /b 1
)

exit /b 0
