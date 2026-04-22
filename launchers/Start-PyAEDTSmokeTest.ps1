$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptRoot "..")
$entryScript = Join-Path $projectRoot "scripts\run_pyaedt_smoke_test.py"
$preferredPython = "C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe"

if (-not (Test-Path $preferredPython)) {
    throw "PyAEDT python not found at $preferredPython"
}

& $preferredPython $entryScript
