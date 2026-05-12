param(
    [int]$Port = 8777,
    [int]$TickSeconds = 60,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Runtime = Join-Path $Root "runtime"
New-Item -ItemType Directory -Force $Runtime | Out-Null

if (-not $PythonPath) {
    $PreferredPython = "C:\Users\shang\AppData\Local\Programs\Python\Python311\python.exe"
    if (Test-Path -LiteralPath $PreferredPython) {
        $PythonPath = $PreferredPython
    } else {
        $PythonPath = "python"
    }
}

$ArgsList = @(
    "-m", "agent_world.watchdog",
    "--port", [string]$Port,
    "--tick-seconds", [string]$TickSeconds
)

Start-Process -FilePath $PythonPath -ArgumentList $ArgsList -WorkingDirectory $Root -WindowStyle Hidden
"Agent World watchdog started at http://127.0.0.1:$Port"
