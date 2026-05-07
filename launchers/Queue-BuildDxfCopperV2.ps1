param(
    [string]$RequestedBy = "external_agent"
)

& (Join-Path $PSScriptRoot "Queue-Command.ps1") `
    -Action run_script `
    -ScriptPath "scripts/build_dxf_copper_v2.py" `
    -RequestedBy $RequestedBy
