import time

import customtkinter as ctk

from app_config import APP_NAME, COLORS, LOGIN_LOCKOUT_SECONDS, MAX_LOGIN_ATTEMPTS
from app_services import EncryptionModule
from app_utils import find_user, load_org, validate_email, verify_password


class LoginWindow(ctk.CTkFrame):
    def __init__(self, parent, on_login):
        super().__init__(parent, fg_color=COLORS["bg_main"])
        self.on_login = on_login
        self.login_attempts = 0
        self.locked_until = 0.0

        # Outer card frame
        card = ctk.CTkFrame(
            self,
            fg_color="#FFFFFF",
            corner_radius=16,
            width=420,
            height=480,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        # Inner content column — centered inside card
        c = ctk.CTkFrame(card, fg_color="transparent", width=360)
        c.place(relx=0.5, rely=0.5, anchor="center")

        # ── Logo icon ──────────────────────────────────────────
        ic = ctk.CTkFrame(
            c, width=56, height=56,
            fg_color=COLORS["text_primary"], corner_radius=14,
        )
        ic.pack(pady=(0, 8))
        ic.pack_propagate(False)
        ctk.CTkLabel(
            ic, text="🔒", font=ctk.CTkFont(size=24), text_color="white",
        ).place(relx=0.5, rely=0.5, anchor="center")

        # ── App name ───────────────────────────────────────────
        ctk.CTkLabel(
            c, text=APP_NAME,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack()

        # ── Org name ───────────────────────────────────────────
        org = load_org()
        org_name = org.get("name", "")
        if org_name:
            ctk.CTkLabel(
                c, text=org_name,
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text_secondary"],
            ).pack(pady=(2, 16))
        else:
            ctk.CTkFrame(c, height=16, fg_color="transparent").pack()

        # ── Divider ────────────────────────────────────────────
        ctk.CTkFrame(c, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=8, pady=(0, 14))

        # ── Email label + entry ────────────────────────────────
        ctk.CTkLabel(
            c, text="Имэйл",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", padx=8)
        self.email = ctk.CTkEntry(
            c, placeholder_text="email@company.mn",
            font=ctk.CTkFont(size=13), height=40,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            corner_radius=8, width=360,
        )
        self.email.pack(fill="x", padx=8, pady=(3, 8))
        self.email.bind("<FocusIn>", lambda e: self.email.configure(border_color=COLORS["text_primary"]))
        self.email.bind("<FocusOut>", lambda e: self.email.configure(border_color=COLORS["border"]))

        # ── Password label + entry ─────────────────────────────
        ctk.CTkLabel(
            c, text="Нууц үг",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", padx=8)
        self.pw = ctk.CTkEntry(
            c, placeholder_text="Нууц үг оруулах", show="*",
            font=ctk.CTkFont(size=13), height=40,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            corner_radius=8, width=360,
        )
        self.pw.pack(fill="x", padx=8, pady=(3, 4))
        self.pw.bind("<FocusIn>", lambda e: self.pw.configure(border_color=COLORS["text_primary"]))
        self.pw.bind("<FocusOut>", lambda e: self.pw.configure(border_color=COLORS["border"]))

        # ── Error label ────────────────────────────────────────
        self.err = ctk.CTkLabel(
            c, text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["danger"],
        )
        self.err.pack(pady=(0, 6))

        # ── Login button ───────────────────────────────────────
        self.login_btn = ctk.CTkButton(
            c, text="Нэвтрэх",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["text_primary"], hover_color="#343a40",
            text_color="white", height=42, corner_radius=8,
            command=self._login,
        )
        self.login_btn.pack(fill="x", padx=8)

        # ── Secondary links (Register / Forgot password) ───────
        links = ctk.CTkFrame(c, fg_color="transparent")
        links.pack(fill="x", padx=8, pady=(10, 0))
        self._make_link(links, "Бүртгүүлэх", self._open_register, "left")
        self._make_link(links, "Нууц үг мартсан", self._forgot_password, "right")

        # ── Bottom note ────────────────────────────────────────
        ctk.CTkFrame(c, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=8, pady=(14, 6))
        ctk.CTkLabel(
            c, text="🔐 Блокчэйн болон хиймэл оюунд суурилсан хурлын систем",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        ).pack()

        # ── Key bindings ───────────────────────────────────────
        self.pw.bind("<Return>", lambda e: self._login())
        self.email.bind("<Return>", lambda e: self.pw.focus())

    def _make_link(self, parent, text, command, side):
        lbl = ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_primary"],
            cursor="hand2",
        )
        lbl.pack(side=side)
        lbl.bind("<Button-1>", lambda e: command())
        lbl.bind("<Enter>", lambda e: lbl.configure(text_color=COLORS["text_secondary"]))
        lbl.bind("<Leave>", lambda e: lbl.configure(text_color=COLORS["text_primary"]))
        return lbl

    def _open_register(self):
        from ui.org_registration_window import OrgRegistrationWindow
        OrgRegistrationWindow(self, on_success=lambda org_id, name: None)

    def _forgot_password(self):
        from tkinter import messagebox
        messagebox.showinfo("Нууц үг мартсан", "Админд хандаж нууц үгээ сэргээнэ үү.")

    def _login(self):
        now = time.time()
        if now < self.locked_until:
            self.err.configure(text=f"Түр хүлээнэ үү ({int(self.locked_until - now)}с)")
            return

        em = self.email.get().strip()
        pw = self.pw.get()

        if not em:
            self.err.configure(text="Имэйл оруулна уу")
            return
        if not validate_email(em):
            self.err.configure(text="Имэйл формат буруу")
            return
        if not pw:
            self.err.configure(text="Нууц үг оруулна уу")
            return

        idx, user = find_user(em)
        if user and verify_password(pw, user["password"]):
            if not user.get("is_active", True):
                self.err.configure(text="Таны бүртгэл идэвхгүй болсон")
                return

            # Unlock the RSA private-key vault with the same password.
            # Login password == master password: one credential, one UX.
            # Auto-migrates legacy plaintext keys the first time a user
            # logs in after upgrade, and auto-generates keys on brand-new
            # installs — all transparent to the user.
            try:
                EncryptionModule.unlock(pw)
            except Exception as exc:
                # Wrong envelope password (user's login pw doesn't match
                # the one that originally encrypted the RSA key — can
                # happen if the admin changed their password via the
                # user-store without rotating the vault).
                self.err.configure(
                    text="❌ RSA сан нээгдсэнгүй — админтай холбогдоно уу"
                )
                # Don't leak the exception to the user, but don't let
                # them into the app half-broken either.
                try:
                    EncryptionModule.lock()
                except Exception:
                    pass
                # Log once to stderr for debugging.
                import sys
                print(f"[login] vault unlock failed: {exc}", file=sys.stderr)
                return

            self.login_attempts = 0
            self.on_login(user["name"], user["role"])
            return

        # Failed
        self.login_attempts += 1
        remaining = MAX_LOGIN_ATTEMPTS - self.login_attempts
        if self.login_attempts >= MAX_LOGIN_ATTEMPTS:
            self.locked_until = time.time() + LOGIN_LOCKOUT_SECONDS
            self.login_attempts = 0
            self.err.configure(text=f"Хэт олон оролдлого! {LOGIN_LOCKOUT_SECONDS}с хүлээнэ үү")
            self.login_btn.configure(state="disabled")
            self.after(LOGIN_LOCKOUT_SECONDS * 1000, lambda: self.login_btn.configure(state="normal"))
        else:
            self.err.configure(text=f"Имэйл эсвэл нууц үг буруу ({remaining} үлдсэн)")