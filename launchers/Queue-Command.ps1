param(
    [Parameter(Mandatory = $true)]
    [string]$Action,
    [string]$ScriptPath = "",
    [string]$PayloadJson = "",
    [string]$RequestedBy = "external_agent"
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptRoot "..")
$configPath = Join-Path $projectRoot "config\project.json"
$config = Get-Content $configPath | ConvertFrom-Json
$pythonExe = $config.python.preferred_interpreter
$entryScript = Join-Path $projectRoot "scripts\queue_command.py"

if (-not (Test-Path $pythonExe)) {
    throw "Preferred interpreter not found at $pythonExe"
}

$args = @($entryScript, $Action, "--requested-by", $RequestedBy)
if ($ScriptPath) {
    $args += @("--script", $ScriptPath)
}
if ($PayloadJson) {
    $args += @("--payload-json", $PayloadJson)
}

& $pythonExe @args
