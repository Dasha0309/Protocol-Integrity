from tkinter import messagebox

import customtkinter as ctk

from app_config import COLORS, ROLE_ADMIN, ROLE_STAFF
from app_utils import (
    hash_password, load_org, save_org,
    validate_email, validate_password,
)


class AdminPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_main"])

        ctk.CTkLabel(
            self, text="Хэрэглэгчдийн удирдлага",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", padx=30, pady=(28, 2))
        ctk.CTkLabel(
            self, text="Хэрэглэгч нэмэх, идэвхжүүлэх, эрх тохируулах",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", padx=30, pady=(0, 12))

        # Add user button
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=30, pady=(0, 8))
        ctk.CTkButton(
            top, text="➕  Шинэ хэрэглэгч",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            height=36, width=170, corner_radius=8,
            command=self._add_user,
        ).pack(side="right")

        # Users list
        self.users_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.users_frame.pack(fill="both", expand=True, padx=30, pady=(0, 24))
        self._load_users()

    def _load_users(self):
        for w in self.users_frame.winfo_children():
            w.destroy()
        org = load_org()
        users = org.get("users", [])

        if not users:
            ctk.CTkLabel(self.users_frame, text="Хэрэглэгч байхгүй",
                         font=ctk.CTkFont(size=13), text_color=COLORS["text_muted"]).pack(pady=30)
            return

        admin_count = sum(1 for u in users if u.get("role") == ROLE_ADMIN)

        for i, u in enumerate(users):
            is_active = u.get("is_active", True)
            role = u.get("role", ROLE_STAFF)

            row = ctk.CTkFrame(
                self.users_frame,
                fg_color=COLORS["bg_card"] if is_active else COLORS["border_light"],
                corner_radius=8, border_width=1, border_color=COLORS["border_light"],
                height=52,
            )
            row.pack(fill="x", pady=3)
            row.pack_propagate(False)

            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=14, pady=8)

            # Icon + Name
            icon = "🛡" if role == ROLE_ADMIN else "👤"
            name_text = u.get("name", "")
            if not is_active:
                name_text += "  (идэвхгүй)"
            ctk.CTkLabel(
                inner, text=f"{icon}  {name_text}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLORS["text_primary"] if is_active else COLORS["text_muted"],
            ).pack(side="left")

            # Email
            ctk.CTkLabel(
                inner, text=u.get("email", ""),
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text_secondary"] if is_active else COLORS["text_muted"],
            ).pack(side="left", padx=(12, 0))

            # Role badge
            role_text = "Админ" if role == ROLE_ADMIN else "Ажилтан"
            role_color = COLORS["accent"] if role == ROLE_ADMIN else COLORS["text_muted"]
            ctk.CTkLabel(
                inner, text=role_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=role_color,
            ).pack(side="right", padx=(8, 0))

            # Active/Deactivate toggle
            if is_active:
                ctk.CTkButton(
                    inner, text="Идэвхгүй", width=70, height=26,
                    font=ctk.CTkFont(size=11),
                    fg_color=COLORS["danger_light"], hover_color=COLORS["danger"],
                    text_color=COLORS["danger"],
                    command=lambda idx=i: self._toggle_active(idx, False),
                ).pack(side="right", padx=4)
            else:
                ctk.CTkButton(
                    inner, text="Идэвхжүүлэх", width=80, height=26,
                    font=ctk.CTkFont(size=11),
                    fg_color=COLORS["success_light"], hover_color=COLORS["success"],
                    text_color=COLORS["success"],
                    command=lambda idx=i: self._toggle_active(idx, True),
                ).pack(side="right", padx=4)

            # Role change button
            if role == ROLE_STAFF and is_active:
                ctk.CTkButton(
                    inner, text="⬆ Админ", width=65, height=26,
                    font=ctk.CTkFont(size=11),
                    fg_color=COLORS["accent_light"], hover_color=COLORS["accent"],
                    text_color=COLORS["accent"],
                    command=lambda idx=i: self._change_role(idx, ROLE_ADMIN),
                ).pack(side="right", padx=2)
            elif role == ROLE_ADMIN and admin_count > 1 and is_active:
                ctk.CTkButton(
                    inner, text="⬇ Ажилтан", width=70, height=26,
                    font=ctk.CTkFont(size=11),
                    fg_color=COLORS["warning_light"], hover_color=COLORS["warning"],
                    text_color=COLORS["warning"],
                    command=lambda idx=i: self._change_role(idx, ROLE_STAFF),
                ).pack(side="right", padx=2)

    def _toggle_active(self, user_idx, active):
        org = load_org()
        users = org.get("users", [])
        if user_idx >= len(users):
            return
        # Prevent deactivating the last admin
        if not active and users[user_idx].get("role") == ROLE_ADMIN:
            admin_active = sum(1 for u in users if u.get("role") == ROLE_ADMIN and u.get("is_active", True))
            if admin_active <= 1:
                messagebox.showwarning("Анхааруулга", "Сүүлчийн админыг идэвхгүй болгох боломжгүй")
                return
        users[user_idx]["is_active"] = active
        save_org(org)
        status = "идэвхжүүлсэн" if active else "идэвхгүй болгосон"
        messagebox.showinfo("Амжилттай", f"{users[user_idx]['name']} — {status}")
        self._load_users()

    def _change_role(self, user_idx, new_role):
        org = load_org()
        users = org.get("users", [])
        if user_idx >= len(users):
            return
        users[user_idx]["role"] = new_role
        save_org(org)
        role_name = "Админ" if new_role == ROLE_ADMIN else "Ажилтан"
        messagebox.showinfo("Амжилттай", f"{users[user_idx]['name']} → {role_name}")
        self._load_users()

    def _add_user(self):
        win = ctk.CTkToplevel(self)
        win.title("Шинэ хэрэглэгч")
        win.geometry("400x480")
        win.minsize(400, 480)
        win.configure(fg_color=COLORS["bg_main"])
        win.grab_set()

        ctk.CTkLabel(win, text="Шинэ хэрэглэгч нэмэх",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(pady=(16, 10))

        fields = {}
        for label, key, show in [
            ("Овог нэр", "name", None),
            ("И-мэйл", "email", None),
            ("Нууц үг", "password", "*"),
        ]:
            ctk.CTkLabel(win, text=label, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=COLORS["text_primary"]).pack(anchor="w", padx=24)
            e = ctk.CTkEntry(win, font=ctk.CTkFont(size=13), height=36,
                             fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                             corner_radius=8, show=show or "")
            e.pack(fill="x", padx=24, pady=(2, 8))
            fields[key] = e

        ctk.CTkLabel(win, text="Эрх", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=24)
        # Display Mongolian labels, translate back to internal role keys
        # (ROLE_STAFF/ROLE_ADMIN) when the form is submitted.
        role_labels = {"Ажилтан": ROLE_STAFF, "Админ": ROLE_ADMIN}
        role_dd = ctk.CTkComboBox(win, values=list(role_labels.keys()),
                                  font=ctk.CTkFont(size=13), height=36,
                                  fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                                  corner_radius=8, state="readonly")
        role_dd.set("Ажилтан")
        role_dd.pack(fill="x", padx=24, pady=(2, 6))

        err_lbl = ctk.CTkLabel(win, text="", font=ctk.CTkFont(size=12), text_color=COLORS["danger"])
        err_lbl.pack()

        def do_add():
            name = fields["name"].get().strip()
            email = fields["email"].get().strip()
            pw = fields["password"].get()
            # Translate the Mongolian-labeled selection back to the
            # internal role key (falls back to staff on unexpected input).
            role = role_labels.get(role_dd.get(), ROLE_STAFF)

            if not name or not email or not pw:
                err_lbl.configure(text="Бүх талбарыг бөглөнө үү")
                return
            if not validate_email(email):
                err_lbl.configure(text="И-мэйл формат буруу")
                return
            pw_err = validate_password(pw)
            if pw_err:
                err_lbl.configure(text=pw_err)
                return

            org = load_org()
            for u in org.get("users", []):
                if u["email"] == email:
                    err_lbl.configure(text="Энэ и-мэйл бүртгэлтэй")
                    return

            org.setdefault("users", []).append({
                "name": name,
                "email": email,
                "role": role,
                "password": hash_password(pw),
                "is_active": True,
            })
            save_org(org)
            messagebox.showinfo("Амжилттай", f"{name} нэмэгдлээ!")
            win.destroy()
            self._load_users()

        ctk.CTkButton(win, text="➕ Нэмэх",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                      height=38, corner_radius=8,
                      command=do_add).pack(fill="x", padx=24, pady=(2, 16))