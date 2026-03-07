# Auto-Update Feature Setup Guide

This guide explains how to set up and use the auto-update feature for AgentJ Trading Bot.

## Overview

The auto-update feature allows users to:
- Check for new versions from GitHub releases
- Download and install updates automatically
- Backup current version before updating
- Rollback if update fails

## Setup Steps

### 1. Create GitHub Repository

1. Create a new repository on GitHub (e.g., `yourusername/agentj-tradingbot`)
2. Push your code to the repository
3. Make sure the repository is public (or provide authentication for private repos)

### 2. Update the GitHub Repository URL

Edit `src/updater.py` and change the default repository:

```python
def __init__(self, github_repo: str = "yourusername/agentj-tradingbot"):
```

Replace `yourusername/agentj-tradingbot` with your actual GitHub repository.

Also update in `src/gui/settings.py`:

```python
updater = Updater(github_repo="yourusername/agentj-tradingbot")
```

### 3. Create GitHub Releases

When you want to release a new version:

#### Step 1: Update Version Number

Edit `src/__version__.py`:

```python
__version__ = "1.1.0"  # Increment version
```

#### Step 2: Commit and Push Changes

```bash
git add .
git commit -m "Release v1.1.0"
git push origin main
```

#### Step 3: Create a GitHub Release

1. Go to your GitHub repository
2. Click on "Releases" → "Create a new release"
3. Tag version: `v1.1.0` (must start with 'v')
4. Release title: `v1.1.0` or `Version 1.1.0`
5. Description: Add release notes (what's new, bug fixes, etc.)
6. Attach files (optional):
   - You can attach a pre-built `.zip` file of your application
   - Or GitHub will automatically create source code archives

7. Click "Publish release"

### 4. Release Package Options

#### Option A: Let GitHub Auto-Generate (Simplest)

GitHub automatically creates source code archives (`.zip` and `.tar.gz`) for each release. The updater will use these by default.

#### Option B: Upload Custom Package (Recommended for End Users)

Create a clean distribution package:

```bash
# Create a clean copy without development files
mkdir release
cp -r src main.py gui_app.py requirements.txt run_gui.bat release/
cd release
zip -r AgentJ-TradingBot-v1.1.0.zip *
```

Upload this `.zip` file as a release asset. The updater will prefer custom `.zip` files over auto-generated ones.

## How Users Check for Updates

### Via GUI (Easiest)

1. Open the application
2. Go to "Settings" tab
3. Scroll to "Application Updates" section
4. Click "Check for Updates"
5. If an update is available, click "Yes" to install
6. Application will restart automatically after update

### Via Command Line

```bash
python -c "from src.updater import Updater; u = Updater('yourusername/agentj-tradingbot'); print(u.perform_update())"
```

## Version Numbering

Follow semantic versioning (MAJOR.MINOR.PATCH):

- `1.0.0` → `1.0.1` - Bug fixes (patch)
- `1.0.0` → `1.1.0` - New features (minor)
- `1.0.0` → `2.0.0` - Breaking changes (major)

## Update Process Flow

1. User clicks "Check for Updates"
2. App queries GitHub API for latest release
3. Compares version numbers
4. If newer version exists:
   - Downloads the release package
   - Creates backup of current version
   - Extracts new files
   - Installs dependencies
   - Prompts user to restart
5. If update fails:
   - Automatically restores from backup
   - Shows error message

## Files Preserved During Update

The updater automatically preserves:
- `.env` file (your configuration)
- `logs/` directory (trading logs)

## Backup Location

Backups are stored in `backup_old_version/` directory in your app folder.

## Testing the Update Feature

### Test Locally

1. Create a test release on GitHub (e.g., v1.0.1)
2. Temporarily change your local version to v1.0.0 in `src/__version__.py`
3. Run the app and click "Check for Updates"
4. Verify it detects and installs the update

### Test Release Process

```bash
# 1. Update version
echo '__version__ = "1.0.1"' > src/__version__.py

# 2. Commit
git add .
git commit -m "Release v1.0.1"
git push

# 3. Create release on GitHub
# (Use GitHub web interface)

# 4. Test update from v1.0.0 to v1.0.1
```

## Troubleshooting

### "Could not check for updates"

- Check internet connection
- Verify GitHub repository URL is correct
- Check if repository is public or accessible

### "Failed to download update"

- Check internet connection
- Verify release has downloadable assets
- Check disk space

### "Failed to install update"

- Check file permissions
- Verify app is not running as administrator (unless needed)
- Check antivirus isn't blocking file operations
- Review logs in `logs/trading_bot.log`

### Update Downloaded but Not Applied

- Make sure app has write permissions to its directory
- Close all instances of the app before updating
- Check if antivirus is blocking the update

## Security Considerations

1. **HTTPS Only**: Updater only uses HTTPS connections
2. **Backup Before Update**: Always creates backup before updating
3. **Rollback on Failure**: Automatically restores if update fails
4. **Preserve User Data**: Never overwrites `.env` or logs

## Advanced: Private Repository Updates

If your repository is private, you'll need to add authentication:

Edit `src/updater.py`:

```python
def check_for_updates(self) -> Tuple[bool, Optional[str], Optional[str]]:
    headers = {
        'Authorization': 'token YOUR_GITHUB_TOKEN',
        'Accept': 'application/vnd.github.v3+json'
    }
    response = requests.get(self.api_url, headers=headers, timeout=10)
    # ... rest of code
```

Create a GitHub Personal Access Token:
1. GitHub Settings → Developer settings → Personal access tokens
2. Generate new token with `repo` scope
3. Use token in the code above

## Example Release Notes Template

```markdown
## What's New in v1.1.0

### New Features
- Added trailing stop functionality
- Improved risk management
- New dashboard UI

### Bug Fixes
- Fixed MT5 connection timeout issue
- Resolved Discord notification delays

### Improvements
- Faster order execution
- Better error handling
- Updated dependencies

### Breaking Changes
- None

## Installation
Download and run the installer, or update via the app's Settings → Check for Updates
```

## Automated Release Workflow (Optional)

You can automate releases using GitHub Actions. Create `.github/workflows/release.yml`:

```yaml
name: Create Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Create Release Package
        run: |
          mkdir release
          cp -r src main.py gui_app.py requirements.txt run_gui.bat release/
          cd release
          zip -r ../AgentJ-TradingBot-${{ github.ref_name }}.zip *
      
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: AgentJ-TradingBot-${{ github.ref_name }}.zip
          draft: false
          prerelease: false
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Then just push a tag to trigger release:

```bash
git tag v1.1.0
git push origin v1.1.0
```

## Support

If users encounter issues with updates:
1. Check `logs/trading_bot.log` for error details
2. Verify GitHub repository is accessible
3. Try manual update by downloading from GitHub releases
4. Restore from `backup_old_version/` if needed
