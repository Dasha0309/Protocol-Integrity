import os
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app_config import COLORS
from app_services import EncryptionModule
from app_utils import (
    get_archive_statuses,
    search_archive_meetings,
    trash_meeting,
    verify_meeting_password,
)

class DocumentsPage(ctk.CTkFrame):
    # English status keys map to Mongolian labels for display only — internal
    # filtering still uses the English keys so no other code has to change.
    STATUS_LABELS = {
        "All": "Бүгд",
        "Approved": "Баталгаажсан",
        "Pending": "Хүлээгдэж буй",
        "Rejected": "Татгалзсан",
        "Draft": "Ноорог",
    }

    def __init__(self, parent, on_use_draft=None):
        super().__init__(parent, fg_color="#F3F4F6")
        self._on_use_draft = on_use_draft
        self._filter = "All"
        self._search_text = ""
        self._all_meetings = []
        self._search_after_id = None
        self._statuses = get_archive_statuses()
        self._filter_btns = {}
        self._list_container = ctk.CTkFrame(self, fg_color="transparent")
        self._list_container.pack(fill="both", expand=True)
        self._view_container = None
        self._build_ui()
        self._reload()

    def _build_ui(self):
        parent = self._list_container
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", padx=36, pady=(28, 0))
        ctk.CTkLabel(hdr, text="Архив хайх", font=ctk.CTkFont(size=30, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Бүх хурлын баримт бичгийг мэдээллүүд", font=ctk.CTkFont(size=17), text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(3, 0))

        search = ctk.CTkFrame(parent, fg_color="#FFFFFF", corner_radius=12, border_width=1, border_color="#D1D5DB")
        search.pack(fill="x", padx=36, pady=(20, 0))
        ctk.CTkLabel(search, text="🔍", font=ctk.CTkFont(size=16), text_color="#9CA3AF").pack(side="left", padx=(16, 8), pady=12)
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search())
        ctk.CTkEntry(
            search,
            textvariable=self.search_var,
            placeholder_text="Хайх нэр, агуулга эсвэл үүсгэгч...",
            fg_color="transparent",
            border_width=0,
            font=ctk.CTkFont(size=15),
            text_color=COLORS["text_primary"],
            height=46,
        ).pack(side="left", fill="x", expand=True, padx=(0, 12))

        chips = ctk.CTkFrame(parent, fg_color="transparent")
        chips.pack(fill="x", padx=36, pady=(14, 0))
        ctk.CTkLabel(chips, text="Төлөв:", font=ctk.CTkFont(size=15), text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        for status in self._statuses:
            label = self.STATUS_LABELS.get(status, status)
            # hover_color matches fg_color so the chip doesn't flash gray on
            # mouse-over — selection still reads clearly via fg/text color.
            btn = ctk.CTkButton(
                chips,
                text=label,
                height=34,
                width=110,
                corner_radius=17,
                border_width=1,
                border_color="#D1D5DB",
                font=ctk.CTkFont(size=14, weight="bold"),
                fg_color="#FFFFFF",
                hover_color="#FFFFFF",
                text_color=COLORS["text_primary"],
                command=lambda x=status: self._set_filter(x),
            )
            btn.pack(side="left", padx=4)
            self._filter_btns[status] = btn
        self._set_filter("All", rerender=False)

        self.count_lbl = ctk.CTkLabel(parent, text="", font=ctk.CTkFont(size=14, weight="bold"), text_color="#6B7280")
        self.count_lbl.pack(anchor="w", padx=36, pady=(14, 4))

        self.list_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=36, pady=(0, 20))

    def _reload(self):
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None
        try:
            self._all_meetings = search_archive_meetings()
            self._render()
        except Exception as e:
            for w in self.list_frame.winfo_children():
                w.destroy()
            self.count_lbl.configure(text="0 илэрц")
            ctk.CTkLabel(
                self.list_frame,
                text=f"Хуудас ачаалахад алдаа гарлаа: {e}",
                font=ctk.CTkFont(size=14),
                text_color=COLORS["danger"],
                wraplength=760,
                justify="left",
            ).pack(anchor="w", padx=8, pady=20)

    def _on_search(self):
        new_text = self.search_var.get().strip()
        if new_text == self._search_text:
            return
        self._search_text = new_text
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(160, self._render_after_search)

    def _render_after_search(self):
        self._search_after_id = None
        self._render()

    def _set_filter(self, key, rerender=True):
        self._filter = key
        for k, btn in self._filter_btns.items():
            if k == key:
                btn.configure(
                    fg_color=COLORS["text_primary"],
                    hover_color=COLORS["text_primary"],
                    text_color="white",
                    border_color=COLORS["text_primary"],
                )
            else:
                btn.configure(
                    fg_color="#FFFFFF",
                    hover_color="#FFFFFF",
                    text_color=COLORS["text_primary"],
                    border_color="#D1D5DB",
                )
        if rerender:
            if self._search_after_id is not None:
                self.after_cancel(self._search_after_id)
                self._search_after_id = None
            self._render()

    def _status_of(self, m):
        return str(m.get("status", "Draft")).strip() or "Draft"

    def _matches(self, m):
        if not isinstance(m, dict):
            return False
        if self._filter != "All" and self._status_of(m) != self._filter:
            return False
        if not self._search_text:
            return True
        hay = " ".join(
            [
                str(m.get("title", "")),
                str(m.get("report", "")),
                str(m.get("redacted_text", "")),
                str(m.get("author", "")),
            ]
        ).lower()
        return self._search_text.lower() in hay

    def _render(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        source = self._all_meetings if isinstance(self._all_meetings, list) else []
        data = [m for m in reversed(source) if self._matches(m)]
        self.count_lbl.configure(text=f"{len(data)} илэрц")
        if not data:
            ctk.CTkLabel(self.list_frame, text="Илэрц олдсонгүй", font=ctk.CTkFont(size=15), text_color=COLORS["text_muted"]).pack(pady=40)
            return
        for m in data:
            self._card(m)

    def _card(self, m):
        card = ctk.CTkFrame(self.list_frame, fg_color="#FFFFFF", corner_radius=12, border_width=1, border_color="#D1D5DB")
        card.pack(fill="x", pady=6)
        inn = ctk.CTkFrame(card, fg_color="transparent")
        inn.pack(fill="both", expand=True, padx=18, pady=16)

        icon = ctk.CTkFrame(inn, width=46, height=46, fg_color="#F3F4F6", corner_radius=10)
        icon.pack(side="left", anchor="n")
        icon.pack_propagate(False)
        ctk.CTkLabel(icon, text="📄", font=ctk.CTkFont(size=22), text_color="#6B7280").place(relx=0.5, rely=0.5, anchor="center")

        act = ctk.CTkFrame(inn, fg_color="transparent")
        act.pack(side="right", anchor="n", padx=(10, 0))

        body = ctk.CTkFrame(inn, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=(14, 10))
        ctk.CTkLabel(
            body, text=m.get("title", "Нэргүй бичлэг"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w", justify="left", wraplength=900,
        ).pack(anchor="w", fill="x")
        preview = (m.get("report") or m.get("redacted_text") or "")[:130]
        if preview and len(preview) == 130:
            preview += "..."
      
        ctk.CTkLabel(
            body, text=preview or "Агуулга алга",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_secondary"],
            anchor="w", justify="left", wraplength=900,
        ).pack(anchor="w", fill="x", pady=(4, 0))

        meta = ctk.CTkFrame(body, fg_color="transparent")
        meta.pack(anchor="w", pady=(8, 0))
        ctk.CTkLabel(meta, text=f"🕐 {m.get('date', '')}", font=ctk.CTkFont(size=13), text_color="#6B7280").pack(side="left")
        ctk.CTkLabel(meta, text=f"   👤 {m.get('author', 'Систем')}", font=ctk.CTkFont(size=13), text_color="#6B7280").pack(side="left")

        status = self._status_of(m)
        status_ui = {
            "approved": ("Баталгаажсан", "#16A34A"),
            "pending": ("Хүлээгдэж буй", "#2563EB"),
            "rejected": ("Татгалзсан", "#DC2626"),
            "draft": ("Ноорог", "#6B7280"),
        }
        stxt, sclr = status_ui.get(status.lower(), (status.title(), "#6B7280"))
        ctk.CTkLabel(meta, text=f"   {stxt}", font=ctk.CTkFont(size=13, weight="bold"), text_color=sclr).pack(side="left")

        status_lower = status.lower()

        if status_lower == "approved":
            ctk.CTkButton(act, text="Нээх", width=120, height=34, corner_radius=8, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=lambda x=m: self._open_document(x)).pack(pady=2)
            ctk.CTkButton(act, text="🔓 Тайлах", width=120, height=34, corner_radius=8, fg_color="#F3F4F6", hover_color=COLORS["accent"], text_color="black", command=lambda x=m: self._decrypt_view(x)).pack(pady=2)
        elif status_lower == "draft":
            ctk.CTkButton(
                act, text="Ноорог ашиглах", width=120, height=34, corner_radius=8,
                fg_color="#7C5CFC", hover_color="#6344E8", text_color="#FFFFFF",
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda x=m: self._use_draft(x),
            ).pack(pady=2)
        else:
         
            ctk.CTkButton(act, text="Нээх", width=120, height=34, corner_radius=8, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=lambda x=m: self._open_document(x)).pack(pady=2)

        # Устгах — бүх статуст харагдана
        ctk.CTkButton(
            act, text="🗑 Устгах", width=120, height=34, corner_radius=8,
            fg_color="#F3F4F6", hover_color="#FEE2E2", text_color="#DC2626",
            font=ctk.CTkFont(size=13),
            command=lambda x=m: self._delete_meeting(x),
        ).pack(pady=(6, 2))

        card.bind("<Button-1>", lambda _e, x=m: self._open_document(x))
        inn.bind("<Button-1>", lambda _e, x=m: self._open_document(x))
        body.bind("<Button-1>", lambda _e, x=m: self._open_document(x))

    def _protocol_sections(
        self, m,
        *,
        restored_text: str | None = None,
        restored_protocol: dict | None = None,
        restored_report: str | None = None,
    ):
        """Return an ordered list of (kind, payload) tuples describing the
        formal protocol document.

        Both the on-screen textbox and the PDF exporter consume this same
        list, so the printed PDF mirrors what the user sees in the app.
        When ``restored_protocol`` is supplied (after a successful decrypt)
        its values override the stored redacted protocol so █ spans are
        replaced with the original names/amounts/dates.

        Kinds:
          title       — centered bold document title
          doc_num     — centered document number ("Дугаар №06")
          date_city   — date on the left, city on the right on one line
          para        — plain left-aligned paragraph
          heading     — section heading (bold)
          attendees   — ``["Т.Аранзал", ...]`` printed as an indented list
          numbered    — ``["нэг", "хоёр", ...]`` printed as 1./2./3.
          decisions   — ``[{"index":1,"text":"…"}, …]`` printed as Асуудал N.
          signature   — review-signature line on the final page
        """
        proto = restored_protocol if restored_protocol is not None else (m.get("protocol") or {})
        sections: list[tuple[str, object]] = []

        # ── Title
        title = (proto.get("doc_title")
                 or m.get("title")
                 or "Хурлын тэмдэглэл").strip()
        sections.append(("title", title))

        # ── Document number
        doc_num = (proto.get("doc_number") or "").strip()
        if doc_num:
            sections.append(("doc_num", f"Дугаар {doc_num}"
                             if not doc_num.lower().startswith("дугаар") else doc_num))

        # ── Date & city on one line
        date = (proto.get("date") or m.get("date") or "").strip()
        city = (proto.get("city") or "").strip()
        if date or city:
            sections.append(("date_city", {"date": date, "city": city}))

        # ── Manually-entered participants (from the meeting creation form).
        # Stored RSA-encrypted by default; decrypt on the fly when the master
        # vault is unlocked, otherwise show a non-revealing placeholder.
        raw_parts = (m.get("participants") or "").strip()
        if raw_parts:
            if m.get("participants_encrypted"):
                try:
                    raw_parts = EncryptionModule.decrypt_sensitive_value(raw_parts)
                except Exception:
                    raw_parts = "(шифрлэгдсэн)"
            sections.append(("manual_participants", raw_parts))

        # ── Location / start-time paragraph
        location = (proto.get("location") or "").strip()
        start_time = (proto.get("start_time") or "").strip()
        loc_para = ""
        if location and start_time:
            loc_para = f"{location}-д {start_time} цагаас эхлэв."
        elif location:
            loc_para = f"{location}-д хурал боллоо."
        elif start_time:
            loc_para = f"{start_time} цагаас эхлэв."
        if loc_para:
            sections.append(("para", loc_para))

        # ── Attendees
        attendees = proto.get("attendees") or []
        if attendees:
            sections.append(("attendees", attendees))

        # ── Agenda
        agenda = proto.get("agenda") or []
        if agenda:
            sections.append(("heading", "Хэлэлцэх асуудал :"))
            sections.append(("numbered", agenda))

        # ── Decisions
        decisions = proto.get("decisions") or []
        if decisions:
            sections.append(("heading", "Шийдвэрлэсэн нь :"))
            sections.append(("decisions", decisions))

        # ── End time
        end_time = (proto.get("end_time") or "").strip()
        if end_time:
            sections.append(("para", f"Хурал {end_time} цагт дуусав"))

        # ── Brief summary (kept from earlier design)
        # Prefer the decrypted summary when available — positions inside
        # the summary differ from the transcript, so this MUST use the
        # separately-restored copy rather than m["report"] (which still
        # contains █ placeholders).
        if restored_report is not None:
            report = restored_report.strip()
        else:
            report = (m.get("report") or "").strip()
        if report:
            sections.append(("heading", "Хурлын товч агуулга"))
            sections.append(("para", report))

        # ── Full (possibly decrypted) transcript body
        body_text = restored_text if restored_text is not None else m.get("redacted_text", "")
        body_text = (body_text or "").strip()
        if body_text:
            sections.append(("heading", "Хурлын тэмдэглэл"))
            sections.append(("para", body_text))

        # ── Signature line on the final page
        reviewer = (proto.get("reviewer_name") or "").strip()
        sections.append(("signature", reviewer))

        return sections

    def _build_document_text(
        self, m,
        *,
        restored_text: str | None = None,
        restored_protocol: dict | None = None,
        restored_report: str | None = None,
    ):
        """Flatten the protocol sections into plain text for the CTkTextbox."""
        sections = self._protocol_sections(
            m,
            restored_text=restored_text,
            restored_protocol=restored_protocol,
            restored_report=restored_report,
        )
        out: list[str] = []
        for kind, payload in sections:
            if kind == "title":
                out += [str(payload).center(80).rstrip(), ""]
            elif kind == "doc_num":
                out += [str(payload).center(80).rstrip(), ""]
            elif kind == "date_city":
                date = payload.get("date", "")
                city = payload.get("city", "")
                width = 80
                pad = max(1, width - len(date) - len(city))
                out += [f"{date}{' ' * pad}{city}".rstrip(), ""]
            elif kind == "heading":
                out += [str(payload), ""]
            elif kind == "para":
                out += [str(payload), ""]
            elif kind == "manual_participants":
                out += [f"Оролцогчид: {payload}", ""]
            elif kind == "attendees":
                first, *rest = payload
                out.append(f"Хуралд оролцсон: {first}")
                for name in rest:
                    out.append(f"                 {name}")
                out.append("")
            elif kind == "numbered":
                for i, item in enumerate(payload, start=1):
                    out.append(f"    {i}. {item}")
                out.append("")
            elif kind == "decisions":
                for d in payload:
                    idx = d.get("index")
                    txt = d.get("text", "")
                    out += [f"Асуудал {idx}. {txt}", ""]
            elif kind == "signature":
                out += [
                    "",
                    "",
                    f"Хурлын тэмдэглэлийг хянасан: ........................  /{payload or '                   '}/",
                ]
        return "\n".join(out).rstrip() + "\n"

    def _show_view(self):
        """Hide the list and create a fresh container for a single view."""
        if self._view_container is not None:
            self._view_container.destroy()
        self._list_container.pack_forget()
        self._view_container = ctk.CTkFrame(self, fg_color="#F3F4F6")
        self._view_container.pack(fill="both", expand=True)
        return self._view_container

    def _back_to_list(self):
        if self._view_container is not None:
            self._view_container.destroy()
            self._view_container = None
        self._list_container.pack(fill="both", expand=True)

    def _open_document(self, m):
        self._render_document_page(m)

    def _render_document_page(
        self, m,
        restored_text: str | None = None,
        restored_protocol: dict | None = None,
        restored_report: str | None = None,
    ):

        is_decrypted = restored_text is not None
        container = self._show_view()

        top = ctk.CTkFrame(
            container, fg_color="#FFFFFF", corner_radius=0,
            border_width=1, border_color="#E5E7EB",
        )
        top.pack(fill="x")

        ctk.CTkButton(
            top, text="← Буцах", width=100, height=34, corner_radius=8,
            fg_color="#E5E7EB", hover_color="#D1D5DB",
            text_color=COLORS["text_primary"],
            command=self._back_to_list,
        ).pack(side="left", padx=(18, 12), pady=12)

        title_text = m.get("title", "Баримт бичиг")
        if is_decrypted:
            title_text = f"🔓  {title_text} — нууц мэдээлэл тайлагдсан"
        ctk.CTkLabel(
            top, text=title_text,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["danger"] if is_decrypted else COLORS["text_primary"],
        ).pack(side="left", pady=12)

        # Export button. In the public view it downloads the redacted
        # document; in the decrypted view it downloads the fully-restored
        # one, so the user can hand off the sensitive-data copy in one
        # click alongside the audio-replay button.
        if is_decrypted:
            ctk.CTkButton(
                top, text="📥 Тэмдэглэл татаж авах", width=190, height=34,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                command=lambda x=m, rt=restored_text, rp=restored_protocol, rr=restored_report:
                    self._export_pdf(x, restored_text=rt, restored_protocol=rp, restored_report=rr),
            ).pack(side="right", padx=12, pady=12)
        else:
            ctk.CTkButton(
                top, text="📥 Тэмдэглэл татаж авах", width=190, height=34,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                command=lambda x=m: self._export_pdf(x),
            ).pack(side="right", padx=12, pady=12)

        if is_decrypted:

            live_path = ""
            for candidate in (m.get("archive_wav", ""), m.get("audio_file", "")):
                if candidate and os.path.exists(candidate):
                    live_path = candidate
                    break
            stored_path = m.get("archive_wav") or m.get("audio_file") or ""

            if live_path:
                ctk.CTkButton(
                    top, text="🎵 Хурлын аудио бичлэг сонсох",
                    height=34, corner_radius=8,
                    fg_color=COLORS["success"], hover_color="#157347",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    command=lambda p=live_path: self._play(p),
                ).pack(side="right", padx=(0, 10), pady=12)
            elif stored_path:
                ctk.CTkButton(
                    top, text="🎵 Аудио олдсонгүй",
                    height=34, corner_radius=8,
                    fg_color="#9CA3AF", hover_color="#6B7280",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    command=lambda p=stored_path: messagebox.showwarning(
                        "Аудио олдсонгүй",
                        "Архивласан байршилд файл олдсонгүй:\n"
                        f"{p}\n\n"
                        "Файлыг шилжүүлсэн эсвэл устгасан байж магадгүй.",
                    ),
                ).pack(side="right", padx=(0, 10), pady=12)
            else:
                ctk.CTkButton(
                    top, text="🎵 Аудио бичлэг бүртгэгдээгүй",
                    height=34, corner_radius=8,
                    fg_color="#9CA3AF", hover_color="#6B7280",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    command=lambda: messagebox.showinfo(
                        "Аудио байхгүй",
                        "Энэ хурлын тэмдэглэлд аудио бичлэг хадгалагдаагүй байна.",
                    ),
                ).pack(side="right", padx=(0, 10), pady=12)

        page_wrap = ctk.CTkFrame(container, fg_color="transparent")
        page_wrap.pack(fill="both", expand=True, padx=28, pady=20)
        page = ctk.CTkFrame(
            page_wrap, fg_color="#FFFFFF", corner_radius=10,
            border_width=1, border_color="#D1D5DB",
        )
        page.pack(fill="both", expand=True)

        doc = ctk.CTkTextbox(
            page, font=ctk.CTkFont(family="Arial", size=15),
            fg_color="#FFFFFF", border_width=0, text_color="#111827",
        )
        doc.pack(fill="both", expand=True, padx=26, pady=20)
        doc.insert(
            "1.0",
            self._build_document_text(
                m,
                restored_text=restored_text,
                restored_protocol=restored_protocol,
                restored_report=restored_report,
            ),
        )

        if is_decrypted:
            sensitive_words = []
            for r in m.get("redactions") or []:
                try:
                    sensitive_words.append(
                        EncryptionModule.decrypt_sensitive_value(r.get("ciphertext", ""))
                    )
                except Exception:
                    continue
            if sensitive_words:
                doc.insert("end", "\n\nТайлагдсан нууц үгс:\n")
                for w in sensitive_words:
                    doc.insert("end", f"  • {w}\n")
        doc.configure(state="disabled")

    def _export_pdf(
        self, m,
        restored_text: str | None = None,
        restored_protocol: dict | None = None,
        restored_report: str | None = None,
    ):
        # Default filename hints whether this is the public or decrypted
        # copy so the user doesn't accidentally mix them up later.
        suffix = "_decrypted" if restored_text is not None else ""
        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF файл", "*.pdf")],
            initialfile=f"{m.get('title','meeting').replace(' ', '_')}{suffix}.pdf",
        )
        if not save_path:
            return
        try:
            self._render_protocol_pdf(
                m, save_path,
                restored_text=restored_text,
                restored_protocol=restored_protocol,
                restored_report=restored_report,
            )
            messagebox.showinfo("Амжилттай", f"PDF үүслээ:\n{save_path}")
        except Exception as e:
            messagebox.showerror("PDF алдаа", f"PDF үүсгэж чадсангүй:\n{e}")

    # ── PDF rendering ─────────────────────────────────────────────
    # The PDF mirrors _protocol_sections so what the user sees in the
    # app is what they get on paper. Platypus handles pagination so
    # long tables/agendas spill onto new pages without breaking layout,
    # and onLaterPages stamps page numbers on every page.

    def _render_protocol_pdf(
        self, m, save_path,
        *,
        restored_text: str | None = None,
        restored_protocol: dict | None = None,
        restored_report: str | None = None,
    ):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            BaseDocTemplate, Frame, PageTemplate,
            Paragraph, Spacer, Table, TableStyle, KeepTogether,
        )

        # Register a Unicode font so Mongolian Cyrillic renders correctly.
        font_regular = "Helvetica"
        font_bold = "Helvetica-Bold"
        for name, path in (
            ("ArialUnicode", r"C:\Windows\Fonts\arial.ttf"),
        ):
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont(name, path))
                font_regular = name
                break
        bold_path = r"C:\Windows\Fonts\arialbd.ttf"
        if os.path.exists(bold_path):
            pdfmetrics.registerFont(TTFont("ArialUnicode-Bold", bold_path))
            font_bold = "ArialUnicode-Bold"

        # Styles
        s_title = ParagraphStyle(
            "title", fontName=font_bold, fontSize=14, leading=18,
            alignment=TA_CENTER, spaceAfter=6,
        )
        s_docnum = ParagraphStyle(
            "docnum", fontName=font_regular, fontSize=11, leading=14,
            alignment=TA_CENTER, spaceAfter=14,
        )
        s_body = ParagraphStyle(
            "body", fontName=font_regular, fontSize=11, leading=16,
            alignment=TA_JUSTIFY, spaceAfter=8,
        )
        s_heading = ParagraphStyle(
            "heading", fontName=font_regular, fontSize=11, leading=16,
            alignment=TA_LEFT, spaceBefore=8, spaceAfter=6,
        )
        s_attendee = ParagraphStyle(
            "attendee", fontName=font_regular, fontSize=11, leading=16,
            alignment=TA_LEFT, leftIndent=18,
        )
        s_numbered = ParagraphStyle(
            "numbered", fontName=font_regular, fontSize=11, leading=16,
            alignment=TA_LEFT, leftIndent=36,
        )
        s_sign = ParagraphStyle(
            "sign", fontName=font_regular, fontSize=11, leading=18,
            alignment=TA_LEFT, spaceBefore=48,
        )

        def _esc(t):
            return (str(t).replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))

        story = []
        sections = self._protocol_sections(
            m,
            restored_text=restored_text,
            restored_protocol=restored_protocol,
            restored_report=restored_report,
        )
        for kind, payload in sections:
            if kind == "title":
                story.append(Paragraph(_esc(payload), s_title))
            elif kind == "doc_num":
                story.append(Paragraph(_esc(payload), s_docnum))
            elif kind == "date_city":
                # Two-column single-row table: date left, city right.
                date = _esc(payload.get("date", ""))
                city = _esc(payload.get("city", ""))
                tbl = Table(
                    [[Paragraph(date, s_body), Paragraph(city, s_body)]],
                    colWidths=[8.5 * cm, 8.5 * cm],
                )
                tbl.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (0, 0), "LEFT"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 8))
            elif kind == "para":
                story.append(Paragraph(_esc(payload), s_body))
            elif kind == "heading":
                story.append(Paragraph(_esc(payload), s_heading))
            elif kind == "manual_participants":
                story.append(Paragraph(f"Оролцогчид: {_esc(payload)}", s_body))
                story.append(Spacer(1, 6))
            elif kind == "attendees":
                first = _esc(payload[0])
                story.append(Paragraph(f"Хуралд оролцсон: {first}", s_body))
                for name in payload[1:]:
                    story.append(Paragraph(_esc(name), s_attendee))
                story.append(Spacer(1, 6))
            elif kind == "numbered":
                for i, item in enumerate(payload, start=1):
                    story.append(Paragraph(f"{i}. {_esc(item)}", s_numbered))
                story.append(Spacer(1, 6))
            elif kind == "decisions":
                for d in payload:
                    idx = d.get("index") or 0
                    txt = _esc(d.get("text", ""))
                    story.append(Paragraph(f"Асуудал {idx}. {txt}", s_body))
            elif kind == "signature":
                name = _esc(payload or "                   ")
                line = ("Хурлын тэмдэглэлийг хянасан: "
                        "................................  "
                        f"/{name}/")
                # Keep the signature block together so it never splits
                # across pages — it must land whole on the final page.
                story.append(KeepTogether([Spacer(1, 24),
                                           Paragraph(line, s_sign)]))

        # Page template with footer page-number stamp (every page).
        page_w, page_h = A4
        frame = Frame(
            2.2 * cm, 2.2 * cm,
            page_w - 4.4 * cm, page_h - 4.4 * cm,
            id="body",
        )

        def _on_page(canvas, doc):
            canvas.saveState()
            canvas.setFont(font_regular, 9)
            canvas.drawCentredString(
                page_w / 2, 1.2 * cm,
                f"— {doc.page} —",
            )
            canvas.restoreState()

        doc = BaseDocTemplate(
            save_path, pagesize=A4,
            leftMargin=2.2 * cm, rightMargin=2.2 * cm,
            topMargin=2.2 * cm, bottomMargin=2.2 * cm,
            title=m.get("title", "Хурлын тэмдэглэл"),
        )
        doc.addPageTemplates([
            PageTemplate(id="all", frames=[frame], onPage=_on_page)
        ])
        doc.build(story)

    def _decrypt_view(self, m):
        redactions = m.get("redactions") or []
        if not redactions:
            messagebox.showinfo(
                "Мэдээлэл",
                "Энэ хурлын тэмдэглэлд шифрлэгдсэн нууц үг олдсонгүй.\n"
                "AI боловсруулалтаар нууц мэдээлэл илрүүлээгүй байна.",
            )
            return

        # Per-meeting password gate — only prompt if the user chose to
        # protect this particular meeting with a password during
        # recording. If no password was set, the RSA vault (already
        # unlocked at login) is the only cryptographic gate, so we
        # can go straight to the decrypted view.
        if m.get("has_password") and m.get("password_hash"):
            self._render_password_page(m)
        else:
            self._restore_and_show(m)

    def _restore_and_show(self, m):
        """Decrypt and render the document page. Assumes vault unlocked."""
        redactions = m.get("redactions") or []
        redacted_text = m.get("redacted_text") or ""
        try:
            restored = EncryptionModule.restore_redacted_text(redacted_text, redactions)
        except Exception as exc:
            messagebox.showerror(
                "Нууцлал тайлалт амжилтгүй",
                f"Шифрлэгдсэн мэдээлэл тайлах үед алдаа гарлаа:\n{exc}",
            )
            return

        # Restore "Хурлын товч агуулга" using its own redaction list —
        # summary offsets are distinct from transcript offsets, so we
        # must NOT reuse ``redactions`` here. Older meetings recorded
        # before this field existed fall back to the still-redacted
        # summary (█ stays visible) rather than crashing.
        report_redactions = m.get("report_redactions") or []
        report_text = m.get("report") or ""
        try:
            restored_report = EncryptionModule.restore_redacted_text(
                report_text, report_redactions
            )
        except Exception:
            restored_report = report_text

        try:
            restored_proto = EncryptionModule.restore_protocol(m.get("protocol") or {})
        except Exception:
            restored_proto = m.get("protocol") or {}
        self._render_document_page(
            m,
            restored_text=restored,
            restored_protocol=restored_proto,
            restored_report=restored_report,
        )

    def _render_password_page(self, m):
        redactions = m.get("redactions") or []
        redacted_text = m.get("redacted_text") or ""
        container = self._show_view()

        # Header with Back button, matches _render_document_page style.
        top = ctk.CTkFrame(
            container, fg_color="#FFFFFF", corner_radius=0,
            border_width=1, border_color="#E5E7EB",
        )
        top.pack(fill="x")
        ctk.CTkButton(
            top, text="← Буцах", width=100, height=34, corner_radius=8,
            fg_color="#E5E7EB", hover_color="#D1D5DB",
            text_color=COLORS["text_primary"],
            command=self._back_to_list,
        ).pack(side="left", padx=(18, 12), pady=12)
        ctk.CTkLabel(
            top, text=f"🔐  {m.get('title', 'Баримт бичиг')} — нууц үг шаардлагатай",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left", pady=12)

        # Centered card with the password form.
        outer = ctk.CTkFrame(container, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=28, pady=40)

        card = ctk.CTkFrame(
            outer, fg_color="#FFFFFF", corner_radius=12,
            border_width=1, border_color="#D1D5DB", width=480,
        )
        card.pack(anchor="center", pady=(20, 0))
        card.pack_propagate(False)
        card.configure(height=220)

        ctk.CTkLabel(
            card, text="🔐  Нууц мэдээлэл тайлах",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(28, 14))

        pw_entry = ctk.CTkEntry(
            card, placeholder_text="Хурлын нууц үг", show="*",
            font=ctk.CTkFont(size=13), height=40,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            corner_radius=8,
        )
        pw_entry.pack(fill="x", padx=30, pady=(0, 8))
        pw_entry.focus_set()

        err_lbl = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=12),
            text_color=COLORS["danger"],
        )
        err_lbl.pack()

        def do_decrypt(_event=None):
            pw = pw_entry.get()
            if not pw:
                err_lbl.configure(text="Нууц үг оруулна уу")
                return
            # Verify against THIS meeting's stored password hash —
            # set by the user in the record page when they created the
            # draft. The RSA vault itself is unlocked at login time
            # with the account password; this per-meeting password is
            # a UI-level gate on top of that.
            if not verify_meeting_password(m, pw):
                err_lbl.configure(text="❌ Буруу нууц үг")
                return
            self._restore_and_show(m)

        pw_entry.bind("<Return>", do_decrypt)
        ctk.CTkButton(
            card, text="🔓  Тайлах",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            height=40, corner_radius=8, command=do_decrypt,
        ).pack(fill="x", padx=30, pady=(8, 0))

    def _use_draft(self, m):
        if callable(self._on_use_draft):
            self._on_use_draft(m)

    def _delete_meeting(self, m):
        title = m.get("title", "энэ бичлэг")
        if not messagebox.askyesno(
            "Устгах",
            f'"{title}"\nхогийн савд зөөх үү?',
            icon="warning",
        ):
            return
        trash_meeting(m.get("id"))
        self._reload()

    def _play(self, path):
        if not path or not os.path.exists(path):
            messagebox.showerror(
                "Аудио алга",
                f"Аудио файл олдсонгүй:\n{path or '(зам бүртгэгдээгүй)'}",
            )
            return
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except AttributeError:
            # Non-Windows fallback
            webbrowser.open(path)
        except OSError as exc:
            messagebox.showerror("Тоглуулахад алдаа", str(exc))
