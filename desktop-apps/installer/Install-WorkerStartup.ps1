<#
.SYNOPSIS
    TeamScreen Enterprise Worker - Administrative Installation & Startup Script
.DESCRIPTION
    Installs WorkerRelay into Program Files with protected NTFS permissions and
    configures a machine-wide auto-startup shortcut in shell:common startup.
    Ensures the application starts reliably upon every system boot.
.NOTES
    Must be executed with Administrator privileges.
#>

# Requires Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Administrator rights required. Relaunching in elevated PowerShell..."
    Start-Process powershell.exe -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"") -Verb RunAs
    exit
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host " TeamScreen Worker - Enterprise Startup Installation" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

$sourceDir = Split-Path -Parent $PSScriptRoot
$binSource = Join-Path $sourceDir "bin\WorkerRelay.exe"
$cfgSource = Join-Path $sourceDir "bin\worker_config.json"

if (-not (Test-Path $binSource)) {
    # Check alternate local paths
    $binSource = Join-Path $PSScriptRoot "..\bin\WorkerRelay.exe"
}

if (-not (Test-Path $binSource)) {
    Write-Error "Could not locate WorkerRelay.exe in source directory: $binSource"
    exit 1
}

# 1. Target Directory: C:\Program Files\TeamScreen
$targetDir = "$env:ProgramFiles\TeamScreen"
Write-Host "[1/4] Preparing installation directory: $targetDir" -ForegroundColor Green
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

# 2. Copy Executable & Default Configuration
Write-Host "[2/4] Deploying WorkerRelay.exe and configuration..." -ForegroundColor Green
Copy-Item $binSource (Join-Path $targetDir "WorkerRelay.exe") -Force

if (Test-Path $cfgSource) {
    Copy-Item $cfgSource (Join-Path $targetDir "worker_config.json") -Force
} else {
    $defaultCfg = @{
        worker_id = "w_$($env:COMPUTERNAME.Substring(0, [Math]::Min(8, $env:COMPUTERNAME.Length)))_$(Get-Random -Minimum 1000 -Maximum 9999)"
        worker_name = "$($env:USERNAME) ($($env:COMPUTERNAME))"
        department = "Operations Workstation"
        relay_url = "https://teamscreen-relay-mktradez.vercel.app"
    } | ConvertTo-Json -Depth 2
    Set-Content -Path (Join-Path $targetDir "worker_config.json") -Value $defaultCfg -Encoding UTF8
}

# 3. Secure NTFS Access Control (Only Admins Can Modify / Delete)
Write-Host "[3/4] Setting secure NTFS permissions (Admin FullControl, Users Read/Execute)..." -ForegroundColor Green
try {
    $acl = Get-Acl $targetDir
    $acl.SetAccessRuleProtection($true, $true) # Disable inheritance, keep existing
    
    # Administrators & SYSTEM: Full Control
    $adminRule = New-Object System.Security.AccessControl.FileSystemAccessRule("BUILTIN\Administrators", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
    $systemRule = New-Object System.Security.AccessControl.FileSystemAccessRule("NT AUTHORITY\SYSTEM", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
    
    # Standard Users: ReadAndExecute only (Prevents unauthorized deletion or tampering)
    $usersRule = New-Object System.Security.AccessControl.FileSystemAccessRule("BUILTIN\Users", "ReadAndExecute", "ContainerInherit,ObjectInherit", "None", "Allow")
    
    $acl.ResetAccessRule($adminRule)
    $acl.AddAccessRule($systemRule)
    $acl.AddAccessRule($usersRule)
    Set-Acl -Path $targetDir -AclObject $acl
    Write-Host "    -> NTFS Access Control successfully locked to Administrators." -ForegroundColor DarkGreen
} catch {
    Write-Warning "Could not update ACLs: $_"
}

# 4. Create Machine-Wide Startup Shortcut in shell:common startup
Write-Host "[4/4] Creating Machine-Wide Startup Shortcut..." -ForegroundColor Green
$commonStartup = [Environment]::GetFolderPath("CommonStartup")
$shortcutPath = Join-Path $commonStartup "TeamScreen Worker.lnk"

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $targetDir "WorkerRelay.exe"
$shortcut.WorkingDirectory = $targetDir
$shortcut.Description = "TeamScreen Enterprise Worker Client - Remote Observation & Guidance"
$shortcut.Save()

Write-Host "    -> Shortcut created at: $shortcutPath" -ForegroundColor DarkGreen

# 5. Launch process if not already running
$existingProc = Get-Process -Name "WorkerRelay" -ErrorAction SilentlyContinue
if (-not $existingProc) {
    Write-Host "`nStarting TeamScreen Worker service now..." -ForegroundColor Cyan
    Start-Process (Join-Path $targetDir "WorkerRelay.exe") -WorkingDirectory $targetDir
} else {
    Write-Host "`nTeamScreen Worker is already active (PID: $($existingProc.Id))." -ForegroundColor Cyan
}

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host " Installation Complete!" -ForegroundColor Green
Write-Host " TeamScreen Worker will now automatically launch upon" -ForegroundColor Green
Write-Host " every workstation boot." -ForegroundColor Green
Write-Host "========================================================`n" -ForegroundColor Green
