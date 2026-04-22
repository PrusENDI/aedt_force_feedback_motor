$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptRoot "..")
$entryScript = Join-Path $projectRoot "scripts\probe_environment.py"
$ansysPython = Get-ChildItem "C:\Program Files\AnsysEM" -Filter python.exe -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match 'CPython' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName

if (-not $ansysPython) {
    throw "Ansys CPython not found under C:\Program Files\AnsysEM"
}

& $ansysPython $entryScript
