import os
from tkinter import filedialog

import customtkinter as ctk

from app_config import COLORS
from app_services import BlockchainConnector
from app_utils import get_settings

class VerifyPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_main"])

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkLabel(hdr, text="Баталгаажуулалт", font=ctk.CTkFont(size=22, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Блокчэйн дээрх hash-тай харьцуулж шалгана", font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(2, 0))

        form = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border_light"])
        form.pack(fill="x", padx=30, pady=(20, 0))

        ctk.CTkLabel(form, text="Хурлын ID", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(20, 4))
        self.id_e = ctk.CTkEntry(form, placeholder_text="1713012345", font=ctk.CTkFont(size=13), height=40, fg_color=COLORS["bg_input"], border_color=COLORS["border"], corner_radius=8)
        self.id_e.pack(fill="x", padx=20)

        ctk.CTkLabel(form, text="Архивлагдсан WAV файл (.wav)", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(14, 4))
        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", padx=20)
        self.wav_e = ctk.CTkEntry(row, placeholder_text="WAV файл сонгоно уу...", font=ctk.CTkFont(size=13), height=40, fg_color=COLORS["bg_input"], border_color=COLORS["border"], corner_radius=8)
        self.wav_e.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="📂", width=40, height=40, fg_color=COLORS["border_light"], hover_color=COLORS["border"], text_color=COLORS["text_primary"], corner_radius=8, command=lambda: self._browse(self.wav_e)).pack(side="left", padx=(6, 0))

        ctk.CTkButton(form, text="🔍  Баталгаажуулах", font=ctk.CTkFont(size=14, weight="bold"), fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], height=44, width=240, corner_radius=8, command=self._verify).pack(pady=(20, 20))

        self.rf = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border_light"])
        self.rf.pack(fill="both", expand=True, padx=30, pady=(12, 24))
        self.rl = ctk.CTkLabel(self.rf, text="Баталгаажуулалтын үр дүн энд харагдана", font=ctk.CTkFont(size=14), text_color=COLORS["text_muted"])
        self.rl.pack(pady=30)
        self.rt = ctk.CTkTextbox(self.rf, font=ctk.CTkFont(size=13), fg_color=COLORS["bg_input"], corner_radius=8, text_color=COLORS["text_primary"], height=200)

    def _browse(self, entry):
        p = filedialog.askopenfilename()
        if p:
            entry.delete(0, "end")
            entry.insert(0, p)

    def _verify(self):
        mid_s = self.id_e.get().strip()
        wp = self.wav_e.get().strip()
        if not all([mid_s, wp]):
            self.rl.configure(text="⚠ Бүх талбарыг бөглөнө үү", text_color=COLORS["danger"])
            return
        try:
            mid = int(mid_s)
        except ValueError:
            self.rl.configure(text="⚠ Хурлын ID тоо байх ёстой", text_color=COLORS["danger"])
            return
        if not os.path.exists(wp):
            self.rl.configure(text="⚠ WAV файл олдсонгүй", text_color=COLORS["danger"])
            return

        with open(wp, "rb") as f:
            wav_data = f.read()

        s = get_settings()
        bc = BlockchainConnector(
            s.get("rpc_url", "http://127.0.0.1:8545"),
            s.get("contract_address", "0x5FbDB2315678afecb367f032d93F642f64180aa3"),
            s.get("abi_path", "artifacts/contracts/ProtocolIntegrity.sol/ProtocolIntegrity.json"),
            s.get("account_address", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"),
        )
        local_hash = bc.compute_keccak(wav_data)
        bc_hash = bc.get_hash(mid) if bc.connected else ""

        lines = [
            f"Хурлын ID: {mid}",
            f"Блокчэйн дэх WAV хэш: {bc_hash or '(холбогдоогүй)'}",
            f"Локал WAV хэш:        {local_hash}",
            "",
        ]
        if not bc.connected:
            lines.append(f"⚠ Блокчэйнтэй холбогдоогүй: {bc.error_msg}")
            self.rl.configure(text="⚠ Блокчэйнтэй холбогдоогүй", text_color=COLORS["warning"])
        elif bc_hash == local_hash:
            self.rl.configure(text="✅  БАТАЛГААЖЛАА: WAV файл өөрчлөгдөөгүй", text_color=COLORS["success"])
            lines.append("Статус: Хэш таарч байна ✓")
        else:
            self.rl.configure(text="❌  Хэш таарахгүй — WAV өөрчлөгдсөн!", text_color=COLORS["danger"])
            lines.append("Статус: ТААРАХГҮЙ ✗")

        self.rl.pack(pady=(16, 4))
        self.rt.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.rt.configure(state="normal")
        self.rt.delete("1.0", "end")
        self.rt.insert("1.0", "\n".join(lines))
