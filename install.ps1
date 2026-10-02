param(
    [Parameter(Mandatory = $true)][string]$GameDir   # e.g. D:\SteamLibrary\steamapps\common\LORT
)
$ue4ss = Join-Path $GameDir "bw\Binaries\Win64\ue4ss"
if (-not (Test-Path (Join-Path $GameDir "bw\Binaries\Win64\LortGame-Win64-Shipping.exe"))) {
    Write-Error "LORT not found in $GameDir"; exit 1
}
if (-not (Test-Path $ue4ss)) {
    Write-Error "UE4SS not installed yet: extract dwmapi.dll and the ue4ss folder into $GameDir\bw\Binaries\Win64 first"; exit 1
}
Copy-Item (Join-Path $PSScriptRoot "MemberVariableLayout.ini") $ue4ss -Force
Write-Host "Installed MemberVariableLayout.ini into $ue4ss"
