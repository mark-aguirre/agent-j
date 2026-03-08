param(
    [string]$ZipFile,
    [string]$Destination
)

$ProgressPreference = 'SilentlyContinue'
$ErrorActionPreference = 'Stop'

try {
    Write-Host "Extracting: $ZipFile"
    Write-Host "To: $Destination"
    Expand-Archive -Path $ZipFile -DestinationPath $Destination -Force
    Write-Host "Extraction completed successfully"
    exit 0
} catch {
    Write-Host "Extraction failed: $($_.Exception.Message)"
    exit 1
}
