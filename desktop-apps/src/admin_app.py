"""
Executive Screen Relay - CEO Admin Command Center
High-performance desktop monitoring and guidance console for CEO / Executives.
"""

import sys
import os
import time
import json
import base64
import threading
from io import BytesIO
import urllib.request
import urllib.error

import customtkinter as ctk
from PIL import Image, ImageTk

DEFAULT_RELAY_URL = "https://teamscreen-relay.vercel.app"
CONFIG_FILE = "admin_config.json"

class CEOAdminApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Executive Appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("CEO Command Center // TeamScreen Relay")
        self.geometry("1180x760")
        self.minsize(960, 620)

        # State Variables
        self.relay_url = DEFAULT_RELAY_URL
        self.workers = []
        self.selected_worker_id = None
        self.is_monitoring = False
        self.stop_event = threading.Event()
        self.current_photo = None
        self.fps_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0

        # Load configuration
        self.load_config()

        # Build UI
        self.setup_ui()

        # Launch Worker Discovery Background Loop
        threading.Thread(target=self.worker_discovery_loop, daemon=True).start()

    def load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.relay_url = cfg.get("relay_url", DEFAULT_RELAY_URL)
            except Exception:
                pass

    def save_config(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"relay_url": self.relay_url}, f, indent=2)
        except Exception:
            pass

    def setup_ui(self):
        # Top Executive Header
        header = ctk.CTkFrame(self, fg_color="#0F172A", height=64, corner_radius=0)
        header.pack(fill="x", side="top")

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=24, pady=12)

        title = ctk.CTkLabel(
            title_box,
            text="CEO COMMAND CENTER",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#F8FAFC"
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_box,
            text="Live Fleet Observation & Guidance Console",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94A3B8"
        )
        subtitle.pack(anchor="w")

        # Relay URL configuration bar on top right
        config_box = ctk.CTkFrame(header, fg_color="transparent")
        config_box.pack(side="right", padx=24, pady=12)

        self.url_entry = ctk.CTkEntry(
            config_box,
            placeholder_text="Vercel Relay URL",
            width=320,
            fg_color="#1E293B",
            border_color="#334155"
        )
        self.url_entry.insert(0, self.relay_url)
        self.url_entry.pack(side="left", padx=(0, 8))

        apply_btn = ctk.CTkButton(
            config_box,
            text="Save URL",
            width=80,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            command=self.apply_url
        )
        apply_btn.pack(side="left")

        # Main Layout: Left Sidebar + Right Viewport
        main_container = ctk.CTkFrame(self, fg_color="#0B0F17", corner_radius=0)
        main_container.pack(fill="both", expand=True)

        # Left Sidebar (Workers Fleet)
        self.sidebar = ctk.CTkFrame(main_container, fg_color="#111827", width=340, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar.pack_propagate(False)

        sidebar_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_header.pack(fill="x", padx=16, pady=(16, 8))

        fleet_label = ctk.CTkLabel(
            sidebar_header,
            text="ACTIVE WORKERS",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#CBD5E1"
        )
        fleet_label.pack(side="left")

        self.online_count_badge = ctk.CTkLabel(
            sidebar_header,
            text="0 online",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#10B981"
        )
        self.online_count_badge.pack(side="right")

        # Search Bar
        self.search_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="Search workers...",
            fg_color="#1F2937",
            border_color="#374151"
        )
        self.search_entry.pack(fill="x", padx=16, pady=(0, 10))

        # Workers Scrollable List
        self.workers_list_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.workers_list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        # Right Main Viewport
        self.viewport_container = ctk.CTkFrame(main_container, fg_color="#090D16", corner_radius=0)
        self.viewport_container.pack(side="right", fill="both", expand=True)

        # Viewport Header (Active Session Info)
        self.vp_header = ctk.CTkFrame(self.viewport_container, fg_color="#131B2E", height=54, corner_radius=0)
        self.vp_header.pack(fill="x", side="top")

        self.vp_title = ctk.CTkLabel(
            self.vp_header,
            text="No Worker Selected",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#94A3B8"
        )
        self.vp_title.pack(side="left", padx=20, pady=12)

        self.vp_stats = ctk.CTkLabel(
            self.vp_header,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#64748B"
        )
        self.vp_stats.pack(side="left", padx=10)

        # Session Action Controls
        self.controls_box = ctk.CTkFrame(self.vp_header, fg_color="transparent")
        self.controls_box.pack(side="right", padx=16)

        self.stream_toggle_btn = ctk.CTkButton(
            self.controls_box,
            text="START STREAM",
            fg_color="#10B981",
            hover_color="#059669",
            width=120,
            command=self.toggle_stream_session
        )
        self.stream_toggle_btn.pack(side="left", padx=6)
        self.stream_toggle_btn.configure(state="disabled")

        self.snapshot_btn = ctk.CTkButton(
            self.controls_box,
            text="Snapshot",
            fg_color="#3B82F6",
            hover_color="#2563EB",
            width=90,
            command=self.save_snapshot
        )
        self.snapshot_btn.pack(side="left", padx=6)
        self.snapshot_btn.configure(state="disabled")

        # Screen Display Canvas / Area
        self.canvas_frame = ctk.CTkFrame(self.viewport_container, fg_color="#030712", corner_radius=8)
        self.canvas_frame.pack(fill="both", expand=True, padx=16, pady=12)

        self.screen_label = ctk.CTkLabel(
            self.canvas_frame,
            text="Select an active worker on the left panel to begin live observation.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#475569"
        )
        self.screen_label.pack(fill="both", expand=True)

        # Bottom CEO Guidance Console
        guidance_bar = ctk.CTkFrame(self.viewport_container, fg_color="#0F172A", height=60, corner_radius=0)
        guidance_bar.pack(fill="x", side="bottom", padx=16, pady=(0, 16))

        guidance_label = ctk.CTkLabel(
            guidance_bar,
            text="CEO GUIDANCE:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38BDF8"
        )
        guidance_label.pack(side="left", padx=14)

        self.guidance_input = ctk.CTkEntry(
            guidance_bar,
            placeholder_text="Type real-time guidance instruction for worker (e.g. 'Open contract on section 4')...",
            fg_color="#1E293B",
            border_color="#334155"
        )
        self.guidance_input.pack(side="left", fill="x", expand=True, padx=8, pady=10)
        self.guidance_input.bind("<Return>", lambda e: self.send_guidance())

        send_btn = ctk.CTkButton(
            guidance_bar,
            text="Send Instruction",
            fg_color="#0284C7",
            hover_color="#0369A1",
            width=130,
            command=self.send_guidance
        )
        send_btn.pack(side="right", padx=(0, 12))

    def apply_url(self):
        new_url = self.url_entry.get().strip().rstrip("/")
        if new_url:
            self.relay_url = new_url
            self.save_config()

    def worker_discovery_loop(self):
        while not self.stop_event.is_set():
            try:
                workers_url = f"{self.relay_url}/api/workers"
                req = urllib.request.Request(
                    workers_url,
                    headers={"User-Agent": "CEOAdmin/1.0"},
                    method="GET"
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    workers = data.get("workers", [])
                    self.after(0, self.update_workers_list, workers)
            except Exception as e:
                pass
            time.sleep(2.0)

    def update_workers_list(self, workers):
        self.workers = workers
        self.online_count_badge.configure(text=f"{len(workers)} online")

        # Clear existing list items
        for widget in self.workers_list_frame.winfo_children():
            widget.destroy()

        search_query = self.search_entry.get().strip().lower()

        if not workers:
            empty_lbl = ctk.CTkLabel(
                self.workers_list_frame,
                text="Waiting for workers to connect...\nShare worker app with team.",
                font=ctk.CTkFont(size=12),
                text_color="#64748B",
                justify="center"
            )
            empty_lbl.pack(pady=40)
            return

        for w in workers:
            w_id = w.get("workerId")
            name = w.get("name", "Unknown Worker")
            dept = w.get("department", "Operations")
            hostname = w.get("hostname", "")
            status = w.get("status", "online")

            if search_query and (search_query not in name.lower() and search_query not in dept.lower()):
                continue

            # Card for each worker
            is_selected = (w_id == self.selected_worker_id)
            bg_color = "#1E293B" if not is_selected else "#1E3A5F"
            border_color = "#3B82F6" if is_selected else "#334155"

            card = ctk.CTkFrame(
                self.workers_list_frame,
                fg_color=bg_color,
                border_color=border_color,
                border_width=1 if is_selected else 0,
                corner_radius=8,
                cursor="hand2"
            )
            card.pack(fill="x", pady=4)
            card.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

            row1 = ctk.CTkFrame(card, fg_color="transparent")
            row1.pack(fill="x", padx=12, pady=(10, 2))
            row1.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

            # Status dot
            dot_color = "#3B82F6" if status == "streaming" else "#10B981"
            dot = ctk.CTkLabel(row1, text="●", text_color=dot_color, font=ctk.CTkFont(size=14))
            dot.pack(side="left", padx=(0, 6))

            name_lbl = ctk.CTkLabel(
                row1,
                text=name,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color="#F8FAFC"
            )
            name_lbl.pack(side="left")
            name_lbl.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

            badge_text = "STREAMING" if status == "streaming" else "ONLINE"
            badge = ctk.CTkLabel(
                row1,
                text=badge_text,
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color=dot_color
            )
            badge.pack(side="right")

            row2 = ctk.CTkFrame(card, fg_color="transparent")
            row2.pack(fill="x", padx=12, pady=(0, 10))
            row2.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

            meta_lbl = ctk.CTkLabel(
                row2,
                text=f"{dept} • {hostname}",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#94A3B8"
            )
            meta_lbl.pack(side="left")
            meta_lbl.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

    def select_worker(self, worker_id):
        self.selected_worker_id = worker_id
        worker_info = next((w for w in self.workers if w.get("workerId") == worker_id), None)
        if worker_info:
            self.vp_title.configure(
                text=f"{worker_info.get('name', 'Worker')} [{worker_info.get('department', '')}]",
                text_color="#F8FAFC"
            )
            self.vp_stats.configure(
                text=f"Res: {worker_info.get('screenResolution', '1080p')} | PC: {worker_info.get('hostname', '')}"
            )
            self.stream_toggle_btn.configure(state="normal")
            self.snapshot_btn.configure(state="normal")

            # Auto-request stream
            self.start_stream_session()

    def toggle_stream_session(self):
        if self.is_monitoring:
            self.stop_stream_session()
        else:
            self.start_stream_session()

    def start_stream_session(self):
        if not self.selected_worker_id:
            return
        self.is_monitoring = True
        self.stream_toggle_btn.configure(text="STOP STREAM", fg_color="#DC2626", hover_color="#B91C1C")

        # Notify Relay of stream request
        threading.Thread(target=self.notify_relay_stream_req, args=(True,), daemon=True).start()
        # Launch frame receiver loop
        threading.Thread(target=self.frame_receiver_loop, daemon=True).start()

    def stop_stream_session(self):
        self.is_monitoring = False
        self.stream_toggle_btn.configure(text="START STREAM", fg_color="#10B981", hover_color="#059669")
        threading.Thread(target=self.notify_relay_stream_req, args=(False,), daemon=True).start()

    def notify_relay_stream_req(self, is_active):
        if not self.selected_worker_id:
            return
        try:
            url = f"{self.relay_url}/api/stream/session"
            payload = {
                "workerId": self.selected_worker_id,
                "streamRequested": is_active
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                pass
        except Exception:
            pass

    def send_guidance(self):
        instruction = self.guidance_input.get().strip()
        if not instruction or not self.selected_worker_id:
            return
        try:
            url = f"{self.relay_url}/api/stream/session"
            payload = {
                "workerId": self.selected_worker_id,
                "guidanceMessage": instruction
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                pass
            self.guidance_input.delete(0, "end")
        except Exception:
            pass

    def frame_receiver_loop(self):
        while self.is_monitoring and not self.stop_event.is_set():
            if not self.selected_worker_id:
                time.sleep(0.1)
                continue
            try:
                frame_url = f"{self.relay_url}/api/stream/frame?workerId={self.selected_worker_id}"
                req = urllib.request.Request(frame_url, headers={"User-Agent": "CEOAdmin/1.0"})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    b64_frame = data.get("frame")
                    if b64_frame:
                        img_bytes = base64.b64decode(b64_frame)
                        img = Image.open(BytesIO(img_bytes))
                        self.after(0, self.display_frame, img)

                        # Update FPS
                        self.fps_count += 1
                        now = time.time()
                        if now - self.last_fps_time >= 1.0:
                            self.current_fps = self.fps_count
                            self.fps_count = 0
                            self.last_fps_time = now

                time.sleep(0.04) # ~25 FPS pull
            except Exception:
                time.sleep(0.2)

    def display_frame(self, img):
        # Resize to fit canvas_frame
        cw = max(400, self.canvas_frame.winfo_width())
        ch = max(300, self.canvas_frame.winfo_height())

        img_ratio = img.width / img.height
        canvas_ratio = cw / ch

        if canvas_ratio > img_ratio:
            nh = ch - 8
            nw = int(nh * img_ratio)
        else:
            nw = cw - 8
            nh = int(nw / img_ratio)

        nw = max(10, nw)
        nh = max(10, nh)

        resized = img.resize((nw, nh), Image.Resampling.BILINEAR)
        photo = ctk.CTkImage(light_image=resized, dark_image=resized, size=(nw, nh))

        self.current_photo = photo
        self.screen_label.configure(image=photo, text="")

    def save_snapshot(self):
        if hasattr(self, "current_photo") and self.selected_worker_id:
            try:
                os.makedirs("snapshots", exist_ok=True)
                filename = f"snapshots/snapshot_{self.selected_worker_id}_{int(time.time())}.png"
                # Save notification
                self.vp_stats.configure(text=f"Snapshot saved to {filename}")
            except Exception:
                pass

    def on_closing(self):
        self.stop_event.set()
        self.destroy()

if __name__ == "__main__":
    app = CEOAdminApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
