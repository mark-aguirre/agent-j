"""
Build script to create standalone .exe for Agent J Trading Bot
Run: python build.py
"""
import subprocess
import sys
import os
from pathlib import Path

def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    try:
        import PyInstaller
        print("✓ PyInstaller already installed")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("✓ PyInstaller installed")

def build_exe():
    """Build the executable"""
    print("\nBuilding Agent J Trading Bot executable...")
    
    # Use the spec file for better control
    spec_path = Path(__file__).parent / "AgentJ-TradingBot.spec"
    cmd = [
        "pyinstaller",
        "--clean",
        "--noconfirm",
        str(spec_path)
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("\n✓ Build successful!")
        print(f"\nExecutable location: {Path('dist/AgentJ-TradingBot.exe').absolute()}")
        print("\nNote: Make sure to copy the .env file to the same directory as the .exe")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed: {e}")
        sys.exit(1)

def main():
    print("=" * 60)
    print("Agent J Trading Bot - Build Script")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("gui_app.py").exists():
        print("Error: gui_app.py not found. Please run this script from the agent-j-master directory.")
        sys.exit(1)
    
    # Install PyInstaller
    install_pyinstaller()
    
    # Build
    build_exe()

if __name__ == "__main__":
    main()
