@echo off
setlocal enabledelayedexpansion
REM ========================================
REM AgentJ Trading Bot - Auto Update Installer
REM This script automatically downloads and installs
REM the latest version from GitHub releases
REM ========================================
echo ========================================
echo AgentJ Trading Bot - Update Installer
echo ========================================
echo.

echo [1/9] Checking for latest version...
set "GITHUB_REPO=mark-aguirre/agent-j"

echo Fetching release information from GitHub...
powershell -ExecutionPolicy Bypass -File "%~dp0get_latest_release.ps1" -RepoOwner "mark-aguirre" -RepoName "agent-j" > temp_release_info.txt 2>&1

if errorlevel 1 (
    echo ERROR: Failed to fetch release information from GitHub!
    echo.
    type temp_release_info.txt
    echo.
    echo Please check:
    echo - Your internet connection
    echo - GitHub repository exists and has releases
    echo - Release contains a .zip file
    if exist temp_release_info.txt del temp_release_info.txt
    pause
    exit /b 1
)

set /p DOWNLOAD_URL=<temp_release_info.txt
for /f "skip=1 delims=" %%i in (temp_release_info.txt) do set VERSION=%%i
del temp_release_info.txt

if "%DOWNLOAD_URL%"=="" (
    echo ERROR: Could not find update package in latest release!
    pause
    exit /b 1
)

echo Found version: %VERSION%
echo Download URL: %DOWNLOAD_URL%

echo [2/9] Downloading latest version...
set "UPDATE_FILE=update_latest.zip"
echo Downloading update package...
echo URL: %DOWNLOAD_URL%
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0download_file.ps1" -Url "%DOWNLOAD_URL%" -OutputFile "%UPDATE_FILE%"

if errorlevel 1 (
    echo ERROR: Failed to download update package!
    pause
    exit /b 1
)

if not exist "%UPDATE_FILE%" (
    echo ERROR: Update file not found after download!
    pause
    exit /b 1
)

echo Download completed successfully.

echo [3/9] Waiting for application to close...
timeout /t 2 /nobreak >nul

echo [4/9] Ensuring application is fully closed...
taskkill /F /IM "AgentJ-TradingBot.exe" 2>nul
if errorlevel 1 (
    echo Application already closed.
) else (
    echo Application terminated.
    timeout /t 1 /nobreak >nul
)

echo [5/9] Creating backup of current version...
if exist "AgentJ-TradingBot-backup.exe" (
    echo Removing old backup: AgentJ-TradingBot-backup.exe
    del "AgentJ-TradingBot-backup.exe"
)
if exist "AgentJ-TradingBot.exe" (
    echo Backing up: AgentJ-TradingBot.exe -> AgentJ-TradingBot-backup.exe
    copy "AgentJ-TradingBot.exe" "AgentJ-TradingBot-backup.exe" >nul
)

echo [6/9] Backing up _internal folder...
if exist "_internal_backup" (
    rmdir /s /q "_internal_backup"
)
if exist "_internal" (
    echo Moving _internal to _internal_backup...
    move "_internal" "_internal_backup" >nul
    if errorlevel 1 (
        echo ERROR: Failed to move _internal folder!
        echo It may be in use. Trying to delete instead...
        rmdir /s /q "_internal"
    )
)

echo [7/9] Extracting update package...
if not exist "%UPDATE_FILE%" (
    echo ERROR: Update package not found!
    goto restore_backup
)

echo Extracting files...
powershell -ExecutionPolicy Bypass -File "%~dp0extract_archive.ps1" -ZipFile "%UPDATE_FILE%" -Destination "temp_update"
if errorlevel 1 (
    echo ERROR: Failed to extract update package!
    goto restore_backup
)

echo Preparing staging folder...
if exist "update_staging" rmdir /s /q "update_staging"
move "temp_update\*" "update_staging" >nul 2>&1
if not exist "update_staging" (
    REM If move failed, try renaming the folder
    move "temp_update" "update_staging" >nul
)
if exist "temp_update" rmdir /s /q "temp_update"

echo [8/9] Installing new version...
echo Copying exe file...
copy /Y "update_staging\AgentJ-TradingBot.exe" "AgentJ-TradingBot.exe" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy exe file!
    goto restore_backup
)

echo Copying _internal folder...
if exist "_internal" (
    echo WARNING: _internal still exists, removing it...
    rmdir /s /q "_internal"
)
xcopy /E /I /Y /Q "update_staging\_internal" "_internal" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy _internal folder!
    goto restore_backup
)

echo Copying other files...
for %%F in (update_staging\*.txt update_staging\*.template) do (
    if exist "%%F" copy /Y "%%F" . >nul
)

echo Verifying installation...
if not exist "AgentJ-TradingBot.exe" (
    echo ERROR: Exe file missing after update!
    goto restore_backup
)
if not exist "_internal" (
    echo ERROR: _internal folder missing after update!
    goto restore_backup
)

echo [9/9] Cleaning up temporary files...
if exist "update_staging" (
    rmdir /s /q "update_staging"
)
if exist "temp_update" (
    rmdir /s /q "temp_update"
)
if exist "%UPDATE_FILE%" (
    del "%UPDATE_FILE%"
)
if exist "_internal_backup" (
    rmdir /s /q "_internal_backup"
)
if exist "AgentJ-TradingBot-backup.exe" (
    del "AgentJ-TradingBot-backup.exe"
)

echo.
echo ========================================
echo Update completed successfully!
echo Version: %VERSION%
echo ========================================
echo.
echo Starting updated application...
start "" "AgentJ-TradingBot.exe"

timeout /t 2 /nobreak >nul

REM Self-delete this script
del "%~f0"
exit /b 0

:restore_backup
echo.
echo ========================================
echo ERROR: Update failed!
echo ========================================
echo Restoring from backup...
if exist "_internal_backup" (
    echo Restoring _internal backup...
    if exist "_internal" rmdir /s /q "_internal"
    move "_internal_backup" "_internal"
)
if exist "AgentJ-TradingBot-backup.exe" (
    echo Restoring exe backup...
    if exist "AgentJ-TradingBot.exe" del "AgentJ-TradingBot.exe"
    move "AgentJ-TradingBot-backup.exe" "AgentJ-TradingBot.exe"
)
echo.
echo Restore completed. Your previous version has been restored.
echo.
pause
exit /b 1
