#!/usr/bin/env python3
"""AgentJ Trading Bot - EXE Release Package Creator"""
import sys
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

def create_exe_release_package(version: str):
    """Create a clean EXE release package"""
    print(f"\nCreating release package v{version}...")
    
    release_name = f"AgentJ-TradingBot-v{version}"
    release_dir = Path("release_temp")
    dist_dir = Path("dist")
    output_file = dist_dir / f"{release_name}.zip"
    
    # Check if dist folder and exe exist
    if not dist_dir.exists():
        print("ERROR: dist folder not found! Run: python deploy/build.py")
        sys.exit(1)
    
    exe_file = dist_dir / "AgentJ-TradingBot.exe"
    if not exe_file.exists():
        print("ERROR: AgentJ-TradingBot.exe not found! Run: python deploy/build.py")
        sys.exit(1)
    
    # Clean up and create release directory
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir()
    
    # Copy executable and create logs directory
    shutil.copy2(exe_file, release_dir / "AgentJ-TradingBot.exe")
    (release_dir / "logs").mkdir()
    
    # Create .env template
    env_template = """# AgentJ Trading Bot Configuration
# Fill in your actual values below

# Discord Settings
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
DISCORD_NOTIFICATION_CHANNEL_ID=your_notification_channel_id_here

# MT5 Settings
MT5_LOGIN=your_mt5_login
MT5_PASSWORD=your_mt5_password
MT5_SERVER=your_mt5_server
MT5_PATH=C:/Program Files/MetaTrader 5/terminal64.exe

# Risk Management
RISK_PERCENT=1.0
MAX_DAILY_TRADES=5

# Spread Limits (in points)
MAX_SPREAD_FOREX=20
MAX_SPREAD_GOLD=500
MAX_SPREAD_INDICES=300
MAX_SPREAD_CRYPTO=5000

# Break-Even Settings
USE_BREAK_EVEN=true
BREAK_EVEN_AT_PIPS=10.0
BREAK_EVEN_OFFSET_PIPS=2.0

# Trailing Stop Settings
USE_TRAILING_STOP=true
TRAILING_START_PIPS=15.0
TRAILING_STEP_PIPS=5.0
"""
    (release_dir / ".env.template").write_text(env_template, encoding='utf-8')
    
    # Create README
    readme = f"""AgentJ Trading Bot v{version}
Released: {datetime.now().strftime('%Y-%m-%d')}

SETUP:
1. Extract ZIP to a folder
2. Copy .env.template to .env and configure:
   - Discord token and channel ID
   - MT5 login, password, server, path
3. Run AgentJ-TradingBot.exe

MODES:
- Client: Monitors Discord for signals (default)
- Master: Sends MT5 trades to Discord (run with --mode master)

FEATURES:
- Auto trade execution from Discord
- Risk management & spread checking
- Break-even & trailing stops
- Real-time position monitoring
- GUI dashboard

TROUBLESHOOTING:
- Check .env file exists and is configured
- Verify MT5 is running and logged in
- Check logs/trading_bot.log for errors
"""
    (release_dir / "README.txt").write_text(readme, encoding='utf-8')
    
    # Delete old zip if exists and create new one
    if output_file.exists():
        output_file.unlink()
    
    print("Creating ZIP archive...")
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in release_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(release_dir)
                zipf.write(file_path, arcname)
    
    # Clean up and show results
    shutil.rmtree(release_dir)
    
    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"\n✓ Release created: {output_file} ({file_size_mb:.2f} MB)")
    print(f"  Next: Create GitHub release v{version} and upload ZIP\n")

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("\nUsage: python create_release_exe.py VERSION")
        print("Example: python create_release_exe.py 1.1.0\n")
        sys.exit(1)
    
    version = sys.argv[1].lstrip('v')
    
    # Validate version format
    parts = version.split('.')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        print(f"\nERROR: Invalid version '{version}'. Use format: MAJOR.MINOR.PATCH\n")
        sys.exit(1)
    
    try:
        create_exe_release_package(version)
    except Exception as e:
        print(f"\nERROR: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
