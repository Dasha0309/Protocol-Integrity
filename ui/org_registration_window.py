import customtkinter as ctk

from datetime import datetime

from app_config import COLORS, ORG_DB_FILE, ROLE_ADMIN
from app_utils import hash_password, load_json, save_json, validate_email, validate_password, validate_phone


class OrgRegistrationWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success
        self.title("Байгууллага бүртгүүлэх")
        self.geometry("520x600")
        self.minsize(500, 520)
        self.resizable(False, True)
        self.configure(fg_color=COLORS["bg_main"])
        self.grab_set()
        self.step = 0

        self.step_count = 3
        self.step_indicators = []

        sf = ctk.CTkFrame(self, fg_color="transparent", height=20)
        sf.pack(fill="x", padx=40, pady=(18, 10))
        sf.pack_propagate(False)
        sf.grid_propagate(False)
        sf.rowconfigure(0, weight=1)

        for i in range(self.step_count * 2 - 1):
            sf.columnconfigure(i, weight=1 if i % 2 == 0 else 0)

        for i in range(self.step_count):
            col_idx = i * 2
            line = ctk.CTkFrame(
                sf, height=4, corner_radius=2,
                fg_color=COLORS["accent"] if i == 0 else COLORS["border_light"],
            )
            line.grid(row=0, column=col_idx, sticky="ew", padx=2)
            self.step_indicators.append(line)
            if i < self.step_count - 1:
                sep = ctk.CTkFrame(sf, fg_color="transparent", width=20, height=4)
                sep.grid(row=0, column=col_idx + 1)

        self.card = ctk.CTkFrame(
            self, fg_color=COLORS["bg_card"], corner_radius=12,
            border_width=1, border_color=COLORS["border_light"],
        )
        self.card.pack(fill="both", expand=True, padx=40, pady=(0, 12))
        self._build_pages()
        self._show_page(0)

    def _build_pages(self):
        self.pages = []

        p0 = ctk.CTkScrollableFrame(self.card, fg_color="transparent")
        self._page_header(p0, "Байгууллагын мэдээлэл", "Байгууллагын үндсэн мэдээллийг оруулна уу")
        self.org_name = self._field(p0, "Байгууллагын нэр", "Жишээ: Монгол Технологи ХХК")
        self.org_reg = self._field(p0, "Регистрийн дугаар", "1234567")
        self.err0 = self._error_label(p0)
        self._nav_buttons(p0, back=None, next_cmd=lambda: self._next(0))
        self.pages.append(p0)

        p1 = ctk.CTkScrollableFrame(self.card, fg_color="transparent")
        self._page_header(p1, "Холбоо барих мэдээлэл", "Утас болон и-мэйл хаягаа оруулна уу")
        self.org_phone = self._field(p1, "Утасны дугаар", "+976 9900 0000")
        self.org_email = self._field(p1, "И-мэйл хаяг", "info@company.mn")
        self.err1 = self._error_label(p1)
        self._nav_buttons(p1, back=lambda: self._show_page(0), next_cmd=lambda: self._next(1))
        self.pages.append(p1)

        p2 = ctk.CTkScrollableFrame(self.card, fg_color="transparent")
        self._page_header(p2, "Админ бүртгэл", "Системд нэвтрэх мэдээллийг тохируулна уу")
        self.admin_name = self._field(p2, "Овог нэр", "Бат-Эрдэнэ Дорж")
        self.admin_pass = self._field(p2, "Нууц үг", "••••••••", show="*")
        self.admin_pass2 = self._field(p2, "Нууц үг давтах", "••••••••", show="*")

        req_frame = ctk.CTkFrame(p2, fg_color=COLORS["accent_light"], corner_radius=8)
        req_frame.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkLabel(
            req_frame, text="Нууц үгийн шаардлага: 8+ тэмдэгт, том үсэг, жижиг үсэг, тоо",
            font=ctk.CTkFont(size=11), text_color=COLORS["accent"], wraplength=420,
        ).pack(padx=12, pady=6)

        self.err2 = self._error_label(p2)
        self._nav_buttons(p2, back=lambda: self._show_page(1), next_cmd=self._submit_registration, next_label="Бүртгэл хадгалах")
        self.pages.append(p2)

    def _page_header(self, parent, title, subtitle):
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(14, 2))
        ctk.CTkLabel(parent, text=subtitle, font=ctk.CTkFont(size=12), text_color=COLORS["text_secondary"]).pack(anchor="w", padx=20)

    def _field(self, parent, label, placeholder, show=None):
        ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(12, 3))
        entry = ctk.CTkEntry(
            parent, placeholder_text=placeholder, font=ctk.CTkFont(size=13), height=38,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"], corner_radius=8, show=show or "",
        )
        entry.pack(fill="x", padx=20)
        return entry

    def _error_label(self, parent):
        lbl = ctk.CTkLabel(parent, text="", font=ctk.CTkFont(size=12), text_color=COLORS["danger"])
        lbl.pack(anchor="w", padx=20, pady=(4, 0))
        return lbl

    def _nav_buttons(self, parent, back, next_cmd, next_label="Дараах →"):
        bf = ctk.CTkFrame(parent, fg_color="transparent")
        bf.pack(fill="x", padx=20, pady=(10, 14))
        if back:
            ctk.CTkButton(
                bf, text="← Буцах", width=90, height=40,
                fg_color=COLORS["bg_input"], hover_color=COLORS["border_light"],
                text_color=COLORS["text_primary"], corner_radius=8, font=ctk.CTkFont(size=13), command=back,
            ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            bf, text=next_label, font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], height=40, corner_radius=8, command=next_cmd,
        ).pack(side="left", fill="x", expand=True)

    def _show_page(self, idx):
        for p in self.pages:
            p.pack_forget()
        self.pages[idx].pack(fill="both", expand=True)
        self.step = idx
        for i, line in enumerate(self.step_indicators):
            line.configure(fg_color=COLORS["accent"] if i <= idx else COLORS["border_light"])

    def _next(self, from_step):
        if from_step == 0:
            self.err0.configure(text="")
            name = self.org_name.get().strip()
            reg = self.org_reg.get().strip()
            if not name or not reg:
                self.err0.configure(text="Бүх талбарыг бөглөнө үү")
                return
            if len(name) < 2:
                self.err0.configure(text="Байгууллагын нэр хэт богино")
                return
            orgs = load_json(ORG_DB_FILE)
            if isinstance(orgs, dict) and reg.replace(" ", "") in orgs:
                self.err0.configure(text="Энэ регистрийн дугаар бүртгэлтэй байна")
                return
            self._show_page(1)
        elif from_step == 1:
            self.err1.configure(text="")
            phone = self.org_phone.get().strip()
            email = self.org_email.get().strip()
            if not phone or not email:
                self.err1.configure(text="Бүх талбарыг бөглөнө үү")
                return
            if not validate_phone(phone):
                self.err1.configure(text="Утасны дугаарын формат буруу")
                return
            if not validate_email(email):
                self.err1.configure(text="И-мэйл хаягийн формат буруу")
                return
            self._show_page(2)

    def _submit_registration(self):
        self.err2.configure(text="")
        admin = self.admin_name.get().strip()
        pw1 = self.admin_pass.get()
        pw2 = self.admin_pass2.get()
        if not admin or not pw1:
            self.err2.configure(text="Бүх талбарыг бөглөнө үү")
            return
        if pw1 != pw2:
            self.err2.configure(text="Нууц үг таарахгүй байна")
            return
        pw_err = validate_password(pw1)
        if pw_err:
            self.err2.configure(text=pw_err)
            return

        orgs = load_json(ORG_DB_FILE)
        if not isinstance(orgs, dict):
            orgs = {}
        org_id = self.org_reg.get().strip().replace(" ", "")
        email = self.org_email.get().strip()
        orgs[org_id] = {
            "name": self.org_name.get().strip(),
            "reg_number": self.org_reg.get().strip(),
            "phone": self.org_phone.get().strip(),
            "email": email,
            "admin_name": admin,
            "created_at": datetime.now().isoformat(),
            "users": [
                {"name": admin, "email": email, "role": ROLE_ADMIN, "password": hash_password(pw1)}
            ],
        }
        save_json(ORG_DB_FILE, orgs)
        self.on_success(org_id, self.org_name.get().strip())
        self.destroy()
