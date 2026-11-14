"""
TeamScreen Relay - Background Worker Agent
Precision DPI-aware mouse clicking, real-time screen streaming, and remote file transfer manager.
"""

import sys
import os
import time
import json
import socket
import base64
import threading
from io import BytesIO
import urllib.request
import urllib.error

# Set DPI Awareness before importing UI/capture tools for pixel-perfect coordinates
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import pystray
from PIL import Image, ImageDraw
import mss
import pyautogui
import win32api
import win32con

pyautogui.FAILSAFE = False

DEFAULT_RELAY_URL = "https://teamscreen-relay-mktradez.vercel.app"
CONFIG_FILE = "worker_config.json"

class BackgroundWorkerAgent:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.config_path = os.path.join(self.base_dir, CONFIG_FILE)
        
        self.config = self.load_config()
        self.worker_id = self.config.get("worker_id", f"w_{socket.gethostname()[:8]}_{int(time.time()) % 10000:04d}")
        
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

        # Tray Icon Handle
        self.tray_icon = None

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
        default_cfg = {
            "worker_id": f"w_{socket.gethostname()[:8]}_{int(time.time()) % 10000:04d}",
            "worker_name": f"{os.environ.get('USERNAME', 'Worker')} ({socket.gethostname()})",
            "department": "Workstation Operations",
            "relay_url": DEFAULT_RELAY_URL
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_cfg.update(data)
            except Exception:
                pass
        else:
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
            dot_color = (234, 179, 8) # Yellow file transfer
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
            self.tray_icon.title = f"TeamScreen: {status_text}"

    def heartbeat_loop(self):
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        ping_url = f"{relay_url}/api/ping"
        res_str = f"{self.mon_width}x{self.mon_height}"

        while self.is_running:
            payload = {
                "workerId": self.worker_id,
                "name": self.config.get("worker_name", "Worker"),
                "department": self.config.get("department", "Operations"),
                "hostname": socket.gethostname(),
                "status": "streaming" if self.is_streaming else "online",
                "screenResolution": res_str,
                "timestamp": int(time.time() * 1000)
            }

            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    ping_url,
                    data=data,
                    headers={"Content-Type": "application/json", "User-Agent": "TeamScreenWorkerAgent/2.1"},
                    method="POST"
                )
                t0 = time.time()
                with urllib.request.urlopen(req, timeout=4) as response:
                    res = json.loads(response.read().decode("utf-8"))
                    self.last_ping_ms = int((time.time() - t0) * 1000)
                    self.is_connected = True

                    stream_req = res.get("streamRequested", False)
                    guidance = res.get("guidanceMessage", "")

                    if stream_req and not self.is_streaming:
                        self.is_streaming = True
                        self.update_tray_state("streaming", f"Live Stream Active ({self.last_ping_ms}ms)")
                    elif not stream_req and self.is_streaming:
                        self.is_streaming = False
                        self.update_tray_state("connected", f"Connected & Ready ({self.last_ping_ms}ms)")
                    elif not self.is_streaming:
                        self.update_tray_state("connected", f"Connected ({self.last_ping_ms}ms)")

                    if guidance:
                        try:
                            self.tray_icon.notify(guidance, title="CEO Guidance Instruction")
                        except Exception:
                            pass

            except Exception:
                self.is_connected = False
                self.update_tray_state("idle", "Reconnecting to Relay...")

            time.sleep(2.0)

    def stream_loop(self):
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        frame_url = f"{relay_url}/api/stream/frame"

        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            self.mon_left = monitor["left"]
            self.mon_top = monitor["top"]
            self.mon_width = monitor["width"]
            self.mon_height = monitor["height"]

            while self.is_running:
                if not self.is_streaming:
                    time.sleep(0.2)
                    continue

                try:
                    t0 = time.time()
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                    target_w = 1280
                    target_h = int(img.height * (1280 / img.width))
                    img = img.resize((target_w, target_h), Image.Resampling.BILINEAR)

                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=68, optimize=True)
                    b64_frame = base64.b64encode(buffer.getvalue()).decode("ascii")

                    payload = {
                        "workerId": self.worker_id,
                        "frame": b64_frame,
                        "timestamp": int(time.time() * 1000)
                    }
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        frame_url,
                        data=data,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=3):
                        pass

                    elapsed = time.time() - t0
                    time.sleep(max(0.04, 0.05 - elapsed))
                except Exception:
                    time.sleep(0.4)

    def input_receiver_loop(self):
        """Precision DPI-Aware mouse click & keystroke execution"""
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        input_url = f"{relay_url}/api/stream/input?workerId={self.worker_id}"

        while self.is_running:
            if not self.is_streaming:
                time.sleep(0.25)
                continue

            try:
                req = urllib.request.Request(input_url, headers={"User-Agent": "TeamScreenWorkerAgent/2.1"})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    events = data.get("events", [])

                    for ev in events:
                        ev_type = ev.get("eventType")
                        if ev_type == "click":
                            xr = max(0.0, min(1.0, float(ev.get("xRatio", 0.5))))
                            yr = max(0.0, min(1.0, float(ev.get("yRatio", 0.5))))
                            click_x = self.mon_left + int(xr * self.mon_width)
                            click_y = self.mon_top + int(yr * self.mon_height)

                            # Win32 hardware mouse positioning & click
                            win32api.SetCursorPos((click_x, click_y))
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, click_x, click_y, 0, 0)
                            time.sleep(0.02)
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, click_x, click_y, 0, 0)

                        elif ev_type == "type":
                            text = ev.get("text", "")
                            if text:
                                pyautogui.write(text, interval=0.015)
                        elif ev_type == "key":
                            key = ev.get("key", "")
                            if key:
                                pyautogui.press(key)

                time.sleep(0.1)
            except Exception:
                time.sleep(0.3)

    # --- Feature 2: Remote File Explorer & Transfer Manager ---
    def file_handler_loop(self):
        """Listens for folder explore and file upload requests from CEO"""
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        cmd_url = f"{relay_url}/api/files/command?workerId={self.worker_id}"
        result_url = f"{relay_url}/api/files/result"

        while self.is_running:
            try:
                req = urllib.request.Request(cmd_url, headers={"User-Agent": "TeamScreenWorkerAgent/2.1"})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    commands = data.get("commands", [])

                    for cmd in commands:
                        action = cmd.get("action")
                        if action == "list":
                            req_path = cmd.get("path", "")
                            self.handle_list_directory(req_path, result_url)
                        elif action == "upload":
                            target_dir = cmd.get("path", "")
                            file_name = cmd.get("fileName", "file.dat")
                            b64_data = cmd.get("fileData", "")
                            self.handle_upload_file(target_dir, file_name, b64_data, result_url)

                time.sleep(0.5)
            except Exception:
                time.sleep(1.0)

    def handle_list_directory(self, target_path, result_url):
        # Resolve target directory or default to Desktop/Home
        if not target_path or target_path == "DEFAULT":
            target_path = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(target_path):
                target_path = os.path.expanduser("~")

        target_path = os.path.abspath(target_path)
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
            # Sort: folders first, then files alphabetically
            items.sort(key=lambda x: (not x["isDir"], x["name"].lower()))
        except Exception as e:
            items = []

        payload = {
            "workerId": self.worker_id,
            "currentPath": target_path,
            "items": items,
            "statusMessage": f"Directory scanned: {len(items)} items"
        }

        try:
            req = urllib.request.Request(
                result_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3):
                pass
        except Exception:
            pass

    def handle_upload_file(self, target_dir, file_name, b64_data, result_url):
        if not target_dir or not os.path.exists(target_dir):
            target_dir = os.path.join(os.path.expanduser("~"), "Desktop")

        dest_file = os.path.join(target_dir, file_name)

        try:
            file_bytes = base64.b64decode(b64_data)
            with open(dest_file, "wb") as f:
                f.write(file_bytes)

            try:
                self.tray_icon.notify(f"Received: {file_name}\nSaved to: {target_dir}", title="File Received from CEO")
            except Exception:
                pass

            # Reply with refreshed folder contents
            self.handle_list_directory(target_dir, result_url)
        except Exception as e:
            pass

    def shutdown(self, icon=None):
        self.is_running = False
        self.is_streaming = False

        try:
            relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
            req = urllib.request.Request(
                f"{relay_url}/api/ping",
                data=json.dumps({"workerId": self.worker_id, "status": "offline"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=1):
                pass
        except Exception:
            pass

        if icon:
            icon.stop()

    def run(self):
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        threading.Thread(target=self.stream_loop, daemon=True).start()
        threading.Thread(target=self.input_receiver_loop, daemon=True).start()
        threading.Thread(target=self.file_handler_loop, daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem(f"Node: {self.config.get('worker_name', 'Worker')}", lambda: None, enabled=False),
            pystray.MenuItem(lambda text: f"Status: {self.current_status_text}", lambda: None, enabled=False),
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
