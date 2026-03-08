param(
    [string]$Url,
    [string]$OutputFile
)

$ProgressPreference = 'SilentlyContinue'
$ErrorActionPreference = 'Stop'

try {
    Write-Host "Downloading from: $Url"
    Write-Host "Saving to: $OutputFile"
    Invoke-WebRequest -Uri $Url -OutFile $OutputFile
    Write-Host "Download completed successfully"
    exit 0
} catch {
    Write-Host "Download failed: $($_.Exception.Message)"
    exit 1
}
