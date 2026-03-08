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
            response = requests.get(self.api_url, timeout=10)
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
            
            response = requests.get(download_url, stream=True, timeout=30)
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
            backup_dir = app_dir / "backup_old_version"
            temp_extract_dir = app_dir / "temp_update"
            
            # Create backup of current version
            logger.info("Creating backup of current version...")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            backup_dir.mkdir()
            
            # Backup important files
            exe_name = "AgentJ-TradingBot.exe"
            if (app_dir / exe_name).exists():
                shutil.copy2(app_dir / exe_name, backup_dir / exe_name)
            
            if (app_dir / ".env").exists():
                shutil.copy2(app_dir / ".env", backup_dir / ".env")
            
            if (app_dir / "logs").exists():
                shutil.copytree(app_dir / "logs", backup_dir / "logs")
            
            # Extract update
            logger.info("Extracting update files...")
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
            temp_extract_dir.mkdir()
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
            
            # Find the actual content directory
            extracted_items = list(temp_extract_dir.iterdir())
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                source_dir = extracted_items[0]
            else:
                source_dir = temp_extract_dir
            
            # Copy new executable (excluding .env and logs)
            logger.info("Installing new executable...")
            new_exe = source_dir / exe_name
            if new_exe.exists():
                # Rename old exe
                old_exe = app_dir / exe_name
                old_exe_backup = app_dir / f"{exe_name}.old"
                if old_exe.exists():
                    shutil.move(str(old_exe), str(old_exe_backup))
                
                # Copy new exe
                shutil.copy2(new_exe, app_dir / exe_name)
                
                # Remove old backup
                if old_exe_backup.exists():
                    old_exe_backup.unlink()
            
            # Copy .env.template if exists (don't overwrite .env)
            if (source_dir / ".env.template").exists() and not (app_dir / ".env").exists():
                shutil.copy2(source_dir / ".env.template", app_dir / ".env.template")
            
            # Cleanup
            shutil.rmtree(temp_extract_dir)
            zip_path.unlink()
            
            logger.info("Update installed successfully!")
            logger.info("Please restart the application to use the new version")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to install exe update: {e}")
            logger.info("Attempting to restore from backup...")
            
            # Restore from backup
            try:
                if backup_dir.exists():
                    exe_name = "AgentJ-TradingBot.exe"
                    if (backup_dir / exe_name).exists():
                        shutil.copy2(backup_dir / exe_name, app_dir / exe_name)
                    logger.info("Restored from backup successfully")
            except Exception as restore_error:
                logger.error(f"Failed to restore from backup: {restore_error}")
            
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
        
        # Download update
        app_dir = Path(__file__).parent.parent
        download_path = app_dir / f"update_{latest_version}.zip"
        
        if not self.download_update(download_url, download_path):
            return False, "Failed to download update"
        
        # Install update
        if not self.install_update(download_path):
            return False, "Failed to install update"
        
        return True, f"Successfully updated to version {latest_version}. Please restart the application."


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
