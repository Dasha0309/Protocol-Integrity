import customtkinter as ctk

from app_config import APP_NAME, COLORS, ROLE_ADMIN
from app_utils import load_org


class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, user_name, user_role, on_nav, on_logout):
        super().__init__(parent, width=250, fg_color=COLORS["bg_card"], border_width=0)
        self.pack_propagate(False)
        self.on_nav = on_nav

        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", padx=16, pady=(20, 4))
        ic = ctk.CTkFrame(h, width=40, height=40, fg_color=COLORS["text_primary"], corner_radius=10)
        ic.pack(side="left")
        ic.pack_propagate(False)
        ctk.CTkLabel(ic, text="🔒", font=ctk.CTkFont(size=18), text_color="white").place(relx=0.5, rely=0.5, anchor="center")

        nf = ctk.CTkFrame(h, fg_color="transparent")
        nf.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(nf, text=APP_NAME, font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w")
        # Prefer the registered organization's name so the sidebar
        # reflects the actual tenant; fall back to a generic Mongolian
        # label on fresh installs.
        try:
            org_label = (load_org() or {}).get("name", "").strip() or "Байгууллага"
        except Exception:
            org_label = "Байгууллага"
        ctk.CTkLabel(nf, text=org_label[:20], font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"]).pack(anchor="w")

        ctk.CTkFrame(self, height=1, fg_color=COLORS["border_light"]).pack(fill="x", padx=16, pady=(16, 12))

        menu_items = [
            ("record",    "🎙  Хурал хөтлөх"),
            ("documents", "📄  Бичлэгүүд"),
            ("trash",     "🗑  Хогийн сав"),
        ]
        # Admin-д нэмэлт цэс
        if user_role == ROLE_ADMIN:
            menu_items.append(("admin", "🛡  Админ удирдлага"))

        self.btns = {}
        for k, label in menu_items:
            b = ctk.CTkButton(
                self, text=label, font=ctk.CTkFont(size=14),
                fg_color="transparent", hover_color=COLORS["accent_light"],
                text_color=COLORS["text_primary"], anchor="w", height=40, corner_radius=8,
                command=lambda x=k: self._click(x),
            )
            b.pack(fill="x", padx=12, pady=2)
            self.btns[k] = b
        self._click("record")

        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)
        ctk.CTkFrame(self, height=1, fg_color=COLORS["border_light"]).pack(fill="x", padx=16, pady=(0, 8))

        uf = ctk.CTkFrame(self, fg_color="transparent")
        uf.pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(uf, text=f"👤  {user_name}", font=ctk.CTkFont(size=13), text_color=COLORS["text_primary"]).pack(anchor="w")
        role_display = "Админ" if user_role == ROLE_ADMIN else "Хэрэглэгч"
        ctk.CTkLabel(uf, text=f"     {role_display}", font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"]).pack(anchor="w")

        ctk.CTkButton(
            self, text="↪  Гарах", font=ctk.CTkFont(size=13),
            fg_color="transparent", hover_color=COLORS["danger_light"],
            text_color=COLORS["text_secondary"], anchor="w", height=36, corner_radius=8, command=on_logout,
        ).pack(fill="x", padx=12, pady=(4, 16))

    def set_active(self, k):
        """Sidebar highlight-г шинэчлэх (навигаци дуудахгүй)."""
        for x, b in self.btns.items():
            b.configure(
                fg_color=COLORS["accent_light"] if x == k else "transparent",
                text_color=COLORS["accent"] if x == k else COLORS["text_primary"],
            )

    def _click(self, k):
        self.set_active(k)
        self.on_nav(k)
