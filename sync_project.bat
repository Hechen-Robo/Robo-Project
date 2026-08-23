@echo off
setlocal

for %%I in ("%~dp0.") do set "START_DIR=%%~fI"
set "GIT_EXE="
set "REPO="

echo.
echo ========================================
echo   Robo-Project Remote Branch Check
echo ========================================
echo.

where.exe git.exe >nul 2>&1
if not errorlevel 1 set "GIT_EXE=git.exe"

if not defined GIT_EXE if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT_EXE=%ProgramFiles%\Git\cmd\git.exe"
if not defined GIT_EXE if exist "%ProgramFiles%\Git\bin\git.exe" set "GIT_EXE=%ProgramFiles%\Git\bin\git.exe"
if not defined GIT_EXE if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set "GIT_EXE=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
if not defined GIT_EXE if exist "%USERPROFILE%\scoop\apps\git\current\cmd\git.exe" set "GIT_EXE=%USERPROFILE%\scoop\apps\git\current\cmd\git.exe"

if not defined GIT_EXE goto :git_missing

set "REPO_FILE=%TEMP%\sync_project_repo_%RANDOM%_%RANDOM%.txt"
"%GIT_EXE%" -C "%START_DIR%" rev-parse --show-toplevel >"%REPO_FILE%" 2>nul
if errorlevel 1 (
    del "%REPO_FILE%" >nul 2>&1
    goto :repo_missing
)

set /p "REPO="<"%REPO_FILE%"
del "%REPO_FILE%" >nul 2>&1

if not defined REPO goto :repo_missing

echo Repository: %REPO%
echo Git:        %GIT_EXE%
echo.

echo [1/3] Fetching all remotes and pruning deleted branches...
"%GIT_EXE%" -C "%REPO%" fetch --all --prune
if errorlevel 1 goto :failed

echo.
echo [2/3] Local branch tracking status:
"%GIT_EXE%" -C "%REPO%" branch -vv

echo.
echo Remote branches:
"%GIT_EXE%" -C "%REPO%" branch -r

echo.
echo Remote checking is complete.
echo No local branch has been switched or pulled yet.
echo.
set "BRANCH="
set /p "BRANCH=Enter a branch to switch and pull, or press Enter to exit: "

if not defined BRANCH goto :checked_only

if /I "%BRANCH:~0,7%"=="origin/" set "BRANCH=%BRANCH:~7%"

echo.
echo Selected branch: %BRANCH%

set "DIRTY="
"%GIT_EXE%" -C "%REPO%" diff --quiet
if errorlevel 1 set "DIRTY=1"
"%GIT_EXE%" -C "%REPO%" diff --cached --quiet
if errorlevel 1 set "DIRTY=1"

if defined DIRTY (
    echo ERROR: The working tree contains uncommitted tracked changes.
    echo Commit or stash them before switching or pulling a branch.
    echo.
    "%GIT_EXE%" -C "%REPO%" status --short
    goto :failed
)

echo.
echo [3/3] Switching and pulling %BRANCH%...

"%GIT_EXE%" -C "%REPO%" show-ref --verify --quiet "refs/heads/%BRANCH%"
if errorlevel 1 (
    "%GIT_EXE%" -C "%REPO%" show-ref --verify --quiet "refs/remotes/origin/%BRANCH%"
    if errorlevel 1 (
        echo ERROR: Remote branch origin/%BRANCH% was not found.
        goto :failed
    )

    "%GIT_EXE%" -C "%REPO%" switch --track "origin/%BRANCH%"
) else (
    "%GIT_EXE%" -C "%REPO%" switch "%BRANCH%"
)
if errorlevel 1 goto :failed

"%GIT_EXE%" -C "%REPO%" pull --ff-only origin "%BRANCH%"
if errorlevel 1 goto :failed

echo.
echo Branch synchronization completed successfully.
"%GIT_EXE%" -C "%REPO%" status -sb
"%GIT_EXE%" -C "%REPO%" log -1 --oneline --decorate
goto :success

:checked_only
echo.
echo Remote branch check completed.
echo No local branch was changed.

:success
echo.
pause
exit /b 0

:git_missing
echo ERROR: Git for Windows could not be found.
echo Install Git or add its cmd directory to the Windows PATH.
echo Common location: C:\Program Files\Git\cmd\git.exe
goto :failed

:repo_missing
echo ERROR: The BAT file is not located inside a Git repository.
echo BAT location: %START_DIR%
echo Move it anywhere inside the Robo-Project folder and run it again.
goto :failed

:failed
echo.
echo Operation failed. Review the error shown above.
echo No local changes were deleted automatically.
echo.
pause
exit /b 1
