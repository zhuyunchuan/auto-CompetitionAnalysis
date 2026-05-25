@echo off
REM ===================================================
REM  auto-CompetitionAnalysis - Windows Launcher
REM  Usage: run.bat <command> [options]
REM
REM  Examples:
REM    run.bat check
REM    run.bat help
REM    run.bat discover:hikvision
REM    run.bat specs:hikvision --concurrency=4
REM    run.bat all
REM ===================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ====================================================
echo   auto-CompetitionAnalysis
echo   Competitor Product Specs Crawler
echo ====================================================
echo.

node run.mjs %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [WARNING] Execution completed with errors
    pause
)
endlocal
