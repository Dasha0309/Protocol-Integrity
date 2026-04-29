import math
import os
import queue
import re
import threading
import time
import wave
from datetime import datetime
from pathlib import Path
import tkinter as tk

import customtkinter as ctk

from app_config import COLORS, RECORDINGS_DIR
from app_services import ChimegeSTT, EncryptionModule, GeminiService
from app_utils import (
    attach_audio_to_meeting,
    create_or_get_draft,
    save_transcript_results,
    store_audio_on_blockchain,
)

_ACCENT = "#7C5CFC"
_DANGER = "#E05555"
_BG     = "#F5F5F7"

class RecordPage(ctk.CTkFrame):
    def __init__(self, parent, draft_data: dict | None = None, on_completed=None):
        super().__init__(parent, fg_color=_BG)

        self._draft_id    = None
        self._draft_title = ""
        self._on_completed = on_completed  # called after audio upload pipeline finishes

        # ── Audio state ──────────────────────────────────────────
        self._recording = False
        self._paused    = False
        self._processing = False
        self._elapsed   = 0
        self._frames: list        = []
        self._audio_filename: str | None = None
        self._rec_thread: threading.Thread | None = None
        self._level_q   = queue.Queue()
        self._wave_levels = [0.0] * 60
        self._phase     = 0.0
        self._timer_job = None
        self._wave_job  = None
        self._audio_status_lbl = None
        self._processing_btn   = None

        if draft_data:
            # Draft-аас шууд аудио view-д орно
            self._draft_id    = draft_data.get("id")
            self._draft_title = draft_data.get("title", "")
            self._build_audio_view()
        else:
            self._build_form()

    # FORM VIEW

    def _build_form(self):
        ctk.CTkLabel(
            self, text="Хурлын бүртгэл",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color="#1A1A1A",
        ).pack(anchor="w", padx=36, pady=(26, 14))

        card = ctk.CTkFrame(
            self, fg_color="#FFFFFF", corner_radius=14,
            border_width=1, border_color="#E0E0E0",
        )
        card.pack(fill="both", expand=True, padx=234, pady=(0, 14))

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=18)

        self.title_e       = self._field(body, "Хурлын гарчиг",  "Хурлын тайлангийн гарчиг")
        self.date_e        = self._field(body, "Хурлын огноо", "")
        self.date_e.insert(0, datetime.now().strftime("%Y/%m/%d"))
        self.date_e.configure(state="readonly", fg_color="#F1F3F5", text_color="#6C757D")
        self.participant_e = self._field(body, "Хуралд оролцогчид", "Оролцогчдын нэрсийг зай аван бичнэ үү")
        self.count_e       = self._field(body, "Оролцогчдын тоо", "0")
        # Count is auto-derived from participant names → readonly, grey
        self.count_e.configure(state="readonly", fg_color="#F1F3F5", text_color="#6C757D")
        # Live update count whenever participant field changes
        self.participant_e.bind("<KeyRelease>", lambda _e: self._recount_participants())
        self.goal_e        = self._field(body, "Хурлын зорилго товч агуулга", "")
        self.pass_e        = self._field(
            body, "Хурлын нууцлалыг тайлах нууц үг оруулна уу !", "", show="*"
        )

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=234, pady=(4, 24))

        ctk.CTkButton(
            btn_row, text="ЦУЦЛАХ", width=130, height=44, corner_radius=22,
            fg_color="#EAEAEA", hover_color="#D8D8D8", text_color="#DA3636",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_cancel,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text="Жишиг хадгалах", width=130, height=44, corner_radius=22,
            fg_color=_ACCENT, hover_color="#6344E8", text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_save,
        ).pack(side="right")

        self._status_lbl = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=12), text_color="#666666"
        )
        self._status_lbl.pack(anchor="w", padx=234, pady=(0, 12))

    def _field(self, parent, label: str, placeholder: str = "", show: str = None):
        ctk.CTkLabel(
            parent, text=label,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1A1A1A",
        ).pack(anchor="w", pady=(9, 4))
        e = ctk.CTkEntry(
            parent, placeholder_text=placeholder, show=show or "",
            height=44, corner_radius=12, fg_color="#FFFFFF",
            border_color="#D5D5D5", text_color="#1A1A1A",
            font=ctk.CTkFont(size=13),
        )
        e.pack(fill="x")
        return e

    # ── Participant helpers ───────────────────────────────────
    @staticmethod
    def _count_participants(text: str) -> int:
        """Count participants — split by comma or whitespace, ignore empties."""
        if not text or not text.strip():
            return 0
        tokens = [t for t in re.split(r"[,\s]+", text.strip()) if t]
        return len(tokens)

    def _set_count(self, n: int):
       
        self.count_e.configure(state="normal")
        self.count_e.delete(0, "end")
        self.count_e.insert(0, str(n))
        self.count_e.configure(state="readonly")

    def _recount_participants(self):
        self._set_count(self._count_participants(self.participant_e.get()))

    def _on_cancel(self):
        for e in (self.title_e, self.participant_e, self.goal_e, self.pass_e):
            e.delete(0, "end")
        self._set_count(0)

    def _on_save(self):
        title = self.title_e.get().strip()
        if not title:
            self._status_lbl.configure(
                text="Хурлын гарчиг оруулна уу.", text_color="#C53030"
            )
            return

        date              = datetime.now().strftime("%Y/%m/%d")
        participants_raw  = self.participant_e.get().strip()
        participant_count = self._count_participants(participants_raw)

        # Encrypt participant names (RSA-OAEP). If encryption unavailable
        # (cryptography not installed), fall back to plaintext storage.
        participants_stored = participants_raw
        participants_encrypted = False
        if participants_raw:
            try:
                participants_stored = EncryptionModule.encrypt_sensitive_value(
                    participants_raw
                )
                participants_encrypted = True
            except Exception as exc:
                self._status_lbl.configure(
                    text=f"Оролцогчдыг шифрлэж чадсангүй: {exc}",
                    text_color="#C53030",
                )
                return

        draft_id, _ = create_or_get_draft(
            title=title,
            date=date,
            participants=participants_stored,
            participant_count=participant_count,
            participants_encrypted=participants_encrypted,
            description=self.goal_e.get().strip(),
            password=self.pass_e.get(),
        )
        self._draft_id    = draft_id
        self._draft_title = title
        self._switch_to_audio()

    # AUDIO VIEW

    def _switch_to_audio(self):
        for w in self.winfo_children():
            w.destroy()
        self._build_audio_view()

    def _build_audio_view(self):
   
        ctk.CTkLabel(
            self, text="Хурлын бүртгэл",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#1A1A1A",
        ).pack(anchor="w", padx=120, pady=(26, 0))

        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        if self._draft_title:
            name_text, name_color = self._draft_title, "#444444"
        else:
            name_text, name_color = "Энэ хэсэгт хурлын гарчиг орж ирнэ", "#8A8A8A"
        ctk.CTkLabel(
            self, text=name_text,
            font=ctk.CTkFont(size=18),
            text_color=name_color,
        ).pack(anchor="center")

        # ── Audio card (narrower, centered) ──────────────────────
        card_wrap = ctk.CTkFrame(self, fg_color="transparent")
        card_wrap.pack(anchor="center", pady=(28, 0))

        card = ctk.CTkFrame(
            card_wrap, fg_color="#FFFFFF", corner_radius=14,
            border_width=1, border_color=_ACCENT, width=900, height=100,
        )
        card.pack()
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=22, pady=10)

        # Waveform + timer row
        wave_row = tk.Frame(inner, bg="#FFFFFF")
        wave_row.pack(fill="x")

        self._canvas = tk.Canvas(
            wave_row, height=20, bg="#FFFFFF", highlightthickness=0
        )
        self._canvas.pack(side="left", fill="x", expand=True)

        self._time_lbl = ctk.CTkLabel(
            wave_row, text="00:00",
            font=ctk.CTkFont(family="Courier New", size=12),
            text_color="#888888", width=44, bg_color="#FFFFFF",
        )
        self._time_lbl.pack(side="right", padx=(8, 0))

        # ── Button row (3 equal columns: left ghost / center pill / right sparkle)
        btn_row = tk.Frame(inner, bg="#FFFFFF")
        btn_row.pack(fill="x", pady=(8, 0))
        btn_row.grid_columnconfigure(0, weight=1, uniform="btns")
        btn_row.grid_columnconfigure(1, weight=1, uniform="btns")
        btn_row.grid_columnconfigure(2, weight=1, uniform="btns")

        # Left: ghost buttons
        left_f = tk.Frame(btn_row, bg="#FFFFFF")
        left_f.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            left_f, text="↑  аудио оруулах", fg_color="transparent",
            hover_color="#F0F0F0", text_color="#555555",
            font=ctk.CTkFont(size=12), height=30, width=125,
            command=self._upload_audio,
        ).pack(side="left", padx=(0, 4))

        self._mic_btn = ctk.CTkButton(
            left_f, text="🎙  мик хаах", fg_color="transparent",
            hover_color="#F0F0F0", text_color="#555555",
            font=ctk.CTkFont(size=12), height=30, width=100,
            command=self._toggle_mic,
        )
        self._mic_btn.pack(side="left")

        # Center: action buttons (geometrically centered)
        self._btn_box = tk.Frame(btn_row, bg="#FFFFFF")
        self._btn_box.grid(row=0, column=1)

        # Right: star emoji
        right_f = tk.Frame(btn_row, bg="#FFFFFF")
        right_f.grid(row=0, column=2, sticky="e")
        ctk.CTkLabel(
            right_f, text="✦",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#4F7BF3", bg_color="#FFFFFF",
        ).pack(padx=4)

        # Gradient pill: Эхлэх
        self._start_btn = self._make_gradient_pill(
            self._btn_box, 170, 34, "Эхлэх", self._start_recording
        )
        self._start_btn.pack(side="left")

        # Pre-build pause + finish (hidden initially)
        self._pause_btn = ctk.CTkButton(
            self._btn_box, text="⏸  Түр зогсоох",
            width=140, height=34, corner_radius=17,
            fg_color="#B0B0B0", hover_color="#9A9A9A", text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_pause,
        )
        self._finish_btn = ctk.CTkButton(
            self._btn_box, text="■  Дуусгах",
            width=110, height=34, corner_radius=17,
            fg_color=_DANGER, hover_color="#C03030", text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._stop_recording,
        )

        # ── Status text under the card (processing progress / errors) ────
        self._audio_status_lbl = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=12),
            text_color="#666666",
        )
        self._audio_status_lbl.pack(pady=(10, 0))

        # ── Bottom spacer ─────────────────────────────────────────
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # Kick off idle waveform animation
        self._wave_job = self.after(30, self._tick_wave)

    def _make_gradient_pill(self, parent, width: int, height: int, text: str, command):
        """Canvas-based gradient pill button (purple → blue)."""
        bg_color = "#FFFFFF"
        canvas = tk.Canvas(
            parent, width=width, height=height, bg=bg_color,
            highlightthickness=0, cursor="hand2",
        )
        img = tk.PhotoImage(width=width, height=height)
        r = height / 2
        c1 = (0x4F, 0x52, 0xF0)  # left: indigo/blue
        c2 = (0xB2, 0x67, 0xCE)  # right: purple
        for y in range(height):
            row = []
            for x in range(width):
                if x < r:
                    cx, cy = r, r
                    if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 > r * r:
                        row.append(bg_color)
                        continue
                elif x >= width - r:
                    cx, cy = width - r, r
                    if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 > r * r:
                        row.append(bg_color)
                        continue
                t = x / max(width - 1, 1)
                rv = int(c1[0] + t * (c2[0] - c1[0]))
                gv = int(c1[1] + t * (c2[1] - c1[1]))
                bv = int(c1[2] + t * (c2[2] - c1[2]))
                row.append(f"#{rv:02x}{gv:02x}{bv:02x}")
            img.put("{" + " ".join(row) + "}", to=(0, y))

        canvas.create_image(0, 0, anchor="nw", image=img)
        canvas.create_text(
            width / 2, height / 2, text=text, fill="#FFFFFF",
            font=("Segoe UI", 12, "bold"),
        )
        canvas._gradient_img = img  # prevent GC
        canvas.bind("<Button-1>", lambda e: command())
        return canvas

    def _draw_sparkle(self, canvas: tk.Canvas, size: int, bg: str = _BG):
     
        cx = cy = size / 2
        R  = size * 0.46   # outer tip distance
        r  = size * 0.09   # inner concave distance

        N = 200
        star_pts = []
        for k in range(N):
            theta = 2 * math.pi * k / N
            r_eff = r + (R - r) * (math.cos(2 * theta)) ** 2
            star_pts.append((cx + r_eff * math.cos(theta),
                             cy + r_eff * math.sin(theta)))

        def _in_star(px: float, py: float) -> bool:
            """Ray-casting point-in-polygon test."""
            inside = False
            n = len(star_pts)
            j = n - 1
            for i in range(n):
                xi, yi = star_pts[i]
                xj, yj = star_pts[j]
                if (yi > py) != (yj > py):
                    if px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                        inside = not inside
                j = i
            return inside

        img = tk.PhotoImage(width=size, height=size)
        # Gemini-style: vivid blue body with soft purple highlight in top-right
        blue   = (0x1F, 0x5E, 0xF0)  # dominant blue
        purple = (0xA7, 0x8B, 0xE6)  # upper-right highlight
        for y in range(size):
            row = []
            for x in range(size):
                if _in_star(x + 0.5, y + 0.5):
                    # top-right brightness: 1 at top-right corner, 0 at bottom-left
                    tr = (x / max(size - 1, 1) + (1 - y / max(size - 1, 1))) * 0.5
                    # skew so blue dominates most of the shape
                    t = max(0.0, min(1.0, (tr - 0.55) / 0.45)) ** 1.5
                    rv = int(blue[0] + t * (purple[0] - blue[0]))
                    gv = int(blue[1] + t * (purple[1] - blue[1]))
                    bv = int(blue[2] + t * (purple[2] - blue[2]))
                    row.append(f"#{rv:02x}{gv:02x}{bv:02x}")
                else:
                    row.append(bg)
            img.put("{" + " ".join(row) + "}", to=(0, y))

        canvas.create_image(0, 0, anchor="nw", image=img)
        canvas._sparkle_img = img   # prevent GC

    # RECORDING LOGIC

    def _auto_filename(self) -> str:
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in self._draft_title
        )[:40]
        return str(Path(RECORDINGS_DIR) / f"meeting_{safe}_{ts}.wav")

    def _start_recording(self):
        try:
            import pyaudio  # noqa: F401
        except ImportError:
            return

        self._audio_filename = self._auto_filename()
        self._frames  = []
        self._elapsed = 0
        self._paused  = False
        self._recording = True

        # Swap: Эхлэх → Түр зогсоох + Дуусгах
        self._start_btn.pack_forget()
        self._pause_btn.pack(side="left", padx=(0, 6))
        self._finish_btn.pack(side="left")

        self._rec_thread = threading.Thread(target=self._record_worker, daemon=True)
        self._rec_thread.start()
        self._tick_timer()

    def _record_worker(self):
        import pyaudio
        import numpy as np

        CHUNK = 1024
        RATE  = 44100
        p = pyaudio.PyAudio()
        try:
            st = p.open(
                format=pyaudio.paInt16, channels=1, rate=RATE,
                input=True, frames_per_buffer=CHUNK,
            )
        except Exception:
            p.terminate()
            return

        while self._recording:
            if not self._paused:
                data = st.read(CHUNK, exception_on_overflow=False)
                self._frames.append(data)
                arr   = np.frombuffer(data, dtype=np.int16)
                level = min(float(np.abs(arr).mean()) / 3000.0, 1.0)
                try:
                    self._level_q.put_nowait(level)
                except queue.Full:
                    pass
            else:
                time.sleep(0.05)

        st.stop_stream()
        st.close()

        if self._audio_filename and self._frames:
            wf = wave.open(self._audio_filename, "wb")
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(RATE)
            wf.writeframes(b"".join(self._frames))
            wf.close()

        p.terminate()

    def _stop_recording(self):
        if not self._recording:
            return
        # Flip the flag first so the worker loop exits and the WAV
        # file gets flushed to disk. We deliberately do NOT call
        # attach_audio_to_meeting here — the file isn't on disk yet
        # because the worker writes it AFTER the loop exits, and
        # the previous version had a race where the meeting record
        # pointed at a non-existent path.
        self._recording = False

        if self._timer_job:
            self.after_cancel(self._timer_job)
            self._timer_job = None

        self._elapsed = 0
        self._time_lbl.configure(text="00:00")
        self._mic_btn.configure(text="🎙  мик хаах")

        # Hide recording controls; _start_processing (called once the
        # WAV is on disk) will show the busy "Аудио файл боловсруулж
        # байна…" pill in their place.
        self._pause_btn.pack_forget()
        self._finish_btn.pack_forget()
        self._start_btn.pack_forget()

        audio_path = self._audio_filename
        rec_thread = self._rec_thread
        if not audio_path:
            # Edge case: user hit Дуусгах without ever recording — just
            # restore the idle state.
            self._start_btn.configure(text="Эхлэх")
            self._start_btn.pack(side="left")
            return

        # Immediate feedback so the gap between Дуусгах and the start
        # of STT processing isn't a silent void.
        if self._audio_status_lbl is not None:
            self._audio_status_lbl.configure(
                text="Аудио файлыг хадгалж байна…",
                text_color="#666666",
            )

        def _await_and_process():
            # Block until the recording worker has flushed the WAV
            # file, then schedule the rest on the UI thread.
            if rec_thread is not None:
                rec_thread.join(timeout=15)
            if not os.path.exists(audio_path):
                self.after(
                    0,
                    self._on_process_error,
                    "Аудио файл хадгалагдсангүй. "
                    "Микрофоны зөвшөөрөл болон драйверыг шалгана уу.",
                )
                return
            self.after(0, self._begin_recorded_processing, audio_path)

        threading.Thread(target=_await_and_process, daemon=True).start()

    def _begin_recorded_processing(self, path: str):
        """Runs on the UI thread once the recording worker has flushed
        the WAV file. Attaches the audio to the draft, then kicks off
        the same Chimege/Gemini/blockchain pipeline used by uploads."""
        if self._draft_id:
            attach_audio_to_meeting(self._draft_id, path, source="recorded")
        self._audio_filename = path
        self._start_processing(path)

    def _toggle_pause(self):
        self._paused = not self._paused
        self._pause_btn.configure(
            text="▶  Үргэлжлүүлэх" if self._paused else "⏸  Түр зогсоох"
        )

    def _toggle_mic(self):
        if not self._recording:
            return
        self._paused = not self._paused
        self._mic_btn.configure(
            text="🔇  мик нээх" if self._paused else "🎙  мик хаах"
        )
        self._pause_btn.configure(
            text="▶  Үргэлжлүүлэх" if self._paused else "⏸  Түр зогсоох"
        )

    def _upload_audio(self):
        # Prevent uploads while recording or while another file is processing
        if self._recording or self._processing:
            return

        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Аудио файл сонгох",
            filetypes=[
                ("Аудио файлууд", "*.wav *.mp3 *.ogg *.flac *.m4a"),
                ("Бүгд", "*.*"),
            ],
        )
        if not path:
            return
        if not self._draft_id:
            if self._audio_status_lbl is not None:
                self._audio_status_lbl.configure(
                    text="Ноорогийн ID олдсонгүй — хуудсыг дахин нээнэ үү.",
                    text_color="#C53030",
                )
            return

        attach_audio_to_meeting(self._draft_id, path, source="uploaded")
        self._audio_filename = path
        self._start_processing(path)

    # ── Upload processing pipeline (Chimege → Gemini) ─────────
    def _start_processing(self, path: str):
        """Swap the Эхлэх button into a busy indicator and kick off
        transcription + redaction in a background thread."""
        self._processing = True

        # Hide recording-related buttons
        self._start_btn.pack_forget()
        self._pause_btn.pack_forget()
        self._finish_btn.pack_forget()

        # Build processing indicator pill if not already built
        if self._processing_btn is None:
            self._processing_btn = ctk.CTkButton(
                self._btn_box,
                text="⟳  Аудио файл боловсруулж байна…",
                width=280, height=34, corner_radius=17,
                fg_color="#888888", hover_color="#888888",
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=12, weight="bold"),
                state="disabled",
            )
        self._processing_btn.pack(side="left")

        if self._audio_status_lbl is not None:
            self._audio_status_lbl.configure(
                text="Хурлын дууг бичвэрлүү хөрвүүлж байна…",
                text_color="#666666",
            )

        threading.Thread(
            target=self._process_worker, args=(path,), daemon=True,
        ).start()

    def _process_worker(self, path: str):
        # 0. Pre-flight: make sure both services are configured so we fail
        #    loudly instead of silently storing the error text as transcript.
        stt = ChimegeSTT()
        if not stt.token:
            self.after(
                0, self._on_process_error,
                "Chimege API token тохируулаагүй байна. "
                "~/.protocol_integrity/env.json эсвэл CHIMEGE_TOKEN "
                "орчны хувьсагчид тохируулна уу.",
            )
            return
        gem_svc = GeminiService()
        if not gem_svc.api_key:
            self.after(
                0, self._on_process_error,
                "Gemini API key тохируулаагүй байна. "
                "~/.protocol_integrity/env.json эсвэл GEMINI_API_KEY "
                "орчны хувьсагчид тохируулна уу.",
            )
            return

        # 1. Load the file
        try:
            with open(path, "rb") as f:
                audio_bytes = f.read()
        except Exception as exc:
            self.after(0, self._on_process_error, f"Файл унших алдаа: {exc}")
            return

        # 2. Chimege STT
        try:
            transcript = stt.transcribe(audio_bytes)
        except Exception as exc:
            self.after(0, self._on_process_error, f"Chimege алдаа: {exc}")
            return
        # ChimegeSTT embeds errors in bracketed strings, e.g.
        # "[Chimege алдаа: 403] API token is missing." — any string
        # starting with '[' is treated as an error, not a transcript.
        if not transcript or not transcript.strip():
            self.after(0, self._on_process_error, "Текст буцаагдсангүй")
            return
        if transcript.lstrip().startswith("["):
            self.after(0, self._on_process_error, transcript.strip())
            return

        # 3. Inform user we're moving to Gemini
        self.after(
            0,
            lambda: self._audio_status_lbl
            and self._audio_status_lbl.configure(
                text="Хиймэл оюун ухаанаар нууц мэдээллийг ялгаж байна…",
                text_color="#666666",
            ),
        )

        # 4. Gemini redaction
        try:
            gem = gem_svc.process_transcript(transcript)
        except Exception as exc:
            self.after(0, self._on_process_error, f"Gemini алдаа: {exc}")
            return
        # Detect Gemini-reported failures in the returned dict
        report_text = (gem.get("report") or "").strip()
        if report_text.startswith("Алдаа:") or report_text.startswith("Gemini API тохируулаагүй"):
            self.after(0, self._on_process_error, report_text or "Gemini алдаа")
            return

        # 5. Persist
        try:
            save_transcript_results(
                self._draft_id,
                transcript=transcript,
                redacted_text=gem.get("redacted_text", transcript),
                report=report_text,
                redactions=gem.get("sensitive_info", []),
                report_redactions=gem.get("report_redactions", []),
                protocol=gem.get("protocol") or {},
            )
        except Exception as exc:
            self.after(0, self._on_process_error, f"Хадгалах алдаа: {exc}")
            return

        # 6. Archive WAV + anchor keccak256 hash on Ethereum. Failure here
        #    (chain offline, RPC down) does not abort completion — the
        #    archive copy is still useful for replay/verification later.
        self.after(
            0,
            lambda: self._audio_status_lbl
            and self._audio_status_lbl.configure(
                text="Аудиог архивлан блокчэйнд баталгаажуулж байна…",
                text_color="#666666",
            ),
        )
        # Surface success/failure in the status label and persist the reason
        # onto the meeting record so the user can diagnose silent drops later.
        try:
            bc_result = store_audio_on_blockchain(self._draft_id, path)
        except Exception as exc:
            bc_result = {"ok": False, "error": f"Дуудлагын алдаа: {exc}",
                         "tx_hash": "", "audio_hash": "", "archive_path": ""}
            try:
                from app_utils import load_json, save_json, MEETINGS_DB_FILE
                data = load_json(MEETINGS_DB_FILE)
                if isinstance(data, list):
                    target = str(self._draft_id)
                    for m in data:
                        if isinstance(m, dict) and str(m.get("id")) == target:
                            m["blockchain_error"] = bc_result["error"]
                            save_json(MEETINGS_DB_FILE, data)
                            break
            except Exception:
                pass

        def _status_msg(res):
            if res.get("ok") and res.get("tx_hash"):
                return (
                    f"✓ Аудио блокчэйнд баталгаажсан — tx {res['tx_hash'][:12]}…",
                    "#16A34A",
                )
            if res.get("archive_path"):
                return (
                    f"⚠ Локал архив хадгалсан, блокчэйн: {res.get('error') or 'алдаа'}",
                    "#B45309",
                )
            return (f"✗ Блокчэйн хадгалалт: {res.get('error') or 'алдаа'}", "#B91C1C")

        msg, color = _status_msg(bc_result)
        self.after(
            0,
            lambda: self._audio_status_lbl
            and self._audio_status_lbl.configure(text=msg, text_color=color),
        )
        self.after(0, self._on_process_complete)

    def _on_process_error(self, msg: str):
        self._processing = False
        if self._audio_status_lbl is not None:
            self._audio_status_lbl.configure(
                text=f"❌ {msg}", text_color="#C53030",
            )
        if self._processing_btn is not None:
            self._processing_btn.pack_forget()
        self._start_btn.configure(text="Эхлэх")
        self._start_btn.pack(side="left")

    def _on_process_complete(self):
        self._processing = False
        if self._audio_status_lbl is not None:
            self._audio_status_lbl.configure(
                text="✓ Боловсруулалт дууслаа. Тэмдэглэл хэсэг рүү шилжиж байна…",
                text_color="#198754",
            )
        # Hand off to the app if it provided a navigation callback
        if callable(self._on_completed):
            self.after(900, self._on_completed)

    # TIMER & WAVEFORM ANIMATION

    def _tick_timer(self):
        if not self._recording:
            return
        if not self._paused:
            self._elapsed += 1
            m, s = divmod(self._elapsed, 60)
            self._time_lbl.configure(text=f"{m:02d}:{s:02d}")
        self._timer_job = self.after(1000, self._tick_timer)

    def _tick_wave(self):
        self._phase += 0.15

        level = None
        while True:
            try:
                level = self._level_q.get_nowait()
            except queue.Empty:
                break

        if level is None:
            level = 0.07 * abs(math.sin(self._phase * 0.4))

        self._wave_levels = self._wave_levels[1:] + [level]
        self._draw_wave()
        self._wave_job = self.after(30, self._tick_wave)

    def _draw_wave(self):
        c = self._canvas
        c.delete("all")
        try:
            w = c.winfo_width()
            h = c.winfo_height()
        except Exception:
            return
        if w < 4 or h < 4:
            return

        # Idle state: thin flat gray line
        if not self._recording:
            cy = h // 2
            c.create_line(0, cy, w, cy, fill="#D8D8D8", width=1)
            return

        n       = len(self._wave_levels)
        bar_w   = max(2, w / n - 1)
        spacing = w / n
        cy      = h / 2

        for i, lv in enumerate(self._wave_levels):
            t = i / max(n - 1, 1)
            # #7B5EA7 purple → #6ECFF6 cyan
            rv = int(0x7B + t * (0x6E - 0x7B))
            gv = int(0x5E + t * (0xCF - 0x5E))
            bv = int(0xA7 + t * (0xF6 - 0xA7))
            color  = f"#{rv:02x}{gv:02x}{bv:02x}"
            bar_h  = max(3, lv * (h - 6))
            x0 = int(i * spacing)
            y0 = int(cy - bar_h / 2)
            x1 = int(x0 + bar_w)
            y1 = int(cy + bar_h / 2)
            c.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

    # ══════════════════════════════════════════════════════════════
    # CLEANUP
    # ══════════════════════════════════════════════════════════════

    def destroy(self):
        self._recording = False
        for job in (self._timer_job, self._wave_job):
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        super().destroy()
