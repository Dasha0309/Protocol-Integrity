import os

import customtkinter as ctk

# ── Optional dependencies ──────────────────────────────────────
pyaudio = None
requests = None
Fernet = None
Web3 = None
genai = None
GEMINI_SDK = None

try:
    import pyaudio as _pyaudio
    pyaudio = _pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

try:
    import requests as _requests
    requests = _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from cryptography.fernet import Fernet as _Fernet
    Fernet = _Fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False

try:
    from web3 import Web3 as _Web3
    Web3 = _Web3
    HAS_WEB3 = True
except ImportError:
    HAS_WEB3 = False

try:
    import google.generativeai as _genai
    genai = _genai
    GEMINI_SDK = "google-generativeai"
    HAS_GEMINI = True
except ImportError:
    try:
        from google import genai as _genai
        genai = _genai
        GEMINI_SDK = "google-genai"
        HAS_GEMINI = True
    except ImportError:
        HAS_GEMINI = False

# ── App ────────────────────────────────────────────────────────
APP_NAME = "Protocol Integrity"
APP_VERSION = "5.0.0"

# ── Roles ──────────────────────────────────────────────────────
ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"

# ── Paths ──────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.expanduser("~"), ".protocol_integrity")
ORG_FILE = os.path.join(DATA_DIR, "organization.json")
ORG_DB_FILE = os.path.join(DATA_DIR, "organizations_db.json")
MEETINGS_DB_FILE = os.path.join(DATA_DIR, "meetings.json")
RECORDINGS_DIR = os.path.join(DATA_DIR, "recordings")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
ENCRYPTED_DIR = os.path.join(DATA_DIR, "encrypted")
KEYS_DIR = os.path.join(DATA_DIR, "keys")

RSA_PUBLIC_FILE = os.path.join(KEYS_DIR, "rsa_public.pem")
RSA_PRIVATE_LEGACY_FILE = os.path.join(KEYS_DIR, "rsa_private.pem")
RSA_PRIVATE_ENC_FILE = os.path.join(KEYS_DIR, "rsa_private.enc")

_ENV_FILE = os.path.join(DATA_DIR, "env.json")
_ENV_FILE_FALLBACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "env.json")


def _load_env():
    import json
    for path in (_ENV_FILE, _ENV_FILE_FALLBACK):
        if os.path.exists(path):
            try:
                # utf-8-sig strips a BOM if the file was saved from Notepad
                with open(path, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
    return {}


def get_credential(key, default=""):
    val = os.environ.get(key.upper(), "")
    if val:
        return val
    return _load_env().get(key, default)

# ── Audio ──────────────────────────────────────────────────────
AUDIO_FORMAT = pyaudio.paInt16 if HAS_PYAUDIO else None
CHANNELS = 1
RATE = 16000
CHUNK = 1024
MAX_SHORT_AUDIO_BYTES = 3 * 1024 * 1024
CHIMEGE_BASE_URL = "https://api.chimege.com/v1.2"

# ── Security ───────────────────────────────────────────────────
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 60

# ── UI ─────────────────────────────────────────────────────────
COLORS = {
    "bg_main": "#f8f9fa",
    "bg_card": "#ffffff",
    "bg_input": "#f1f3f5",
    "accent": "#2a7af3",
    "accent_hover": "#0b5ed7",
    "accent_light": "#e7f1ff",
    "success": "#198754",
    "success_light": "#d1e7dd",
    "warning": "#fd7e14",
    "warning_light": "#fff3cd",
    "danger": "#dc3545",
    "danger_light": "#f8d7da",
    "text_primary": "#212529",
    "text_secondary": "#6c757d",
    "text_muted": "#adb5bd",
    "border": "#dee2e6",
    "border_light": "#e9ecef",
    "redacted": "#000000",
}

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Default font with full Mongolian Cyrillic support (Ө, Ү, etc.).
# CustomTkinter's bundled Roboto lacks Cyrillic Extended glyphs, so
# Tk renders them as "?". Segoe UI ships with Windows and covers all
# Mongolian letters.
UI_FONT_FAMILY = "Segoe UI"
try:
    font_cfg = ctk.ThemeManager.theme.get("CTkFont", {})
    # CustomTkinter 5.x stores per-OS defaults
    for os_key in ("Windows", "macOS", "Linux"):
        if isinstance(font_cfg.get(os_key), dict):
            font_cfg[os_key]["family"] = UI_FONT_FAMILY
    # Fallback for flat structure (older versions)
    if "family" in font_cfg:
        font_cfg["family"] = UI_FONT_FAMILY
except Exception:
    pass