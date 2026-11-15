<#
.SYNOPSIS
    TeamScreen Enterprise Worker - Administrative Removal Script
.DESCRIPTION
    Safely stops the worker process, removes the startup shortcut,
    and uninstalls files from Program Files.
#>

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Administrator rights required. Relaunching in elevated PowerShell..."
    Start-Process powershell.exe -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"") -Verb RunAs
    exit
}

Write-Host "`nStopping TeamScreen Worker processes..." -ForegroundColor Yellow
Stop-Process -Name "WorkerRelay" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Write-Host "Removing startup shortcut..." -ForegroundColor Yellow
$commonStartup = [Environment]::GetFolderPath("CommonStartup")
$shortcutPath = Join-Path $commonStartup "TeamScreen Worker.lnk"
if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host "Startup shortcut removed." -ForegroundColor Green
}

$targetDir = "$env:ProgramFiles\TeamScreen"
if (Test-Path $targetDir) {
    Write-Host "Removing application files from $targetDir..." -ForegroundColor Yellow
    Remove-Item $targetDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Installation directory removed." -ForegroundColor Green
}

Write-Host "`nTeamScreen Worker has been successfully uninstalled.`n" -ForegroundColor Green
