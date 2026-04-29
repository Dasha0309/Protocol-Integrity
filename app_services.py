import base64
import hashlib
import json
import os
import re
import time
from datetime import datetime

from app_config import (
    CHIMEGE_BASE_URL,
    ENCRYPTED_DIR,
    HAS_FERNET,
    HAS_GEMINI,
    HAS_REQUESTS,
    HAS_WEB3,
    GEMINI_SDK,
    KEYS_DIR,
    MAX_SHORT_AUDIO_BYTES,
    RSA_PRIVATE_ENC_FILE,
    RSA_PRIVATE_LEGACY_FILE,
    RSA_PUBLIC_FILE,
    Fernet,
    Web3,
    genai,
    requests,
    get_credential,
)


def _normalize_sensitive_items(items):
    if not isinstance(items, list):
        return []
    cleaned = []
    seen = set()
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _collect_sensitive_spans(text, items):
    if not text or not items:
        return []
    spans = []
    taken = [False] * len(text)
    for item in sorted(items, key=len, reverse=True):
        if not item:
            continue
        pattern = re.escape(item)
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            start, end = match.span()
            if any(taken[start:end]):
                continue
            spans.append((start, end))
            for i in range(start, end):
                taken[i] = True
    spans.sort(key=lambda x: x[0])
    return spans


def _redact_text(text, spans, placeholder_char="█"):
    if not spans:
        return text
    parts = []
    last = 0
    for start, end in spans:
        parts.append(text[last:start])
        parts.append(placeholder_char * (end - start))
        last = end
    parts.append(text[last:])
    return "".join(parts)


def _redact_string(s, sensitive_items, placeholder_char="█"):
    """Redact sensitive substrings inside a single free-form string."""
    if not s or not sensitive_items:
        return s or ""
    spans = _collect_sensitive_spans(s, sensitive_items)
    return _redact_text(s, spans, placeholder_char=placeholder_char)


def _process_field(s, sensitive_items):

    s = str(s or "").strip()
    if not s:
        return "", []
    spans = _collect_sensitive_spans(s, sensitive_items)
    if not spans:
        return s, []
    redacted = _redact_text(s, spans)
    reds = []
    for start, end in spans:
        token = s[start:end]
        try:
            cipher = EncryptionModule.encrypt_sensitive_value(token)
        except Exception:
     
            continue
        reds.append({"index": start, "length": end - start, "ciphertext": cipher})
    return redacted, reds


def _normalize_protocol(raw, sensitive_items):
    """Shape Gemini's protocol dict into a consistent schema and redact
    free-text fields against the sensitive-item list. A parallel
    ``_field_redactions`` map keeps RSA-encrypted spans so every field
    (title, attendees, agenda items, decision texts …) can be restored
    after the user decrypts."""
    if not isinstance(raw, dict):
        raw = {}

    field_reds: dict = {}

    def _scalar(key):
        red, reds = _process_field(raw.get(key, ""), sensitive_items)
        if reds:
            field_reds[key] = reds
        return red

    def _str_list(key):
        v = raw.get(key) or []
        if not isinstance(v, list):
            return []
        out_vals = []
        out_reds = []
        for item in v:
            red, reds = _process_field(str(item), sensitive_items)
            out_vals.append(red)
            out_reds.append(reds)
        # Keep the redactions list only if at least one entry has content.
        if any(out_reds):
            field_reds[key] = out_reds
        return out_vals

    # Decisions are [{"index": N, "text": "…"}] — only the text is sensitive.
    decisions_raw = raw.get("decisions") or []
    decisions = []
    dec_reds = []
    if isinstance(decisions_raw, list):
        for i, d in enumerate(decisions_raw, start=1):
            if isinstance(d, dict):
                idx_val = d.get("index") or i
                src_text = str(d.get("text", ""))
            else:
                idx_val, src_text = i, str(d)
            red, reds = _process_field(src_text, sensitive_items)
            if not red:
                continue
            try:
                idx = int(idx_val)
            except (TypeError, ValueError):
                idx = i
            decisions.append({"index": idx, "text": red})
            dec_reds.append(reds)
    if any(dec_reds):
        field_reds["decisions"] = dec_reds

    protocol = {
        "doc_title":     _scalar("doc_title"),
        "doc_number":    _scalar("doc_number"),
        "date":          _scalar("date"),
        "city":          _scalar("city"),
        "location":      _scalar("location"),
        "start_time":    _scalar("start_time"),
        "end_time":      _scalar("end_time"),
        "attendees":     _str_list("attendees"),
        "agenda":        _str_list("agenda"),
        "decisions":     decisions,
        "reviewer_name": _scalar("reviewer_name"),
    }
    if field_reds:
        protocol["_field_redactions"] = field_reds
    return protocol


class ChimegeSTT:
    def __init__(self, token=None):
        self.token = (token or get_credential("chimege_token")).strip()

    @staticmethod
    def _format_error(status_code, detail):
        """Turn a Chimege error response into a friendly Mongolian message."""
        detail = (detail or "").strip()
        if status_code in (401, 403):
            # Server actively rejected the token — not a missing-token case.
            hint = (
                "Chimege API token хүчингүй байна. "
                "Шалтгаан: token буруу, хүчинтэй хугацаа дууссан, "
                "эсвэл тухайн account-д STT (яриа → текст) эрх нээгдээгүй байж магадгүй. "
                "https://console.chimege.com/ хаягаар шинэ token авч "
                "~/.protocol_integrity/env.json файлд chimege_token түлхүүрт оруулна уу."
            )
            return f"[Chimege алдаа: {status_code}] {detail} — {hint}"
        return f"[Chimege алдаа: {status_code}] {detail}" if detail else f"[Chimege алдаа: {status_code}]"

    def transcribe_short(self, audio_data):
        if not HAS_REQUESTS:
            return "[requests суулгаагүй]"
        r = requests.post(
            f"{CHIMEGE_BASE_URL}/transcribe",
            data=audio_data,
            headers={
                "Content-Type": "application/octet-stream",
                "Token": self.token,
                "Punctuate": "true",
            },
            timeout=60,
        )
        if r.status_code == 200:
            return r.text.strip()
        return self._format_error(r.status_code, r.text)

    def transcribe_long(self, audio_data):
        if not HAS_REQUESTS:
            return "[requests суулгаагүй]"
        r = requests.post(
            f"{CHIMEGE_BASE_URL}/stt-long",
            data=audio_data,
            headers={"Content-Type": "application/octet-stream", "Token": self.token},
            timeout=120,
        )
        if r.status_code != 200:
            return self._format_error(r.status_code, r.text)
        uuid = r.json().get("uuid", "")
        if not uuid:
            return "[UUID хоосон]"
        start = time.time()
        while time.time() - start < 3600:
            time.sleep(3)
            p = requests.get(
                f"{CHIMEGE_BASE_URL}/stt-long-transcript",
                headers={"Token": self.token, "UUID": uuid},
                timeout=30,
            )
            if p.status_code != 200:
                continue
            d = p.json()
            if isinstance(d, list) and all(i.get("done") for i in d) and d:
                return " ".join(i.get("transcription", "") for i in d if i.get("transcription"))
            if isinstance(d, dict) and d.get("done"):
                return d.get("transcription", "")
        return "[Хугацаа хэтэрлээ]"

    def transcribe(self, audio_data):
       
        return self.transcribe_long(audio_data)


class GeminiService:
    def __init__(self, api_key=None):
        self.api_key = api_key or get_credential("gemini_api_key")
        self.client = None
        self.model = None
        self.rest_model = "gemini-flash-latest"
        if HAS_GEMINI and self.api_key:
            if GEMINI_SDK == "google-generativeai":
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-1.5-flash")
            elif GEMINI_SDK == "google-genai":
                self.client = genai.Client(api_key=self.api_key)
                self.model = "gemini-1.5-flash"


    _RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
    _OVERLOAD_MSG = (
        "Gemini сервер түр ачаалал ихсэж байна. "
        "Хэсэг хугацааны дараа дахин оролдоно уу."
    )

    def _generate_via_rest(self, prompt):
        if not HAS_REQUESTS:
            return None
        if not self.api_key:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.rest_model}:generateContent"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key,
        }

        max_attempts = 4
        backoff = 1.0
        r = None
        for attempt in range(max_attempts):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=60)
            except requests.exceptions.RequestException as exc:
                if attempt < max_attempts - 1:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise RuntimeError(
                    "Хиймэл оюун сервертэй холбогдож чадсангүй. "
                    "Интернэт холболтоо шалгана уу."
                ) from exc

            if r.status_code == 200:
                break
            if r.status_code in self._RETRY_STATUSES and attempt < max_attempts - 1:
                time.sleep(backoff)
                backoff *= 2
                continue
        
            break

        if r is None or r.status_code != 200:
  
            if r is not None and r.status_code in self._RETRY_STATUSES:
                raise RuntimeError(self._OVERLOAD_MSG)
            status = r.status_code if r is not None else "?"
            raise RuntimeError(f"Gemini REST алдаа: {status}")

        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini REST: candidates хоосон байна")

        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            raise RuntimeError("Gemini REST: parts хоосон байна")

        text = parts[0].get("text", "")
        return text.strip()

    def process_transcript(self, text):
        if not self.api_key:
            return {"redacted_text": text, "report": "Gemini API тохируулаагүй.", "sensitive_info": []}

        prompt = f"""
        Дараах хурлын тэмдэглэлээс:
        1) Хувь хүний нууц мэдээлэл (хүний нэр, утасны дугаар, мөнгөн дүн,
           он сар өдөр, байгууллагын нэр, оролцогчдын нэр), мөн газрын нэршил хаяг мөн тэмдэглэлийн онцлогоос шалтгаалан 
            нууцлах шаардлагатай гэсэн мэдээллүүд зэргийг ЯЛГАН
           авч "sensitive_info" жагсаалт болгон өгнө үү. Нууцлалт/солилтыг
           бүү хийнэ — зөвхөн ялган авна.
        2) Мэргэжлийн түвшний хурлын хураангуй ("report") бэлтгэнэ үү.
        3) Албан ёсны тэмдэглэлийн бүтэцтэй талбаруудыг "protocol" объектод
           задлан гаргана уу. Бүтэц нь дараах байдлаар:
           {{
             "doc_title": "тэмдэглэлийн гарчиг, жишээ нь 'ХХК байгуулах тухай хурлын тэмдэглэл'",
             "doc_number": "дугаар (жишээ: '№06'), олдоогүй бол хоосон",
             "date": "хурал болсон огноо (YYYY.MM.DD форматаар, олдоогүй бол хоосон)",
             "city": "хот/орон нутаг (жишээ: 'Улаанбаатар хот')",
             "location": "хурал болсон байршил/өрөөний дэлгэрэнгүй",
             "start_time": "эхэлсэн цаг (HH:MM), олдоогүй бол хоосон",
             "end_time": "дууссан цаг (HH:MM), олдоогүй бол хоосон",
             "attendees": ["хуралд оролцогчдын нэрсийг жагсаалтаар"],
             "agenda": ["хэлэлцэх асуудал тус бүр нэг мөр"],
             "decisions": [
                {{"index": 1, "text": "асуудал бүрийн шийдвэрлэсэн агуулга"}}
             ],
             "reviewer_name": "тэмдэглэлийг хянаж гарын үсэг зурах хүний нэр"
           }}
           Олдохгүй талбарыг хоосон мөр эсвэл хоосон жагсаалт болгоно.

        Хариуг ЗААВАЛ цэвэр JSON форматаар, тайлбаргүй буцаана уу:
        {{
            "redacted_text": "",
            "report": "хурлын хураангуй",
            "sensitive_info": ["extracted_item1", "extracted_item2"],
            "protocol": {{ ... дээрх бүтцийн дагуу ... }}
        }}

        Хурлын тэмдэглэл:
        {text}
        """
        try:
            # Орчин үеийн Gemini SDK-ууд нь алдааны мэдээллийг сайн өгдөггүй тул REST fallback-тай давхар хэрэгжүүлсэн.
            try:
                res_text = self._generate_via_rest(prompt)
            except Exception as rest_exc:
               
                if str(rest_exc) == self._OVERLOAD_MSG:
                    raise
                if GEMINI_SDK == "google-generativeai" and self.model:
                    response = self.model.generate_content(prompt)
                    res_text = response.text
                elif GEMINI_SDK == "google-genai" and self.client and self.model:
                    response = self.client.models.generate_content(model=self.model, contents=prompt)
                    res_text = response.text
                else:
                    raise

            if "```json" in res_text:
                res_text = res_text.split("```json")[1].split("```")[0]
            elif "```" in res_text:
                res_text = res_text.split("```")[1].split("```")[0]

            model_data = json.loads(res_text.strip())
            sensitive_items = _normalize_sensitive_items(model_data.get("sensitive_info", []))
            report_text = (model_data.get("report") or "").strip()
            # "Хурлын тэмдэглэл" body.
            spans = _collect_sensitive_spans(text, sensitive_items)
            redacted_text = _redact_text(text, spans)
            redactions = []
            for start, end in spans:
                token = text[start:end]
                cipher = EncryptionModule.encrypt_sensitive_value(token)
                redactions.append({"index": start, "length": end - start, "ciphertext": cipher})

            # "Хурлын товч агуулга" 
 
            report_spans = _collect_sensitive_spans(report_text, sensitive_items)
            redacted_report = _redact_text(report_text, report_spans)
            report_redactions = []
            for start, end in report_spans:
                token = report_text[start:end]
                try:
                    cipher = EncryptionModule.encrypt_sensitive_value(token)
                except Exception:
             
                    continue
                report_redactions.append(
                    {"index": start, "length": end - start, "ciphertext": cipher}
                )

            protocol = _normalize_protocol(model_data.get("protocol"), sensitive_items)

            return {
                "redacted_text": redacted_text,
                "report": redacted_report,
                "sensitive_info": redactions,
                "report_redactions": report_redactions,
                "protocol": protocol,
            }
        except Exception as e:
            msg = str(e)
        
            if msg == self._OVERLOAD_MSG or "холбогдож чадсангүй" in msg:
                report = msg
            elif "503" in msg or "UNAVAILABLE" in msg.upper() or "OVERLOADED" in msg.upper():
          
                report = self._OVERLOAD_MSG
            else:
                report = f"Алдаа: {msg}"
            return {
                "redacted_text": text,
                "report": report,
                "sensitive_info": [],
                "protocol": {},
            }


class BlockchainConnector:
    def __init__(self):
        """Credentials are loaded from env/config automatically."""
        self.w3 = self.contract = None
        self.account = get_credential("account_address", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
        self.connected = False
        self.error_msg = ""
        if not HAS_WEB3:
            self.error_msg = "web3 суулгаагүй"
            return
        rpc_url = get_credential("rpc_url", "http://127.0.0.1:8545")
        contract_address = get_credential("contract_address", "0x5FbDB2315678afecb367f032d93F642f64180aa3")
        abi_path = get_credential("abi_path", "artifacts/contracts/ProtocolIntegrity.sol/ProtocolIntegrity.json")
        try:
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not self.w3.is_connected():
                self.error_msg = f"Холбогдож чадсангүй: {rpc_url}"
                return
            if os.path.exists(abi_path):
                with open(abi_path, encoding="utf-8") as f:
                    abi = json.load(f)["abi"]
                self.contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address), abi=abi
                )
                self.connected = True
            else:
                self.error_msg = f"ABI олдсонгүй: {abi_path}"
        except Exception as e:
            self.error_msg = str(e)

    def store_hash(self, meeting_id, data_hash):

        if not self.connected:
            return None
        try:
            mid = int(meeting_id)
        except (TypeError, ValueError):
            return None
        try:
            tx = self.contract.functions.storeHash(mid, data_hash).transact(
                {"from": Web3.to_checksum_address(self.account)}
            )
            self.w3.eth.wait_for_transaction_receipt(tx)
            return tx.hex()
        except Exception:
            return None

    def get_hash(self, meeting_id):
        if not self.connected:
            return ""
        try:
            mid = int(meeting_id)
        except (TypeError, ValueError):
            return ""
        try:
            return self.contract.functions.getHash(mid).call()
        except Exception:
            return ""

    def compute_keccak(self, data):
        if self.w3:
            return self.w3.keccak(data).hex()
        return hashlib.sha256(data).hexdigest()


class EncryptionModule:

    RSA_KEY_SIZE = 2056
    RSA_PUBLIC_PATH = RSA_PUBLIC_FILE
    RSA_PRIVATE_PATH = RSA_PRIVATE_LEGACY_FILE      
    RSA_ENC_PRIVATE_PATH = RSA_PRIVATE_ENC_FILE     

    _vault_private_key = None

    @staticmethod
    def is_unlocked() -> bool:
        return EncryptionModule._vault_private_key is not None

    @staticmethod
    def lock() -> None:
        """Drop the in-memory private key. Call on logout / app exit."""
        EncryptionModule._vault_private_key = None

    @staticmethod
    def has_encrypted_private_key() -> bool:
        return os.path.exists(EncryptionModule.RSA_ENC_PRIVATE_PATH)

    @staticmethod
    def has_legacy_private_key() -> bool:
        return os.path.exists(EncryptionModule.RSA_PRIVATE_PATH)

    @staticmethod
    def _load_encrypted_envelope() -> dict:
        with open(EncryptionModule.RSA_ENC_PRIVATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _save_encrypted_envelope(private_key, password: str) -> None:
        if not HAS_FERNET:
            raise RuntimeError("cryptography суулгаагүй байна")
        from cryptography.hazmat.primitives import serialization
        from app_utils import derive_key_from_password

        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        fkey, salt = derive_key_from_password(password)
        ciphertext = Fernet(fkey).encrypt(pem)
        envelope = {
            "version": 1,
            "kdf": "pbkdf2-sha256",
            "salt": base64.b64encode(salt).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        os.makedirs(KEYS_DIR, exist_ok=True)
        tmp = EncryptionModule.RSA_ENC_PRIVATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(envelope, f)
        os.replace(tmp, EncryptionModule.RSA_ENC_PRIVATE_PATH)

    @staticmethod
    def _decrypt_envelope_with_password(password: str):
        """Return the RSA private key object (raises on bad password)."""
        if not HAS_FERNET:
            raise RuntimeError("cryptography суулгаагүй байна")
        from cryptography.hazmat.primitives import serialization
        from app_utils import derive_key_from_password

        envelope = EncryptionModule._load_encrypted_envelope()
        salt = base64.b64decode(envelope["salt"])
        ciphertext = base64.b64decode(envelope["ciphertext"])
        fkey, _ = derive_key_from_password(password, salt)
        pem = Fernet(fkey).decrypt(ciphertext)  # InvalidToken on wrong pw
        return serialization.load_pem_private_key(pem, password=None)

    # ── Public-key side (no password ever needed) ──────────────
    @staticmethod
    def _ensure_public_key():
     
        if not HAS_FERNET:
            raise RuntimeError("cryptography суулгаагүй байна")
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        os.makedirs(KEYS_DIR, exist_ok=True)
        if os.path.exists(EncryptionModule.RSA_PUBLIC_PATH):
            with open(EncryptionModule.RSA_PUBLIC_PATH, "rb") as f:
                return serialization.load_pem_public_key(f.read())

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=EncryptionModule.RSA_KEY_SIZE,
        )
        public_key = private_key.public_key()
        with open(EncryptionModule.RSA_PUBLIC_PATH, "wb") as f:
            f.write(
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

        with open(EncryptionModule.RSA_PRIVATE_PATH, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
        return public_key

    @staticmethod
    def set_master_password(new_password: str, current_password: str | None = None) -> None:

        if not HAS_FERNET:
            raise RuntimeError("cryptography суулгаагүй байна")
        if not new_password:
            raise ValueError("Шинэ нууц үг хоосон байна")
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        os.makedirs(KEYS_DIR, exist_ok=True)

        private_key = None
        if os.path.exists(EncryptionModule.RSA_ENC_PRIVATE_PATH):
          
            if not current_password:
                raise ValueError("Одоогийн нууц үг шаардлагатай")
            private_key = EncryptionModule._decrypt_envelope_with_password(current_password)
        elif os.path.exists(EncryptionModule.RSA_PRIVATE_PATH):
          
            with open(EncryptionModule.RSA_PRIVATE_PATH, "rb") as f:
                private_key = serialization.load_pem_private_key(f.read(), password=None)
        else:
         
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=EncryptionModule.RSA_KEY_SIZE,
            )

        public_key = private_key.public_key()
        with open(EncryptionModule.RSA_PUBLIC_PATH, "wb") as f:
            f.write(
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

        EncryptionModule._save_encrypted_envelope(private_key, new_password)

        # Plaintext private (if any) is no longer needed.
        if os.path.exists(EncryptionModule.RSA_PRIVATE_PATH):
            try:
                os.remove(EncryptionModule.RSA_PRIVATE_PATH)
            except OSError:
                pass

        # Leave the vault unlocked for the caller.
        EncryptionModule._vault_private_key = private_key

    @staticmethod
    def verify_master_password(password: str) -> bool:
  
        if not password:
            return False
        if not os.path.exists(EncryptionModule.RSA_ENC_PRIVATE_PATH):

            return True
        try:
            EncryptionModule._decrypt_envelope_with_password(password)
            return True
        except Exception:
            return False

    @staticmethod
    def unlock(password: str) -> bool:
      
        if EncryptionModule._vault_private_key is not None:
            return True

        if os.path.exists(EncryptionModule.RSA_ENC_PRIVATE_PATH):
            private_key = EncryptionModule._decrypt_envelope_with_password(password)
            EncryptionModule._vault_private_key = private_key
            return True

        if os.path.exists(EncryptionModule.RSA_PRIVATE_PATH):
            EncryptionModule.set_master_password(password)
            return True

        EncryptionModule.set_master_password(password)
        return True

    @staticmethod
    def encrypt_sensitive_value(value: str) -> str:
        """Public-key side — NEVER requires an unlocked vault."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        public_key = EncryptionModule._ensure_public_key()
        cipher = public_key.encrypt(
            value.encode("utf-8"),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(cipher).decode("ascii")

    @staticmethod
    def decrypt_sensitive_value(ciphertext: str) -> str:
        """Private-key side — requires the session vault to be unlocked."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        if EncryptionModule._vault_private_key is None:
            raise PermissionError(
                "RSA түлхүүрийн сан түгжээтэй. Эхлээд мастер нууц үгээр нэвтэрнэ үү."
            )

        data = base64.b64decode(ciphertext.encode("ascii"))
        plain = EncryptionModule._vault_private_key.decrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return plain.decode("utf-8")

    @staticmethod
    def restore_redacted_text(redacted_text: str, redactions: list[dict]) -> str:
        if not redactions:
            return redacted_text
        chars = list(redacted_text)
        for item in sorted(redactions, key=lambda x: x.get("index", 0), reverse=True):
            start = int(item.get("index", 0))
            length = int(item.get("length", 0))
            if length <= 0:
                continue
            value = EncryptionModule.decrypt_sensitive_value(item.get("ciphertext", ""))
            end = start + length
            chars[start:end] = list(value)
        return "".join(chars)

    @staticmethod
    def restore_protocol(protocol: dict) -> dict:

        if not isinstance(protocol, dict):
            return {}
        field_reds = protocol.get("_field_redactions") or {}
        out = {k: v for k, v in protocol.items() if k != "_field_redactions"}

        scalar_keys = (
            "doc_title", "doc_number", "date", "city",
            "location", "start_time", "end_time", "reviewer_name",
        )
        for key in scalar_keys:
            reds = field_reds.get(key)
            if reds:
                try:
                    out[key] = EncryptionModule.restore_redacted_text(
                        out.get(key, ""), reds
                    )
                except Exception:
                    pass  # Leave redacted if decrypt fails for this field

        for key in ("attendees", "agenda"):
            reds_list = field_reds.get(key)
            if not reds_list:
                continue
            items = out.get(key) or []
            restored = []
            for i, val in enumerate(items):
                reds = reds_list[i] if i < len(reds_list) else []
                try:
                    restored.append(
                        EncryptionModule.restore_redacted_text(val, reds)
                    )
                except Exception:
                    restored.append(val)
            out[key] = restored

        dec_reds_list = field_reds.get("decisions")
        if dec_reds_list:
            decisions = out.get("decisions") or []
            new_decs = []
            for i, d in enumerate(decisions):
                reds = dec_reds_list[i] if i < len(dec_reds_list) else []
                try:
                    text = EncryptionModule.restore_redacted_text(
                        d.get("text", ""), reds
                    )
                except Exception:
                    text = d.get("text", "")
                new_decs.append({"index": d.get("index"), "text": text})
            out["decisions"] = new_decs

        return out
    @staticmethod
    def encrypt_with_password(content, meeting_id, password):
        if not HAS_FERNET:
            return "", "", b""
        from app_utils import derive_key_from_password
        key, salt = derive_key_from_password(password)
        encrypted = Fernet(key).encrypt(content.encode("utf-8"))
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        enc_path = os.path.join(ENCRYPTED_DIR, f"meeting_{ts}_{meeting_id}.enc")
        salt_path = os.path.join(KEYS_DIR, f"salt_{ts}_{meeting_id}.salt")
        with open(enc_path, "wb") as f:
            f.write(encrypted)
        with open(salt_path, "wb") as f:
            f.write(salt)
        return enc_path, salt_path, encrypted

    @staticmethod
    def decrypt_with_password(enc_path, salt_path, password):
        if not HAS_FERNET:
            return None
        try:
            from app_utils import derive_key_from_password
            with open(salt_path, "rb") as f:
                salt = f.read()
            with open(enc_path, "rb") as f:
                data = f.read()
            key, _ = derive_key_from_password(password, salt)
            return Fernet(key).decrypt(data).decode("utf-8")
        except Exception:
            return None
