"""
Executive Screen Relay - Worker Node
High-performance, ultra-low CPU/RAM client for Windows workstations.
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

import customtkinter as ctk
from PIL import Image
import mss

# Application Constants
DEFAULT_RELAY_URL = "https://teamscreen-relay.vercel.app"
CONFIG_FILE = "worker_config.json"

class WorkerNodeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Appearance & Theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        self.title("TeamScreen Relay // Worker Node")
        self.geometry("480x640")
        self.minsize(440, 580)

        # State Variables
        self.is_connected = False
        self.is_streaming = False
        self.admin_watching = False
        self.last_ping_ms = 0
        self.frames_sent = 0
        self.worker_id = self.load_or_create_id()
        self.stop_event = threading.Event()

        # Load persisted config
        self.config = self.load_config()

        # Build UI
        self.setup_ui()

        # Auto-connect if enabled
        self.after(500, self.auto_start_if_configured)

    def load_or_create_id(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if "worker_id" in cfg:
                        return cfg["worker_id"]
            except Exception:
                pass
        import uuid
        return f"w_{socket.gethostname()[:8]}_{uuid.uuid4().hex[:6]}"

    def load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
        default_cfg = {
            "worker_id": self.worker_id,
            "worker_name": f"Agent - {os.environ.get('USERNAME', 'Workstation')}",
            "department": "Customer Operations",
            "relay_url": DEFAULT_RELAY_URL,
            "auto_connect": True
        }
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_cfg.update(data)
            except Exception:
                pass
        return default_cfg

    def save_config(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
        try:
            self.config["worker_name"] = self.name_entry.get().strip() or "Worker"
            self.config["department"] = self.dept_entry.get().strip() or "Operations"
            self.config["relay_url"] = self.url_entry.get().strip().rstrip("/")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print("Error saving config:", e)

    def setup_ui(self):
        # Header banner
        header_frame = ctk.CTkFrame(self, fg_color="#0F172A", corner_radius=0)
        header_frame.pack(fill="x", padx=0, pady=0)

        title_label = ctk.CTkLabel(
            header_frame,
            text="TEAMSCREEN RELAY",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#F8FAFC"
        )
        title_label.pack(anchor="w", padx=20, pady=(16, 2))

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Worker Node // Secure Live Observation Relay",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#94A3B8"
        )
        subtitle_label.pack(anchor="w", padx=20, pady=(0, 16))

        # Main Scrollable Container
        content_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=16, pady=12)

        # Status Card
        self.status_card = ctk.CTkFrame(content_frame, fg_color="#1E293B", corner_radius=12)
        self.status_card.pack(fill="x", pady=(0, 12))

        status_row = ctk.CTkFrame(self.status_card, fg_color="transparent")
        status_row.pack(fill="x", padx=16, pady=14)

        self.status_dot = ctk.CTkLabel(
            status_row,
            text="●",
            font=ctk.CTkFont(size=22),
            text_color="#EF4444"
        )
        self.status_dot.pack(side="left", padx=(0, 8))

        self.status_text = ctk.CTkLabel(
            status_row,
            text="DISCONNECTED",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#F8FAFC"
        )
        self.status_text.pack(side="left")

        self.ping_badge = ctk.CTkLabel(
            status_row,
            text="-- ms",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#64748B"
        )
        self.ping_badge.pack(side="right")

        # Admin Observation Alert Banner
        self.alert_frame = ctk.CTkFrame(self.status_card, fg_color="#064E3B", corner_radius=8)
        self.alert_label = ctk.CTkLabel(
            self.alert_frame,
            text="⚡ CEO IS CURRENTLY OBSERVING SCREEN",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#34D399"
        )
        self.alert_label.pack(padx=12, pady=8)
        # Not packed initially

        # Settings Card
        settings_card = ctk.CTkFrame(content_frame, fg_color="#1E293B", corner_radius=12)
        settings_card.pack(fill="x", pady=(0, 12))

        card_title = ctk.CTkLabel(
            settings_card,
            text="WORKSTATION IDENTITY",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#94A3B8"
        )
        card_title.pack(anchor="w", padx=16, pady=(14, 8))

        # Worker Name
        name_label = ctk.CTkLabel(settings_card, text="Your Name / Workstation ID", font=ctk.CTkFont(size=12), text_color="#CBD5E1")
        name_label.pack(anchor="w", padx=16, pady=(4, 2))
        self.name_entry = ctk.CTkEntry(settings_card, placeholder_text="e.g. Sarah Smith", fg_color="#0F172A", border_color="#334155")
        self.name_entry.insert(0, self.config.get("worker_name", ""))
        self.name_entry.pack(fill="x", padx=16, pady=(0, 10))

        # Department
        dept_label = ctk.CTkLabel(settings_card, text="Department / Role", font=ctk.CTkFont(size=12), text_color="#CBD5E1")
        dept_label.pack(anchor="w", padx=16, pady=(4, 2))
        self.dept_entry = ctk.CTkEntry(settings_card, placeholder_text="e.g. Sales Team", fg_color="#0F172A", border_color="#334155")
        self.dept_entry.insert(0, self.config.get("department", "Customer Support"))
        self.dept_entry.pack(fill="x", padx=16, pady=(0, 10))

        # Relay URL
        url_label = ctk.CTkLabel(settings_card, text="Vercel Live Ping Relay URL", font=ctk.CTkFont(size=12), text_color="#CBD5E1")
        url_label.pack(anchor="w", padx=16, pady=(4, 2))
        self.url_entry = ctk.CTkEntry(settings_card, placeholder_text="https://your-relay.vercel.app", fg_color="#0F172A", border_color="#334155")
        self.url_entry.insert(0, self.config.get("relay_url", DEFAULT_RELAY_URL))
        self.url_entry.pack(fill="x", padx=16, pady=(0, 16))

        # Guidance Messages Card
        self.msg_card = ctk.CTkFrame(content_frame, fg_color="#1E293B", corner_radius=12)
        self.msg_card.pack(fill="x", pady=(0, 12))

        msg_title = ctk.CTkLabel(
            self.msg_card,
            text="CEO GUIDANCE CHANNEL",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#94A3B8"
        )
        msg_title.pack(anchor="w", padx=16, pady=(14, 6))

        self.guidance_box = ctk.CTkLabel(
            self.msg_card,
            text="No active instructions. The CEO can send live guidance notes directly here.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#64748B",
            wraplength=380,
            justify="left"
        )
        self.guidance_box.pack(anchor="w", padx=16, pady=(0, 14))

        # Performance & Metrics Card
        metrics_card = ctk.CTkFrame(content_frame, fg_color="#1E293B", corner_radius=12)
        metrics_card.pack(fill="x", pady=(0, 16))

        metrics_grid = ctk.CTkFrame(metrics_card, fg_color="transparent")
        metrics_grid.pack(fill="x", padx=16, pady=12)

        self.cpu_label = ctk.CTkLabel(metrics_grid, text="CPU: <1%", font=ctk.CTkFont(size=11), text_color="#94A3B8")
        self.cpu_label.pack(side="left", expand=True)

        self.ram_label = ctk.CTkLabel(metrics_grid, text="RAM: ~28 MB", font=ctk.CTkFont(size=11), text_color="#94A3B8")
        self.ram_label.pack(side="left", expand=True)

        self.fps_label = ctk.CTkLabel(metrics_grid, text="FPS: 0", font=ctk.CTkFont(size=11), text_color="#94A3B8")
        self.fps_label.pack(side="left", expand=True)

        # Action Buttons
        self.connect_btn = ctk.CTkButton(
            self,
            text="CONNECT TO RELAY",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#10B981",
            hover_color="#059669",
            height=46,
            corner_radius=10,
            command=self.toggle_connection
        )
        self.connect_btn.pack(fill="x", padx=16, pady=(0, 14))

    def auto_start_if_configured(self):
        if self.config.get("auto_connect", True):
            self.toggle_connection()

    def toggle_connection(self):
        if not self.is_connected:
            self.save_config()
            self.is_connected = True
            self.stop_event.clear()
            self.connect_btn.configure(text="DISCONNECT", fg_color="#DC2626", hover_color="#B91C1C")
            self.status_dot.configure(text_color="#F59E0B")
            self.status_text.configure(text="CONNECTING...")

            # Launch Heartbeat & Ping Thread
            threading.Thread(target=self.heartbeat_loop, daemon=True).start()
            # Launch Screen Stream Thread
            threading.Thread(target=self.stream_loop, daemon=True).start()
        else:
            self.is_connected = False
            self.is_streaming = False
            self.stop_event.set()
            self.connect_btn.configure(text="CONNECT TO RELAY", fg_color="#10B981", hover_color="#059669")
            self.status_dot.configure(text_color="#EF4444")
            self.status_text.configure(text="DISCONNECTED")
            self.ping_badge.configure(text="-- ms")
            self.alert_frame.pack_forget()

    def heartbeat_loop(self):
        while self.is_connected and not self.stop_event.is_set():
            relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
            ping_url = f"{relay_url}/api/ping"

            payload = {
                "workerId": self.worker_id,
                "name": self.name_entry.get().strip() or "Worker",
                "department": self.dept_entry.get().strip() or "Operations",
                "hostname": socket.gethostname(),
                "status": "streaming" if self.is_streaming else "online",
                "screenResolution": f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}",
                "timestamp": int(time.time() * 1000)
            }

            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    ping_url,
                    data=data,
                    headers={"Content-Type": "application/json", "User-Agent": "TeamScreenWorker/1.0"},
                    method="POST"
                )
                start_t = time.time()
                with urllib.request.urlopen(req, timeout=4) as response:
                    res_body = json.loads(response.read().decode("utf-8"))
                    latency = int((time.time() - start_t) * 1000)

                    # Update UI in main thread
                    self.after(0, self.update_heartbeat_ui, latency, res_body)
            except Exception as e:
                self.after(0, self.update_error_ui, str(e))

            time.sleep(2.0)

    def update_heartbeat_ui(self, latency, res_body):
        self.last_ping_ms = latency
        self.ping_badge.configure(text=f"{latency} ms")
        self.status_dot.configure(text_color="#10B981")
        self.status_text.configure(text="CONNECTED TO RELAY")

        # Check if Admin requested live observation
        requested = res_body.get("streamRequested", False)
        instruction = res_body.get("guidanceMessage", "")

        if instruction:
            self.guidance_box.configure(
                text=f"📌 {instruction}",
                text_color="#F8FAFC"
            )

        if requested and not self.is_streaming:
            self.is_streaming = True
            self.status_dot.configure(text_color="#3B82F6")
            self.status_text.configure(text="LIVE STREAMING TO CEO")
            self.alert_frame.pack(fill="x", padx=16, pady=(0, 10))
        elif not requested and self.is_streaming:
            self.is_streaming = False
            self.status_dot.configure(text_color="#10B981")
            self.status_text.configure(text="CONNECTED TO RELAY")
            self.alert_frame.pack_forget()

    def update_error_ui(self, err_msg):
        self.status_dot.configure(text_color="#F59E0B")
        self.status_text.configure(text="RECONNECTING...")
        self.ping_badge.configure(text="err")

    def stream_loop(self):
        """Ultra-fast, low-CPU screen capture engine using mss and adaptive JPEG encoding"""
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]

            while self.is_connected and not self.stop_event.is_set():
                if not self.is_streaming:
                    time.sleep(0.2)
                    continue

                try:
                    t0 = time.time()
                    # Capture screen buffer
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                    # Optimize resolution for low bandwidth and <1% CPU
                    target_w = 1280
                    target_h = int(img.height * (1280 / img.width))
                    img = img.resize((target_w, target_h), Image.Resampling.BILINEAR)

                    # Compress to JPEG
                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=68, optimize=True)
                    frame_bytes = buffer.getvalue()
                    b64_frame = base64.b64encode(frame_bytes).decode("ascii")

                    # Transmit to Vercel Relay
                    relay_url = self.config.get("relay_url", DEFAULT_RELAY_URL).rstrip("/")
                    frame_url = f"{relay_url}/api/stream/frame"

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
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        pass

                    self.frames_sent += 1
                    elapsed = time.time() - t0
                    # Target ~20-25 FPS with low CPU
                    delay = max(0.04, 0.05 - elapsed)
                    time.sleep(delay)

                except Exception as e:
                    time.sleep(0.5)

    def on_closing(self):
        self.stop_event.set()
        self.destroy()

if __name__ == "__main__":
    app = WorkerNodeApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
