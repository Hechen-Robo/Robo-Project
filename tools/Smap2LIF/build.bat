@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   Smap2LIF Windows Build
echo ========================================
echo.

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
set "REPOSITORY_PYTHON=%CD%\..\..\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo Creating project virtual environment...

    if exist "%REPOSITORY_PYTHON%" (
        "%REPOSITORY_PYTHON%" -m venv .venv
        goto :venv_created
    )

    python -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        python -m venv .venv
        goto :venv_created
    )

    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv .venv
        goto :venv_created
    )

    echo ERROR: No usable Python interpreter was found.
    echo Install Python 3.10 or newer, then run build.bat again.
    goto :failed
)

goto :venv_ready

:venv_created
if errorlevel 1 goto :failed

:venv_ready
if not exist "%VENV_PYTHON%" (
    echo ERROR: Virtual-environment Python was not created.
    goto :failed
)

"%VENV_PYTHON%" -c "import sys; print('Base Python:', sys.base_prefix)"
if errorlevel 1 goto :failed

echo Installing application and build dependencies...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"%VENV_PYTHON%" -m pip install -e ".[build]"
if errorlevel 1 goto :failed

echo.
echo Checking build-time Tk runtime...
"%VENV_PYTHON%" -c "import tkinter as tk; root = tk.Tk(); root.withdraw(); root.update_idletasks(); root.destroy(); print('Tk runtime check: PASSED')"
if errorlevel 1 (
    echo ERROR: Tkinter or its Tcl/Tk runtime is not usable.
    echo Install Python 3.10 or newer with Tcl/Tk support,
    echo recreate .venv, and then run build.bat again.
    goto :failed
)

echo.
echo Running tests...
"%VENV_PYTHON%" -m unittest discover -s tests -v
if errorlevel 1 goto :failed

echo.
echo Building Smap2LIF.exe...
"%VENV_PYTHON%" -m PyInstaller --noconfirm --clean Smap2LIF.spec
if errorlevel 1 goto :failed

if not exist "%CD%\dist\Smap2LIF.exe" (
    echo ERROR: dist\Smap2LIF.exe was not created.
    goto :failed
)

echo.
echo Running executable startup smoke test...
"%CD%\dist\Smap2LIF.exe" --version
if errorlevel 1 goto :failed

echo Running packaged Tk runtime smoke test...
"%CD%\dist\Smap2LIF.exe" --tk-smoke-test
if errorlevel 1 (
    echo ERROR: The packaged executable cannot start its GUI runtime.
    goto :failed
)

echo.
echo ========================================
echo   Build completed successfully
echo ========================================
echo Output: %CD%\dist\Smap2LIF.exe
echo.
pause
exit /b 0

:failed
echo.
echo ========================================
echo   Build failed
echo ========================================
echo Review the error shown above.
echo.
pause
exit /b 1
