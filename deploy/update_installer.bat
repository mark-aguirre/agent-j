@echo off
setlocal enabledelayedexpansion
REM ========================================
REM AgentJ Trading Bot - Auto Update Installer
REM This script automatically downloads and installs
REM the latest version from GitHub releases
REM ========================================
echo.
echo ========================================
echo AgentJ Trading Bot - Update Installer
echo ========================================
echo.

echo [1/9] Checking for latest version...
set "GITHUB_REPO=mark-aguirre/agent-j"

powershell -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { $apiUrl='https://api.github.com/repos/mark-aguirre/agent-j/releases/latest'; $release=Invoke-RestMethod -Uri $apiUrl; $asset=$release.assets | Where-Object { $_.name -like '*.zip' } | Select-Object -First 1; if ($asset) { Write-Output $asset.browser_download_url; Write-Output $release.tag_name; exit 0 } else { Write-Output 'NO_ASSET'; Write-Output 'No .zip file found in latest release'; exit 1 } } catch { Write-Output 'API_ERROR'; Write-Output $_.Exception.Message; exit 1 }" > temp_release_info.txt 2>&1

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
echo.

echo [2/9] Downloading latest version...
set "UPDATE_FILE=update_latest.zip"
powershell -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%UPDATE_FILE%'; exit 0 } catch { Write-Host 'Download failed:' $_.Exception.Message; exit 1 }" >nul 2>&1

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
echo.

echo [3/9] Waiting for application to close...
timeout /t 2 /nobreak >nul
echo.

echo [4/9] Ensuring application is fully closed...
taskkill /F /IM "AgentJ-TradingBot.exe" 2>nul
if errorlevel 1 (
    echo Application already closed.
) else (
    echo Application terminated.
    timeout /t 1 /nobreak >nul
)
echo.

echo [5/9] Creating backup of current version...
if exist "AgentJ-TradingBot-backup.exe" (
    echo Removing old backup: AgentJ-TradingBot-backup.exe
    del "AgentJ-TradingBot-backup.exe"
)
if exist "AgentJ-TradingBot.exe" (
    echo Backing up: AgentJ-TradingBot.exe -> AgentJ-TradingBot-backup.exe
    copy "AgentJ-TradingBot.exe" "AgentJ-TradingBot-backup.exe" >nul
)
echo.

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
echo.

echo [7/9] Extracting update package...
if not exist "%UPDATE_FILE%" (
    echo ERROR: Update package not found!
    goto restore_backup
)

powershell -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Expand-Archive -Path '%UPDATE_FILE%' -DestinationPath 'temp_update' -Force; exit 0 } catch { Write-Host 'Extraction failed:' $_.Exception.Message; exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to extract update package!
    goto restore_backup
)
echo.

echo Preparing staging folder...
if exist "update_staging" rmdir /s /q "update_staging"
move "temp_update\*" "update_staging" >nul 2>&1
if not exist "update_staging" (
    REM If move failed, try renaming the folder
    move "temp_update" "update_staging" >nul
)
if exist "temp_update" rmdir /s /q "temp_update"
echo.

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
echo.

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
