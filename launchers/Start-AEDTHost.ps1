$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptRoot "..")
$configPath = Join-Path $projectRoot "config\project.json"
$config = Get-Content $configPath | ConvertFrom-Json
$pythonExe = $config.python.preferred_interpreter
$entryScript = Join-Path $projectRoot "scripts\bootstrap_agent_host.py"

if (-not (Test-Path $pythonExe)) {
    throw "Preferred interpreter not found at $pythonExe"
}

& $pythonExe $entryScript
