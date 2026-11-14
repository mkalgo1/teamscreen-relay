"""
Executive Screen Relay - CEO Admin Command Center
Enhanced with:
1. Pixel-Perfect DPI-Aware Remote Mouse Clicking
2. Remote File Explorer & Direct Invoice/File Transfer Manager
3. Live Session Video Recording (MP4)
4. Masked Password & Keystroke Injection
"""

import sys
import os
import time
import json
import base64
import tempfile
import threading
import tkinter as tk
from io import BytesIO
import urllib.request
import urllib.error
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk
import cv2
import numpy as np

DEFAULT_RELAY_URL = "https://teamscreen-relay-mktradez.vercel.app"
CONFIG_FILE = "admin_config.json"

class CEOAdminApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Executive Appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("CEO Command Center // TeamScreen Relay")
        self.geometry("1300x840")
        self.minsize(1040, 700)

        # State Variables
        self.relay_url = DEFAULT_RELAY_URL
        self.workers = []
        self.selected_worker_id = None
        self.is_monitoring = False
        self.stop_event = threading.Event()
        self.current_photo = None
        self.latest_cv_frame = None
        self.fps_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0

        # Video Recording State
        self.is_recording = False
        self.record_start_time = 0
        self.video_writer = None
        self.temp_record_path = None
        self.record_frame_size = None

        # Precision Remote Input State
        self.remote_input_enabled = False
        self.image_display_rect = (0, 0, 800, 500) # ox, oy, nw, nh

        # Remote File Manager State
        self.active_view = "stream" # "stream" or "files"
        self.worker_current_path = ""
        self.worker_files = []
        self.last_file_sync_time = 0

        # Load config
        self.load_config()

        # Build UI
        self.setup_ui()

        # Launch Background Loops
        threading.Thread(target=self.worker_discovery_loop, daemon=True).start()
        threading.Thread(target=self.file_result_poll_loop, daemon=True).start()

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
        title_box.pack(side="left", padx=20, pady=12)

        title = ctk.CTkLabel(
            title_box,
            text="CEO COMMAND CENTER",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#F8FAFC"
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_box,
            text="Executive Observation, Precision Input & File Transfer Hub",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94A3B8"
        )
        subtitle.pack(anchor="w")

        # Relay URL configuration bar on top right
        config_box = ctk.CTkFrame(header, fg_color="transparent")
        config_box.pack(side="right", padx=20, pady=12)

        self.url_entry = ctk.CTkEntry(
            config_box,
            placeholder_text="Vercel Relay URL",
            width=280,
            fg_color="#1E293B",
            border_color="#334155"
        )
        self.url_entry.insert(0, self.relay_url)
        self.url_entry.pack(side="left", padx=(0, 8))

        apply_btn = ctk.CTkButton(
            config_box,
            text="Save URL",
            width=76,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            command=self.apply_url
        )
        apply_btn.pack(side="left")

        # Main Layout: Left Sidebar + Right Viewport
        main_container = ctk.CTkFrame(self, fg_color="#0B0F17", corner_radius=0)
        main_container.pack(fill="both", expand=True)

        # Left Sidebar (Workers Fleet)
        self.sidebar = ctk.CTkFrame(main_container, fg_color="#111827", width=320, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar.pack_propagate(False)

        sidebar_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_header.pack(fill="x", padx=16, pady=(16, 8))

        fleet_label = ctk.CTkLabel(
            sidebar_header,
            text="ACTIVE FLEET",
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

        # Right Main Viewport Area
        self.viewport_container = ctk.CTkFrame(main_container, fg_color="#090D16", corner_radius=0)
        self.viewport_container.pack(side="right", fill="both", expand=True)

        # Viewport Header
        self.vp_header = ctk.CTkFrame(self.viewport_container, fg_color="#131B2E", height=58, corner_radius=0)
        self.vp_header.pack(fill="x", side="top")

        self.vp_title = ctk.CTkLabel(
            self.vp_header,
            text="No Worker Selected",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#94A3B8"
        )
        self.vp_title.pack(side="left", padx=16, pady=12)

        self.vp_stats = ctk.CTkLabel(
            self.vp_header,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#64748B"
        )
        self.vp_stats.pack(side="left", padx=6)

        # Controls Container
        self.controls_box = ctk.CTkFrame(self.vp_header, fg_color="transparent")
        self.controls_box.pack(side="right", padx=14)

        # Toggle File Manager View Button
        self.files_toggle_btn = ctk.CTkButton(
            self.controls_box,
            text="📁 Remote Files",
            fg_color="#1E293B",
            hover_color="#334155",
            width=120,
            command=self.toggle_files_view
        )
        self.files_toggle_btn.pack(side="left", padx=3)
        self.files_toggle_btn.configure(state="disabled")

        # Remote Input Toggle Button
        self.input_toggle_btn = ctk.CTkButton(
            self.controls_box,
            text="🖱️ Remote Input: OFF",
            fg_color="#334155",
            hover_color="#475569",
            width=135,
            command=self.toggle_remote_input
        )
        self.input_toggle_btn.pack(side="left", padx=3)
        self.input_toggle_btn.configure(state="disabled")

        # Record Session Button
        self.record_btn = ctk.CTkButton(
            self.controls_box,
            text="⏺️ Record MP4",
            fg_color="#7C2D12",
            hover_color="#991B1B",
            width=115,
            command=self.toggle_recording
        )
        self.record_btn.pack(side="left", padx=3)
        self.record_btn.configure(state="disabled")

        # Stream Toggle Button
        self.stream_toggle_btn = ctk.CTkButton(
            self.controls_box,
            text="START STREAM",
            fg_color="#10B981",
            hover_color="#059669",
            width=105,
            command=self.toggle_stream_session
        )
        self.stream_toggle_btn.pack(side="left", padx=3)
        self.stream_toggle_btn.configure(state="disabled")

        # Central Switchable Container: Stream View vs File Explorer View
        self.center_area = ctk.CTkFrame(self.viewport_container, fg_color="transparent", corner_radius=0)
        self.center_area.pack(fill="both", expand=True, padx=12, pady=6)

        # --- STREAM VIEW WIDGETS ---
        self.stream_view_frame = ctk.CTkFrame(self.center_area, fg_color="transparent")
        self.stream_view_frame.pack(fill="both", expand=True)

        self.canvas_frame = ctk.CTkFrame(self.stream_view_frame, fg_color="#030712", corner_radius=8)
        self.canvas_frame.pack(fill="both", expand=True)

        # Precision Native Canvas for pixel-perfect click coordinate capture
        self.screen_canvas = tk.Canvas(
            self.canvas_frame,
            bg="#030712",
            highlightthickness=0,
            cursor=""
        )
        self.screen_canvas.pack(fill="both", expand=True)
        self.screen_canvas.bind("<Button-1>", self.on_canvas_click)

        # Initial placeholder text
        self.canvas_placeholder = self.screen_canvas.create_text(
            400, 250,
            text="Select an active worker on the left to begin live observation.",
            fill="#475569",
            font=("Segoe UI", 13)
        )

        # --- REMOTE FILE EXPLORER VIEW WIDGETS ---
        self.file_view_frame = ctk.CTkFrame(self.center_area, fg_color="#0F172A", corner_radius=8)
        # Not packed initially

        # File Manager Top Navigation Bar
        fm_navbar = ctk.CTkFrame(self.file_view_frame, fg_color="#1E293B", height=46, corner_radius=6)
        fm_navbar.pack(fill="x", padx=12, pady=(12, 6))

        up_btn = ctk.CTkButton(fm_navbar, text="⬆️ Up", width=65, fg_color="#334155", hover_color="#475569", command=self.navigate_up_folder)
        up_btn.pack(side="left", padx=6)

        refresh_fm_btn = ctk.CTkButton(fm_navbar, text="🔄 Refresh", width=80, fg_color="#334155", hover_color="#475569", command=self.refresh_current_folder)
        refresh_fm_btn.pack(side="left", padx=4)

        # Path display entry
        self.fm_path_entry = ctk.CTkEntry(fm_navbar, fg_color="#0F172A", border_color="#334155")
        self.fm_path_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.fm_path_entry.bind("<Return>", lambda e: self.request_browse_folder(self.fm_path_entry.get().strip()))

        # Shortcuts: Desktop, Documents, Downloads
        desktop_btn = ctk.CTkButton(fm_navbar, text="Desktop", width=70, fg_color="#2563EB", hover_color="#1D4ED8", command=lambda: self.request_browse_folder("DEFAULT"))
        desktop_btn.pack(side="left", padx=4)

        # Upload / Send Invoice button
        send_file_btn = ctk.CTkButton(
            fm_navbar,
            text="📤 Send File / Invoice",
            fg_color="#10B981",
            hover_color="#059669",
            width=150,
            command=self.send_file_to_worker
        )
        send_file_btn.pack(side="left", padx=(4, 6))

        # Files list scrollable table
        self.files_scroll = ctk.CTkScrollableFrame(self.file_view_frame, fg_color="#090D16")
        self.files_scroll.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        # --- BOTTOM ACTION BARS ---
        # Assisted Credential & Remote Keystroke Console
        input_bar = ctk.CTkFrame(self.viewport_container, fg_color="#0F172A", height=48, corner_radius=6)
        input_bar.pack(fill="x", side="bottom", padx=12, pady=(0, 6))

        input_title = ctk.CTkLabel(
            input_bar,
            text="REMOTE KEYSTROKES:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#A855F7"
        )
        input_title.pack(side="left", padx=(12, 6))

        self.mask_var = ctk.BooleanVar(value=True)
        self.mask_checkbox = ctk.CTkCheckBox(
            input_bar,
            text="Mask Password",
            variable=self.mask_var,
            command=self.toggle_password_mask,
            checkbox_width=18,
            checkbox_height=18,
            font=ctk.CTkFont(size=11)
        )
        self.mask_checkbox.pack(side="left", padx=(0, 8))

        self.key_input = ctk.CTkEntry(
            input_bar,
            placeholder_text="Enter password or text to type into worker's focused window...",
            show="*",
            fg_color="#1E293B",
            border_color="#334155"
        )
        self.key_input.pack(side="left", fill="x", expand=True, padx=6, pady=7)
        self.key_input.bind("<Return>", lambda e: self.send_remote_text())

        type_btn = ctk.CTkButton(
            input_bar,
            text="Type into PC",
            fg_color="#9333EA",
            hover_color="#7E22CE",
            width=110,
            command=self.send_remote_text
        )
        type_btn.pack(side="left", padx=4)

        enter_btn = ctk.CTkButton(input_bar, text="[Enter]", width=55, fg_color="#374151", hover_color="#4B5563", command=lambda: self.send_special_key("enter"))
        enter_btn.pack(side="left", padx=2)
        tab_btn = ctk.CTkButton(input_bar, text="[Tab]", width=50, fg_color="#374151", hover_color="#4B5563", command=lambda: self.send_special_key("tab"))
        tab_btn.pack(side="left", padx=2)
        esc_btn = ctk.CTkButton(input_bar, text="[Esc]", width=50, fg_color="#374151", hover_color="#4B5563", command=lambda: self.send_special_key("esc"))
        esc_btn.pack(side="left", padx=(2, 10))

        # Bottom CEO Guidance Console
        guidance_bar = ctk.CTkFrame(self.viewport_container, fg_color="#0F172A", height=44, corner_radius=6)
        guidance_bar.pack(fill="x", side="bottom", padx=12, pady=(0, 10))

        guidance_label = ctk.CTkLabel(
            guidance_bar,
            text="CEO GUIDANCE:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#38BDF8"
        )
        guidance_label.pack(side="left", padx=(12, 6))

        self.guidance_input = ctk.CTkEntry(
            guidance_bar,
            placeholder_text="Type guidance note for worker (e.g. 'Opening the database now')...",
            fg_color="#1E293B",
            border_color="#334155"
        )
        self.guidance_input.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        self.guidance_input.bind("<Return>", lambda e: self.send_guidance())

        send_btn = ctk.CTkButton(
            guidance_bar,
            text="Send Guidance",
            fg_color="#0284C7",
            hover_color="#0369A1",
            width=110,
            command=self.send_guidance
        )
        send_btn.pack(side="right", padx=(0, 10))

    def toggle_files_view(self):
        if self.active_view == "stream":
            self.active_view = "files"
            self.stream_view_frame.pack_forget()
            self.file_view_frame.pack(fill="both", expand=True)
            self.files_toggle_btn.configure(text="📺 Live Screen", fg_color="#3B82F6", hover_color="#2563EB")
            # Request initial folder
            if not self.worker_current_path:
                self.request_browse_folder("DEFAULT")
        else:
            self.active_view = "stream"
            self.file_view_frame.pack_forget()
            self.stream_view_frame.pack(fill="both", expand=True)
            self.files_toggle_btn.configure(text="📁 Remote Files", fg_color="#1E293B", hover_color="#334155")

    def toggle_password_mask(self):
        if self.mask_var.get():
            self.key_input.configure(show="*")
        else:
            self.key_input.configure(show="")

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
                    headers={"User-Agent": "CEOAdmin/2.1"},
                    method="GET"
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    workers = data.get("workers", [])
                    self.after(0, self.update_workers_list, workers)
            except Exception:
                pass
            time.sleep(2.0)

    def update_workers_list(self, workers):
        self.workers = workers
        self.online_count_badge.configure(text=f"{len(workers)} online")

        for widget in self.workers_list_frame.winfo_children():
            widget.destroy()

        search_query = self.search_entry.get().strip().lower()

        if not workers:
            empty_lbl = ctk.CTkLabel(
                self.workers_list_frame,
                text="Waiting for workers to connect...\nWorkers run WorkerRelay.exe in tray.",
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
            self.record_btn.configure(state="normal")
            self.input_toggle_btn.configure(state="normal")
            self.files_toggle_btn.configure(state="normal")

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
        threading.Thread(target=self.notify_relay_stream_req, args=(True,), daemon=True).start()
        threading.Thread(target=self.frame_receiver_loop, daemon=True).start()

    def stop_stream_session(self):
        if self.is_recording:
            self.stop_recording_and_save()
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
            with urllib.request.urlopen(req, timeout=3):
                pass
        except Exception:
            pass

    # --- Feature 1: Video Recording Engine (MP4) ---
    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording_and_save()

    def start_recording(self):
        if not self.is_monitoring or not self.selected_worker_id:
            messagebox.showinfo("Recording", "Please initiate a live stream before starting recording.")
            return

        fd, temp_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        self.temp_record_path = temp_path
        self.record_frame_size = None
        self.video_writer = None
        self.is_recording = True
        self.record_start_time = time.time()

        self.record_btn.configure(
            text="⏹️ Stop & Save",
            fg_color="#DC2626",
            hover_color="#B91C1C"
        )

        threading.Thread(target=self.recording_timer_loop, daemon=True).start()

    def recording_timer_loop(self):
        while self.is_recording:
            elapsed = int(time.time() - self.record_start_time)
            mins = elapsed // 60
            secs = elapsed % 60
            self.after(0, lambda: self.vp_stats.configure(text=f"● REC [{mins:02d}:{secs:02d}]"))
            time.sleep(1.0)

    def write_frame_to_video(self, cv_frame):
        if not self.is_recording:
            return
        h, w = cv_frame.shape[:2]
        if self.video_writer is None:
            self.record_frame_size = (w, h)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.video_writer = cv2.VideoWriter(self.temp_record_path, fourcc, 20.0, (w, h))

        if (w, h) == self.record_frame_size:
            self.video_writer.write(cv_frame)

    def stop_recording_and_save(self):
        self.is_recording = False
        self.record_btn.configure(
            text="⏺️ Record MP4",
            fg_color="#7C2D12",
            hover_color="#991B1B"
        )

        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

        if self.temp_record_path and os.path.exists(self.temp_record_path):
            save_path = filedialog.asksaveasfilename(
                title="Save Worker Screen Video Recording",
                defaultextension=".mp4",
                initialfile=f"session_{self.selected_worker_id}_{int(time.time())}.mp4",
                filetypes=[("MP4 Video File", "*.mp4"), ("All Files", "*.*")]
            )

            if save_path:
                try:
                    import shutil
                    shutil.copy2(self.temp_record_path, save_path)
                    messagebox.showinfo("Recording Saved", f"Session video successfully saved to:\n{save_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Could not save video: {e}")

            try:
                os.remove(self.temp_record_path)
            except Exception:
                pass

        self.vp_stats.configure(text="")

    # --- Feature 2: Precision DPI-Aware Remote Mouse Clicking ---
    def toggle_remote_input(self):
        self.remote_input_enabled = not self.remote_input_enabled
        if self.remote_input_enabled:
            self.input_toggle_btn.configure(
                text="🖱️ Remote Input: ON",
                fg_color="#9333EA",
                hover_color="#7E22CE"
            )
            self.screen_canvas.configure(cursor="crosshair")
        else:
            self.input_toggle_btn.configure(
                text="🖱️ Remote Input: OFF",
                fg_color="#334155",
                hover_color="#475569"
            )
            self.screen_canvas.configure(cursor="")

    def on_canvas_click(self, event):
        if not self.remote_input_enabled or not self.selected_worker_id:
            return

        ox, oy, dw, dh = self.image_display_rect
        cx = event.x - ox
        cy = event.y - oy

        # Verify click falls strictly inside the rendered screen image bounds
        if 0 <= cx <= dw and 0 <= cy <= dh and dw > 0 and dh > 0:
            x_ratio = cx / float(dw)
            y_ratio = cy / float(dh)

            # Draw visual click ripple indicator on canvas
            self.screen_canvas.create_oval(
                event.x - 6, event.y - 6, event.x + 6, event.y + 6,
                outline="#A855F7", width=2, tags="click_ripple"
            )
            self.after(300, lambda: self.screen_canvas.delete("click_ripple"))

            self.dispatch_remote_input("click", xRatio=x_ratio, yRatio=y_ratio)

    def send_remote_text(self):
        text = self.key_input.get()
        if not text or not self.selected_worker_id:
            return
        self.dispatch_remote_input("type", text=text)
        self.key_input.delete(0, "end")

    def send_special_key(self, key_name):
        if not self.selected_worker_id:
            return
        self.dispatch_remote_input("key", key=key_name)

    def dispatch_remote_input(self, event_type, xRatio=None, yRatio=None, text=None, key=None):
        if not self.selected_worker_id:
            return
        payload = {
            "workerId": self.selected_worker_id,
            "eventType": event_type
        }
        if xRatio is not None: payload["xRatio"] = xRatio
        if yRatio is not None: payload["yRatio"] = yRatio
        if text is not None: payload["text"] = text
        if key is not None: payload["key"] = key

        threading.Thread(target=self._send_input_http, args=(payload,), daemon=True).start()

    def _send_input_http(self, payload):
        try:
            url = f"{self.relay_url}/api/stream/input"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=2):
                pass
        except Exception:
            pass

    # --- Feature 3: Remote File Explorer & Direct File Transfer ---
    def request_browse_folder(self, folder_path):
        if not self.selected_worker_id:
            return
        payload = {
            "workerId": self.selected_worker_id,
            "action": "list",
            "path": folder_path
        }
        threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

    def refresh_current_folder(self):
        curr = self.fm_path_entry.get().strip() or self.worker_current_path or "DEFAULT"
        self.request_browse_folder(curr)

    def navigate_up_folder(self):
        curr = self.worker_current_path
        if curr:
            parent = os.path.dirname(curr)
            if parent and parent != curr:
                self.request_browse_folder(parent)

    def send_file_to_worker(self):
        if not self.selected_worker_id:
            messagebox.showinfo("Select Worker", "Please select an active worker first.")
            return

        file_path = filedialog.askopenfilename(
            title="Select File / Invoice to Send to Worker",
            filetypes=[
                ("Invoices & Documents", "*.pdf;*.docx;*.xlsx;*.txt;*.png;*.jpg"),
                ("All Files", "*.*")
            ]
        )

        if not file_path:
            return

        file_name = os.path.basename(file_path)
        target_dir = self.worker_current_path or "DEFAULT"

        try:
            with open(file_path, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("ascii")

            payload = {
                "workerId": self.selected_worker_id,
                "action": "upload",
                "path": target_dir,
                "fileName": file_name,
                "fileData": b64_content
            }
            threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()
            messagebox.showinfo("Sending File", f"File '{file_name}' is being transmitted to worker's folder:\n{target_dir}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {e}")

    def _post_file_command(self, payload):
        try:
            url = f"{self.relay_url}/api/files/command"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=4):
                pass
        except Exception:
            pass

    def file_result_poll_loop(self):
        """Polls for folder listings and upload confirmations from worker"""
        while not self.stop_event.is_set():
            if self.active_view == "files" and self.selected_worker_id:
                try:
                    url = f"{self.relay_url}/api/files/result?workerId={self.selected_worker_id}"
                    req = urllib.request.Request(url, headers={"User-Agent": "CEOAdmin/2.1"})
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        if data.get("ok"):
                            res = data.get("result", {})
                            cur_path = res.get("currentPath", "")
                            items = res.get("items", [])
                            ts = res.get("timestamp", 0)

                            if ts > self.last_file_sync_time:
                                self.last_file_sync_time = ts
                                self.after(0, self.update_files_ui, cur_path, items)
                except Exception:
                    pass
            time.sleep(1.2)

    def update_files_ui(self, current_path, items):
        self.worker_current_path = current_path
        self.fm_path_entry.delete(0, "end")
        self.fm_path_entry.insert(0, current_path)

        for widget in self.files_scroll.winfo_children():
            widget.destroy()

        if not items:
            empty_lbl = ctk.CTkLabel(
                self.files_scroll,
                text="Directory is empty or awaiting worker response.",
                font=ctk.CTkFont(size=12),
                text_color="#64748B"
            )
            empty_lbl.pack(pady=40)
            return

        for item in items:
            name = item.get("name")
            is_dir = item.get("isDir", False)
            size_bytes = item.get("size", 0)

            size_str = f"{size_bytes / 1024:.1f} KB" if size_bytes > 0 else "<dir>"
            icon = "📁" if is_dir else "📄"

            row = ctk.CTkFrame(self.files_scroll, fg_color="#1E293B", corner_radius=6)
            row.pack(fill="x", pady=2, padx=4)

            btn_text = f"{icon}  {name}"
            lbl = ctk.CTkLabel(
                row,
                text=btn_text,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold" if is_dir else "normal"),
                text_color="#F8FAFC" if is_dir else "#CBD5E1",
                cursor="hand2" if is_dir else ""
            )
            lbl.pack(side="left", padx=10, pady=8)

            if is_dir:
                # Double click to enter folder
                sub_path = os.path.join(current_path, name)
                lbl.bind("<Double-Button-1>", lambda e, p=sub_path: self.request_browse_folder(p))
                row.bind("<Double-Button-1>", lambda e, p=sub_path: self.request_browse_folder(p))

            size_lbl = ctk.CTkLabel(row, text=size_str, font=ctk.CTkFont(size=11), text_color="#64748B")
            size_lbl.pack(side="right", padx=12)

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
            with urllib.request.urlopen(req, timeout=3):
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
                req = urllib.request.Request(frame_url, headers={"User-Agent": "CEOAdmin/2.1"})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    b64_frame = data.get("frame")
                    if b64_frame:
                        img_bytes = base64.b64decode(b64_frame)
                        img = Image.open(BytesIO(img_bytes))

                        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                        self.latest_cv_frame = cv_img

                        if self.is_recording:
                            self.write_frame_to_video(cv_img)

                        self.after(0, self.display_frame, img)

                        self.fps_count += 1
                        now = time.time()
                        if now - self.last_fps_time >= 1.0:
                            self.current_fps = self.fps_count
                            self.fps_count = 0
                            self.last_fps_time = now

                time.sleep(0.04)
            except Exception:
                time.sleep(0.2)

    def display_frame(self, img):
        if self.active_view != "stream":
            return

        cw = max(400, self.screen_canvas.winfo_width())
        ch = max(300, self.screen_canvas.winfo_height())

        img_ratio = img.width / float(img.height)
        canvas_ratio = cw / float(ch)

        if canvas_ratio > img_ratio:
            nh = ch - 6
            nw = int(nh * img_ratio)
        else:
            nw = cw - 6
            nh = int(nw / img_ratio)

        nw = max(10, nw)
        nh = max(10, nh)

        # Precision centered offset
        ox = (cw - nw) // 2
        oy = (ch - nh) // 2
        self.image_display_rect = (ox, oy, nw, nh)

        resized = img.resize((nw, nh), Image.Resampling.BILINEAR)
        photo = ImageTk.PhotoImage(resized)
        self.current_photo = photo

        self.screen_canvas.delete("all")
        self.screen_canvas.create_image(ox, oy, anchor="nw", image=photo)

    def on_closing(self):
        if self.is_recording:
            self.stop_recording_and_save()
        self.stop_event.set()
        self.destroy()

if __name__ == "__main__":
    app = CEOAdminApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
