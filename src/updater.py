"""
Auto-updater module for AgentJ Trading Bot
Checks for updates from GitHub releases and downloads/installs them
"""
import requests
import logging
import os
import sys
import subprocess
import zipfile
import shutil
from pathlib import Path
from typing import Optional, Tuple
from packaging import version

from src.__version__ import __version__

logger = logging.getLogger(__name__)

class Updater:
    """Handles checking and installing updates"""
    
    def __init__(self, github_repo: str = "mark-aguirre/agent-j"):
        """
        Initialize updater
        
        Args:
            github_repo: GitHub repository in format "owner/repo"
        """
        self.github_repo = github_repo
        self.api_url = f"https://api.github.com/repos/{github_repo}/releases/latest"
        self.current_version = __version__
    
    def check_for_updates(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if a new version is available
        
        Returns:
            Tuple of (has_update, latest_version, download_url)
        """
        try:
            logger.info(f"Checking for updates... Current version: {self.current_version}")
            
            # Get latest release info from GitHub
            # Set headers to avoid rate limiting and ensure proper SSL/TLS
            headers = {
                'User-Agent': 'AgentJ-TradingBot',
                'Accept': 'application/vnd.github.v3+json'
            }
            response = requests.get(self.api_url, headers=headers, timeout=10, verify=True)
            response.raise_for_status()
            
            release_data = response.json()
            latest_version = release_data.get("tag_name", "").lstrip("v")
            
            if not latest_version:
                logger.warning("Could not determine latest version")
                return False, None, None
            
            logger.info(f"Latest version available: {latest_version}")
            
            # Compare versions
            if version.parse(latest_version) > version.parse(self.current_version):
                # Find the download URL for the zip file
                download_url = None
                for asset in release_data.get("assets", []):
                    if asset["name"].endswith(".zip"):
                        download_url = asset["browser_download_url"]
                        break
                
                if not download_url:
                    # Fallback to source code zip
                    download_url = release_data.get("zipball_url")
                
                return True, latest_version, download_url
            else:
                logger.info("You are running the latest version")
                return False, latest_version, None
                
        except requests.RequestException as e:
            logger.error(f"Failed to check for updates: {e}")
            return False, None, None
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return False, None, None
    
    def download_update(self, download_url: str, save_path: Path) -> bool:
        """
        Download the update file
        
        Args:
            download_url: URL to download from
            save_path: Path to save the downloaded file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Downloading update from {download_url}")
            
            # Set headers for proper download
            headers = {
                'User-Agent': 'AgentJ-TradingBot',
                'Accept': 'application/octet-stream'
            }
            response = requests.get(download_url, headers=headers, stream=True, timeout=30, verify=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            logger.info(f"Download progress: {progress:.1f}%")
            
            logger.info("Download completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download update: {e}")
            return False
    
    def install_update(self, zip_path: Path) -> bool:
        """
        Install the downloaded update
        
        Args:
            zip_path: Path to the downloaded zip file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Installing update...")
            
            app_dir = Path(__file__).parent.parent
            
            # Check if running as executable or source
            import sys
            is_executable = getattr(sys, 'frozen', False)
            
            if is_executable:
                # Running as .exe - update executable
                return self._install_exe_update(zip_path, app_dir)
            else:
                # Running as source - update source files
                return self._install_source_update(zip_path, app_dir)
                
        except Exception as e:
            logger.error(f"Failed to install update: {e}")
            return False
    
    def _install_exe_update(self, zip_path: Path, app_dir: Path) -> bool:
        """Install update for executable version"""
        try:
            # Get the current executable path and version
            current_exe = Path(sys.executable)
            exe_name = current_exe.name
            current_version = self.current_version
            
            logger.info(f"Installing update from {zip_path}")
            logger.info(f"Current version: {current_version}")
            logger.info(f"App directory: {app_dir}")
            
            # Extract the new version to a temporary location
            logger.info("Extracting update files...")
            temp_extract_dir = app_dir / "temp_update"
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
            temp_extract_dir.mkdir()
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
            
            # Find the actual content directory (GitHub releases may have a root folder)
            extracted_items = list(temp_extract_dir.iterdir())
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                source_dir = extracted_items[0]
            else:
                source_dir = temp_extract_dir
            
            logger.info(f"Source directory: {source_dir}")
            logger.info(f"Contents: {[item.name for item in source_dir.iterdir()]}")
            
            # Find the new exe in the extracted files (only at root level, not in subdirs)
            new_exe = None
            for item in source_dir.iterdir():
                if item.is_file() and item.suffix == ".exe" and ("AgentJ" in item.name or item.name == exe_name):
                    new_exe = item
                    logger.info(f"Found new exe: {item}")
                    break
            
            if not new_exe or not new_exe.exists():
                logger.error(f"Could not find new executable in update package")
                logger.error(f"Searched in: {source_dir}")
                logger.error(f"Looking for: {exe_name} or files containing 'AgentJ'")
                return False
            
            # Determine if this is a onedir or onefile build
            # Onedir builds have _internal folder alongside the exe
            is_onedir = (new_exe.parent / "_internal").exists()
            logger.info(f"Build type: {'onedir' if is_onedir else 'onefile'}")
            
            # Backup filename with current version
            backup_name = f"AgentJ-TradingBot-v{current_version}.exe"
            
            if is_onedir:
                # For onedir builds, we need to update all files
                # Copy entire update directory to a staging area
                staging_dir = app_dir / "update_staging"
                if staging_dir.exists():
                    shutil.rmtree(staging_dir)
                
                logger.info(f"Copying onedir build from {new_exe.parent} to {staging_dir}")
                shutil.copytree(new_exe.parent, staging_dir)
                
                # Create batch script to replace all files
                updater_script = app_dir / "update_installer.bat"
                
                script_content = f"""@echo off
echo ========================================
echo AgentJ Trading Bot - Update Installer
echo ========================================
echo.

echo [1/7] Waiting for application to close...
timeout /t 2 /nobreak >nul

echo [2/7] Ensuring application is fully closed...
taskkill /F /IM "{exe_name}" 2>nul
if errorlevel 1 (
    echo Application already closed.
) else (
    echo Application terminated.
    timeout /t 1 /nobreak >nul
)

echo [3/7] Creating backup of current version...
if exist "{backup_name}" (
    echo Removing old backup: {backup_name}
    del "{backup_name}"
)
if exist "{exe_name}" (
    echo Backing up: {exe_name} -^> {backup_name}
    copy "{exe_name}" "{backup_name}" >nul
)

echo [4/7] Backing up _internal folder...
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

echo [5/7] Installing new version...
echo Copying exe file...
copy /Y "update_staging\\{exe_name}" "{exe_name}" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy exe file!
    goto restore_backup
)

echo Copying _internal folder...
if exist "_internal" (
    echo WARNING: _internal still exists, removing it...
    rmdir /s /q "_internal"
)
xcopy /E /I /Y /Q "update_staging\\_internal" "_internal" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy _internal folder!
    goto restore_backup
)

echo Copying other files...
for %%F in (update_staging\\*.txt update_staging\\*.template) do (
    if exist "%%F" copy /Y "%%F" . >nul
)

echo Verifying installation...
if not exist "{exe_name}" (
    echo ERROR: Exe file missing after update!
    goto restore_backup
)
if not exist "_internal" (
    echo ERROR: _internal folder missing after update!
    goto restore_backup
)

echo [6/7] Cleaning up temporary files...
if exist "update_staging" (
    rmdir /s /q "update_staging"
)
if exist "temp_update" (
    rmdir /s /q "temp_update"
)
if exist "{zip_path.name}" (
    del "{zip_path.name}"
)
if exist "_internal_backup" (
    rmdir /s /q "_internal_backup"
)

echo [7/7] Starting updated application...
start "" "{exe_name}"

echo.
echo Update completed successfully!
echo The application is now starting...
timeout /t 2 /nobreak >nul

REM Self-delete this script
del "%~f0"
exit /b 0

:restore_backup
echo.
echo Restoring from backup...
if exist "_internal_backup" (
    echo Restoring _internal backup...
    if exist "_internal" rmdir /s /q "_internal"
    move "_internal_backup" "_internal"
)
if exist "{backup_name}" (
    echo Restoring exe backup...
    if exist "{exe_name}" del "{exe_name}"
    move "{backup_name}" "{exe_name}"
)
echo.
echo Restore completed. Update failed.
pause
exit /b 1
"""
            else:
                # For onefile builds, just replace the exe
                new_exe_temp = app_dir / f"{exe_name}.new"
                logger.info(f"Copying new exe to: {new_exe_temp}")
                shutil.copy2(new_exe, new_exe_temp)
                
                updater_script = app_dir / "update_installer.bat"
                
                script_content = f"""@echo off
echo ========================================
echo AgentJ Trading Bot - Update Installer
echo ========================================
echo.

echo [1/5] Waiting for application to close...
timeout /t 3 /nobreak >nul

echo [2/5] Creating backup of current version...
if exist "{backup_name}" (
    echo Removing old backup: {backup_name}
    del "{backup_name}"
)
if exist "{exe_name}" (
    echo Backing up: {exe_name} -^> {backup_name}
    move "{exe_name}" "{backup_name}"
)

echo [3/5] Installing new version...
if exist "{exe_name}.new" (
    move "{exe_name}.new" "{exe_name}"
    echo New version installed successfully!
) else (
    echo ERROR: New exe file not found!
    if exist "{backup_name}" (
        echo Restoring backup...
        move "{backup_name}" "{exe_name}"
    )
    pause
    exit /b 1
)

echo [4/5] Cleaning up temporary files...
if exist "temp_update" (
    rmdir /s /q "temp_update" 2>nul
)
if exist "{zip_path.name}" (
    del "{zip_path.name}" 2>nul
)

echo [5/5] Starting updated application...
start "" "{exe_name}"

echo.
echo Update completed successfully!
echo The application is now starting...
timeout /t 2 /nobreak >nul

REM Self-delete this script
del "%~f0"
"""
            
            logger.info(f"Creating updater script: {updater_script}")
            with open(updater_script, 'w') as f:
                f.write(script_content)
            
            logger.info("Update prepared successfully!")
            logger.info("Starting updater script...")
            
            # Start the updater script in a new window (visible for debugging)
            subprocess.Popen(
                ['cmd', '/c', str(updater_script)],
                cwd=str(app_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            # Signal that we need to exit for update
            return True
            
        except Exception as e:
            logger.error(f"Failed to prepare exe update: {e}", exc_info=True)
            # Clean up on failure
            try:
                if temp_extract_dir.exists():
                    shutil.rmtree(temp_extract_dir)
            except:
                pass
            return False
    
    def _install_source_update(self, zip_path: Path, app_dir: Path) -> bool:
        """Install update for source code version"""
        try:
            backup_dir = app_dir / "backup_old_version"
            temp_extract_dir = app_dir / "temp_update"
            
            logger.info("Installing update...")
            
            # Create backup of current version
            logger.info("Creating backup of current version...")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            backup_dir.mkdir()
            
            # Backup important files
            files_to_backup = ['.env', 'logs', 'src', 'main.py', 'gui_app.py', 'requirements.txt']
            for item in files_to_backup:
                src_path = app_dir / item
                if src_path.exists():
                    if src_path.is_dir():
                        shutil.copytree(src_path, backup_dir / item)
                    else:
                        shutil.copy2(src_path, backup_dir / item)
            
            # Extract update
            logger.info("Extracting update files...")
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
            temp_extract_dir.mkdir()
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
            
            # Find the actual content directory (GitHub zips have a root folder)
            extracted_items = list(temp_extract_dir.iterdir())
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                source_dir = extracted_items[0]
            else:
                source_dir = temp_extract_dir
            
            # Copy new files (excluding .env to preserve user settings)
            logger.info("Installing new files...")
            for item in source_dir.iterdir():
                if item.name in ['.env', 'logs', '.git', '__pycache__']:
                    continue
                
                dest_path = app_dir / item.name
                
                if item.is_dir():
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(item, dest_path)
                else:
                    shutil.copy2(item, dest_path)
            
            # Install dependencies
            logger.info("Installing dependencies...")
            requirements_file = app_dir / "requirements.txt"
            if requirements_file.exists():
                import sys
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
                    check=True
                )
            
            # Cleanup
            shutil.rmtree(temp_extract_dir)
            zip_path.unlink()
            
            logger.info("Update installed successfully!")
            logger.info("Please restart the application to use the new version")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to install source update: {e}")
            logger.info("Attempting to restore from backup...")
            
            # Restore from backup if installation failed
            try:
                if backup_dir.exists():
                    for item in backup_dir.iterdir():
                        dest_path = app_dir / item.name
                        if dest_path.exists():
                            if dest_path.is_dir():
                                shutil.rmtree(dest_path)
                            else:
                                dest_path.unlink()
                        
                        if item.is_dir():
                            shutil.copytree(item, dest_path)
                        else:
                            shutil.copy2(item, dest_path)
                    
                    logger.info("Restored from backup successfully")
            except Exception as restore_error:
                logger.error(f"Failed to restore from backup: {restore_error}")
            
            return False
    
    def perform_update(self) -> Tuple[bool, str]:
        """
        Check for updates and install if available
        
        Returns:
            Tuple of (success, message)
        """
        # Check for updates
        has_update, latest_version, download_url = self.check_for_updates()
        
        if not has_update:
            if latest_version:
                return True, f"You are already running the latest version ({latest_version})"
            else:
                return False, "Could not check for updates. Please try again later."
        
        if not download_url:
            return False, "Update available but download URL not found"
        
        # Determine app directory
        if getattr(sys, 'frozen', False):
            # When frozen, sys.executable points to the exe
            exe_dir = Path(sys.executable).parent
            
            # Check if we're running from _internal (shouldn't happen, but just in case)
            if exe_dir.name == "_internal":
                app_dir = exe_dir.parent
                logger.info(f"Running from _internal folder, using parent: {app_dir}")
            else:
                app_dir = exe_dir
                
            logger.info(f"App directory: {app_dir}")
            logger.info(f"sys.executable: {sys.executable}")
        else:
            app_dir = Path(__file__).parent.parent
            logger.info(f"Running from source, app directory: {app_dir}")
        
        # For frozen executables, the installer is in _internal folder
        # We need to use it from there directly
        if getattr(sys, 'frozen', False):
            installer_path = app_dir / "_internal" / "update_installer.bat"
            logger.info(f"Looking for installer in _internal: {installer_path}")
        else:
            installer_path = app_dir / "deploy" / "update_installer.bat"
            logger.info(f"Looking for installer in deploy: {installer_path}")
        
        logger.info(f"Installer exists: {installer_path.exists()}")
        
        if not installer_path.exists():
            logger.error(f"Update installer not found at: {installer_path}")
            return False, "Update installer not found. Please reinstall the application."
        
        # Launch the update installer script
        try:
            import subprocess
            logger.info(f"Launching update installer: {installer_path}")
            
            # Start the installer in a new process (detached)
            # Use CREATE_NEW_CONSOLE to run in separate window
            # Use shell=True to execute the batch file
            subprocess.Popen(
                str(installer_path),
                cwd=str(app_dir),
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
            
            logger.info("Update installer launched successfully")
            return True, f"Update to version {latest_version} is starting"
            
        except Exception as e:
            logger.error(f"Failed to launch update installer: {e}")
            return False, f"Failed to start update installer: {str(e)}"


def check_for_updates_simple(github_repo: str = "yourusername/agentj-tradingbot") -> Tuple[bool, Optional[str]]:
    """
    Simple function to check if updates are available
    
    Args:
        github_repo: GitHub repository in format "owner/repo"
        
    Returns:
        Tuple of (has_update, latest_version)
    """
    updater = Updater(github_repo)
    has_update, latest_version, _ = updater.check_for_updates()
    return has_update, latest_version
