# Runs the research loop around the clock and restarts it if it exits unexpectedly.
# Stop it by creating the file runs\PAUSE. Extra arguments are passed to scripts\run_loop.py.
#   .\scripts\start_loop.ps1
#   .\scripts\start_loop.ps1 --director-effort xhigh --workers 12
Set-Location "D:\Traders sir"
$env:PYTHONIOENCODING = "utf-8"
if (-not (Test-Path ".env")) {
    Write-Host "No .env file. Copy .env.example to .env and set ANTHROPIC_API_KEY first."
    exit 2
}
while ($true) {
    if (Test-Path "runs\PAUSE") { Write-Host "runs\PAUSE present; not starting."; break }
    & ".\.venv\Scripts\python.exe" "scripts\run_loop.py" @args
    if (Test-Path "runs\GOAL_REACHED") { Write-Host "Goal reached; loop finished."; break }
    if (Test-Path "runs\PAUSE") { Write-Host "Paused."; break }
    Write-Host "Loop exited; restarting in 60 seconds (Ctrl+C to stop)."
    Start-Sleep -Seconds 60
}
