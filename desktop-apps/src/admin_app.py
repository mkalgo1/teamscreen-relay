"""
CEO Command Center // TeamScreen Relay (High Performance v3.0)
Ultra-fast asynchronous rendering, DPI-aware precision remote mouse clicking,
and complete remote file & folder management (browse, upload, download, launch, delete, mkdir).
"""

import sys
import os
import time
import json
import base64
import tempfile
import threading
import subprocess
import csv
import datetime
import webbrowser
import tkinter as tk
from io import BytesIO
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk
from PIL import Image, ImageTk
import cv2
import numpy as np
import requests

try:
    import sounddevice as sd
except Exception:
    sd = None

DEFAULT_RELAY_URL = "https://teamscreen-relay-mktradez.vercel.app"
CONFIG_FILE = "admin_config.json"

class CEOAdminApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Executive White Pro Max Theme
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.title("CEO Command Center // TeamScreen Relay Pro")
        self.geometry("1340x860")
        self.minsize(1080, 720)

        # State Variables
        self.relay_url = DEFAULT_RELAY_URL
        self.workers = []
        self.selected_worker_id = None
        self.is_monitoring = False
        self.stop_event = threading.Event()
        
        # High-Speed Rendering State
        self.current_photo = None
        self.canvas_img_id = None
        self.latest_cv_frame = None
        self.fps_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0

        # Anti-Flicker Live Refresh Signatures
        self.last_workers_signature = None
        self.last_gps_signature = None
        self.last_frame_timestamp = 0
        self.pending_render_data = None
        self.is_render_scheduled = False

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
        self.selected_file_item = None
        self.last_file_sync_time = 0
        self.cached_cs_logs = []
        self.file_clipboard = None # {"path": str, "name": str, "op": "copy" | "cut", "isDir": bool}
        self._guidance_typing_timer = None

        # Live Interactive Notepad Guidance State
        self.live_notepad_active = False
        self.last_guidance_sent = ""

        # Two-Way Audio Intercom State
        self.worker_mic_active = False
        self.ceo_mic_active = False
        self.last_worker_audio_seq = 0

        # Reusable HTTP Session for persistent Keep-Alive
        self.http_session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
        self.http_session.mount("https://", adapter)
        self.http_session.mount("http://", adapter)

        # Downloads cache folder
        self.received_files_dir = os.path.join(os.path.expanduser("~"), "Downloads", "TeamScreen_Files")
        os.makedirs(self.received_files_dir, exist_ok=True)

        # Load config
        self.load_config()

        # Build UI
        self.setup_ui()

        # Launch Background Discovery & File Result Pollers
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
        # --- Top Executive Header (Clean White Ceramic) ---
        header = ctk.CTkFrame(self, fg_color="#FFFFFF", height=66, corner_radius=0)
        header.pack(fill="x", side="top")

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=12)

        title = ctk.CTkLabel(
            title_box,
            text="CEO COMMAND CENTER",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#0F172A"
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_box,
            text="Ultra-Fast Screen Guidance, Precision Remote Input & Remote File Manager",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#64748B"
        )
        subtitle.pack(anchor="w")

        # Top Right Relay Configuration Bar
        config_box = ctk.CTkFrame(header, fg_color="transparent")
        config_box.pack(side="right", padx=20, pady=12)

        self.url_entry = ctk.CTkEntry(
            config_box,
            placeholder_text="Vercel Relay URL",
            width=290,
            fg_color="#F8FAFC",
            border_color="#CBD5E1",
            text_color="#0F172A"
        )
        self.url_entry.insert(0, self.relay_url)
        self.url_entry.pack(side="left", padx=(0, 8))

        apply_btn = ctk.CTkButton(
            config_box,
            text="Save URL",
            width=76,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            text_color="#FFFFFF",
            command=self.apply_url
        )
        apply_btn.pack(side="left")

        # --- Main Layout: Left Sidebar + Right Viewport ---
        main_container = ctk.CTkFrame(self, fg_color="#F8FAFC", corner_radius=0)
        main_container.pack(fill="both", expand=True)

        # Left Sidebar (Active Workers Fleet - Clean White)
        self.sidebar = ctk.CTkFrame(main_container, fg_color="#FFFFFF", width=335, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar.pack_propagate(False)

        sidebar_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_header.pack(fill="x", padx=14, pady=(16, 8))

        fleet_label = ctk.CTkLabel(
            sidebar_header,
            text="ACTIVE FLEET",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#0F172A"
        )
        fleet_label.pack(side="left")

        self.online_count_badge = ctk.CTkLabel(
            sidebar_header,
            text="0 online",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#10B981"
        )
        self.online_count_badge.pack(side="right")

        clear_btn = ctk.CTkButton(
            sidebar_header,
            text="🧹 Clear",
            width=58,
            height=24,
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self.purge_inactive_workers
        )
        clear_btn.pack(side="right", padx=(0, 6))

        # Search Bar
        self.search_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="Search workers...",
            fg_color="#F8FAFC",
            border_color="#CBD5E1",
            text_color="#0F172A"
        )
        self.search_entry.pack(fill="x", padx=16, pady=(0, 10))

        # Workers Scrollable List
        self.workers_list_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.workers_list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        # Right Main Viewport Area
        self.viewport_container = ctk.CTkFrame(main_container, fg_color="#F8FAFC", corner_radius=0)
        self.viewport_container.pack(side="right", fill="both", expand=True)

        # Viewport Header Toolbar
        self.vp_header = ctk.CTkFrame(self.viewport_container, fg_color="#FFFFFF", height=58, corner_radius=0)
        self.vp_header.pack(fill="x", side="top")

        self.vp_title = ctk.CTkLabel(
            self.vp_header,
            text="No Worker Selected",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#0F172A"
        )
        self.vp_title.pack(side="left", padx=16, pady=12)

        self.vp_stats = ctk.CTkLabel(
            self.vp_header,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#2563EB"
        )
        self.vp_stats.pack(side="left", padx=6)

        # Top Navigation Bar (Switch between Live Screen, Remote Files, Customer Logs, Worker GPS)
        self.nav_bar = ctk.CTkFrame(self.vp_header, fg_color="#F1F5F9", corner_radius=8, border_color="#E2E8F0", border_width=1)
        self.nav_bar.pack(side="right", padx=14, pady=10)

        self.nav_btn_stream = ctk.CTkButton(
            self.nav_bar,
            text="🖥️ Live Screen",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            width=115,
            height=34,
            corner_radius=6,
            command=lambda: self.switch_to_view("stream")
        )
        self.nav_btn_stream.pack(side="left", padx=2, pady=2)

        self.nav_btn_files = ctk.CTkButton(
            self.nav_bar,
            text="📁 Remote Files",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            hover_color="#E2E8F0",
            text_color="#64748B",
            width=115,
            height=34,
            corner_radius=6,
            command=lambda: self.switch_to_view("files")
        )
        self.nav_btn_files.pack(side="left", padx=2, pady=2)

        self.nav_btn_cs = ctk.CTkButton(
            self.nav_bar,
            text="📞 Customer Logs",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            hover_color="#E2E8F0",
            text_color="#64748B",
            width=125,
            height=34,
            corner_radius=6,
            command=lambda: self.switch_to_view("cs_logs")
        )
        self.nav_btn_cs.pack(side="left", padx=2, pady=2)

        self.nav_btn_gps = ctk.CTkButton(
            self.nav_bar,
            text="📍 Worker GPS",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            hover_color="#E2E8F0",
            text_color="#64748B",
            width=115,
            height=34,
            corner_radius=6,
            command=lambda: self.switch_to_view("gps")
        )
        self.nav_btn_gps.pack(side="left", padx=2, pady=2)

        # Aliases for backward compatibility
        self.files_toggle_btn = self.nav_btn_files
        self.cs_logs_btn = self.nav_btn_cs
        self.gps_toggle_btn = self.nav_btn_gps

        # Central Area: Stream View vs File Explorer View
        self.center_area = ctk.CTkFrame(self.viewport_container, fg_color="transparent", corner_radius=0)
        self.center_area.pack(fill="both", expand=True, padx=12, pady=6)

        # --- STREAM VIEW WIDGETS ---
        self.stream_view_frame = ctk.CTkFrame(self.center_area, fg_color="transparent")
        self.stream_view_frame.pack(fill="both", expand=True)

        # Stream Action Toolbar (Live Status, FPS, and Remote Controls)
        self.stream_action_bar = ctk.CTkFrame(self.stream_view_frame, fg_color="#FFFFFF", height=46, corner_radius=8, border_color="#E2E8F0", border_width=1)
        self.stream_action_bar.pack(fill="x", pady=(0, 6))

        # Left: Stream Status Indicator & FPS
        sab_left = ctk.CTkFrame(self.stream_action_bar, fg_color="transparent")
        sab_left.pack(side="left", padx=12, pady=6)

        self.stream_status_dot = ctk.CTkLabel(sab_left, text="●", text_color="#94A3B8", font=ctk.CTkFont(size=14))
        self.stream_status_dot.pack(side="left", padx=(0, 6))

        self.stream_status_text = ctk.CTkLabel(
            sab_left,
            text="STREAM IDLE",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#64748B"
        )
        self.stream_status_text.pack(side="left")

        self.vp_fps_badge = ctk.CTkLabel(
            sab_left,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#2563EB"
        )
        self.vp_fps_badge.pack(side="left", padx=(10, 0))

        # Right: Stream Control Action Buttons (Start/Stop, Remote Input, Record, Auto-Startup)
        sab_right = ctk.CTkFrame(self.stream_action_bar, fg_color="transparent")
        sab_right.pack(side="right", padx=10, pady=6)

        # 1. Stream Toggle Button
        self.stream_toggle_btn = ctk.CTkButton(
            sab_right,
            text="▶ START STREAM",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#10B981",
            hover_color="#059669",
            text_color="#FFFFFF",
            width=135,
            height=32,
            command=self.toggle_stream_session
        )
        self.stream_toggle_btn.pack(side="left", padx=4)
        self.stream_toggle_btn.configure(state="disabled")

        # 2. Remote Input Toggle Button
        self.input_toggle_btn = ctk.CTkButton(
            sab_right,
            text="🖱️ Remote Input: OFF",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            width=150,
            height=32,
            command=self.toggle_remote_input
        )
        self.input_toggle_btn.pack(side="left", padx=4)
        self.input_toggle_btn.configure(state="disabled")

        # 3. Record Session Button
        self.record_btn = ctk.CTkButton(
            sab_right,
            text="⏺️ Record MP4",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#FFF1F2",
            hover_color="#FFE4E6",
            text_color="#E11D48",
            border_color="#FECDD3",
            border_width=1,
            width=120,
            height=32,
            command=self.toggle_recording
        )
        self.record_btn.pack(side="left", padx=4)
        self.record_btn.configure(state="disabled")

        # 4. Remote Auto-Startup Button
        self.autostart_btn = ctk.CTkButton(
            sab_right,
            text="⚡ Auto-Startup",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            width=115,
            height=32,
            command=self.remote_ensure_autostart
        )
        self.autostart_btn.pack(side="left", padx=4)
        self.autostart_btn.configure(state="disabled")

        # 5. Worker Mic Button (Listen to Worker)
        self.worker_mic_btn = ctk.CTkButton(
            sab_right,
            text="🎧 Worker Mic: OFF",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            width=135,
            height=32,
            command=self.toggle_worker_mic
        )
        self.worker_mic_btn.pack(side="left", padx=4)
        self.worker_mic_btn.configure(state="disabled")

        # 6. CEO Mic Button (Speak to Worker)
        self.ceo_mic_btn = ctk.CTkButton(
            sab_right,
            text="🎙️ Speak: OFF",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            width=115,
            height=32,
            command=self.toggle_ceo_mic
        )
        self.ceo_mic_btn.pack(side="left", padx=4)
        self.ceo_mic_btn.configure(state="disabled")

        self.canvas_frame = ctk.CTkFrame(self.stream_view_frame, fg_color="#0F172A", border_color="#E2E8F0", border_width=1, corner_radius=10)
        self.canvas_frame.pack(fill="both", expand=True)

        self.screen_canvas = tk.Canvas(
            self.canvas_frame,
            bg="#0F172A",
            highlightthickness=0,
            cursor=""
        )
        self.screen_canvas.pack(fill="both", expand=True)
        self.screen_canvas.bind("<Button-1>", self.on_canvas_click)

        self.canvas_placeholder = self.screen_canvas.create_text(
            400, 250,
            text="Select an active worker on the left to begin live observation.",
            fill="#64748B",
            font=("Segoe UI", 13)
        )

        # --- REMOTE FILE & FOLDER EXPLORER VIEW WIDGETS ---
        self.file_view_frame = ctk.CTkFrame(self.center_area, fg_color="#FFFFFF", border_color="#E2E8F0", border_width=1, corner_radius=8)

        # File Manager Navigation Bar (Path & Shortcuts)
        fm_nav_top = ctk.CTkFrame(self.file_view_frame, fg_color="#F8FAFC", height=46, corner_radius=6, border_color="#E2E8F0", border_width=1)
        fm_nav_top.pack(fill="x", padx=12, pady=(12, 4))

        up_btn = ctk.CTkButton(fm_nav_top, text="⬆️ Up", width=65, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#334155", border_color="#CBD5E1", border_width=1, command=self.navigate_up_folder)
        up_btn.pack(side="left", padx=4)

        refresh_btn = ctk.CTkButton(fm_nav_top, text="🔄 Refresh", width=75, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#334155", border_color="#CBD5E1", border_width=1, command=self.refresh_current_folder)
        refresh_btn.pack(side="left", padx=3)

        self.fm_path_entry = ctk.CTkEntry(fm_nav_top, fg_color="#FFFFFF", border_color="#CBD5E1", text_color="#0F172A")
        self.fm_path_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.fm_path_entry.bind("<Return>", lambda e: self.request_browse_folder(self.fm_path_entry.get().strip()))

        go_btn = ctk.CTkButton(fm_nav_top, text="Go", width=50, fg_color="#2563EB", hover_color="#1D4ED8", text_color="#FFFFFF", command=lambda: self.request_browse_folder(self.fm_path_entry.get().strip()))
        go_btn.pack(side="left", padx=3)

        # Quick Jump Buttons
        desktop_btn = ctk.CTkButton(fm_nav_top, text="Desktop", width=70, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#334155", border_color="#CBD5E1", border_width=1, command=lambda: self.request_browse_folder("DESKTOP"))
        desktop_btn.pack(side="left", padx=2)

        docs_btn = ctk.CTkButton(fm_nav_top, text="Documents", width=80, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#334155", border_color="#CBD5E1", border_width=1, command=lambda: self.request_browse_folder("DOCUMENTS"))
        docs_btn.pack(side="left", padx=2)

        downloads_btn = ctk.CTkButton(fm_nav_top, text="Downloads", width=80, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#334155", border_color="#CBD5E1", border_width=1, command=lambda: self.request_browse_folder("DOWNLOADS"))
        downloads_btn.pack(side="left", padx=2)

        c_drive_btn = ctk.CTkButton(fm_nav_top, text="C:\\", width=45, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#334155", border_color="#CBD5E1", border_width=1, command=lambda: self.request_browse_folder("C:\\"))
        c_drive_btn.pack(side="left", padx=2)

        trash_jump_btn = ctk.CTkButton(fm_nav_top, text="🗑️ Recycle Bin", width=105, fg_color="#FFF1F2", hover_color="#FFE4E6", text_color="#BE123C", border_color="#FECDD3", border_width=1, command=self.browse_recycle_bin)
        trash_jump_btn.pack(side="left", padx=(2, 6))

        # File Action Toolbar (Upload, Download/Open, Launch on Worker, Copy, Cut, Paste, Delete, Trash)
        fm_actions_bar = ctk.CTkFrame(self.file_view_frame, fg_color="#F8FAFC", height=44, corner_radius=6, border_color="#E2E8F0", border_width=1)
        fm_actions_bar.pack(fill="x", padx=12, pady=(0, 6))

        upload_btn = ctk.CTkButton(
            fm_actions_bar,
            text="📤 Upload",
            fg_color="#10B981",
            hover_color="#059669",
            text_color="#FFFFFF",
            width=90,
            command=self.send_file_to_worker
        )
        upload_btn.pack(side="left", padx=4, pady=6)

        self.download_btn = ctk.CTkButton(
            fm_actions_bar,
            text="📥 Download",
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            text_color="#FFFFFF",
            width=100,
            command=self.download_selected_file
        )
        self.download_btn.pack(side="left", padx=3, pady=6)

        self.launch_btn = ctk.CTkButton(
            fm_actions_bar,
            text="🖥️ Launch",
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            text_color="#FFFFFF",
            width=85,
            command=self.launch_selected_file_on_worker
        )
        self.launch_btn.pack(side="left", padx=3, pady=6)

        new_folder_btn = ctk.CTkButton(
            fm_actions_bar,
            text="📁 New Folder",
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            width=95,
            command=self.create_remote_folder
        )
        new_folder_btn.pack(side="left", padx=3, pady=6)

        self.copy_btn = ctk.CTkButton(
            fm_actions_bar,
            text="📋 Copy",
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            width=70,
            command=self.copy_selected_item
        )
        self.copy_btn.pack(side="left", padx=3, pady=6)

        self.cut_btn = ctk.CTkButton(
            fm_actions_bar,
            text="✂️ Cut",
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            width=65,
            command=self.cut_selected_item
        )
        self.cut_btn.pack(side="left", padx=3, pady=6)

        self.paste_btn = ctk.CTkButton(
            fm_actions_bar,
            text="📌 Paste",
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            width=75,
            state="disabled",
            command=self.paste_item
        )
        self.paste_btn.pack(side="left", padx=3, pady=6)

        self.delete_btn = ctk.CTkButton(
            fm_actions_bar,
            text="🗑️ Delete",
            fg_color="#FFF1F2",
            hover_color="#FFE4E6",
            text_color="#BE123C",
            border_color="#FECDD3",
            border_width=1,
            width=75,
            command=self.delete_selected_item
        )
        self.delete_btn.pack(side="left", padx=3, pady=6)

        self.empty_trash_btn = ctk.CTkButton(
            fm_actions_bar,
            text="🧹 Empty Trash",
            fg_color="#FFF1F2",
            hover_color="#FFE4E6",
            text_color="#BE123C",
            border_color="#FECDD3",
            border_width=1,
            width=105,
            command=self.empty_recycle_bin
        )
        self.empty_trash_btn.pack(side="left", padx=4, pady=6)

        self.fm_status_lbl = ctk.CTkLabel(
            fm_actions_bar,
            text="Select an item to view options",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#64748B"
        )
        self.fm_status_lbl.pack(side="right", padx=12)

        # File List Scrollable Table
        self.files_scroll = ctk.CTkScrollableFrame(self.file_view_frame, fg_color="#FFFFFF")
        self.files_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # --- CUSTOMER SERVICE CALL & COMMUNICATION LOGS VIEW ---
        self.cs_logs_view_frame = ctk.CTkFrame(self.center_area, fg_color="#FFFFFF", border_color="#E2E8F0", border_width=1, corner_radius=8)

        cs_top = ctk.CTkFrame(self.cs_logs_view_frame, fg_color="#F8FAFC", height=46, corner_radius=6, border_color="#E2E8F0", border_width=1)
        cs_top.pack(fill="x", padx=12, pady=(12, 6))

        cs_title = ctk.CTkLabel(
            cs_top,
            text="📞 Customer Service Interactions & Call Logs",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#0F172A"
        )
        cs_title.pack(side="left", padx=12)

        export_csv_btn = ctk.CTkButton(
            cs_top,
            text="📥 Export CSV",
            fg_color="#10B981",
            hover_color="#059669",
            text_color="#FFFFFF",
            width=100,
            command=self.export_cs_logs_csv
        )
        export_csv_btn.pack(side="right", padx=8)

        cs_refresh_btn = ctk.CTkButton(
            cs_top,
            text="🔄 Refresh Logs",
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            width=110,
            command=self.fetch_cs_logs
        )
        cs_refresh_btn.pack(side="right", padx=4)

        self.cs_status_lbl = ctk.CTkLabel(
            cs_top,
            text="Ready to load records.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#64748B"
        )
        self.cs_status_lbl.pack(side="right", padx=12)

        # Scrollable list for customer logs
        self.cs_logs_scroll = ctk.CTkScrollableFrame(self.cs_logs_view_frame, fg_color="#F8FAFC")
        self.cs_logs_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # --- FIELD WORKER GPS & LIVE LOCATION TRACKING VIEW ---
        self.gps_view_frame = ctk.CTkFrame(self.center_area, fg_color="#FFFFFF", border_color="#E2E8F0", border_width=1, corner_radius=8)

        gps_top = ctk.CTkFrame(self.gps_view_frame, fg_color="#F8FAFC", height=46, corner_radius=6, border_color="#E2E8F0", border_width=1)
        gps_top.pack(fill="x", padx=12, pady=(12, 6))

        gps_title = ctk.CTkLabel(
            gps_top,
            text="📍 Field Workers Live GPS & Location Verification",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#0F172A"
        )
        gps_title.pack(side="left", padx=12)

        gps_refresh_btn = ctk.CTkButton(
            gps_top,
            text="🔄 Refresh Map Locations",
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color="#334155",
            border_color="#CBD5E1",
            border_width=1,
            width=160,
            command=self.render_gps_locations
        )
        gps_refresh_btn.pack(side="right", padx=8)

        self.gps_status_lbl = ctk.CTkLabel(
            gps_top,
            text="Tracking active field devices",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#2563EB"
        )
        self.gps_status_lbl.pack(side="right", padx=12)

        # Scrollable list for GPS locations
        self.gps_scroll = ctk.CTkScrollableFrame(self.gps_view_frame, fg_color="#F8FAFC")
        self.gps_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # --- BOTTOM ACTION BARS ---
        # Remote Keystrokes & Password Injection Console
        input_bar = ctk.CTkFrame(self.viewport_container, fg_color="#FFFFFF", height=48, corner_radius=8, border_color="#E2E8F0", border_width=1)
        input_bar.pack(fill="x", side="bottom", padx=12, pady=(0, 6))

        input_title = ctk.CTkLabel(
            input_bar,
            text="REMOTE KEYSTROKES:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#7C3AED"
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
            font=ctk.CTkFont(size=11),
            text_color="#334155"
        )
        self.mask_checkbox.pack(side="left", padx=(0, 8))

        self.key_input = ctk.CTkEntry(
            input_bar,
            placeholder_text="Enter password or text to type into worker's focused window...",
            show="*",
            fg_color="#F8FAFC",
            border_color="#CBD5E1",
            text_color="#0F172A"
        )
        self.key_input.pack(side="left", fill="x", expand=True, padx=6, pady=7)
        self.key_input.bind("<Return>", lambda e: self.send_remote_text())

        type_btn = ctk.CTkButton(
            input_bar,
            text="Type into PC",
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            text_color="#FFFFFF",
            width=110,
            command=self.send_remote_text
        )
        type_btn.pack(side="left", padx=4)

        enter_btn = ctk.CTkButton(input_bar, text="[Enter]", width=55, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#334155", border_color="#CBD5E1", border_width=1, command=lambda: self.send_special_key("enter"))
        enter_btn.pack(side="left", padx=2)
        tab_btn = ctk.CTkButton(input_bar, text="[Tab]", width=50, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#334155", border_color="#CBD5E1", border_width=1, command=lambda: self.send_special_key("tab"))
        tab_btn.pack(side="left", padx=2)
        esc_btn = ctk.CTkButton(input_bar, text="[Esc]", width=50, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#334155", border_color="#CBD5E1", border_width=1, command=lambda: self.send_special_key("esc"))
        esc_btn.pack(side="left", padx=(2, 10))

        # Bottom CEO Live Interactive Guidance Console
        guidance_bar = ctk.CTkFrame(self.viewport_container, fg_color="#FFFFFF", height=48, corner_radius=8, border_color="#E2E8F0", border_width=1)
        guidance_bar.pack(fill="x", side="bottom", padx=12, pady=(0, 8))

        guidance_label = ctk.CTkLabel(
            guidance_bar,
            text="CEO GUIDANCE:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#2563EB"
        )
        guidance_label.pack(side="left", padx=(12, 6))

        self.guidance_toggle_btn = ctk.CTkButton(
            guidance_bar,
            text="▶ Start Live Notepad",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#10B981",
            hover_color="#059669",
            text_color="#FFFFFF",
            width=150,
            height=32,
            command=self.toggle_live_notepad
        )
        self.guidance_toggle_btn.pack(side="left", padx=(2, 6))
        self.guidance_toggle_btn.configure(state="disabled")

        self.guidance_input = ctk.CTkEntry(
            guidance_bar,
            placeholder_text="Type real-time guidance (syncs live to worker screen Notepad)...",
            fg_color="#F8FAFC",
            border_color="#CBD5E1",
            text_color="#0F172A",
            height=32
        )
        self.guidance_input.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        self.guidance_input.bind("<Return>", lambda e: self.send_guidance())
        self.guidance_input.bind("<KeyRelease>", lambda e: self.on_guidance_typing(e))

        self.guidance_send_btn = ctk.CTkButton(
            guidance_bar,
            text="Send Note",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            text_color="#FFFFFF",
            width=95,
            height=32,
            command=self.send_guidance
        )
        self.guidance_send_btn.pack(side="right", padx=(0, 10))
        self.guidance_send_btn.configure(state="disabled")

    def toggle_files_view(self):
        self.switch_to_view("stream" if self.active_view == "files" else "files")

    def toggle_cs_logs_view(self):
        self.switch_to_view("stream" if self.active_view == "cs_logs" else "cs_logs")

    def toggle_gps_view(self):
        self.switch_to_view("stream" if self.active_view == "gps" else "gps")

    def switch_to_view(self, target):
        self.active_view = target
        self.stream_view_frame.pack_forget()
        self.file_view_frame.pack_forget()
        self.cs_logs_view_frame.pack_forget()
        self.gps_view_frame.pack_forget()

        # Reset all navigation tabs to inactive state
        for btn in [self.nav_btn_stream, self.nav_btn_files, self.nav_btn_cs, self.nav_btn_gps]:
            btn.configure(fg_color="transparent", hover_color="#E2E8F0", text_color="#64748B", border_width=0)

        if target == "stream":
            self.stream_view_frame.pack(fill="both", expand=True)
            self.nav_btn_stream.configure(fg_color="#FFFFFF", hover_color="#F8FAFC", text_color="#2563EB", border_color="#CBD5E1", border_width=1)
        elif target == "files":
            self.file_view_frame.pack(fill="both", expand=True)
            self.nav_btn_files.configure(fg_color="#FFFFFF", hover_color="#F8FAFC", text_color="#059669", border_color="#CBD5E1", border_width=1)
            if not self.worker_current_path and self.selected_worker_id:
                self.request_browse_folder("DEFAULT")
        elif target == "cs_logs":
            self.cs_logs_view_frame.pack(fill="both", expand=True)
            self.nav_btn_cs.configure(fg_color="#FFFFFF", hover_color="#F8FAFC", text_color="#7C3AED", border_color="#CBD5E1", border_width=1)
            self.fetch_cs_logs()
        elif target == "gps":
            self.gps_view_frame.pack(fill="both", expand=True)
            self.nav_btn_gps.configure(fg_color="#FFFFFF", hover_color="#F8FAFC", text_color="#0284C7", border_color="#CBD5E1", border_width=1)
            self.last_gps_signature = None  # Force fresh render on tab switch
            self.render_gps_locations()

    def fetch_cs_logs(self):
        self.cs_status_lbl.configure(text="Fetching logs from relay...", text_color="#38BDF8")
        def _bg():
            try:
                url = f"{self.relay_url}/api/cs/logs"
                resp = self.http_session.get(url, timeout=3.5)
                if resp.status_code == 200:
                    data = resp.json()
                    logs = data.get("logs", [])
                    self.after(0, lambda: self.render_cs_logs(logs))
                else:
                    self.after(0, lambda: self.cs_status_lbl.configure(text=f"HTTP {resp.status_code}", text_color="#EF4444"))
            except Exception as e:
                self.after(0, lambda: self.cs_status_lbl.configure(text=f"Error: {str(e)}", text_color="#EF4444"))
        threading.Thread(target=_bg, daemon=True).start()

    def render_cs_logs(self, logs):
        self.cached_cs_logs = logs
        for child in self.cs_logs_scroll.winfo_children():
            child.destroy()

        if not logs:
            empty = ctk.CTkLabel(
                self.cs_logs_scroll,
                text="No customer service interactions logged yet.\nLogs entered from company Android phones will appear here instantly.",
                font=ctk.CTkFont(size=13),
                text_color="#64748B"
            )
            empty.pack(pady=50)
            self.cs_status_lbl.configure(text="0 logs found", text_color="#94A3B8")
            return

        self.cs_status_lbl.configure(text=f"{len(logs)} logs loaded", text_color="#10B981")

        for log in logs:
            ts = log.get("timestamp", 0)
            time_str = datetime.datetime.fromtimestamp(ts / 1000.0).strftime("%Y-%m-%d %H:%M:%S") if ts else "N/A"
            worker_name = log.get("workerName", "Phone Agent")
            customer_name = log.get("customerName", "Customer")
            phone = log.get("customerPhone", "")
            direction = log.get("direction", "outgoing").upper()
            status = log.get("status", "completed").capitalize()
            notes = log.get("notes", "")

            card = ctk.CTkFrame(self.cs_logs_scroll, fg_color="#FFFFFF", border_color="#E2E8F0", border_width=1, corner_radius=8)
            card.pack(fill="x", pady=3, padx=4)

            # Top row inside card
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 2))

            badge = ctk.CTkLabel(
                top_row,
                text=f"📞 {direction}",
                fg_color="#ECFDF5" if direction == "INCOMING" else "#EFF6FF",
                corner_radius=4,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color="#059669" if direction == "INCOMING" else "#2563EB",
                padx=6, pady=2
            )
            badge.pack(side="left", padx=(0, 8))

            name_lbl = ctk.CTkLabel(
                top_row,
                text=f"{customer_name} ({phone})",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#0F172A"
            )
            name_lbl.pack(side="left", padx=4)

            status_badge = ctk.CTkLabel(
                top_row,
                text=status,
                fg_color="#F1F5F9",
                corner_radius=4,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#2563EB",
                padx=6, pady=1
            )
            status_badge.pack(side="left", padx=8)

            time_lbl = ctk.CTkLabel(
                top_row,
                text=f"🕒 {time_str}  •  📱 {worker_name}",
                font=ctk.CTkFont(size=11),
                text_color="#64748B"
            )
            time_lbl.pack(side="right", padx=6)

            # Bottom row inside card (Notes)
            if notes:
                notes_lbl = ctk.CTkLabel(
                    card,
                    text=f"📝 {notes}",
                    font=ctk.CTkFont(size=11),
                    text_color="#475569",
                    anchor="w",
                    justify="left"
                )
                notes_lbl.pack(fill="x", padx=12, pady=(0, 8))
            else:
                top_row.pack_configure(pady=(8, 8))

    def export_cs_logs_csv(self):
        if not getattr(self, "cached_cs_logs", None):
            messagebox.showinfo("Export CSV", "No customer logs loaded to export. Click 'Refresh Logs' first.")
            return
        save_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile="Customer_Service_Logs.csv"
        )
        if not save_path:
            return
        try:
            with open(save_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Agent_Device", "Customer_Name", "Phone", "Direction", "Status", "Notes"])
                for log in self.cached_cs_logs:
                    ts = log.get("timestamp", 0)
                    time_str = datetime.datetime.fromtimestamp(ts / 1000.0).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
                    writer.writerow([
                        time_str,
                        log.get("workerName", ""),
                        log.get("customerName", ""),
                        log.get("customerPhone", ""),
                        log.get("direction", ""),
                        log.get("status", ""),
                        log.get("notes", "")
                    ])
            messagebox.showinfo("Export Successful", f"Exported {len(self.cached_cs_logs)} records to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not save CSV:\n{str(e)}")

    def purge_inactive_workers(self):
        try:
            relay_url = self.url_entry.get().strip().rstrip("/")
            self.http_session.delete(f"{relay_url}/api/workers", timeout=3)
            self.workers = []
            self.last_workers_signature = None
            self.last_gps_signature = None
            self.update_workers_list([])
            self.online_count_badge.configure(text="0 online")
        except Exception:
            pass

    def render_gps_locations(self):
        # Anti-Flicker: Compute signature of GPS state to avoid unnecessary widget destruction
        gps_sig = tuple(
            (
                w.get("workerId"),
                w.get("name"),
                w.get("department"),
                w.get("hostname"),
                w.get("location", {}).get("latitude"),
                w.get("location", {}).get("longitude"),
                w.get("location", {}).get("timestamp")
            )
            for w in self.workers if w.get("location")
        ) + (len(self.workers),)

        if gps_sig == self.last_gps_signature:
            # Coordinates and devices unchanged: skip destroying widgets to eliminate blinking!
            return

        self.last_gps_signature = gps_sig

        for child in self.gps_scroll.winfo_children():
            child.destroy()

        if not self.workers:
            empty = ctk.CTkLabel(
                self.gps_scroll,
                text="No active worker devices connected.\nLocations will appear once field phones or laptops connect.",
                font=ctk.CTkFont(size=13),
                text_color="#64748B"
            )
            empty.pack(pady=50)
            self.gps_status_lbl.configure(text="0 devices connected", text_color="#94A3B8")
            return

        active_with_loc = [w for w in self.workers if w.get("location")]
        self.gps_status_lbl.configure(
            text=f"{len(active_with_loc)} of {len(self.workers)} devices reporting live location",
            text_color="#10B981" if active_with_loc else "#94A3B8"
        )

        for w in self.workers:
            w_id = w.get("workerId", "")
            name = w.get("name", "Unknown Worker")
            dept = w.get("department", "Field Operations")
            hostname = w.get("hostname", "")
            platform = (w.get("platform") or "").lower()
            device_type_field = (w.get("deviceType") or "").lower()

            is_android = (
                platform == "android" or
                device_type_field == "phone" or
                "android" in w_id.lower() or
                "android" in hostname.lower() or
                "phone" in name.lower() or
                "phone" in dept.lower() or
                "samsung" in hostname.lower() or
                "pixel" in hostname.lower() or
                "xiaomi" in hostname.lower()
            )
            device_icon = "📱" if is_android else "🪟"
            device_type = "Android Field Phone" if is_android else "Windows Workstation / Laptop"

            loc = w.get("location")

            card = ctk.CTkFrame(self.gps_scroll, fg_color="#FFFFFF", border_color="#E2E8F0", border_width=1, corner_radius=8)
            card.pack(fill="x", pady=4, padx=4)

            # Left side: Worker info
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="y", padx=14, pady=10)

            title_lbl = ctk.CTkLabel(
                info_frame,
                text=f"{device_icon}  {name}  [{dept}]",
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color="#0F172A"
            )
            title_lbl.pack(anchor="w")

            sub_lbl = ctk.CTkLabel(
                info_frame,
                text=f"{device_type} • {hostname}",
                font=ctk.CTkFont(size=11),
                text_color="#64748B"
            )
            sub_lbl.pack(anchor="w", pady=(2, 0))

            # Center: Location Coordinates & Accuracy
            center_frame = ctk.CTkFrame(card, fg_color="transparent")
            center_frame.pack(side="left", expand=True, padx=14, pady=10)

            if loc and "latitude" in loc and "longitude" in loc:
                lat = float(loc["latitude"])
                lon = float(loc["longitude"])
                acc = loc.get("accuracy", 0)
                provider = loc.get("provider", "GPS")
                ts = loc.get("timestamp", 0)
                time_str = datetime.datetime.fromtimestamp(ts / 1000.0).strftime("%H:%M:%S") if ts else "Just now"

                coords_lbl = ctk.CTkLabel(
                    center_frame,
                    text=f"📍 Lat: {lat:.6f},  Lon: {lon:.6f}",
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                    text_color="#2563EB"
                )
                coords_lbl.pack(anchor="w")

                acc_str = f"Accuracy: ±{acc:.0f}m" if acc else "Location locked"
                detail_lbl = ctk.CTkLabel(
                    center_frame,
                    text=f"📡 Source: {provider.upper()}  •  {acc_str}  •  Updated: {time_str}",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#10B981"
                )
                detail_lbl.pack(anchor="w", pady=(2, 0))

                # Right side: Map buttons
                btn_frame = ctk.CTkFrame(card, fg_color="transparent")
                btn_frame.pack(side="right", padx=12, pady=10)

                maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                map_btn = ctk.CTkButton(
                    btn_frame,
                    text="🗺️ Open in Google Maps",
                    fg_color="#2563EB",
                    hover_color="#1D4ED8",
                    text_color="#FFFFFF",
                    width=165,
                    command=lambda u=maps_url: webbrowser.open(u)
                )
                map_btn.pack(side="top", pady=2)

                copy_btn = ctk.CTkButton(
                    btn_frame,
                    text="📋 Copy Coordinates",
                    fg_color="#F1F5F9",
                    hover_color="#E2E8F0",
                    text_color="#334155",
                    border_color="#CBD5E1",
                    border_width=1,
                    width=165,
                    command=lambda c=f"{lat},{lon}": self.copy_to_clipboard(c)
                )
                copy_btn.pack(side="top", pady=2)
            else:
                no_loc_lbl = ctk.CTkLabel(
                    center_frame,
                    text="⏳ Location pending / Waiting for GPS fix from worker device...",
                    font=ctk.CTkFont(size=12),
                    text_color="#64748B"
                )
                no_loc_lbl.pack(anchor="w")

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", f"Coordinates copied to clipboard:\n{text}")

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
                resp = self.http_session.get(f"{self.relay_url}/api/workers", timeout=2.5)
                if resp.status_code == 200:
                    data = resp.json()
                    workers = data.get("workers", [])
                    self.after(0, self.update_workers_list, workers)
            except Exception:
                pass
            time.sleep(2.0)

    def update_workers_list(self, workers):
        # 1. De-duplicate workers: Ensure each physical device is displayed exactly ONCE
        unique_workers = []
        seen = set()
        for w in sorted(workers, key=lambda x: (x.get("status") == "streaming", x.get("lastPing", 0)), reverse=True):
            h_key = (w.get("hostname") or w.get("workerId") or "").strip().lower()
            if h_key and h_key in seen:
                continue
            seen.add(h_key)
            unique_workers.append(w)
        workers = unique_workers
        self.workers = workers
        self.online_count_badge.configure(text=f"{len(workers)} online")

        search_query = self.search_entry.get().strip().lower()

        # Anti-Flicker: Compute current state signature
        current_sig = (
            tuple(
                (
                    w.get("workerId"),
                    w.get("name"),
                    w.get("status"),
                    w.get("department"),
                    w.get("hostname"),
                    bool(w.get("location")),
                    w.get("workerId") == self.selected_worker_id
                )
                for w in workers
            ),
            search_query,
            len(workers)
        )

        # If data hasn't visually changed, DO NOT destroy or rebuild widgets (eliminates UI blinking!)
        if current_sig == self.last_workers_signature:
            if self.active_view == "gps":
                self.render_gps_locations()
            return

        self.last_workers_signature = current_sig

        for widget in self.workers_list_frame.winfo_children():
            widget.destroy()

        if not workers:
            empty_lbl = ctk.CTkLabel(
                self.workers_list_frame,
                text="Waiting for workers to connect...\n• Windows: Run WorkerRelay.exe\n• Phone: Open TeamScreenSupport.apk",
                font=ctk.CTkFont(size=12),
                text_color="#64748B",
                justify="center"
            )
            empty_lbl.pack(pady=40)
            return

        for w in workers:
            w_id = w.get("workerId", "")
            name = w.get("name", "Unknown Worker")
            dept = w.get("department", "Operations")
            hostname = w.get("hostname", "")
            status = w.get("status", "online")
            platform = (w.get("platform") or "").lower()
            device_type = (w.get("deviceType") or "").lower()

            is_phone = (
                platform == "android" or
                device_type == "phone" or
                w_id.startswith("android") or
                "android" in hostname.lower() or
                "phone" in name.lower() or
                "phone" in dept.lower() or
                "samsung" in hostname.lower() or
                "pixel" in hostname.lower() or
                "xiaomi" in hostname.lower()
            )

            if search_query and (search_query not in name.lower() and search_query not in dept.lower() and search_query not in hostname.lower()):
                continue

            is_selected = (w_id == self.selected_worker_id)
            bg_color = "#FFFFFF" if not is_selected else "#EFF6FF"
            border_color = "#3B82F6" if is_selected else "#E2E8F0"

            card = ctk.CTkFrame(
                self.workers_list_frame,
                fg_color=bg_color,
                border_color=border_color,
                border_width=1,
                corner_radius=8,
                cursor="hand2"
            )
            card.pack(fill="x", pady=4)
            card.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

            row1 = ctk.CTkFrame(card, fg_color="transparent")
            row1.pack(fill="x", padx=10, pady=(8, 2))
            row1.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

            # Left side: Device Logo (🪟 Windows vs 📱 Phone)
            device_logo = "📱" if is_phone else "🪟"
            logo_lbl = ctk.CTkLabel(row1, text=device_logo, font=ctk.CTkFont(size=14))
            logo_lbl.pack(side="left", padx=(0, 4))
            logo_lbl.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

            dot_color = "#3B82F6" if status == "streaming" else "#10B981"
            dot = ctk.CTkLabel(row1, text="●", text_color=dot_color, font=ctk.CTkFont(size=12))
            dot.pack(side="left", padx=(0, 6))
            dot.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

            name_lbl = ctk.CTkLabel(
                row1,
                text=name,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color="#0F172A"
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

            if w.get("location"):
                loc_badge = ctk.CTkLabel(
                    row1,
                    text="📍 GPS",
                    font=ctk.CTkFont(size=9, weight="bold"),
                    text_color="#38BDF8"
                )
                loc_badge.pack(side="right", padx=(0, 5))

            row2 = ctk.CTkFrame(card, fg_color="transparent")
            row2.pack(fill="x", padx=10, pady=(0, 8))
            row2.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

            platform_tag = "📱 Android" if is_phone else "🪟 Windows"
            meta_lbl = ctk.CTkLabel(
                row2,
                text=f"{platform_tag} • {dept} • {hostname}",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color="#64748B"
            )
            meta_lbl.pack(side="left")
            meta_lbl.bind("<Button-1>", lambda e, wid=w_id: self.select_worker(wid))

        if self.active_view == "gps":
            self.render_gps_locations()

    def select_worker(self, worker_id):
        self.selected_worker_id = worker_id
        # Invalidate anti-flicker signature so the selected border updates smoothly
        self.last_workers_signature = None
        self.update_workers_list(self.workers)

        worker_info = next((w for w in self.workers if w.get("workerId") == worker_id), None)
        if worker_info:
            is_phone = (
                (worker_info.get("platform") or "").lower() == "android" or
                (worker_info.get("deviceType") or "").lower() == "phone" or
                worker_info.get("workerId", "").startswith("android") or
                "android" in worker_info.get("hostname", "").lower() or
                "phone" in worker_info.get("name", "").lower()
            )
            device_tag = "📱 Android Phone" if is_phone else "🪟 Windows PC"
            self.vp_title.configure(
                text=f"{device_tag}: {worker_info.get('name', 'Worker')} [{worker_info.get('department', '')}]",
                text_color="#34D399" if is_phone else "#38BDF8"
            )
            self.vp_stats.configure(
                text=f"Res: {worker_info.get('screenResolution', '1080p')} | Host: {worker_info.get('hostname', '')}"
            )
            self.stream_toggle_btn.configure(state="normal")
            self.record_btn.configure(state="normal")
            self.input_toggle_btn.configure(state="normal")
            self.autostart_btn.configure(state="normal")
            self.worker_mic_btn.configure(state="normal")
            self.ceo_mic_btn.configure(state="normal")
            self.guidance_toggle_btn.configure(state="normal")
            self.guidance_send_btn.configure(state="normal")

            self.start_stream_session()

    def remote_ensure_autostart(self):
        """Dispatches remote command to worker PC to install to %LOCALAPPDATA% and register Windows Startup"""
        if not self.selected_worker_id:
            messagebox.showinfo("Select Worker", "Please select an active worker first.")
            return

        worker_id = self.selected_worker_id
        relay_url = self.relay_url

        def _task():
            try:
                self.after(0, lambda: self.autostart_btn.configure(state="disabled", text="⚡ Setting..."))
                self.http_session.post(
                    f"{relay_url}/api/files/command",
                    json={"workerId": worker_id, "action": "autostart"},
                    timeout=3.0
                )
                time.sleep(1.2)
                res_resp = self.http_session.get(f"{relay_url}/api/files/result?workerId={worker_id}", timeout=3.0)
                if res_resp.status_code == 200:
                    data = res_resp.json()
                    res = data.get("result", {})
                    msg = res.get("statusMessage", "Persistent installation and Windows Startup verified on worker PC.")
                    self.after(0, lambda: messagebox.showinfo("Auto-Startup Confirmed", f"Worker Response:\n{msg}"))
                else:
                    self.after(0, lambda: messagebox.showinfo("Auto-Startup Sent", "Command dispatched to worker agent."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to send startup command: {e}"))
            finally:
                self.after(0, lambda: self.autostart_btn.configure(state="normal", text="⚡ Auto-Startup"))

        threading.Thread(target=_task, daemon=True).start()

    def toggle_stream_session(self):
        if self.is_monitoring:
            self.stop_stream_session()
        else:
            self.start_stream_session()

    def start_stream_session(self):
        if not self.selected_worker_id:
            return
        self.is_monitoring = True
        self.stream_toggle_btn.configure(text="⏹ STOP STREAM", fg_color="#DC2626", hover_color="#B91C1C")
        self.stream_status_dot.configure(text_color="#10B981")
        self.stream_status_text.configure(text="STREAMING LIVE", text_color="#10B981")
        threading.Thread(target=self.notify_relay_stream_req, args=(True,), daemon=True).start()
        threading.Thread(target=self.frame_receiver_loop, daemon=True).start()

    def stop_stream_session(self):
        if self.is_recording:
            self.stop_recording_and_save()
        self.is_monitoring = False
        self.stream_toggle_btn.configure(text="▶ START STREAM", fg_color="#10B981", hover_color="#059669")
        self.stream_status_dot.configure(text_color="#64748B")
        self.stream_status_text.configure(text="STREAM IDLE", text_color="#94A3B8")
        self.vp_fps_badge.configure(text="")
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
            self.http_session.post(url, json=payload, timeout=2.0)
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
            self.after(0, lambda: self.vp_fps_badge.configure(text=f"● REC [{mins:02d}:{secs:02d}]", text_color="#EF4444"))
            time.sleep(1.0)

    def write_frame_to_video(self, cv_frame):
        if not self.is_recording or cv_frame is None:
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

            # Draw visual click ripple on canvas
            self.screen_canvas.create_oval(
                event.x - 7, event.y - 7, event.x + 7, event.y + 7,
                outline="#C084FC", width=2, tags="click_ripple"
            )
            self.after(250, lambda: self.screen_canvas.delete("click_ripple"))

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
            self.http_session.post(f"{self.relay_url}/api/stream/input", json=payload, timeout=2.0)
        except Exception:
            pass

    # --- Feature 3: Complete Remote File & Folder Manager ---
    def request_browse_folder(self, folder_path):
        if not self.selected_worker_id:
            return
        self.fm_status_lbl.configure(text="Reading folder...", text_color="#38BDF8")
        payload = {
            "workerId": self.selected_worker_id,
            "action": "list",
            "path": folder_path
        }
        threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

    def refresh_current_folder(self):
        curr = self.fm_path_entry.get().strip() or self.worker_current_path or "DESKTOP"
        self.request_browse_folder(curr)

    def navigate_up_folder(self):
        curr = self.worker_current_path
        if curr:
            parent = os.path.dirname(curr)
            if parent and parent != curr:
                self.request_browse_folder(parent)
            elif curr.endswith(":\\") or curr.endswith(":/"):
                pass
            else:
                self.request_browse_folder(parent)

    def select_file_item(self, item_info, row_widget):
        self.selected_file_item = item_info
        # Reset colors of other rows
        for child in self.files_scroll.winfo_children():
            try:
                child.configure(fg_color="#FFFFFF", border_color="#E2E8F0", border_width=1)
            except Exception:
                pass
        # Highlight selected row
        try:
            row_widget.configure(fg_color="#EFF6FF", border_color="#3B82F6", border_width=1)
        except Exception:
            pass

        name = item_info.get("name", "")
        is_dir = item_info.get("isDir", False)
        size_kb = item_info.get("size", 0) / 1024.0

        if is_dir:
            self.fm_status_lbl.configure(text=f"Selected Folder: {name}", text_color="#93C5FD")
        else:
            self.fm_status_lbl.configure(text=f"Selected File: {name} ({size_kb:.1f} KB)", text_color="#86EFAC")

    def on_item_double_click(self, item_info):
        name = item_info.get("name")
        is_dir = item_info.get("isDir", False)
        target_path = os.path.join(self.worker_current_path, name)

        if is_dir:
            self.request_browse_folder(target_path)
        else:
            # Direct prompt to download or launch on worker
            choice = messagebox.askyesnocancel(
                "Open Worker File",
                f"File: {name}\n\n• Click 'Yes' to Download & View on your CEO PC\n• Click 'No' to Launch on Worker's screen\n• Click 'Cancel' to abort"
            )
            if choice is True:
                self.download_file_direct(target_path, name)
            elif choice is False:
                self.launch_file_direct(target_path)

    def send_file_to_worker(self):
        if not self.selected_worker_id:
            messagebox.showinfo("Select Worker", "Please select an active worker first.")
            return

        file_path = filedialog.askopenfilename(
            title="Select File / Invoice to Send to Worker",
            filetypes=[
                ("Invoices & Documents", "*.pdf;*.docx;*.xlsx;*.xls;*.csv;*.txt;*.png;*.jpg"),
                ("All Files", "*.*")
            ]
        )
        if not file_path:
            return

        file_name = os.path.basename(file_path)
        target_dir = self.worker_current_path or "DESKTOP"

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
            self.fm_status_lbl.configure(text=f"Uploading '{file_name}'...", text_color="#FBBF24")
            threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()
            messagebox.showinfo("Sending File", f"File '{file_name}' is being sent to worker's folder:\n{target_dir}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {e}")

    def download_selected_file(self):
        if not self.selected_file_item:
            messagebox.showinfo("Select File", "Please select a file from the list first.")
            return
        if self.selected_file_item.get("isDir"):
            messagebox.showinfo("Folder Selected", "Cannot download a folder directly. Please select a file.")
            return

        name = self.selected_file_item.get("name")
        full_path = os.path.join(self.worker_current_path, name)
        self.download_file_direct(full_path, name)

    def download_file_direct(self, full_path, file_name):
        self.fm_status_lbl.configure(text=f"Requesting '{file_name}' from worker...", text_color="#60A5FA")
        payload = {
            "workerId": self.selected_worker_id,
            "action": "download",
            "path": full_path,
            "fileName": file_name
        }
        threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

    def launch_selected_file_on_worker(self):
        if not self.selected_file_item:
            messagebox.showinfo("Select File", "Please select a file or folder from the list first.")
            return

        name = self.selected_file_item.get("name")
        full_path = os.path.join(self.worker_current_path, name)
        self.launch_file_direct(full_path)

    def launch_file_direct(self, full_path):
        payload = {
            "workerId": self.selected_worker_id,
            "action": "launch",
            "path": full_path
        }
        self.fm_status_lbl.configure(text=f"Launching '{os.path.basename(full_path)}' on worker PC...", text_color="#C084FC")
        threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

    def delete_selected_item(self):
        if not self.selected_file_item:
            messagebox.showinfo("Select Item", "Please select a file or folder to delete.")
            return

        name = self.selected_file_item.get("name")
        is_dir = self.selected_file_item.get("isDir", False)
        full_path = os.path.join(self.worker_current_path, name)

        item_type = "folder and all its contents" if is_dir else "file"
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete this {item_type} on the worker's PC?\n\n{full_path}"
        )
        if confirm:
            payload = {
                "workerId": self.selected_worker_id,
                "action": "delete",
                "path": full_path
            }
            self.fm_status_lbl.configure(text=f"Deleting '{name}'...", text_color="#F87171")
            threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

    def create_remote_folder(self):
        if not self.selected_worker_id:
            messagebox.showinfo("Select Worker", "Please select an active worker first.")
            return

        folder_name = simpledialog.askstring("New Remote Folder", "Enter new folder name:")
        if folder_name and folder_name.strip():
            target_dir = self.worker_current_path or "DESKTOP"
            payload = {
                "workerId": self.selected_worker_id,
                "action": "mkdir",
                "path": target_dir,
                "fileName": folder_name.strip()
            }
            self.fm_status_lbl.configure(text=f"Creating folder '{folder_name}'...", text_color="#FBBF24")
            threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

    def _post_file_command(self, payload):
        try:
            self.http_session.post(f"{self.relay_url}/api/files/command", json=payload, timeout=4.0)
        except Exception:
            pass

    def send_file_command(self, action, path="", destination="", fileName="", fileData="", text=""):
        """Sends a high-priority file or guidance control command to worker"""
        if not self.selected_worker_id:
            return
        payload = {
            "workerId": self.selected_worker_id,
            "action": action,
            "path": path,
            "destination": destination,
            "fileName": fileName,
            "fileData": fileData,
            "text": text
        }
        threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

    def file_result_poll_loop(self):
        """High-frequency poller for directory listings, downloads, and operation confirmations"""
        while not self.stop_event.is_set():
            if self.selected_worker_id:
                try:
                    url = f"{self.relay_url}/api/files/result?workerId={self.selected_worker_id}"
                    resp = self.http_session.get(url, timeout=2.5)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("ok"):
                            res = data.get("result", {})
                            action = res.get("action", "")
                            cur_path = res.get("currentPath", "")
                            items = res.get("items", [])
                            file_data = res.get("fileData")
                            file_name = res.get("fileName")
                            status_msg = res.get("statusMessage", "")
                            ts = res.get("timestamp", 0)

                            if ts > self.last_file_sync_time:
                                self.last_file_sync_time = ts
                                
                                # Check if a downloaded file arrived
                                if action == "download" and file_data and file_name:
                                    self.after(0, self.handle_received_file_download, file_name, file_data)
                                elif action in ("list", "upload", "delete", "mkdir", "copy", "move", "list_trash", "empty_trash") or items:
                                    self.after(0, self.update_files_ui, cur_path, items, status_msg)
                                elif status_msg:
                                    self.after(0, lambda m=status_msg: self.fm_status_lbl.configure(text=m))
                except Exception:
                    pass
            time.sleep(0.8)

    def handle_received_file_download(self, file_name, b64_data):
        try:
            raw_bytes = base64.b64decode(b64_data)
            save_path = os.path.join(self.received_files_dir, file_name)
            with open(save_path, "wb") as f:
                f.write(raw_bytes)

            self.fm_status_lbl.configure(
                text=f"Downloaded '{file_name}' ({len(raw_bytes)/1024:.1f} KB)",
                text_color="#10B981"
            )

            # If opened via "View" button, automatically launch default viewer without extra prompt
            if getattr(self, "auto_open_downloaded_file", False):
                self.auto_open_downloaded_file = False
                try:
                    os.startfile(save_path)
                except Exception as e:
                    messagebox.showerror("View Error", f"Could not launch file: {e}")
                return

            # Prompt to open automatically
            ask_open = messagebox.askyesno(
                "File Downloaded",
                f"File '{file_name}' downloaded successfully to:\n{save_path}\n\nDo you want to open it now?"
            )
            if ask_open:
                try:
                    os.startfile(save_path)
                except Exception as e:
                    messagebox.showerror("Open Error", f"Could not launch file: {e}")

        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to save file: {e}")

    def open_folder_direct(self, folder_name):
        """Navigates into clicked folder on worker's PC"""
        full_path = os.path.join(self.worker_current_path, folder_name)
        self.request_browse_folder(full_path)

    def download_and_view_direct(self, file_name):
        """Downloads file and opens it in default viewer on CEO PC"""
        if not self.selected_worker_id:
            return
        full_path = os.path.join(self.worker_current_path, file_name)
        self.fm_status_lbl.configure(text=f"Fetching '{file_name}' for viewing...", text_color="#38BDF8")
        self.auto_open_downloaded_file = True
        self.download_file_direct(full_path, file_name)

    def copy_selected_item(self):
        """Copies currently selected file or folder to clipboard"""
        if not self.selected_file_item:
            messagebox.showinfo("Select Item", "Please select a file or folder from the list first.")
            return
        self.copy_item_direct(self.selected_file_item.get("name"), self.selected_file_item.get("isDir", False))

    def copy_item_direct(self, name, is_dir):
        """Marks file or folder for copying"""
        full_path = os.path.join(self.worker_current_path, name)
        self.file_clipboard = {
            "path": full_path,
            "name": name,
            "op": "copy",
            "isDir": is_dir
        }
        short_name = name if len(name) <= 12 else name[:10] + ".."
        self.paste_btn.configure(
            state="normal",
            text=f"📌 Paste ({short_name})",
            fg_color="#0D9488",
            hover_color="#0F766E"
        )
        self.fm_status_lbl.configure(text=f"Copied '{name}'. Navigate to target folder and click Paste.", text_color="#34D399")

    def cut_selected_item(self):
        """Cuts currently selected file or folder to clipboard for moving"""
        if not self.selected_file_item:
            messagebox.showinfo("Select Item", "Please select a file or folder from the list first.")
            return
        self.cut_item_direct(self.selected_file_item.get("name"), self.selected_file_item.get("isDir", False))

    def cut_item_direct(self, name, is_dir):
        """Marks file or folder for moving (cut)"""
        full_path = os.path.join(self.worker_current_path, name)
        self.file_clipboard = {
            "path": full_path,
            "name": name,
            "op": "cut",
            "isDir": is_dir
        }
        short_name = name if len(name) <= 12 else name[:10] + ".."
        self.paste_btn.configure(
            state="normal",
            text=f"📌 Paste Cut ({short_name})",
            fg_color="#D97706",
            hover_color="#B45309"
        )
        self.fm_status_lbl.configure(text=f"Cut '{name}'. Navigate to target folder and click Paste.", text_color="#FBBF24")

    def paste_item(self):
        """Pastes the copied or cut item into the currently open worker directory"""
        if not self.file_clipboard or not self.selected_worker_id:
            return

        target_dir = self.worker_current_path
        if target_dir == "RECYCLE_BIN":
            messagebox.showwarning("Invalid Destination", "Cannot paste files into the Recycle Bin.")
            return

        src = self.file_clipboard.get("path")
        name = self.file_clipboard.get("name")
        op = self.file_clipboard.get("op", "copy")

        payload = {
            "workerId": self.selected_worker_id,
            "action": "copy" if op == "copy" else "move",
            "path": src,
            "destination": target_dir
        }

        action_desc = "Copying" if op == "copy" else "Moving"
        self.fm_status_lbl.configure(text=f"{action_desc} '{name}' to current folder...", text_color="#38BDF8")
        threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

        if op == "cut":
            self.file_clipboard = None
            self.paste_btn.configure(state="disabled", text="📌 Paste", fg_color="#F1F5F9", text_color="#334155")

    def browse_recycle_bin(self):
        """Navigates to the Windows Recycle Bin view on the worker PC"""
        if not self.selected_worker_id:
            messagebox.showinfo("Select Worker", "Please select an active worker first.")
            return

        payload = {
            "workerId": self.selected_worker_id,
            "action": "list_trash"
        }
        self.fm_status_lbl.configure(text="Querying worker's Recycle Bin...", text_color="#F87171")
        threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

    def empty_recycle_bin(self):
        """Prompts confirmation and empties the Recycle Bin on the worker PC"""
        if not self.selected_worker_id:
            messagebox.showinfo("Select Worker", "Please select an active worker first.")
            return

        confirm = messagebox.askyesno(
            "Empty Recycle Bin",
            "Are you sure you want to permanently empty the Recycle Bin on the worker's PC?\n\nAll discarded files will be permanently erased and cannot be recovered."
        )
        if confirm:
            payload = {
                "workerId": self.selected_worker_id,
                "action": "empty_trash"
            }
            self.fm_status_lbl.configure(text="Emptying worker PC Recycle Bin...", text_color="#F87171")
            threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

    def delete_item_direct(self, name, is_dir):
        """Prompts confirmation and moves file or folder to Recycle Bin on worker's PC"""
        if not self.selected_worker_id:
            messagebox.showinfo("Select Worker", "Please select an active worker first.")
            return

        full_path = os.path.join(self.worker_current_path, name)
        item_type = "folder and all its contents" if is_dir else "file"

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete this {item_type} on the worker's computer?\n\n{name}\n\nPath: {full_path}\n(Item will be placed into the worker's Recycle Bin)"
        )
        if confirm:
            payload = {
                "workerId": self.selected_worker_id,
                "action": "delete",
                "path": full_path
            }
            self.fm_status_lbl.configure(text=f"Deleting '{name}' to Recycle Bin...", text_color="#F87171")
            threading.Thread(target=self._post_file_command, args=(payload,), daemon=True).start()

    def update_files_ui(self, current_path, items, status_msg=""):
        self.worker_current_path = current_path
        self.fm_path_entry.delete(0, "end")
        display_path = "Recycle Bin (Trash)" if current_path == "RECYCLE_BIN" else current_path
        self.fm_path_entry.insert(0, display_path)
        self.selected_file_item = None

        if status_msg:
            self.fm_status_lbl.configure(text=status_msg, text_color="#94A3B8")
        else:
            self.fm_status_lbl.configure(text=f"{len(items)} items in folder", text_color="#94A3B8")

        for widget in self.files_scroll.winfo_children():
            widget.destroy()

        if not items:
            empty_lbl = ctk.CTkLabel(
                self.files_scroll,
                text="Folder or Recycle Bin is empty.",
                font=ctk.CTkFont(size=12),
                text_color="#64748B"
            )
            empty_lbl.pack(pady=40)
            return

        for item in items:
            name = item.get("name", "")
            is_dir = item.get("isDir", False)
            size_bytes = item.get("size", 0)

            # Choose rich icon based on extension
            if is_dir:
                icon = "📁"
                size_str = "<DIR>"
            else:
                ext = os.path.splitext(name)[1].lower()
                if ext in (".pdf",): icon = "📑"
                elif ext in (".xlsx", ".xls", ".csv"): icon = "📊"
                elif ext in (".docx", ".doc", ".txt"): icon = "📝"
                elif ext in (".png", ".jpg", ".jpeg", ".bmp"): icon = "🖼️"
                elif ext in (".zip", ".rar", ".7z", ".tar"): icon = "📦"
                elif ext in (".exe", ".bat", ".cmd"): icon = "⚙️"
                else: icon = "📄"
                size_str = f"{size_bytes / 1024:.1f} KB" if size_bytes > 0 else "0 KB"

            row = ctk.CTkFrame(self.files_scroll, fg_color="#FFFFFF", border_color="#E2E8F0", border_width=1, corner_radius=6, cursor="hand2")
            row.pack(fill="x", pady=2, padx=4)

            # Left side: Icon + Name
            btn_text = f"{icon}  {name}"
            lbl = ctk.CTkLabel(
                row,
                text=btn_text,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold" if is_dir else "normal"),
                text_color="#0F172A" if is_dir else "#334155"
            )
            lbl.pack(side="left", padx=10, pady=6)

            # Right side actions: [Delete] [Cut] [Copy] [View / Open] [Size]
            del_btn = ctk.CTkButton(
                row,
                text="🗑️",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color="#FEE2E2",
                hover_color="#FECACA",
                text_color="#DC2626",
                border_color="#FCA5A5",
                border_width=1,
                width=36,
                height=26,
                corner_radius=4,
                command=lambda nm=name, d=is_dir: self.delete_item_direct(nm, d)
            )
            del_btn.pack(side="right", padx=(2, 6), pady=5)

            if current_path != "RECYCLE_BIN":
                cut_btn = ctk.CTkButton(
                    row,
                    text="✂️",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    fg_color="#F1F5F9",
                    hover_color="#E2E8F0",
                    text_color="#475569",
                    border_color="#CBD5E1",
                    border_width=1,
                    width=34,
                    height=26,
                    corner_radius=4,
                    command=lambda nm=name, d=is_dir: self.cut_item_direct(nm, d)
                )
                cut_btn.pack(side="right", padx=2, pady=5)

                cp_btn = ctk.CTkButton(
                    row,
                    text="📋",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    fg_color="#F1F5F9",
                    hover_color="#E2E8F0",
                    text_color="#475569",
                    border_color="#CBD5E1",
                    border_width=1,
                    width=34,
                    height=26,
                    corner_radius=4,
                    command=lambda nm=name, d=is_dir: self.copy_item_direct(nm, d)
                )
                cp_btn.pack(side="right", padx=2, pady=5)

                if is_dir:
                    view_btn = ctk.CTkButton(
                        row,
                        text="📂 Open",
                        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                        fg_color="#EFF6FF",
                        hover_color="#DBEAFE",
                        text_color="#2563EB",
                        border_color="#93C5FD",
                        border_width=1,
                        width=66,
                        height=26,
                        corner_radius=4,
                        command=lambda nm=name: self.open_folder_direct(nm)
                    )
                else:
                    view_btn = ctk.CTkButton(
                        row,
                        text="👁️ View",
                        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                        fg_color="#ECFDF5",
                        hover_color="#D1FAE5",
                        text_color="#059669",
                        border_color="#6EE7B7",
                        border_width=1,
                        width=66,
                        height=26,
                        corner_radius=4,
                        command=lambda nm=name: self.download_and_view_direct(nm)
                    )
                view_btn.pack(side="right", padx=2, pady=5)

            size_lbl = ctk.CTkLabel(
                row,
                text=size_str,
                font=ctk.CTkFont(size=11),
                text_color="#64748B",
                width=65,
                anchor="e"
            )
            size_lbl.pack(side="right", padx=(6, 8), pady=5)

            # Bind single click to select and double click to enter or open
            row.bind("<Button-1>", lambda e, it=item, r=row: self.select_file_item(it, r))
            lbl.bind("<Button-1>", lambda e, it=item, r=row: self.select_file_item(it, r))
            size_lbl.bind("<Button-1>", lambda e, it=item, r=row: self.select_file_item(it, r))

            if current_path != "RECYCLE_BIN":
                row.bind("<Double-Button-1>", lambda e, it=item: self.on_item_double_click(it))
                lbl.bind("<Double-Button-1>", lambda e, it=item: self.on_item_double_click(it))

    # --- Live Interactive Guidance & Audio Intercom ---
    def toggle_live_notepad(self):
        """Toggles real-time interactive Notepad on worker PC"""
        if not self.selected_worker_id:
            return
        self.live_notepad_active = not self.live_notepad_active
        if self.live_notepad_active:
            self.guidance_toggle_btn.configure(
                text="⏹ Stop Live Notepad",
                fg_color="#EF4444",
                hover_color="#DC2626"
            )
            initial_text = self.guidance_input.get().strip()
            self.last_guidance_sent = initial_text
            self.dispatch_guidance_session(active=True, text=initial_text)
            self.send_file_command("notepad_open", text=initial_text)
        else:
            self.guidance_toggle_btn.configure(
                text="▶ Start Live Notepad",
                fg_color="#10B981",
                hover_color="#059669"
            )
            if self._guidance_typing_timer is not None:
                try:
                    self.after_cancel(self._guidance_typing_timer)
                except Exception:
                    pass
                self._guidance_typing_timer = None
            self.dispatch_guidance_session(active=False, text="")
            self.send_file_command("notepad_close")

    def on_guidance_typing(self, event=None):
        """Debounced live streaming of CEO keystrokes into worker's Notepad when active"""
        if not self.live_notepad_active or not self.selected_worker_id:
            return

        if self._guidance_typing_timer is not None:
            try:
                self.after_cancel(self._guidance_typing_timer)
            except Exception:
                pass
            self._guidance_typing_timer = None

        def _delayed_sync():
            self._guidance_typing_timer = None
            if not self.live_notepad_active or not self.selected_worker_id:
                return
            text = self.guidance_input.get()
            if text != self.last_guidance_sent:
                self.last_guidance_sent = text
                self.dispatch_guidance_session(active=True, text=text)
                self.send_file_command("notepad_update", text=text)

        self._guidance_typing_timer = self.after(250, _delayed_sync)

    def dispatch_guidance_session(self, active=True, text=""):
        if not self.selected_worker_id:
            return
        worker_id = self.selected_worker_id
        relay_url = self.relay_url

        def _task():
            try:
                self.http_session.post(
                    f"{relay_url}/api/stream/session",
                    json={
                        "workerId": worker_id,
                        "guidanceNotepadActive": active,
                        "guidanceMessage": text
                    },
                    timeout=2.0
                )
            except Exception:
                pass

        threading.Thread(target=_task, daemon=True).start()

    def send_guidance(self):
        """Dispatches guidance note to worker immediately"""
        instruction = self.guidance_input.get().strip()
        if not instruction or not self.selected_worker_id:
            return

        is_notepad = self.live_notepad_active
        self.last_guidance_sent = instruction

        if is_notepad:
            self.dispatch_guidance_session(active=True, text=instruction)
            self.send_file_command("notepad_update", text=instruction)
        else:
            self.dispatch_guidance_session(active=False, text=instruction)
            self.send_file_command("notepad_update", text=instruction)
            self.guidance_input.delete(0, "end")

    def toggle_worker_mic(self):
        """Toggles listening to Worker's PC / Phone microphone"""
        if not self.selected_worker_id:
            return
        self.worker_mic_active = not self.worker_mic_active
        worker_id = self.selected_worker_id
        relay_url = self.relay_url

        if self.worker_mic_active:
            self.worker_mic_btn.configure(
                text="🎧 Worker Mic: ON",
                fg_color="#10B981",
                hover_color="#059669"
            )
            threading.Thread(target=self.worker_audio_listener_loop, daemon=True).start()
        else:
            self.worker_mic_btn.configure(
                text="🎧 Worker Mic: OFF",
                fg_color="#334155",
                hover_color="#475569"
            )

        def _task():
            try:
                self.http_session.post(
                    f"{relay_url}/api/stream/session",
                    json={
                        "workerId": worker_id,
                        "workerMicActive": self.worker_mic_active
                    },
                    timeout=2.0
                )
            except Exception:
                pass

        threading.Thread(target=_task, daemon=True).start()

    def worker_audio_listener_loop(self):
        """Polls worker's microphone stream from relay and plays through CEO speakers"""
        fs = 16000
        while self.worker_mic_active and self.selected_worker_id:
            if sd is None:
                time.sleep(0.4)
                continue
            try:
                url = f"{self.relay_url}/api/audio/stream?workerId={self.selected_worker_id}&channel=worker_to_ceo&afterSeq={self.last_worker_audio_seq}"
                resp = self.http_session.get(url, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    packets = data.get("packets", [])
                    for p in packets:
                        seq = p.get("seq", 0)
                        if seq > self.last_worker_audio_seq:
                            self.last_worker_audio_seq = seq
                            b64 = p.get("chunk", "")
                            if b64:
                                raw = base64.b64decode(b64)
                                samples = np.frombuffer(raw, dtype=np.int16)
                                sd.play(samples, samplerate=fs)
                                sd.wait()
                time.sleep(0.04)
            except Exception:
                time.sleep(0.3)

    def toggle_ceo_mic(self):
        """Toggles speaking to Worker via CEO's microphone"""
        if not self.selected_worker_id:
            return
        self.ceo_mic_active = not self.ceo_mic_active
        worker_id = self.selected_worker_id
        relay_url = self.relay_url

        if self.ceo_mic_active:
            self.ceo_mic_btn.configure(
                text="🎙️ Speak: LIVE",
                fg_color="#EF4444",
                hover_color="#DC2626"
            )
            threading.Thread(target=self.ceo_audio_speaker_loop, daemon=True).start()
        else:
            self.ceo_mic_btn.configure(
                text="🎙️ Speak: OFF",
                fg_color="#334155",
                hover_color="#475569"
            )

        def _task():
            try:
                self.http_session.post(
                    f"{relay_url}/api/stream/session",
                    json={
                        "workerId": worker_id,
                        "ceoMicActive": self.ceo_mic_active
                    },
                    timeout=2.0
                )
            except Exception:
                pass

        threading.Thread(target=_task, daemon=True).start()

    def ceo_audio_speaker_loop(self):
        """Records CEO's microphone and streams voice packets to worker's speakers in real time"""
        fs = 16000
        chunk_samples = int(fs * 0.25) # 250ms chunks
        while self.ceo_mic_active and self.selected_worker_id:
            if sd is None:
                time.sleep(0.4)
                continue
            try:
                rec = sd.rec(chunk_samples, samplerate=fs, channels=1, dtype="int16")
                sd.wait()
                raw_bytes = rec.tobytes()
                b64 = base64.b64encode(raw_bytes).decode("ascii")

                payload = {
                    "workerId": self.selected_worker_id,
                    "channel": "ceo_to_worker",
                    "chunk": b64
                }
                self.http_session.post(f"{self.relay_url}/api/audio/stream", json=payload, timeout=2.0)
            except Exception:
                time.sleep(0.3)

    # --- Ultra-Fast Asynchronous Frame Streaming Loop ---
    def frame_receiver_loop(self):
        """Pulls frames via Keep-Alive HTTP and performs OpenCV resize in background thread"""
        while self.is_monitoring and not self.stop_event.is_set():
            if not self.selected_worker_id:
                time.sleep(0.08)
                continue
            try:
                frame_url = f"{self.relay_url}/api/stream/frame?workerId={self.selected_worker_id}"
                resp = self.http_session.get(frame_url, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    b64_frame = data.get("frame")
                    ts = data.get("timestamp", 0)

                    # Only process if this is a fresh frame
                    if b64_frame and ts != self.last_frame_timestamp:
                        self.last_frame_timestamp = ts
                        img_bytes = base64.b64decode(b64_frame)

                        # SIMD C++ JPEG decoding using OpenCV
                        np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
                        cv_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                        if cv_img is not None:
                            self.latest_cv_frame = cv_img

                            # Save to video if recording
                            if self.is_recording:
                                self.write_frame_to_video(cv_img)

                            # If streaming view is active, calculate canvas resize in background thread
                            if self.active_view == "stream":
                                cw = max(400, self.screen_canvas.winfo_width())
                                ch = max(300, self.screen_canvas.winfo_height())
                                
                                ih, iw = cv_img.shape[:2]
                                img_ratio = iw / float(ih)
                                canvas_ratio = cw / float(ch)

                                if canvas_ratio > img_ratio:
                                    nh = ch - 6
                                    nw = int(nh * img_ratio)
                                else:
                                    nw = cw - 6
                                    nh = int(nw / img_ratio)

                                nw = max(10, nw)
                                nh = max(10, nh)
                                ox = (cw - nw) // 2
                                oy = (ch - nh) // 2

                                # Fast SIMD resize in background thread
                                resized_bgr = cv2.resize(cv_img, (nw, nh), interpolation=cv2.INTER_LINEAR)
                                rgb_frame = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)
                                pil_img = Image.fromarray(rgb_frame)
                                photo = ImageTk.PhotoImage(pil_img)

                                # Zero-latency latest-frame scheduling (drops stale backlog immediately)
                                self.pending_render_data = (photo, ox, oy, nw, nh)
                                if not self.is_render_scheduled:
                                    self.is_render_scheduled = True
                                    self.after(0, self._render_latest_frame)

                                self.fps_count += 1
                                now = time.time()
                                if now - self.last_fps_time >= 1.0:
                                    self.current_fps = self.fps_count
                                    self.fps_count = 0
                                    self.last_fps_time = now
                                    if not self.is_recording:
                                        self.after(0, lambda: self.vp_fps_badge.configure(text=f"{self.current_fps} FPS (Live)"))

                time.sleep(0.035)
            except Exception:
                time.sleep(0.2)

    def _render_latest_frame(self):
        self.is_render_scheduled = False
        if self.pending_render_data:
            photo, ox, oy, nw, nh = self.pending_render_data
            self.pending_render_data = None
            self.render_frame_on_canvas(photo, ox, oy, nw, nh)

    def render_frame_on_canvas(self, photo, ox, oy, nw, nh):
        """Runs on main thread: instant 0-cost image update via persistent canvas handle"""
        if self.active_view != "stream":
            return

        self.current_photo = photo
        self.image_display_rect = (ox, oy, nw, nh)

        if self.canvas_placeholder:
            try:
                self.screen_canvas.delete(self.canvas_placeholder)
                self.canvas_placeholder = None
            except Exception:
                pass

        if self.canvas_img_id is None:
            self.canvas_img_id = self.screen_canvas.create_image(ox, oy, anchor="nw", image=photo)
        else:
            self.screen_canvas.coords(self.canvas_img_id, ox, oy)
            self.screen_canvas.itemconfig(self.canvas_img_id, image=photo)

    def on_closing(self):
        if self.is_recording:
            self.stop_recording_and_save()
        self.stop_event.set()
        self.destroy()

if __name__ == "__main__":
    app = CEOAdminApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
