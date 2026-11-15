# TeamScreen Enterprise Deployment Guide

## Overview
This directory contains standard administrative deployment scripts for setting up the **TeamScreen Worker Client (`WorkerRelay.exe`)** across company-owned workstations.

---

## 1. Quick Installation (Automatic Auto-Startup)

To install the Worker Client on a worker's workstation with automatic startup on system reboot:

1. Right-click **`Install-WorkerStartup.ps1`** and select **"Run with PowerShell"** (or run from an elevated Administrator PowerShell prompt):
   ```powershell
   powershell.exe -ExecutionPolicy Bypass -File .\Install-WorkerStartup.ps1
   ```
2. **What this does automatically:**
   - Copies `WorkerRelay.exe` and `worker_config.json` into `C:\Program Files\TeamScreen\`.
   - Creates an official Windows startup shortcut in:  
     `shell:common startup` (`C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp\TeamScreen Worker.lnk`).
   - Configures **NTFS Access Control**: Administrators have Full Control, while Standard Users have Read & Execute only. This prevents unauthorized modification, deletion, or tampering by non-administrative users.
   - Launches the worker agent immediately in the system tray.
   - **On any computer restart or reboot**, Windows automatically launches the tool.

---

## 2. Uninstallation

If you need to decommission or remove the tool from a workstation:

1. Right-click **`Uninstall-WorkerStartup.ps1`** and select **"Run with PowerShell"**:
   ```powershell
   powershell.exe -ExecutionPolicy Bypass -File .\Uninstall-WorkerStartup.ps1
   ```
2. Safely stops the background process, deletes the startup shortcut, and cleans up the directory.

---

## 3. Best Practices for Company-Owned PCs

- **Standard User Accounts**: Ensure employee Windows accounts are created as **Standard Users** (non-administrators). This ensures they cannot delete files in `C:\Program Files\`, alter system services, or terminate protected administrator software.
- **Relay URL**: The worker configuration points by default to:  
  `https://teamscreen-relay-mktradez.vercel.app`
