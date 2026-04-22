$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptRoot "..")
$entryScript = Join-Path $projectRoot "scripts\run_linear_2d_screen.py"

$ansysExe = Get-ChildItem "C:\Program Files\AnsysEM" -Filter ansysedt.exe -Recurse -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName

if (-not $ansysExe) {
    throw "ansysedt.exe not found under C:\Program Files\AnsysEM"
}

Push-Location (Join-Path $projectRoot "scripts")
try {
    & $ansysExe -ng -RunScriptAndExit $entryScript
}
finally {
    Pop-Location
}
