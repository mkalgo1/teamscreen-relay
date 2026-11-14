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

import pystray
from PIL import Image, ImageDraw
import mss
import pyautogui
import win32api
import win32con
import cv2
import numpy as np
import requests

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

        # Reusable HTTP Session with Keep-Alive connection pooling
        self.http_session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
        self.http_session.mount("https://", adapter)
        self.http_session.mount("http://", adapter)

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

                    # Fast downsampled thumbnail to check for screen motion
                    thumb = cv2.resize(bgr_frame, (160, 90), interpolation=cv2.INTER_NEAREST)
                    has_motion = True
                    if prev_thumb is not None:
                        diff = np.mean(np.abs(thumb.astype(np.float32) - prev_thumb.astype(np.float32)))
                        # If difference is negligible (<0.4%) and sent recently, skip frame
                        if diff < 0.4 and (t0 - last_sent_time) < 1.0:
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

                    # SIMD JPEG encoding with quality 58 (crisp text, low bandwidth, ~2ms encoding)
                    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 58]
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
                        file_name = cmd.get("fileName", "")
                        file_data = cmd.get("fileData", "")

                        if action == "list":
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

                time.sleep(0.4)
            except Exception:
                time.sleep(1.0)

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

    def handle_list_directory(self, target_path, result_url):
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
        """Deletes a file or directory from worker's PC"""
        parent_dir = os.path.dirname(item_path)
        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
            self.handle_list_directory(parent_dir, result_url)
        except Exception as e:
            payload = {
                "workerId": self.worker_id,
                "action": "delete",
                "currentPath": parent_dir,
                "statusMessage": f"Delete failed: {str(e)}",
                "success": False
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
