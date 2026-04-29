import hashlib
import hmac
import json
import os
import re
import tkinter as tk
from datetime import datetime

from app_config import (
    ARCHIVE_DIR,
    DATA_DIR,
    ENCRYPTED_DIR,
    KEYS_DIR,
    MEETINGS_DB_FILE,
    ORG_FILE,
    RECORDINGS_DIR,
)


def ensure_dirs():
    for d in [DATA_DIR, RECORDINGS_DIR, ARCHIVE_DIR, ENCRYPTED_DIR, KEYS_DIR]:
        os.makedirs(d, exist_ok=True)


def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            return {}
    return {}


def save_json(path, data):
    ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Single-org helpers ─────────────────────────────────────────
def load_org():
    """Load the single organization data."""
    return load_json(ORG_FILE) or {}


def save_org(data):
    """Save organization data."""
    save_json(ORG_FILE, data)


def org_exists():
    """Check if organization is registered."""
    org = load_org()
    return bool(org.get("name"))


def get_org_users():
    """Get users list from org."""
    return load_org().get("users", [])


def find_user(email):
    """Find user by email. Returns (index, user_dict) or (-1, None)."""
    for i, u in enumerate(get_org_users()):
        if u.get("email") == email:
            return i, u
    return -1, None


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def create_or_get_draft(
    *,
    title: str,
    date: str = "",
    participants: str = "",
    participant_count: int = 0,
    participants_encrypted: bool = False,
    description: str = "",
    password: str = "",
):
    """Create a new draft if not existing, otherwise return existing draft id.

    If ``participants_encrypted`` is True, ``participants`` must already be the
    RSA-OAEP ciphertext (base64). The flag is persisted so viewers know to
    decrypt before display.
    """
    data = load_json(MEETINGS_DB_FILE)
    if not isinstance(data, list):
        data = []

    normalized = {
        "title": (title or "").strip(),
        "date": (date or "").strip() or datetime.now().strftime("%Y/%m/%d"),
        "participants": (participants or "").strip(),
        "participant_count": _safe_int(participant_count),
        "participants_encrypted": bool(participants_encrypted),
        "description": (description or "").strip(),
        "status": "draft",
    }

    existing = next(
        (
            m
            for m in data
            if isinstance(m, dict)
            and (m.get("title") or "").strip() == normalized["title"]
            and (m.get("date") or "").strip() == normalized["date"]
            and _safe_int(m.get("participant_count")) == normalized["participant_count"]
            and (m.get("description") or "").strip() == normalized["description"]
            and (m.get("status") or "").strip().lower() == "draft"
        ),
        None,
    )

    pw_hash = hash_password(password) if password else ""

    if existing:
        # If a password was (re)supplied, update the hash so later decrypts
        # can verify against the latest value the user typed.
        if pw_hash:
            existing["password_hash"] = pw_hash
            existing["has_password"] = True
            save_json(MEETINGS_DB_FILE, data)
        return existing.get("id"), False

    next_id = max([_safe_int(m.get("id")) for m in data if isinstance(m, dict)] + [0]) + 1
    data.append(
        {
            "id": next_id,
            "title": normalized["title"],
            "date": normalized["date"],
            "description": normalized["description"],
            "report": normalized["description"],
            "redacted_text": "",
            "author": "System",
            "participants": normalized["participants"],
            "participant_count": normalized["participant_count"],
            "participants_encrypted": normalized["participants_encrypted"],
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "has_password": bool(password),
            "password_hash": pw_hash,
        }
    )
    save_json(MEETINGS_DB_FILE, data)
    return next_id, True


def verify_meeting_password(meeting: dict, password: str) -> bool:
    """Return True if ``password`` matches the meeting's stored hash.

    If no hash is stored (older draft, or user skipped the password field),
    access is granted — the RSA private key on disk is the real cryptographic
    gate; the password is just a UI-level lock the user can optionally set.
    """
    stored = (meeting or {}).get("password_hash", "")
    if not stored:
        return True
    return verify_password(password, stored)


def trash_meeting(meeting_id) -> bool:
    """Meeting-г хогийн савд зөөх (status = trash)."""
    data = load_json(MEETINGS_DB_FILE)
    if not isinstance(data, list):
        return False
    target = str(meeting_id)
    for m in data:
        if isinstance(m, dict) and str(m.get("id")) == target:
            m["status"] = "trash"
            m["trashed_at"] = datetime.now().isoformat()
            save_json(MEETINGS_DB_FILE, data)
            return True
    return False


def restore_meeting(meeting_id) -> bool:
    """Хогийн савнаас сэргээх (status = draft)."""
    data = load_json(MEETINGS_DB_FILE)
    if not isinstance(data, list):
        return False
    target = str(meeting_id)
    for m in data:
        if isinstance(m, dict) and str(m.get("id")) == target:
            m["status"] = "draft"
            m.pop("trashed_at", None)
            save_json(MEETINGS_DB_FILE, data)
            return True
    return False


def permanent_delete_meeting(meeting_id) -> bool:
    """Хогийн савнаас бүрмөсөн устгах."""
    data = load_json(MEETINGS_DB_FILE)
    if not isinstance(data, list):
        return False
    target = str(meeting_id)
    new_data = [m for m in data if not (isinstance(m, dict) and str(m.get("id")) == target)]
    if len(new_data) < len(data):
        save_json(MEETINGS_DB_FILE, new_data)
        return True
    return False


def get_trashed_meetings() -> list:
    """Хогийн савны бүх meeting-г авах."""
    data = load_json(MEETINGS_DB_FILE)
    if not isinstance(data, list):
        return []
    return [m for m in data if isinstance(m, dict) and m.get("status") == "trash"]


def attach_audio_to_meeting(meeting_id, audio_file: str, source: str = "recorded") -> bool:
    """Attach audio path to an existing meeting draft."""
    if not meeting_id or not audio_file:
        return False

    data = load_json(MEETINGS_DB_FILE)
    if not isinstance(data, list):
        return False

    target_id = str(meeting_id)
    updated = False
    for m in data:
        if isinstance(m, dict) and str(m.get("id")) == target_id:
            m["audio_file"] = audio_file
            m["audio_source"] = source
            m["updated_at"] = datetime.now().isoformat()
            updated = True
            break

    if updated:
        save_json(MEETINGS_DB_FILE, data)
    return updated


def store_audio_on_blockchain(meeting_id, audio_path: str) -> dict:
    """Archive the processed WAV and anchor its keccak256 hash on-chain.

    Three things happen here:
      1. A copy of ``audio_path`` is written into ``ARCHIVE_DIR`` so the
         original source can always be replayed from the Documents page,
         even if the user later deletes the uploaded file.
      2. A keccak256 hash of the bytes is stored on the Ethereum contract
         via ``BlockchainConnector.store_hash`` — this is the tamper seal
         used to verify the archive copy later.
      3. ``archive_wav``, ``audio_hash`` and ``blockchain_tx`` are persisted
         onto the meeting record so the UI can show the Сонсох button and
         the verification badge.

    Failures are captured instead of raised so the STT → Gemini pipeline
    isn't interrupted when the local chain node is down.
    """
    result = {
        "audio_hash": "", "tx_hash": "", "archive_path": "",
        "ok": False, "error": "",
    }
    if not meeting_id or not audio_path:
        result["error"] = "meeting_id эсвэл аудио зам дутуу"
        return result
    if not os.path.exists(audio_path):
        result["error"] = f"Аудио файл олдсонгүй: {audio_path}"
        return result

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
    except Exception as exc:
        result["error"] = f"Файл унших алдаа: {exc}"
        return result

    archive_path = ""
    try:
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        _, ext = os.path.splitext(audio_path)
        ext = (ext or ".wav").lower()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = os.path.join(
            ARCHIVE_DIR, f"meeting_{meeting_id}_{ts}{ext}"
        )
        import shutil
        shutil.copy2(audio_path, archive_path)
        result["archive_path"] = archive_path
    except Exception as exc:
        # Archiving is best-effort — log but don't abort the hash step.
        result["error"] = f"Архивлахад алдаа: {exc}"
        archive_path = ""

    # Lazy import — avoids circular dependency with app_services → app_utils.
    from app_services import BlockchainConnector

    bc = BlockchainConnector()
    audio_hash = bc.compute_keccak(audio_bytes)
    if audio_hash and not audio_hash.startswith("0x"):
        audio_hash = "0x" + audio_hash
    result["audio_hash"] = audio_hash

    if bc.connected:
        tx_hash = bc.store_hash(str(meeting_id), audio_hash)
        if tx_hash:
            if not tx_hash.startswith("0x"):
                tx_hash = "0x" + tx_hash
            result["tx_hash"] = tx_hash
            result["ok"] = True
        else:
            result["error"] = "Blockchain руу илгээж чадсангүй"
    else:
   
        result["error"] = bc.error_msg or "Blockchain-д холбогдоогүй"

    data = load_json(MEETINGS_DB_FILE)
    if isinstance(data, list):
        target = str(meeting_id)
        for m in data:
            if isinstance(m, dict) and str(m.get("id")) == target:
                if archive_path:
                    m["archive_wav"] = archive_path
                if audio_hash:
                    m["audio_hash"] = audio_hash
                if result["tx_hash"]:
                    m["blockchain_tx"] = result["tx_hash"]
                if result["error"]:
                    m["blockchain_error"] = result["error"]
                else:
                    m.pop("blockchain_error", None)
                save_json(MEETINGS_DB_FILE, data)
                break

    return result


def save_transcript_results(
    meeting_id,
    *,
    transcript: str = "",
    redacted_text: str = "",
    report: str = "",
    redactions: list | None = None,
    report_redactions: list | None = None,
    protocol: dict | None = None,
    status: str = "approved",
) -> bool:
    """Save Chimege transcript + Gemini redaction output onto a meeting.

    ``protocol`` — structured meeting fields extracted by Gemini
    (doc_title, doc_number, date, attendees, agenda, decisions,
    reviewer_name, …) used to render the formal protocol layout.

    Defaults the meeting status to ``"approved"`` so it appears in the
    Documents page under the Approved filter after successful processing.
    """
    if not meeting_id:
        return False

    data = load_json(MEETINGS_DB_FILE)
    if not isinstance(data, list):
        return False

    target_id = str(meeting_id)
    updated = False
    for m in data:
        if isinstance(m, dict) and str(m.get("id")) == target_id:
            m["transcript"] = transcript or ""
            m["redacted_text"] = redacted_text or transcript or ""
            m["report"] = report or m.get("report", "")
            m["redactions"] = redactions or []
            # Parallel redaction list for the summary; positions are
            # offsets inside ``report`` (NOT the transcript).
            m["report_redactions"] = report_redactions or []
            if protocol is not None:
                m["protocol"] = protocol
            m["status"] = status
            m["processed_at"] = datetime.now().isoformat()
            m["updated_at"] = m["processed_at"]
            updated = True
            break

    if updated:
        save_json(MEETINGS_DB_FILE, data)
    return updated


# ── Archive search backend (Flask logic converted) ──────────────
def get_archive_statuses():
    return ["All", "Draft", "Pending", "Approved", "Rejected"]


def _normalize_status(status: str) -> str:
    s = (status or "").strip().lower()
    if s == "approved":
        return "Approved"
    if s == "pending":
        return "Pending"
    if s == "rejected":
        return "Rejected"
    if s == "draft":
        return "Draft"
    return "Draft"


def search_archive_meetings(q: str = "", status: str = "All"):
    data = load_json(MEETINGS_DB_FILE)
    if not isinstance(data, list):
        data = []

    # Trash item-уудыг архивын жагсаалтаас хасна
    results = [m for m in data if isinstance(m, dict) and m.get("status") != "trash"]
    status = (status or "All").strip()
    q = (q or "").strip().lower()

    if status != "All":
        results = [m for m in results if _normalize_status(m.get("status", "")) == status]

    if q:
        def match(m):
            title = str(m.get("title", "")).lower()
            description = str(m.get("description", "")).lower()
            if not description:
                description = str(m.get("report") or m.get("redacted_text") or "").lower()
            author = str(m.get("author", "")).lower()
            return q in title or q in description or q in author

        results = [m for m in results if match(m)]

    normalized = []
    for m in results:
        item = dict(m)
        item["status"] = _normalize_status(item.get("status", ""))
        if not item.get("description"):
            item["description"] = (item.get("report") or item.get("redacted_text") or "")[:160]
        if not item.get("author"):
            item["author"] = "System"
        normalized.append(item)
    return normalized


# ── Credentials (from env/config, not UI) ──────────────────────
def get_credential(key, default=""):
    from app_config import get_credential as _gc
    return _gc(key, default)


# ── Password hashing ──────────────────────────────────────────
def hash_password(password: str, salt: str = None) -> str:
    if salt is None:
        salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if "$" not in stored_hash:
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    salt, _ = stored_hash.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt), stored_hash)


# ── Encryption key derivation ─────────────────────────────────
def derive_key_from_password(password: str, salt: bytes = None) -> tuple:
    import base64
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    key = base64.urlsafe_b64encode(dk)
    return key, salt


# ── Validation ─────────────────────────────────────────────────
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
PHONE_RE = re.compile(r"^(\+976\s?)?[0-9\s\-]{8,15}$")


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))


def validate_phone(phone: str) -> bool:
    return bool(PHONE_RE.match(phone.strip()))


def validate_password(pw: str) -> str | None:
    if len(pw) < 8:
        return "Нууц үг хамгийн багадаа 8 тэмдэгт"
    if not re.search(r"[A-ZА-ЯЁ]", pw):
        return "Том үсэг байх ёстой"
    if not re.search(r"[a-zа-яё]", pw):
        return "Жижиг үсэг байх ёстой"
    if not re.search(r"\d", pw):
        return "Тоо байх ёстой"
    return None


# ── Tkinter shortcuts ─────────────────────────────────────────
def is_editable_widget(widget) -> bool:
    if not isinstance(widget, (tk.Entry, tk.Text)):
        return False
    try:
        return str(widget.cget("state")) != "disabled"
    except Exception:
        return False


def install_text_edit_shortcuts(root: tk.Tk):
    menu = tk.Menu(root, tearoff=0)

    def _copy():
        w = root.focus_get()
        if isinstance(w, (tk.Entry, tk.Text)):
            w.event_generate("<<Copy>>")

    def _paste():
        w = root.focus_get()
        if is_editable_widget(w):
            w.event_generate("<<Paste>>")

    def _cut():
        w = root.focus_get()
        if is_editable_widget(w):
            w.event_generate("<<Cut>>")

    def _select_all(event=None):
        w = event.widget if event else root.focus_get()
        if isinstance(w, tk.Entry):
            w.select_range(0, "end")
            w.icursor("end")
            return "break"
        if isinstance(w, tk.Text):
            w.tag_add("sel", "1.0", "end-1c")
            w.mark_set("insert", "end-1c")
            w.see("insert")
            return "break"
        return None

    menu.add_command(label="Хуулах (Ctrl+C)", command=_copy)
    menu.add_command(label="Таслах (Ctrl+X)", command=_cut)
    menu.add_command(label="Буулгах (Ctrl+V)", command=_paste)
    menu.add_separator()
    menu.add_command(label="Бүгдийг сонгох (Ctrl+A)", command=_select_all)

    def _show_menu(event):
        w = event.widget
        if not isinstance(w, (tk.Entry, tk.Text)):
            return
        editable = is_editable_widget(w)
        menu.entryconfigure(1, state="normal" if editable else "disabled")
        menu.entryconfigure(2, state="normal" if editable else "disabled")
        menu.tk_popup(event.x_root, event.y_root)

    def _on_copy(event):
        if isinstance(event.widget, (tk.Entry, tk.Text)):
            event.widget.event_generate("<<Copy>>")
            return "break"
        return None

    def _on_paste(event):
        if is_editable_widget(event.widget):
            event.widget.event_generate("<<Paste>>")
            return "break"
        return None

    def _on_cut(event):
        if is_editable_widget(event.widget):
            event.widget.event_generate("<<Cut>>")
            return "break"
        return None

    root.bind_all("<Control-c>", _on_copy, add="+")
    root.bind_all("<Control-C>", _on_copy, add="+")
    root.bind_all("<Control-v>", _on_paste, add="+")
    root.bind_all("<Control-V>", _on_paste, add="+")
    root.bind_all("<Control-x>", _on_cut, add="+")
    root.bind_all("<Control-X>", _on_cut, add="+")
    root.bind_all("<Control-a>", _select_all, add="+")
    root.bind_all("<Control-A>", _select_all, add="+")
    root.bind_all("<Button-3>", _show_menu, add="+")


# ── Mongolian Cyrillic keyboard fix ────────────────────────────
# On Windows, Tk's WM_CHAR path routes non-cp1252 characters (Ө U+04E8,
# Ү U+04AE, etc.) through the system ANSI codepage, which replaces them
# with '?'. event.keysym_num, however, carries the real Unicode codepoint.
# We intercept <KeyPress> BEFORE the default Entry/Text class binding
# fires and insert the correct character manually.
_MN_FIX_TAG = "MnCyrillicFix"


def _mn_fix_keypress(event):
    ks = event.keysym_num
    # Only act on printable BMP chars above ASCII; skip Tk special keysyms
    # (BackSpace 0xFF08, Return 0xFF0D, arrows, Alt, Shift, etc. are 0xFF00+).
    if not (0x80 <= ks <= 0xFDFF):
        return None
    # Skip if Tk already produced the correct char (e.g. Latin-1 extras).
    if event.char and len(event.char) == 1 and ord(event.char) == ks:
        return None
    try:
        real_char = chr(ks)
    except (ValueError, OverflowError):
        return None
    w = event.widget
    try:
        # For Entry: if text is selected, overwrite the selection
        if isinstance(w, tk.Entry):
            try:
                if w.selection_present():
                    w.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            w.insert("insert", real_char)
            return "break"
        if isinstance(w, tk.Text):
            try:
                if w.tag_ranges("sel"):
                    w.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            w.insert("insert", real_char)
            return "break"
    except Exception:
        return None
    return None


def _mn_attach_tag(widget):
    if not isinstance(widget, (tk.Entry, tk.Text)):
        return
    try:
        tags = list(widget.bindtags())
    except Exception:
        return
    if _MN_FIX_TAG in tags:
        return
    # Insert before the class tag ("Entry"/"Text") so our handler fires first.
    insert_at = 1  # after widget-id tag
    for i, t in enumerate(tags):
        if t in ("Entry", "Text"):
            insert_at = i
            break
    tags.insert(insert_at, _MN_FIX_TAG)
    widget.bindtags(tuple(tags))


def install_mn_keyboard_fix(root: tk.Tk):
    """Fix Ө/Ү/... keyboard input being mangled to '?' on Windows Tk."""
    root.bind_class(_MN_FIX_TAG, "<KeyPress>", _mn_fix_keypress)

    # Patch existing widget tree
    def _walk(w):
        _mn_attach_tag(w)
        for c in w.winfo_children():
            _walk(c)
    _walk(root)

    # Ensure any Entry/Text created later also gets the tag
    if not getattr(tk.Entry, "_mn_patched", False):
        _orig_entry_init = tk.Entry.__init__

        def _patched_entry_init(self, *args, **kwargs):
            _orig_entry_init(self, *args, **kwargs)
            _mn_attach_tag(self)
        tk.Entry.__init__ = _patched_entry_init
        tk.Entry._mn_patched = True

    if not getattr(tk.Text, "_mn_patched", False):
        _orig_text_init = tk.Text.__init__

        def _patched_text_init(self, *args, **kwargs):
            _orig_text_init(self, *args, **kwargs)
            _mn_attach_tag(self)
        tk.Text.__init__ = _patched_text_init
        tk.Text._mn_patched = True
