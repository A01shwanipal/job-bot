# Run once in PowerShell:  powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
# Schedules the daily run at 9:00 AM *Windows local time* (set Windows time zone to India Standard Time).
$root = Split-Path -Parent $PSScriptRoot
$action   = New-ScheduledTaskAction -Execute "$root\scripts\run_daily.bat" -WorkingDirectory $root
$trigger  = New-ScheduledTaskTrigger -Daily -At 9:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "JobBot Daily" -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "Registered 'JobBot Daily'. -StartWhenAvailable runs it as soon as the PC is on if 9:00 was missed."
