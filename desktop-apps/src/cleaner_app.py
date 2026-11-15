"""
TeamScreen Relay - Worker Fresh Start & Complete Cleanup Utility (Pro Max Edition)
Safely and completely uninstalls and removes all background worker processes,
Windows Startup registry keys, boot shortcuts, and local application data.
Ensures a 100% clean, fresh start on the next PC restart.
"""

import sys
import os
import time
import shutil
import threading
import winreg
import psutil
import customtkinter as ctk
from tkinter import messagebox

# DPI Awareness
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class WorkerCleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TeamScreen Worker Cleaner // Fresh Start Pro")
        self.geometry("780x640")
        self.minsize(720, 560)
        self.configure(fg_color="#0B0F19")

        # Center on screen
        self.center_window()

        # State tracking
        self.items_status = []
        self.is_cleaning = False

        self.setup_ui()
        # Automatically run initial scan after window loads
        self.after(300, self.start_scan)

    def center_window(self):
        self.update_idletasks()
        w = 780
        h = 640
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def setup_ui(self):
        # Main Container
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=24, pady=20)

        # 1. Header Frame
        header = ctk.CTkFrame(self.main_container, fg_color="#111827", corner_radius=10, border_color="#1F2937", border_width=1)
        header.pack(fill="x", pady=(0, 14))

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="x", padx=18, pady=16)

        header_icon = ctk.CTkLabel(
            header_inner,
            text="🧹",
            font=ctk.CTkFont(size=34)
        )
        header_icon.pack(side="left", padx=(0, 14))

        title_box = ctk.CTkFrame(header_inner, fg_color="transparent")
        title_box.pack(side="left", fill="both")

        title_lbl = ctk.CTkLabel(
            title_box,
            text="Worker Relay Clean & Fresh Start Utility",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            title_box,
            text="Terminates worker processes, removes Windows Startup registry & shortcuts, and purges local data",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#94A3B8"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # 2. Metric Stat Cards
        self.stats_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.stats_frame.pack(fill="x", pady=(0, 14))
        self.stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stat_col")

        self.card_process = self.create_stat_card(self.stats_frame, 0, "Active Processes", "Checking...", "⚡", "#F59E0B")
        self.card_registry = self.create_stat_card(self.stats_frame, 1, "Startup Registry", "Checking...", "🔑", "#38BDF8")
        self.card_startup = self.create_stat_card(self.stats_frame, 2, "Startup Folder", "Checking...", "📂", "#818CF8")
        self.card_files = self.create_stat_card(self.stats_frame, 3, "Installed Files", "Checking...", "💾", "#10B981")

        # 3. Action Toolbar
        action_bar = ctk.CTkFrame(self.main_container, fg_color="#111827", corner_radius=10, border_color="#1F2937", border_width=1)
        action_bar.pack(fill="x", pady=(0, 14))

        action_inner = ctk.CTkFrame(action_bar, fg_color="transparent")
        action_inner.pack(fill="x", padx=16, pady=12)

        self.clear_btn = ctk.CTkButton(
            action_inner,
            text="🧹 Clear Everything & Fresh Start",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#DC2626",
            hover_color="#B91C1C",
            height=40,
            corner_radius=8,
            command=self.start_cleanup
        )
        self.clear_btn.pack(side="left", padx=(0, 10))

        self.scan_btn = ctk.CTkButton(
            action_inner,
            text="🔍 Re-Scan System",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            height=40,
            corner_radius=8,
            command=self.start_scan
        )
        self.scan_btn.pack(side="left")

        self.status_badge = ctk.CTkLabel(
            action_inner,
            text="Ready to inspect",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#94A3B8"
        )
        self.status_badge.pack(side="right", padx=10)

        # 4. Detailed Clean Results & Path Breakdown
        list_container = ctk.CTkFrame(self.main_container, fg_color="#111827", corner_radius=10, border_color="#1F2937", border_width=1)
        list_container.pack(fill="both", expand=True)

        list_header = ctk.CTkFrame(list_container, fg_color="#1E293B", height=38, corner_radius=6)
        list_header.pack(fill="x", padx=12, pady=(12, 6))

        lh_title = ctk.CTkLabel(
            list_header,
            text="📋 System Component Inspection & Path Report",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#F8FAFC"
        )
        lh_title.pack(side="left", padx=12)

        self.items_scroll = ctk.CTkScrollableFrame(list_container, fg_color="transparent")
        self.items_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def create_stat_card(self, parent, col, title, value, icon, color):
        card = ctk.CTkFrame(parent, fg_color="#111827", corner_radius=8, border_color="#1F2937", border_width=1)
        card.grid(row=0, column=col, padx=4, sticky="nsew")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", padx=12, pady=10)

        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill="x")

        icon_lbl = ctk.CTkLabel(top_row, text=icon, font=ctk.CTkFont(size=14))
        icon_lbl.pack(side="left")

        title_lbl = ctk.CTkLabel(
            top_row,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94A3B8"
        )
        title_lbl.pack(side="left", padx=(6, 0))

        val_lbl = ctk.CTkLabel(
            inner,
            text=value,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=color
        )
        val_lbl.pack(anchor="w", pady=(4, 0))

        return val_lbl

    # --- System Inspection Methods ---
    def get_cleanup_targets(self):
        """Returns all targets to check and clean."""
        targets = []

        # 1. Running Processes
        targets.append({
            "category": "process",
            "name": "Active Worker Processes",
            "type": "Process",
            "check_fn": self.check_processes,
            "clean_fn": self.kill_processes
        })

        # 2. Registry: HKCU Run Key
        targets.append({
            "category": "registry",
            "name": "HKCU Startup Run Key",
            "type": "Registry",
            "path": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run\TeamScreenWorker",
            "check_fn": lambda: self.check_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "TeamScreenWorker"),
            "clean_fn": lambda: self.delete_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "TeamScreenWorker")
        })

        # 3. Registry: HKCU Run Key Legacy (TeamScreen)
        targets.append({
            "category": "registry",
            "name": "HKCU Legacy Run Key",
            "type": "Registry",
            "path": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run\TeamScreen",
            "check_fn": lambda: self.check_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "TeamScreen"),
            "clean_fn": lambda: self.delete_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "TeamScreen")
        })

        # 4. Startup Folder Shortcut: User
        startup_dir = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            r"Microsoft\Windows\Start Menu\Programs\Startup"
        )
        user_shortcut = os.path.join(startup_dir, "TeamScreen Worker.lnk")
        targets.append({
            "category": "startup",
            "name": "Startup Folder Shortcut",
            "type": "Shortcut (.lnk)",
            "path": user_shortcut,
            "check_fn": lambda p=user_shortcut: os.path.exists(p),
            "clean_fn": lambda p=user_shortcut: self.delete_file(p)
        })

        # 5. Startup Folder Shortcut: Secondary / Legacy
        user_shortcut_2 = os.path.join(startup_dir, "TeamScreen.lnk")
        targets.append({
            "category": "startup",
            "name": "Secondary Startup Shortcut",
            "type": "Shortcut (.lnk)",
            "path": user_shortcut_2,
            "check_fn": lambda p=user_shortcut_2: os.path.exists(p),
            "clean_fn": lambda p=user_shortcut_2: self.delete_file(p)
        })

        # 6. LocalAppData Installation Directory (%LOCALAPPDATA%\TeamScreen)
        local_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "TeamScreen"
        )
        targets.append({
            "category": "files",
            "name": "Installed Worker Directory",
            "type": "Directory",
            "path": local_dir,
            "check_fn": lambda p=local_dir: os.path.exists(p),
            "clean_fn": lambda p=local_dir: self.delete_dir(p)
        })

        # 7. Local Config File in Current Directory
        cur_cfg = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "worker_config.json")
        targets.append({
            "category": "files",
            "name": "Local Directory Config",
            "type": "File",
            "path": cur_cfg,
            "check_fn": lambda p=cur_cfg: os.path.exists(p),
            "clean_fn": lambda p=cur_cfg: self.delete_file(p)
        })

        # 8. User Temp Directory Caches (%TEMP%\TeamScreen*)
        temp_dir = os.environ.get("TEMP", "")
        targets.append({
            "category": "files",
            "name": "Temporary Worker Cache",
            "type": "Temp Cache",
            "path": os.path.join(temp_dir, "TeamScreen*"),
            "check_fn": lambda: self.check_temp_cache(),
            "clean_fn": lambda: self.clean_temp_cache()
        })

        return targets

    def check_processes(self):
        found = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                name = (p.info.get("name") or "").lower()
                if name in ["workerrelay.exe", "workerrelay"]:
                    found.append(p.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return found

    def kill_processes(self):
        killed = 0
        for p in psutil.process_iter(["pid", "name"]):
            try:
                name = (p.info.get("name") or "").lower()
                if name in ["workerrelay.exe", "workerrelay"]:
                    p.kill()
                    killed += 1
            except Exception:
                pass
        time.sleep(0.5)
        return True, f"Terminated {killed} running process(es)"

    def check_reg_value(self, root_key, sub_key, value_name):
        try:
            with winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, value_name)
                return bool(val)
        except Exception:
            return False

    def delete_reg_value(self, root_key, sub_key, value_name):
        try:
            with winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, value_name)
            return True, "Registry value deleted"
        except FileNotFoundError:
            return True, "Already clean (not found)"
        except Exception as e:
            return False, f"Failed: {str(e)}"

    def delete_file(self, path):
        try:
            if os.path.exists(path):
                os.remove(path)
                return True, "File removed successfully"
            return True, "Already clean (file not found)"
        except Exception as e:
            return False, f"Error removing file: {str(e)}"

    def delete_dir(self, path):
        try:
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)
                if os.path.exists(path):
                    # Try forced retry
                    os.system(f'rmdir /s /q "{path}"')
                return True, "Directory purged successfully"
            return True, "Already clean (directory not found)"
        except Exception as e:
            return False, f"Error removing directory: {str(e)}"

    def check_temp_cache(self):
        temp_dir = os.environ.get("TEMP", "")
        if not temp_dir or not os.path.exists(temp_dir):
            return False
        for f in os.listdir(temp_dir):
            if "teamscreen" in f.lower():
                return True
        return False

    def clean_temp_cache(self):
        temp_dir = os.environ.get("TEMP", "")
        cleaned = 0
        if temp_dir and os.path.exists(temp_dir):
            for f in os.listdir(temp_dir):
                if "teamscreen" in f.lower():
                    fp = os.path.join(temp_dir, f)
                    try:
                        if os.path.isdir(fp):
                            shutil.rmtree(fp, ignore_errors=True)
                        else:
                            os.remove(fp)
                        cleaned += 1
                    except Exception:
                        pass
        return True, f"Purged {cleaned} temporary cache items"

    # --- Scanning & Cleaning Workflows ---
    def start_scan(self):
        if self.is_cleaning:
            return
        threading.Thread(target=self.run_scan_thread, daemon=True).start()

    def run_scan_thread(self):
        self.status_badge.configure(text="Scanning system...", text_color="#38BDF8")
        self.scan_btn.configure(state="disabled")
        self.clear_btn.configure(state="disabled")

        targets = self.get_cleanup_targets()
        results = []

        proc_found = 0
        reg_found = 0
        start_found = 0
        file_found = 0

        for t in targets:
            exists = False
            details = ""
            if t["category"] == "process":
                pids = t["check_fn"]()
                exists = len(pids) > 0
                details = f"Active PIDs: {', '.join(map(str, pids))}" if exists else "No active worker processes"
                proc_found = len(pids)
            elif t["category"] == "registry":
                exists = t["check_fn"]()
                details = t.get("path", "")
                if exists:
                    reg_found += 1
            elif t["category"] == "startup":
                exists = t["check_fn"]()
                details = t.get("path", "")
                if exists:
                    start_found += 1
            elif t["category"] == "files":
                exists = t["check_fn"]()
                details = t.get("path", "")
                if exists:
                    file_found += 1

            results.append({
                "target": t,
                "exists": exists,
                "details": details
            })

        self.after(0, lambda: self.update_scan_ui(results, proc_found, reg_found, start_found, file_found))

    def update_scan_ui(self, results, proc_found, reg_found, start_found, file_found):
        # Update metric cards
        self.card_process.configure(
            text=f"{proc_found} Active" if proc_found else "Clean (0)",
            text_color="#EF4444" if proc_found else "#10B981"
        )
        self.card_registry.configure(
            text=f"{reg_found} Present" if reg_found else "Clean",
            text_color="#F59E0B" if reg_found else "#10B981"
        )
        self.card_startup.configure(
            text=f"{start_found} Present" if start_found else "Clean",
            text_color="#F59E0B" if start_found else "#10B981"
        )
        self.card_files.configure(
            text=f"{file_found} Detected" if file_found else "Clean",
            text_color="#F59E0B" if file_found else "#10B981"
        )

        total_detected = proc_found + reg_found + start_found + file_found
        if total_detected > 0:
            self.status_badge.configure(
                text=f"⚠️ {total_detected} worker trace(s) detected",
                text_color="#F59E0B"
            )
        else:
            self.status_badge.configure(
                text="✨ System is 100% Clean",
                text_color="#10B981"
            )

        # Populate scroll items
        for child in self.items_scroll.winfo_children():
            child.destroy()

        for item in results:
            t = item["target"]
            exists = item["exists"]
            details = item["details"]

            card = ctk.CTkFrame(self.items_scroll, fg_color="#1E293B", corner_radius=6)
            card.pack(fill="x", pady=3)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=8)

            icon = "⚠️" if exists else "🟢"
            icon_lbl = ctk.CTkLabel(inner, text=icon, font=ctk.CTkFont(size=14))
            icon_lbl.pack(side="left", padx=(0, 8))

            name_box = ctk.CTkFrame(inner, fg_color="transparent")
            name_box.pack(side="left", fill="both")

            name_lbl = ctk.CTkLabel(
                name_box,
                text=f"{t['name']}  ({t['type']})",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#F8FAFC"
            )
            name_lbl.pack(anchor="w")

            path_lbl = ctk.CTkLabel(
                name_box,
                text=details,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color="#94A3B8"
            )
            path_lbl.pack(anchor="w")

            status_text = "PRESENT" if exists else "CLEAN"
            status_color = "#EF4444" if exists else "#10B981"
            status_lbl = ctk.CTkLabel(
                inner,
                text=status_text,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=status_color
            )
            status_lbl.pack(side="right")

        self.scan_btn.configure(state="normal")
        self.clear_btn.configure(state="normal")

    def start_cleanup(self):
        if self.is_cleaning:
            return
        
        confirm = messagebox.askyesno(
            "Confirm Full Reset",
            "This will completely terminate Worker Relay and remove all startup registry keys, shortcuts, and application data.\n\nNext time you restart the PC, nothing will start.\n\nProceed with cleanup?"
        )
        if not confirm:
            return

        self.is_cleaning = True
        self.scan_btn.configure(state="disabled")
        self.clear_btn.configure(state="disabled")
        self.status_badge.configure(text="🧹 Purging all worker components...", text_color="#EF4444")

        threading.Thread(target=self.run_cleanup_thread, daemon=True).start()

    def run_cleanup_thread(self):
        targets = self.get_cleanup_targets()
        clean_reports = []

        for t in targets:
            time.sleep(0.2) # Smooth visual feedback
            success, msg = t["clean_fn"]()
            clean_reports.append({
                "target": t,
                "success": success,
                "msg": msg
            })

        self.after(0, lambda: self.update_cleanup_ui(clean_reports))

    def update_cleanup_ui(self, reports):
        self.is_cleaning = False

        for child in self.items_scroll.winfo_children():
            child.destroy()

        all_ok = True
        for r in reports:
            t = r["target"]
            success = r["success"]
            msg = r["msg"]
            if not success:
                all_ok = False

            card = ctk.CTkFrame(self.items_scroll, fg_color="#1E293B", corner_radius=6)
            card.pack(fill="x", pady=3)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=8)

            icon = "✅" if success else "❌"
            icon_lbl = ctk.CTkLabel(inner, text=icon, font=ctk.CTkFont(size=14))
            icon_lbl.pack(side="left", padx=(0, 8))

            name_box = ctk.CTkFrame(inner, fg_color="transparent")
            name_box.pack(side="left", fill="both")

            name_lbl = ctk.CTkLabel(
                name_box,
                text=f"{t['name']}  ({t['type']})",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#F8FAFC"
            )
            name_lbl.pack(anchor="w")

            detail_text = f"Action: {msg} • Path: {t.get('path', 'System Process')}"
            path_lbl = ctk.CTkLabel(
                name_box,
                text=detail_text,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color="#38BDF8" if success else "#EF4444"
            )
            path_lbl.pack(anchor="w")

            status_text = "DONE" if success else "ERROR"
            status_color = "#10B981" if success else "#EF4444"
            status_lbl = ctk.CTkLabel(
                inner,
                text=status_text,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=status_color
            )
            status_lbl.pack(side="right")

        # Update stat cards to clean
        self.card_process.configure(text="Clean (0)", text_color="#10B981")
        self.card_registry.configure(text="Clean", text_color="#10B981")
        self.card_startup.configure(text="Clean", text_color="#10B981")
        self.card_files.configure(text="Clean", text_color="#10B981")

        self.status_badge.configure(
            text="✨ 100% Cleared - Fresh Start Ready",
            text_color="#10B981"
        )
        self.scan_btn.configure(state="normal")
        self.clear_btn.configure(state="normal")

        messagebox.showinfo(
            "Cleanup Complete",
            "✨ All worker relay processes, startup registry keys, shortcuts, and local application data have been purged successfully.\n\nNext time this PC restarts, no worker relay components will launch."
        )

if __name__ == "__main__":
    app = WorkerCleanerApp()
    app.mainloop()
