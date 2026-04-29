from tkinter import messagebox

import customtkinter as ctk

from app_config import ADMIN_ONLY_SETTINGS, APP_VERSION, COLORS, DATA_DIR, HAS_FERNET, HAS_PYAUDIO, HAS_REQUESTS, HAS_WEB3, ROLE_ADMIN
from app_utils import get_settings, save_json


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, org_id, user_role):
        super().__init__(parent, fg_color=COLORS["bg_main"])
        self.user_role = user_role

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkLabel(hdr, text="Тохиргоо", font=ctk.CTkFont(size=22, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w")

        if user_role != ROLE_ADMIN:
            note = ctk.CTkFrame(self, fg_color=COLORS["warning_light"], corner_radius=8)
            note.pack(fill="x", padx=30, pady=(12, 0))
            ctk.CTkLabel(note, text="⚠  API тохиргоог зөвхөн админ эрхтэй хэрэглэгч өөрчлөх боломжтой", font=ctk.CTkFont(size=12), text_color=COLORS["warning"]).pack(padx=12, pady=8)

        s = get_settings()
        card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border_light"])
        card.pack(fill="x", padx=30, pady=(20, 0))

        fields = [
            ("Chimege API токен", "chimege_token", ""),
            ("Gemini API түлхүүр", "gemini_api_key", ""),
            ("Блокчэйн RPC хаяг", "rpc_url", "http://127.0.0.1:8545"),
            ("Гэрээний хаяг", "contract_address", "0x5FbDB2315678afecb367f032d93F642f64180aa3"),
            ("Дансны хаяг", "account_address", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"),
            ("ABI файлын зам", "abi_path", "artifacts/contracts/ProtocolIntegrity.sol/ProtocolIntegrity.json"),
        ]
        self.entries = {}
        for lbl, key, default in fields:
            is_admin_field = key in ADMIN_ONLY_SETTINGS
            is_locked = is_admin_field and user_role != ROLE_ADMIN

            label_text = f"🔒 {lbl}" if is_locked else lbl
            ctk.CTkLabel(card, text=label_text, font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text_primary"] if not is_locked else COLORS["text_muted"]).pack(anchor="w", padx=20, pady=(14, 4))
            e = ctk.CTkEntry(
                card, font=ctk.CTkFont(size=13), height=40,
                fg_color=COLORS["bg_input"] if not is_locked else COLORS["border_light"],
                border_color=COLORS["border"], corner_radius=8,
            )
            e.pack(fill="x", padx=20)
            val = s.get(key, default)
            if is_locked and val:
                # Нууцлагдсан байдлаар харуулах
                masked = val[:4] + "•" * max(0, len(val) - 8) + val[-4:] if len(val) > 8 else "••••••••"
                e.insert(0, masked)
                e.configure(state="disabled")
            else:
                e.insert(0, val)
                if is_locked:
                    e.configure(state="disabled")
            self.entries[key] = e

        if user_role == ROLE_ADMIN:
            ctk.CTkButton(
                card, text="💾  Хадгалах", font=ctk.CTkFont(size=14, weight="bold"),
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], height=44, width=240, corner_radius=8, command=self._save,
            ).pack(pady=20)
        else:
            ctk.CTkLabel(card, text="Тохиргоо өөрчлөхийн тулд админ-аар нэвтэрнэ үү", font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"]).pack(pady=20)

        info = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border_light"])
        info.pack(fill="x", padx=30, pady=(12, 24))
        ctk.CTkLabel(info, text="Системийн мэдээлэл", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(16, 8))

        for label, value in [
            ("Хувилбар", APP_VERSION),
            ("Аудио сан", "✅" if HAS_PYAUDIO else "❌"),
            ("Сүлжээний модуль", "✅" if HAS_REQUESTS else "❌"),
            ("Шифрлэлтийн сан", "✅" if HAS_FERNET else "❌"),
            ("Блокчэйн сан", "✅" if HAS_WEB3 else "❌"),
            ("Яриа таних", "Chimege API v1.2"),
            ("Хиймэл оюун", "Gemini 1.5 Flash"),
            ("Блокчэйн", "Ethereum (Hardhat)"),
            ("Нууц үг хэшлэлт", "PBKDF2-HMAC-SHA256"),
            ("Шифрлэлт", "Fernet + Нууц үгэнд суурилсан (PBKDF2)"),
            ("Өгөгдлийн зам", DATA_DIR),
        ]:
            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12), text_color=COLORS["text_secondary"]).pack(side="left")
            clr = COLORS["danger"] if "❌" in str(value) else COLORS["text_primary"]
            ctk.CTkLabel(row, text=value, font=ctk.CTkFont(size=12), text_color=clr).pack(side="right")
        ctk.CTkFrame(info, height=16, fg_color="transparent").pack()

    def _save(self):
        from app_config import SETTINGS_FILE
        # Admin-д зөвхөн бодит утгуудыг хадгална
        data = {}
        for k, e in self.entries.items():
            if str(e.cget("state")) != "disabled":
                data[k] = e.get().strip()
            else:
                # Disabled entry-ийн хуучин утгыг хадгална
                old = get_settings()
                data[k] = old.get(k, "")
        save_json(SETTINGS_FILE, data)
        messagebox.showinfo("Амжилттай", "Тохиргоо хадгалагдлаа!")
