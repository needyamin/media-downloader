param(
    [Parameter(Mandatory = $true)]
    [string[]]$Path
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pfx = Join-Path $repoRoot "certs\codesign-test.pfx"
$passwordFile = Join-Path $repoRoot "certs\pfx-password.txt"
$signTool = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"

if (-not (Test-Path $signTool)) {
    throw "SignTool not found: $signTool"
}
if (-not (Test-Path $pfx)) {
    throw "PFX not found: $pfx"
}
if (-not (Test-Path $passwordFile)) {
    throw "Password file not found: $passwordFile"
}

$password = (Get-Content -LiteralPath $passwordFile -Raw).Trim()

foreach ($item in $Path) {
    if (-not (Test-Path $item)) {
        throw "File not found: $item"
    }
    & $signTool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f $pfx /p $password /d "Media Downloader" $item
    if ($LASTEXITCODE -ne 0) {
        throw "SignTool sign failed for $item"
    }
    & $signTool verify /v $item
    $signature = Get-AuthenticodeSignature -FilePath $item
    Write-Output "Signed: $item"
    Write-Output "Signer: $($signature.SignerCertificate.Subject)"
    Write-Output "Timestamp: $($signature.TimeStamperCertificate.Subject)"
    Write-Output "Status: $($signature.Status)"
}
