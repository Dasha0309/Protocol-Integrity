from datetime import datetime

import customtkinter as ctk

from app_config import COLORS, ROLE_ADMIN
from app_services import EncryptionModule
from app_utils import hash_password, save_org, validate_email, validate_password, validate_phone


class OrgSetupWindow(ctk.CTkFrame):
    """First-run setup: register the single organization and admin account."""

    def __init__(self, parent, on_done):
        super().__init__(parent, fg_color=COLORS["bg_main"])
        self.on_done = on_done

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        c = ctk.CTkFrame(scroll, fg_color="transparent", width=460)
        c.pack(fill="x", expand=True, padx=8, pady=8)

        ctk.CTkLabel(
            c, text="🔒  Анхны тохиргоо",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(0, 4))
        ctk.CTkLabel(
            c, text="Байгууллага болон админ бүртгэлийг тохируулна уу",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_secondary"],
        ).pack(pady=(0, 20))

        card = ctk.CTkFrame(
            c, fg_color=COLORS["bg_card"], corner_radius=12,
            border_width=1, border_color=COLORS["border_light"],
        )
        card.pack(fill="x")

        # Org fields
        self.org_name = self._field(card, "Байгууллагын нэр", "Монгол Технологи ХХК")
        self.org_reg = self._field(card, "Регистрийн дугаар", "1234567")
        self.org_phone = self._field(card, "Утас", "+976 9900 0000")
        self.org_email = self._field(card, "Байгууллагын и-мэйл", "info@company.mn")

        # Separator
        ctk.CTkFrame(card, height=1, fg_color=COLORS["border_light"]).pack(fill="x", padx=20, pady=(12, 4))
        ctk.CTkLabel(
            card, text="Админ бүртгэл",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", padx=20, pady=(8, 0))

        self.admin_name = self._field(card, "Овог нэр", "Бат-Эрдэнэ Дорж")
        self.admin_email = self._field(card, "Админ и-мэйл", "admin@company.mn")
        self.admin_pass = self._field(card, "Нууц үг", "••••••••", show="*")
        self.admin_pass2 = self._field(card, "Нууц үг давтах", "••••••••", show="*")

        self.err = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=12), text_color=COLORS["danger"])
        self.err.pack(anchor="w", padx=20, pady=(4, 0))

        ctk.CTkButton(
            card, text="Бүртгэх",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORS["text_primary"], hover_color="#343a40",
            text_color="white", height=44, corner_radius=8,
            command=self._submit,
        ).pack(fill="x", padx=20, pady=(12, 20))

    def _field(self, parent, label, placeholder, show=None):
        ctk.CTkLabel(
            parent, text=label,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", padx=20, pady=(10, 2))
        entry = ctk.CTkEntry(
            parent, placeholder_text=placeholder,
            font=ctk.CTkFont(size=13), height=38,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            corner_radius=8, show=show or "",
        )
        entry.pack(fill="x", padx=20)
        return entry

    def _submit(self):
        self.err.configure(text="")
        name = self.org_name.get().strip()
        reg = self.org_reg.get().strip()
        phone = self.org_phone.get().strip()
        org_email = self.org_email.get().strip()
        admin = self.admin_name.get().strip()
        adm_email = self.admin_email.get().strip()
        pw1 = self.admin_pass.get()
        pw2 = self.admin_pass2.get()

        if not all([name, reg, phone, org_email, admin, adm_email, pw1]):
            self.err.configure(text="Бүх талбарыг бөглөнө үү")
            return
        if len(name) < 2:
            self.err.configure(text="Байгууллагын нэр хэт богино")
            return
        if not validate_phone(phone):
            self.err.configure(text="Утасны дугаар буруу")
            return
        if not validate_email(org_email):
            self.err.configure(text="Байгууллагын и-мэйл буруу")
            return
        if not validate_email(adm_email):
            self.err.configure(text="Админ и-мэйл буруу")
            return
        if pw1 != pw2:
            self.err.configure(text="Нууц үг таарахгүй")
            return
        pw_err = validate_password(pw1)
        if pw_err:
            self.err.configure(text=pw_err)
            return

        save_org({
            "name": name,
            "reg_number": reg,
            "phone": phone,
            "email": org_email,
            "created_at": datetime.now().isoformat(),
            "users": [
                {
                    "name": admin,
                    "email": adm_email,
                    "role": ROLE_ADMIN,
                    "password": hash_password(pw1),
                    "is_active": True,
                }
            ],
        })

        # Seed the RSA keypair + encrypted-envelope private key using
        # the admin's password as the master password.  This ensures
        # the very first login already has a password-protected vault
        # to unlock — no plaintext private key ever touches disk in
        # a fresh install.
        try:
            EncryptionModule.set_master_password(pw1)
            EncryptionModule.lock()  # re-lock; real unlock happens at login
        except Exception as exc:
            # Non-fatal: the vault will auto-initialize on first
            # login instead.  Log for visibility.
            import sys
            print(f"[org-setup] vault seed failed: {exc}", file=sys.stderr)

        self.on_done()
