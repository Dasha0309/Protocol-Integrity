from tkinter import messagebox

import customtkinter as ctk

from app_config import APP_NAME, COLORS, ROLE_ADMIN
from app_services import EncryptionModule
from app_ui import (
    AdminPage,
    DocumentsPage,
    LoginWindow,
    OrgSetupWindow,
    RecordPage,
    Sidebar,
    TrashPage,
)
from app_utils import ensure_dirs, install_mn_keyboard_fix, install_text_edit_shortcuts, org_exists


class ProtocolApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        try:
            self.tk.call("encoding", "system", "utf-8")
        except Exception:
            pass
        self.title(APP_NAME)
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(fg_color=COLORS["bg_main"])
        install_mn_keyboard_fix(self)
        install_text_edit_shortcuts(self)
        ensure_dirs()
        self.user = self.role = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._boot()

    def _on_close(self):
        # Ensure the decrypted private key is wiped from process
        # memory before Tk tears everything down.
        try:
            EncryptionModule.lock()
        except Exception:
            pass
        self.destroy()

    def _boot(self):
        """First-run: org setup. Otherwise: login."""
        if not org_exists():
            self._setup_ui()
        else:
            self._login_ui()

    def _setup_ui(self):
        for w in self.winfo_children():
            w.destroy()
        OrgSetupWindow(self, self._on_setup_done).pack(fill="both", expand=True)

    def _on_setup_done(self):
        messagebox.showinfo("Амжилттай", "Байгууллага бүртгэгдлээ!")
        self._login_ui()

    def _login_ui(self):
        for w in self.winfo_children():
            w.destroy()
        LoginWindow(self, self._on_login).pack(fill="both", expand=True)

    def _on_login(self, user_name, role):
        self.user = user_name
        self.role = role
        self._main_ui()

    def _main_ui(self):
        for w in self.winfo_children():
            w.destroy()
        self.ct = ctk.CTkFrame(self, fg_color=COLORS["bg_main"])
        self.ct.pack(side="left", fill="both", expand=True)
        self._sidebar = Sidebar(self, self.user, self.role, self._nav, self._logout)
        self._sidebar.pack(side="left", fill="y", before=self.ct)
        ctk.CTkFrame(self, width=1, fg_color=COLORS["border_light"]).pack(
            side="left", fill="y", before=self.ct
        )
        self._nav("record")

    def _nav(self, key, draft_data=None):
        for w in self.ct.winfo_children():
            w.destroy()
        if key == "admin" and self.role != ROLE_ADMIN:
            messagebox.showwarning("Анхааруулга", "Зөвхөн админ эрхтэй!")
            return
        if key == "record":
            RecordPage(
                self.ct,
                draft_data=draft_data,
                on_completed=self._on_record_completed,
            ).pack(fill="both", expand=True)
        elif key == "documents":
            DocumentsPage(self.ct, on_use_draft=self._on_use_draft).pack(fill="both", expand=True)
        elif key == "trash":
            TrashPage(self.ct).pack(fill="both", expand=True)
        elif key == "admin":
            AdminPage(self.ct).pack(fill="both", expand=True)

    def _on_use_draft(self, draft_data):
        """Documents хуудсаас draft сонгоход Record хуудсанд шилжинэ."""
        self._sidebar.set_active("record")
        self._nav("record", draft_data=draft_data)

    def _on_record_completed(self):
        """Called by RecordPage after audio upload + STT + redaction finish —
        navigate the user to the documents page."""
        self._sidebar.set_active("documents")
        self._nav("documents")

    def _logout(self):
        # Drop the decrypted RSA private key from memory before
        # tearing down the UI — any lingering decrypt attempt after
        # this point will fail with a "vault locked" error instead of
        # silently using the previous user's key.
        try:
            EncryptionModule.lock()
        except Exception:
            pass
        self.user = self.role = None
        self._login_ui()