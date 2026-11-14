"""
TeamScreen Relay - Background Worker Agent
Runs as a discreet, lightweight system tray process with zero desktop window intrusion.
Streaming activates automatically when commanded by the CEO Admin console.
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

import pystray
from PIL import Image, ImageDraw
import mss

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
        
        # Tray Icon Handle
        self.tray_icon = None

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
        """Generate dynamic 64x64 tray icon based on state"""
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Background rounded dark base
        draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=(15, 23, 42, 240))

        # Color based on state
        if state == "streaming":
            dot_color = (56, 189, 248) # Cyan/Blue active pulse
            glow_color = (14, 165, 233, 100)
        elif state == "connected":
            dot_color = (16, 185, 129) # Emerald Green online
            glow_color = (5, 150, 105, 100)
        else:
            dot_color = (245, 158, 11) # Amber connecting
            glow_color = (217, 119, 6, 100)

        # Outer glow
        draw.ellipse([16, 16, 48, 48], fill=glow_color)
        # Inner dot
        draw.ellipse([20, 20, 44, 44], fill=dot_color)

        return img

    def update_tray_state(self, state, status_text):
        self.current_status_text = status_text
        if self.tray_icon:
            self.tray_icon.icon = self.create_tray_image(state)
            self.tray_icon.title = f"TeamScreen: {status_text}"

    def heartbeat_loop(self):
        """Discreet ping loop notifying relay of workstation availability"""
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        ping_url = f"{relay_url}/api/ping"

        # Determine screen resolution
        res_str = "1920x1080"
        try:
            with mss.mss() as sct:
                mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                res_str = f"{mon['width']}x{mon['height']}"
        except Exception:
            pass

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
                    headers={"Content-Type": "application/json", "User-Agent": "TeamScreenWorkerAgent/2.0"},
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

                    # If CEO sends guidance, display a brief tray notification
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
        """Screen capture loop using mss with near-zero CPU and low RAM"""
        relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
        frame_url = f"{relay_url}/api/stream/frame"

        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]

            while self.is_running:
                if not self.is_streaming:
                    time.sleep(0.2)
                    continue

                try:
                    t0 = time.time()
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                    # High-quality scale optimized for low CPU
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
