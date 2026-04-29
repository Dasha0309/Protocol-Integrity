from tkinter import messagebox

import customtkinter as ctk

from app_config import COLORS
from app_utils import get_trashed_meetings, permanent_delete_meeting, restore_meeting


class TrashPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="#F3F4F6")
        self._build_ui()
        self._reload()

    def _build_ui(self):
        # ── Header ───────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=36, pady=(28, 0))

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", fill="y")

        ctk.CTkLabel(
            left, text="Хогийн сав", #🗑 
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text="Устгасан бичлэгүүд энд хадгалагдана",
            font=ctk.CTkFont(size=15),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", pady=(3, 0))

        ctk.CTkButton(
            hdr, text="🗑  Бүгдийг устгах",
            width=160, height=38, corner_radius=10,
            fg_color="#DC2626", hover_color="#B91C1C", text_color="#FFFFFF",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._clear_all,
        ).pack(side="right", anchor="center", padx=(0, 12))

        # ── Count label ──────────────────────────────────────────
        self._count_lbl = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#6B7280",
        )
        self._count_lbl.pack(anchor="w", padx=36, pady=(18, 4))

        # ── Scrollable list ──────────────────────────────────────
        self._list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._list.pack(fill="both", expand=True, padx=36, pady=(0, 20))

    def _reload(self):
        for w in self._list.winfo_children():
            w.destroy()

        items = get_trashed_meetings()
        # Хамгийн сүүлд устгасан нь эхэнд
        items = sorted(items, key=lambda m: str(m.get("trashed_at", "")), reverse=True)

        self._count_lbl.configure(text=f"{len(items)} бичлэг")

        if not items:
            ctk.CTkLabel(
                self._list,
                text="Хогийн сав хоосон байна",
                font=ctk.CTkFont(size=16),
                text_color=COLORS["text_muted"],
            ).pack(pady=60)
            return

        for m in items:
            self._card(m)

    def _card(self, m):
        card = ctk.CTkFrame(
            self._list, fg_color="#FFFFFF", corner_radius=12,
            border_width=1, border_color="#888888",
        )
        card.pack(fill="x", pady=6)

        inn = ctk.CTkFrame(card, fg_color="transparent")
        inn.pack(fill="both", expand=True, padx=18, pady=14)

        # Icon
        icon = ctk.CTkFrame(inn, width=46, height=46, fg_color="#F3F4F6", corner_radius=10)
        icon.pack(side="left", anchor="n")
        icon.pack_propagate(False)
        ctk.CTkLabel(
            icon, text="🗑", font=ctk.CTkFont(size=22), text_color="#6B7280",
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Body
        body = ctk.CTkFrame(inn, fg_color="transparent")
        body.pack(side="left", fill="x", expand=True, padx=(14, 10))

        ctk.CTkLabel(
            body, text=m.get("title", "Нэргүй бичлэг"),
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        preview = (m.get("report") or m.get("description") or "")[:120]
        if preview and len(preview) == 120:
            preview += "..."
        if preview:
            ctk.CTkLabel(
                body, text=preview,
                font=ctk.CTkFont(size=13),
                text_color=COLORS["text_secondary"],
            ).pack(anchor="w", pady=(3, 0))

        meta = ctk.CTkFrame(body, fg_color="transparent")
        meta.pack(anchor="w", pady=(6, 0))

        ctk.CTkLabel(
            meta, text=f"🕐 {m.get('date', '')}",
            font=ctk.CTkFont(size=12), text_color="#6B7280",
        ).pack(side="left")

        trashed_at = m.get("trashed_at", "")
        if trashed_at:
            try:
                # ISO -> хялбар харагдалт
                short = trashed_at[:16].replace("T", "  ")
            except Exception:
                short = trashed_at
            ctk.CTkLabel(
                meta, text=f"   Устгасан: {short}",
                font=ctk.CTkFont(size=12), text_color="#DC2626",
            ).pack(side="left")

        # Action buttons
        act = ctk.CTkFrame(inn, fg_color="transparent")
        act.pack(side="right", anchor="n")

        action_btn_width = 140

        ctk.CTkButton(
            act, text="↩  Сэргээх",
            width=action_btn_width, height=34, corner_radius=8,
            fg_color="#7C5CFC", hover_color="#6344E8", text_color="#FFFFFF",
            border_width=1, border_color="#888888",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda x=m: self._restore(x),
        ).pack(pady=3)
    
        ctk.CTkButton(
            act, text="Бүрмөсөн устгах",
            width=action_btn_width, height=34, corner_radius=8,
            fg_color="#FFFFFF", hover_color="#FEE2E2", text_color="#B91C1C",
            border_width=1, border_color="#888888",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda x=m: self._perm_delete(x),
        ).pack(pady=3)

    def _restore(self, m):
        restore_meeting(m.get("id"))
        self._reload()

    def _perm_delete(self, m):
        title = m.get("title", "энэ бичлэг")
        if not messagebox.askyesno(
            "Бүрмөсөн устгах",
            f'"{title}"\nбүрмөсөн устгах уу?\n\nЭнэ үйлдлийг буцаах боломжгүй.',
            icon="warning",
        ):
            return
        permanent_delete_meeting(m.get("id"))
        self._reload()

    def _clear_all(self):
        items = get_trashed_meetings()
        if not items:
            return
        if not messagebox.askyesno(
            "Бүгдийг устгах",
            f"Хогийн савны {len(items)} бичлэгийг бүрмөсөн устгах уу?\n\nЭнэ үйлдлийг буцаах боломжгүй.",
            icon="warning",
        ):
            return
        for m in items:
            permanent_delete_meeting(m.get("id"))
        self._reload()
