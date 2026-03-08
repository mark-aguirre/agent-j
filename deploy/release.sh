#!/bin/bash
# AgentJ Trading Bot - Automated Release Script
# Usage: ./deploy/release.sh [VERSION] [patch|minor|major]
# Examples:
#   ./deploy/release.sh 2.1.0          # Set specific version
#   ./deploy/release.sh patch          # Bump patch (2.0.0 -> 2.0.1)
#   ./deploy/release.sh minor          # Bump minor (2.0.0 -> 2.1.0)
#   ./deploy/release.sh major          # Bump major (2.0.0 -> 3.0.0)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

VERSION_FILE="src/__version__.py"

# Function to get current version
get_current_version() {
    grep -oP '__version__ = "\K[^"]+' "$VERSION_FILE"
}

# Function to bump version
bump_version() {
    local current=$1
    local bump_type=$2
    
    IFS='.' read -r major minor patch <<< "$current"
    
    case $bump_type in
        major)
            echo "$((major + 1)).0.0"
            ;;
        minor)
            echo "${major}.$((minor + 1)).0"
            ;;
        patch)
            echo "${major}.${minor}.$((patch + 1))"
            ;;
        *)
            echo "$bump_type"
            ;;
    esac
}

# Function to update version file
update_version_file() {
    local new_version=$1
    sed -i "s/__version__ = \".*\"/__version__ = \"${new_version}\"/" "$VERSION_FILE"
}

# Function to update release.txt
update_release_txt() {
    local version=$1
    cat > deploy/release.txt << EOF

# Login
gh auth login

# Create release with file
gh release create v${version} AgentJ-TradingBot-v${version}.zip --title "Version ${version}" --notes "Release notes"

EOF
}

# Main script
main() {
    echo -e "${GREEN}AgentJ Trading Bot - Release Automation${NC}\n"
    
    # Get current version
    current_version=$(get_current_version)
    echo -e "Current version: ${YELLOW}${current_version}${NC}"
    
    # Determine new version
    if [ $# -eq 0 ]; then
        echo -e "${RED}Error: No version specified${NC}"
        echo "Usage: $0 [VERSION|patch|minor|major]"
        exit 1
    fi
    
    new_version=$(bump_version "$current_version" "$1")
    
    # Validate version format
    if ! [[ $new_version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo -e "${RED}Error: Invalid version format '${new_version}'${NC}"
        echo "Use format: MAJOR.MINOR.PATCH (e.g., 2.1.0)"
        exit 1
    fi
    
    echo -e "New version: ${GREEN}${new_version}${NC}\n"
    
    # Confirm
    read -p "Continue with release v${new_version}? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Release cancelled"
        exit 0
    fi
    
    # Update version file
    echo -e "\n${YELLOW}[1/5]${NC} Updating version file..."
    update_version_file "$new_version"
    echo -e "${GREEN}✓${NC} Updated $VERSION_FILE"
    
    # Update release.txt
    echo -e "\n${YELLOW}[2/5]${NC} Updating release.txt..."
    update_release_txt "$new_version"
    echo -e "${GREEN}✓${NC} Updated deploy/release.txt"
    
    # Build executable
    echo -e "\n${YELLOW}[3/5]${NC} Building executable..."
    python deploy/build.py
    
    # Create release package
    echo -e "\n${YELLOW}[4/5]${NC} Creating release package..."
    python deploy/create_release_exe.py "$new_version"
    
    # Git operations
    echo -e "\n${YELLOW}[5/7]${NC} Git operations..."
    git add "$VERSION_FILE" deploy/release.txt
    git commit -m "Release v${new_version}"
    git tag -a "v${new_version}" -m "Version ${new_version}"
    echo -e "${GREEN}✓${NC} Created git commit and tag"
    
    # Push to remote
    echo -e "\n${YELLOW}[6/7]${NC} Pushing to remote..."
    read -p "Push to GitHub now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push && git push --tags
        echo -e "${GREEN}✓${NC} Pushed changes and tags"
    else
        echo -e "${YELLOW}⚠${NC} Skipped push - remember to run: git push && git push --tags"
    fi
    
    # Create GitHub release
    echo -e "\n${YELLOW}[7/7]${NC} Creating GitHub release..."
    
    # Find gh CLI command (check common paths for Windows)
    GH_CMD="gh"
    if ! command -v gh &> /dev/null; then
        # Try Windows default installation path
        if [ -f "/c/Program Files/GitHub CLI/gh.exe" ]; then
            GH_CMD="/c/Program Files/GitHub CLI/gh.exe"
        elif [ -f "$PROGRAMFILES/GitHub CLI/gh.exe" ]; then
            GH_CMD="$PROGRAMFILES/GitHub CLI/gh.exe"
        else
            echo -e "${YELLOW}⚠${NC} GitHub CLI (gh) not found"
            echo ""
            echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${GREEN}Release v${new_version} prepared successfully!${NC}"
            echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
            echo "To complete the release, run:"
            echo -e "${YELLOW}gh release create v${new_version} dist/AgentJ-TradingBot-v${new_version}.zip --title \"Version ${new_version}\" --notes \"Release notes\" --latest${NC}"
            echo ""
            echo "Or install GitHub CLI from: https://cli.github.com/"
            exit 0
        fi
    fi
    
    # Check if authenticated
    if ! "$GH_CMD" auth status &> /dev/null; then
        echo "Authenticating with GitHub..."
        "$GH_CMD" auth login
    fi
    
    # Create release
    "$GH_CMD" release create "v${new_version}" \
        "dist/AgentJ-TradingBot-v${new_version}.zip" \
        --title "Version ${new_version}" \
        --notes "Release notes for version ${new_version}" \
        --latest
    
    echo -e "${GREEN}✓${NC} GitHub release created and marked as latest"
    
    # Final success message
    echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Release v${new_version} completed successfully!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    echo "View release: https://github.com/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/releases/tag/v${new_version}"
}

main "$@"
