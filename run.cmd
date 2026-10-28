@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "scripts\bootstrap.py" %*
    exit /b %errorlevel%
)
where python >nul 2>nul
if not errorlevel 1 (
    python "scripts\bootstrap.py" %*
    exit /b %errorlevel%
)
echo Brak Pythona 3.10+. Zainstaluj Python z https://www.python.org/downloads/windows/
exit /b 2
