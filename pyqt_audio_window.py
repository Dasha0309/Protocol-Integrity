import sys
import os
import wave
import math
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QFileDialog,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import (
    QFont,
    QColor,
    QPainter,
    QLinearGradient,
    QBrush,
    QPen,
    QIcon,
    QPixmap,
)
import pyaudio
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from app_utils import attach_audio_to_meeting
    from app_config import RECORDINGS_DIR
except Exception:
    attach_audio_to_meeting = None
    RECORDINGS_DIR = str(ROOT_DIR / "data" / "recordings")


def _get_arg(flag: str, default: str = "") -> str:
    for i, arg in enumerate(sys.argv):
        if arg == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1].strip()
    return default


class AudioRecorder(QThread):
    level_signal = pyqtSignal(float)
    time_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.running = False
        self.paused = False
        self.frames = []
        self.elapsed = 0
        self.filename = None

    def run(self):
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHAN = 1
        RATE = 44100

        p = pyaudio.PyAudio()
        try:
            st = p.open(
                format=FORMAT,
                channels=CHAN,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
        except Exception:
            p.terminate()
            return

        self.running = True
        self.frames = []
        self.elapsed = 0
        tick = 0

        while self.running:
            if not self.paused:
                data = st.read(CHUNK, exception_on_overflow=False)
                self.frames.append(data)
                arr = np.frombuffer(data, dtype=np.int16)
                level = min(float(np.abs(arr).mean()) / 3000.0, 1.0)
                self.level_signal.emit(level)
                tick += CHUNK
                if tick >= RATE:
                    self.elapsed += 1
                    self.time_signal.emit(self.elapsed)
                    tick = 0
            else:
                self.msleep(50)

        st.stop_stream()
        st.close()

        if self.filename and self.frames:
            wf = wave.open(self.filename, "wb")
            wf.setnchannels(CHAN)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b"".join(self.frames))
            wf.close()

        p.terminate()

    def stop(self):
        self.running = False


class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.levels = [0.0] * 80
        self.level = 0.0
        self._phase = 0.0
        self._idle = True

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_level(self, v: float):
        self.level = v
        self._idle = False

    def set_idle(self, idle: bool):
        self._idle = idle
        if idle:
            self.level = 0.0

    def _tick(self):
        self._phase += 0.15
        if self._idle:
            new_level = 0.08 * abs(math.sin(self._phase * 0.5))
        else:
            new_level = self.level
        self.levels = self.levels[1:] + [new_level]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        cx = h / 2
        bar_w = max(2, w / len(self.levels) - 1)
        spacing = w / len(self.levels)

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor("#7B5EA7"))
        grad.setColorAt(0.5, QColor("#9B6FD4"))
        grad.setColorAt(1.0, QColor("#6ECFF6"))

        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)

        for i, lv in enumerate(self.levels):
            bar_h = max(3, lv * (h - 4))
            x = i * spacing
            y = cx - bar_h / 2
            p.drawRoundedRect(int(x), int(y), int(bar_w), int(bar_h), 2, 2)


class CardFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "QFrame#card { background: #ffffff; border-radius: 16px; }"
        )

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        grad = QLinearGradient(r.topLeft(), r.topRight())
        grad.setColorAt(0.0, QColor("#7B5EA7"))
        grad.setColorAt(0.5, QColor("#A78ED4"))
        grad.setColorAt(1.0, QColor("#6ECFF6"))
        pen = QPen(QBrush(grad), 1.5)
        p.setPen(pen)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.drawRoundedRect(r, 14, 14)


class SidebarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet("background-color: #BDBDBD;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 40, 20, 40)
        layout.setSpacing(0)

        label = QLabel("Энд side bar")
        label.setFont(QFont("Arial", 13, QFont.Bold))
        label.setStyleSheet("color: #333333;")
        layout.addWidget(label)
        layout.addStretch()


class KhurulBurttgel(QMainWindow):
    def __init__(self, meeting_id: str = "", meeting_title: str = ""):
        super().__init__()
        self.meeting_id = (meeting_id or "").strip()
        self.meeting_title = (meeting_title or "").strip() or "Хурлын гарчиг"
        self.setWindowTitle("Хурлын бүртгэл")
        self.setStyleSheet("background-color: #F8F8FC;")

        self.recorder = AudioRecorder()
        self.is_recording = False
        self.elapsed_sec = 0

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # Horizontal split: sidebar | content
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────
        root_layout.addWidget(SidebarWidget())

        # ── Main content area ────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background-color: #FFFFFF;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(60, 50, 60, 50)
        content_layout.setSpacing(0)

        # Title
        title_label = QLabel("Хурлын бүртгэл")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setStyleSheet("color: #111111;")
        content_layout.addWidget(title_label)

        content_layout.addSpacing(32)

        # Meeting name placeholder
        self.meeting_name_label = QLabel(self.meeting_title)
        self.meeting_name_label.setFont(QFont("Arial", 13))
        self.meeting_name_label.setStyleSheet("color: #555555;")
        self.meeting_name_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.meeting_name_label)

        content_layout.addSpacing(24)

        # ── Audio card ───────────────────────────────────────────
        card = CardFrame()
        card.setMinimumHeight(120)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 16, 24, 16)
        card_layout.setSpacing(12)

        # Waveform + timer row
        wave_row = QHBoxLayout()
        wave_row.setSpacing(16)

        self.waveform = WaveformWidget()
        wave_row.addWidget(self.waveform, 1)

        self.time_label = QLabel("00:00")
        self.time_label.setFont(QFont("Courier New", 13))
        self.time_label.setStyleSheet("color: #666666; min-width: 50px;")
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        wave_row.addWidget(self.time_label)

        card_layout.addLayout(wave_row)

        # Controls row
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(20)

        self.btn_upload = QPushButton()
        self.btn_upload.setText("  аудио оруулах")
        self.btn_upload.setFixedHeight(34)
        self.btn_upload.setIcon(self._upload_icon())
        self.btn_upload.setStyleSheet(self._ghost_btn_style())
        ctrl_row.addWidget(self.btn_upload)

        self.btn_mic = QPushButton()
        self.btn_mic.setText("  мик хаах")
        self.btn_mic.setFixedHeight(34)
        self.btn_mic.setIcon(self._mic_icon())
        self.btn_mic.setStyleSheet(self._ghost_btn_style())
        ctrl_row.addWidget(self.btn_mic)

        ctrl_row.addStretch()

        self.btn_start = QPushButton("Эхлэх")
        self.btn_start.setFixedSize(120, 38)
        self.btn_start.setStyleSheet(self._start_btn_style(recording=False))
        ctrl_row.addWidget(self.btn_start)

        # Sparkle icon (decorative)
        spark = QLabel("✦")
        spark.setStyleSheet("color: #6ECFF6; font-size: 20px;")
        ctrl_row.addWidget(spark)

        card_layout.addLayout(ctrl_row)
        content_layout.addWidget(card)
        content_layout.addStretch()

        root_layout.addWidget(content, 1)

    # ── Icons ────────────────────────────────────────────────────

    def _upload_icon(self):
        pix = QPixmap(20, 20)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#555555"), 1.5))
        p.drawLine(10, 13, 10, 4)
        p.drawLine(6, 8, 10, 4)
        p.drawLine(14, 8, 10, 4)
        p.drawRect(3, 14, 14, 3)
        p.end()
        return QIcon(pix)

    def _mic_icon(self):
        from PyQt5.QtCore import QRectF
        pix = QPixmap(20, 20)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#555555"), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(7, 2, 6, 9, 3, 3)
        p.drawArc(QRectF(4, 8, 12, 7), 0, -180 * 16)
        p.drawLine(10, 15, 10, 18)
        p.drawLine(7, 18, 13, 18)
        p.end()
        return QIcon(pix)

    # ── Styles ───────────────────────────────────────────────────

    def _ghost_btn_style(self):
        return """
            QPushButton {
                background: transparent;
                border: none;
                color: #555555;
                font-size: 13px;
            }
            QPushButton:hover { color: #7B5EA7; }
        """

    def _start_btn_style(self, recording: bool = False):
        if recording:
            return """
                QPushButton {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 #E05555, stop:1 #C03030);
                    color: white; border: none; border-radius: 19px;
                    font-size: 13px; font-weight: 600;
                }
                QPushButton:hover { background: #CC3333; }
            """
        return """
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #7B5EA7, stop:1 #9B6FD4);
                color: white; border: none; border-radius: 19px;
                font-size: 13px; font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #6A4E96, stop:1 #8A5FC3);
            }
        """

    # ── Signal wiring ────────────────────────────────────────────

    def _connect_signals(self):
        self.btn_start.clicked.connect(self._toggle_recording)
        self.btn_upload.clicked.connect(self._upload_audio)
        self.btn_mic.clicked.connect(self._toggle_mic)
        self.recorder.level_signal.connect(self.waveform.set_level)
        self.recorder.time_signal.connect(self._on_time)

    # ── Recording logic ──────────────────────────────────────────

    def _auto_filename(self) -> str:
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.meeting_title)[:40]
        return str(Path(RECORDINGS_DIR) / f"meeting_{safe_title}_{ts}.wav")

    def _toggle_recording(self):
        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        # Create a fresh recorder thread each time
        self.recorder = AudioRecorder()
        self.recorder.level_signal.connect(self.waveform.set_level)
        self.recorder.time_signal.connect(self._on_time)

        self.recorder.filename = self._auto_filename()
        self.recorder.start()

        self.is_recording = True
        self.elapsed_sec = 0
        self.btn_start.setText("Зогсоох")
        self.btn_start.setStyleSheet(self._start_btn_style(recording=True))
        self.waveform.set_idle(False)

    def _stop_recording(self):
        self.recorder.stop()
        self.recorder.wait()

        saved_path = self.recorder.filename
        if self.meeting_id and saved_path and callable(attach_audio_to_meeting):
            attach_audio_to_meeting(self.meeting_id, saved_path, source="recorded")

        self.is_recording = False
        self.elapsed_sec = 0
        self.time_label.setText("00:00")
        self.btn_start.setText("Эхлэх")
        self.btn_start.setStyleSheet(self._start_btn_style(recording=False))
        self.waveform.set_idle(True)
        self.btn_mic.setText("  мик хаах")

    def _upload_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Аудио файл сонгох",
            "",
            "Аудио файлууд (*.wav *.mp3 *.ogg *.flac *.m4a)",
        )
        if path:
            fname = os.path.basename(path)
            self.setWindowTitle(f"Хурлын бүртгэл — {fname}")
            if self.meeting_id and callable(attach_audio_to_meeting):
                attach_audio_to_meeting(self.meeting_id, path, source="uploaded")

    def _toggle_mic(self):
        if not self.is_recording:
            return
        self.recorder.paused = not self.recorder.paused
        self.btn_mic.setText("  мик нээх" if self.recorder.paused else "  мик хаах")

    def _on_time(self, sec: int):
        self.elapsed_sec = sec
        m, s = divmod(sec, 60)
        self.time_label.setText(f"{m:02d}:{s:02d}")

    def closeEvent(self, event):
        if self.is_recording:
            self.recorder.stop()
            self.recorder.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    meeting_id = _get_arg("--meeting-id")
    meeting_title = _get_arg("--meeting-title")
    win = KhurulBurttgel(meeting_id=meeting_id, meeting_title=meeting_title)
    win.showMaximized()
    sys.exit(app.exec_())
