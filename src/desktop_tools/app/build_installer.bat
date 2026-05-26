@echo off
setlocal

set "REPO_ROOT=%~dp0..\..\.."
cd /d "%REPO_ROOT%"

echo Building Media Downloader Windows release
echo =======================================

echo Step 1: Installing required build dependencies...
python -m pip install nuitka
python -m pip install -r "src\desktop_tools\app\requirements.txt"

echo Step 2: Building EXE and installer with Nuitka + Inno Setup...
python "src\desktop_tools\app\nutika_build.py"
if errorlevel 1 goto :error

echo Done! EXE and installer created in 'release\windows'.
pause
exit /b 0

:error
echo Build failed.
pause
exit /b 1
