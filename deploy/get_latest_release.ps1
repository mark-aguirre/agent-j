param(
    [string]$RepoOwner,
    [string]$RepoName
)

$ProgressPreference = 'SilentlyContinue'
$ErrorActionPreference = 'Stop'

try {
    $apiUrl = "https://api.github.com/repos/$RepoOwner/$RepoName/releases/latest"
    $release = Invoke-RestMethod -Uri $apiUrl
    
    $asset = $release.assets | Where-Object { $_.name -like '*.zip' } | Select-Object -First 1
    
    if ($asset) {
        Write-Output $asset.browser_download_url
        Write-Output $release.tag_name
        exit 0
    } else {
        Write-Output "NO_ASSET"
        Write-Output "No .zip file found in latest release"
        exit 1
    }
} catch {
    Write-Output "API_ERROR"
    Write-Output $_.Exception.Message
    exit 1
}
