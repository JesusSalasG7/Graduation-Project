"""Pantalla de consentimiento informado: se muestra la primera vez que un
participante entra al estudio y no se puede pasar sin firmarla (ver
App._ensure_consent).

Muestra la carta original renderizada con PyMuPDF, con los datos del
participante ya colocados sobre las líneas, y un lienzo para firmar. Al
firmar se guarda una copia nueva del PDF (el original no se toca), se
registra la firma y se envía la copia por correo en un hilo aparte.

Los datos que se manejan acá (nombre, C.I., correo, firma) son
personales: solo van a `consent_store` / al PDF firmado, nunca a los
datos del estudio, a la IA ni a la consola.
"""

import re
import tkinter as tk
import tkinter.messagebox as messagebox
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
import pymupdf
from PIL import Image, ImageDraw, ImageTk

from consent import consent_mailer, consent_pdf
from paths import CONSENT_PDF, CONSENT_VERSION
from storage import consent_store
from storage.participant_store import participant_label
from storage.personal_records import load_personal_record

FONT_FAMILY = "Segoe UI"
FONT_SCALE = 1.5  # igual que el panel principal (ver app.py)


def scaled(size: int) -> int:
    return round(size * FONT_SCALE)


RESULT_ACCEPTED = "accepted"
RESULT_DECLINED = "declined"
RESULT_BACK = "back"

ACCEPT_TEXT = "He leído y entendido la información y acepto participar voluntariamente"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]{2,}$")
CI_RE = re.compile(r"^(?:([VvEe])-?)?(\d{6,9})$")
CI_TYPING_RE = re.compile(r"^[VvEe]?-?\d{0,9}$")

MIN_ZOOM, MAX_ZOOM, DEFAULT_ZOOM = 1.0, 2.0, 1.5
PREVIEW_DEBOUNCE_MS = 350

SIGNATURE_HEIGHT = 150
# La firma se dibuja también sobre una imagen Pillow al doble de
# resolución que el lienzo, para que no se vea pixelada en el PDF.
SIGNATURE_SCALE = 2
SIGNATURE_PEN = 2
SIGNATURE_INK = (16, 24, 60, 255)
# Trazo mínimo (px del lienzo) para contar como firma: un clic suelto no alcanza.
SIGNATURE_MIN_LENGTH = 40


def normalize_ci(text: str) -> Optional[str]:
    """"v12345678" -> "V-12345678"; "12345678" queda igual. None si no
    es una C.I. válida."""
    match = CI_RE.match(text.strip())
    if not match:
        return None
    prefix, digits = match.groups()
    return f"{prefix.upper()}-{digits}" if prefix else digits


def open_consent_viewer(parent, pdf_path: Path, title: str = "Consentimiento firmado") -> None:
    """Ventana de solo lectura con las páginas de un consentimiento ya firmado."""
    try:
        with pymupdf.open(pdf_path) as doc:
            pages = consent_pdf.render_pages(doc, DEFAULT_ZOOM)
    except Exception as exc:  # noqa: BLE001 -- archivo borrado/dañado
        messagebox.showerror(
            "No se pudo abrir el consentimiento",
            f"No se pudo leer el PDF firmado ({type(exc).__name__}).", parent=parent,
        )
        return

    window = ctk.CTkToplevel(parent)
    window.title(title)
    width = pages[0].width + 70
    window.geometry(f"{width}x{min(parent.winfo_screenheight() - 120, 1000)}")
    window.transient(parent)
    scroll = ctk.CTkScrollableFrame(window, fg_color="#3a3d47")
    scroll.pack(fill="both", expand=True)
    window._consent_photos = []  # sin la referencia, Tk pierde las imágenes
    for page in pages:
        photo = ImageTk.PhotoImage(page, master=window)
        window._consent_photos.append(photo)
        tk.Label(scroll, image=photo, borderwidth=0).pack(pady=10)
    window.after(100, window.lift)


class ConsentView:
    def __init__(self, container: ctk.CTkFrame, app, colors: dict):
        self.container = container
        self.app = app
        self.c = colors
        self._participant: Optional[dict] = None
        self._on_close: Optional[Callable[[str], None]] = None
        self._preview_job = None
        self._photos: list[ImageTk.PhotoImage] = []
        self._page_labels: list[tk.Label] = []
        self._zoom = DEFAULT_ZOOM
        self._template_error: Optional[str] = None
        self._signature_image: Optional[Image.Image] = None
        self._signature_length = 0.0
        self._last_point: Optional[tuple[int, int]] = None

    # ---------------- helpers ----------------
    def _font(self, size: int, bold: bool = False) -> ctk.CTkFont:
        return ctk.CTkFont(family=FONT_FAMILY, size=scaled(size), weight="bold" if bold else "normal")

    def _clear(self):
        if self._preview_job is not None:
            try:
                self.app.after_cancel(self._preview_job)
            except Exception:
                pass
            self._preview_job = None
        for child in self.container.winfo_children():
            child.destroy()
        self._photos = []
        self._page_labels = []

    def _finish(self, result: str):
        self._clear()
        on_close, self._on_close = self._on_close, None
        if on_close is not None:
            on_close(result)

    # ---------------- pantalla principal ----------------
    def show(self, participant: dict, on_close: Callable[[str], None]):
        """`on_close(resultado)` recibe RESULT_ACCEPTED / RESULT_DECLINED /
        RESULT_BACK. Solo ACCEPTED deja un consentimiento registrado."""
        self._clear()
        self._participant = participant
        self._on_close = on_close
        self._template_error = None
        self._signature_length = 0.0
        self._fecha = datetime.now().strftime("%d / %m / %Y")

        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_columnconfigure(1, weight=0)
        self.container.grid_rowconfigure(0, weight=1)

        # --- izquierda: la carta ---
        self._pdf_scroll = ctk.CTkScrollableFrame(self.container, fg_color="#3a3d47", corner_radius=0)
        self._pdf_scroll.grid(row=0, column=0, sticky="nsew")

        # --- derecha: datos, firma y botones ---
        panel = ctk.CTkFrame(self.container, fg_color=self.c["BG_CARD"], corner_radius=0, width=scaled(330))
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        ctk.CTkLabel(header, text="📝  Consentimiento informado", font=self._font(16, bold=True)).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=f"{participant_label(participant)} · documento v{CONSENT_VERSION}\n"
                 "Lee la carta completa, revisa tus datos y firma para continuar.",
            font=self._font(11), text_color=self.c["TEXT_MUTED"], justify="left",
            wraplength=scaled(290),
        ).pack(anchor="w", pady=(2, 0))

        body = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=8)

        record = load_personal_record(participant["number"])
        self._nombre_var = tk.StringVar(value=" ".join(record).strip() if record else "")
        self._ci_var = tk.StringVar()
        self._correo_var = tk.StringVar()
        self._accept_var = tk.BooleanVar(value=False)
        self._copy_var = tk.BooleanVar(value=True)

        def field(label: str, var: tk.StringVar, placeholder: str, **entry_kwargs) -> ctk.CTkEntry:
            ctk.CTkLabel(body, text=label, font=self._font(11), text_color=self.c["TEXT_MUTED"]).pack(
                anchor="w", padx=12, pady=(8, 2))
            entry = ctk.CTkEntry(
                body, textvariable=var, height=scaled(30), corner_radius=8,
                fg_color=self.c["BG_CARD_ALT"], border_width=1, border_color=self.c["BORDER"],
                font=self._font(12), placeholder_text=placeholder, **entry_kwargs,
            )
            entry.pack(fill="x", padx=12)
            return entry

        field("Nombre completo", self._nombre_var, "Nombre y apellido")
        ci_check = (body.register(lambda value: bool(CI_TYPING_RE.match(value))), "%P")
        self._ci_entry = field(
            "C.I. (solo números; prefijo V- o E- opcional)", self._ci_var, "12345678",
            validate="key", validatecommand=ci_check,
        )
        self._correo_entry = field("Correo electrónico", self._correo_var, "nombre@correo.com")

        ctk.CTkLabel(body, text="Fecha", font=self._font(11), text_color=self.c["TEXT_MUTED"]).pack(
            anchor="w", padx=12, pady=(8, 0))
        ctk.CTkLabel(body, text=self._fecha, font=self._font(12, bold=True)).pack(anchor="w", padx=12)

        sig_header = ctk.CTkFrame(body, fg_color="transparent")
        sig_header.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            sig_header, text="Firma (dibuja con el mouse)", font=self._font(11),
            text_color=self.c["TEXT_MUTED"],
        ).pack(side="left")
        ctk.CTkButton(
            sig_header, text="Limpiar", width=scaled(60), height=scaled(22), corner_radius=6,
            font=self._font(10), fg_color="transparent", hover_color=self.c["BORDER"],
            border_width=1, border_color=self.c["BORDER"], command=self._clear_signature,
        ).pack(side="right")
        self._canvas = tk.Canvas(
            body, height=SIGNATURE_HEIGHT, bg="white", highlightthickness=1,
            highlightbackground=self.c["BORDER"], cursor="pencil",
        )
        self._canvas.pack(fill="x", padx=12)
        self._canvas.bind("<ButtonPress-1>", self._on_pen_down)
        self._canvas.bind("<B1-Motion>", self._on_pen_move)
        self._canvas.bind("<ButtonRelease-1>", self._on_pen_up)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        accept_box = ctk.CTkCheckBox(
            body, text=ACCEPT_TEXT, variable=self._accept_var, command=self._refresh_state,
            font=self._font(11), fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
        )
        accept_box.pack(anchor="w", padx=12, pady=(14, 6))
        # CTkCheckBox no parte el texto solo: se le fija el ancho al label interno.
        accept_box._text_label.configure(wraplength=scaled(240), justify="left")
        ctk.CTkCheckBox(
            body, text="Enviarme una copia por correo", variable=self._copy_var,
            font=self._font(11), fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
        ).pack(anchor="w", padx=12, pady=(0, 10))

        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(6, 16))
        self._hint_label = ctk.CTkLabel(
            footer, text="", font=self._font(10), text_color=self.c["WARNING"],
            wraplength=scaled(290), justify="left",
        )
        self._hint_label.pack(anchor="w", pady=(0, 6))
        self._sign_button = ctk.CTkButton(
            footer, text="✍️  Firmar y continuar", height=scaled(36), corner_radius=8,
            font=self._font(12, bold=True), fg_color=self.c["SUCCESS"], hover_color=self.c["SUCCESS_HOVER"],
            state="disabled", command=self._sign,
        )
        self._sign_button.pack(fill="x")
        ctk.CTkButton(
            footer, text="No deseo participar", height=scaled(32), corner_radius=8,
            font=self._font(11), fg_color="transparent", hover_color=self.c["DANGER"],
            border_width=1, border_color=self.c["DANGER"], text_color=self.c["DANGER"],
            command=self._decline,
        ).pack(fill="x", pady=(8, 0))
        ctk.CTkButton(
            footer, text="←  Volver al panel (sin firmar)", height=scaled(26), corner_radius=8,
            font=self._font(10), fg_color="transparent", hover_color=self.c["BORDER"],
            text_color=self.c["TEXT_MUTED"], command=lambda: self._finish(RESULT_BACK),
        ).pack(fill="x", pady=(6, 0))

        for var in (self._nombre_var, self._ci_var, self._correo_var):
            var.trace_add("write", lambda *_: self._on_data_changed())

        # El zoom se ajusta al ancho real del área de la carta, que recién
        # se conoce cuando Tk terminó de acomodar la ventana.
        self.container.update_idletasks()
        available = self._pdf_scroll.winfo_width() - 60
        try:
            self._zoom = max(MIN_ZOOM, min(MAX_ZOOM, available / consent_pdf.page_width()))
        except Exception:  # noqa: BLE001 -- el error real lo informa _render_preview
            self._zoom = DEFAULT_ZOOM
        self._render_preview()
        self._refresh_state()

    # ---------------- vista previa ----------------
    def _on_data_changed(self):
        self._refresh_state()
        if self._preview_job is not None:
            self.app.after_cancel(self._preview_job)
        self._preview_job = self.app.after(PREVIEW_DEBOUNCE_MS, self._render_preview)

    def _build_document(self, with_signature: bool) -> pymupdf.Document:
        ci = self._ci_var.get().strip()
        return consent_pdf.build_filled(
            nombre=" ".join(self._nombre_var.get().split()),
            ci=normalize_ci(ci) or ci,
            fecha=self._fecha,
            signature=self._signature_image if with_signature and self._has_signature() else None,
        )

    def _render_preview(self):
        self._preview_job = None
        try:
            doc = self._build_document(with_signature=True)
            pages = consent_pdf.render_pages(doc, self._zoom)
            doc.close()
        except Exception as exc:  # noqa: BLE001
            self._show_template_error(
                str(exc) if isinstance(exc, consent_pdf.ConsentTemplateError)
                else f"No se pudo preparar la carta de consentimiento ({type(exc).__name__})."
            )
            return

        photos = [ImageTk.PhotoImage(page, master=self.container) for page in pages]
        if len(self._page_labels) != len(photos):
            for label in self._page_labels:
                label.destroy()
            self._page_labels = []
            for photo in photos:
                label = tk.Label(self._pdf_scroll, image=photo, borderwidth=0)
                label.pack(pady=10)
                self._page_labels.append(label)
        else:
            # Se reemplaza la imagen en el mismo label: no se pierde la
            # posición del scroll al actualizar la vista previa.
            for label, photo in zip(self._page_labels, photos):
                label.configure(image=photo)
        self._photos = photos

    def _show_template_error(self, text: str):
        self._template_error = text
        for label in self._page_labels:
            label.destroy()
        self._page_labels = []
        for child in self._pdf_scroll.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self._pdf_scroll, text=f"⚠️  {text}\n\nRuta esperada: {CONSENT_PDF}",
            font=self._font(13, bold=True), text_color=self.c["WARNING"],
            wraplength=scaled(420), justify="left",
        ).pack(padx=30, pady=40)
        self._refresh_state()

    # ---------------- firma ----------------
    def _new_signature_image(self) -> Image.Image:
        width = max(self._canvas.winfo_width(), 50)
        return Image.new("RGBA", (width * SIGNATURE_SCALE, SIGNATURE_HEIGHT * SIGNATURE_SCALE), (0, 0, 0, 0))

    def _on_canvas_resize(self, event):
        # Solo antes del primer trazo: después no se toca para no perder la firma.
        if self._signature_image is None or (
            not self._has_ink() and self._signature_image.width != event.width * SIGNATURE_SCALE
        ):
            self._signature_image = self._new_signature_image()

    def _has_ink(self) -> bool:
        return self._signature_length > 0

    def _has_signature(self) -> bool:
        return self._signature_image is not None and self._signature_length >= SIGNATURE_MIN_LENGTH

    def _draw_segment(self, start: tuple[int, int], end: tuple[int, int]):
        self._canvas.create_line(
            *start, *end, fill="#10183c", width=SIGNATURE_PEN, capstyle="round", smooth=True,
        )
        s = SIGNATURE_SCALE
        draw = ImageDraw.Draw(self._signature_image)
        width = SIGNATURE_PEN * s
        draw.line([(start[0] * s, start[1] * s), (end[0] * s, end[1] * s)], fill=SIGNATURE_INK, width=width)
        # Extremos redondeados (ImageDraw.line los deja cuadrados).
        radius = width / 2
        for x, y in (start, end):
            draw.ellipse([x * s - radius, y * s - radius, x * s + radius, y * s + radius], fill=SIGNATURE_INK)

    def _on_pen_down(self, event):
        if self._signature_image is None:
            self._signature_image = self._new_signature_image()
        self._last_point = (event.x, event.y)

    def _on_pen_move(self, event):
        if self._last_point is None:
            return
        point = (event.x, event.y)
        self._draw_segment(self._last_point, point)
        self._signature_length += ((point[0] - self._last_point[0]) ** 2 + (point[1] - self._last_point[1]) ** 2) ** 0.5
        self._last_point = point

    def _on_pen_up(self, _event):
        self._last_point = None
        self._on_data_changed()

    def _clear_signature(self):
        self._canvas.delete("all")
        self._signature_image = self._new_signature_image()
        self._signature_length = 0.0
        self._on_data_changed()

    # ---------------- validación ----------------
    def _missing(self) -> list[str]:
        if self._template_error:
            return ["la carta no se pudo cargar"]
        missing = []
        if len(self._nombre_var.get().split()) < 2:
            missing.append("nombre completo")
        if normalize_ci(self._ci_var.get()) is None:
            missing.append("C.I. válida (6 a 9 dígitos)")
        if not EMAIL_RE.match(self._correo_var.get().strip()):
            missing.append("correo válido")
        if not self._has_signature():
            missing.append("firma")
        if not self._accept_var.get():
            missing.append("marcar la casilla de aceptación")
        return missing

    def _refresh_state(self):
        missing = self._missing()
        self._sign_button.configure(state="disabled" if missing else "normal")
        self._hint_label.configure(text=f"Falta: {', '.join(missing)}." if missing else "")
        correo = self._correo_var.get().strip()
        self._correo_entry.configure(
            border_color=self.c["DANGER"] if correo and not EMAIL_RE.match(correo) else self.c["BORDER"])

    # ---------------- acciones ----------------
    def _sign(self):
        if self._missing():
            self._refresh_state()
            return
        number = self._participant["number"]
        nombre = " ".join(self._nombre_var.get().split())
        try:
            doc = self._build_document(with_signature=True)
            pdf_path = consent_pdf.save_filled(doc, consent_store.signed_pdf_path(number))
            doc.close()
            consent_store.save_signed(
                number, nombre=nombre, ci=normalize_ci(self._ci_var.get()),
                correo=self._correo_var.get().strip(), send_copy=self._copy_var.get(), pdf_path=pdf_path,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "No se pudo guardar el consentimiento",
                f"Ocurrió un error al guardar el PDF firmado ({type(exc).__name__}). "
                "No se registró la firma; inténtalo de nuevo.",
                parent=self.app,
            )
            return
        self._show_signed(pdf_path)

    def _decline(self):
        if not messagebox.askyesno(
            "No deseo participar",
            "¿Confirmas que no deseas participar en el estudio?\n\n"
            "No se guardará ninguno de los datos que hayas escrito en esta pantalla.",
            parent=self.app,
        ):
            return
        consent_store.save_declined(self._participant["number"])
        self._show_declined()

    # ---------------- pantallas finales ----------------
    def _centered(self) -> ctk.CTkFrame:
        self._clear()
        wrapper = ctk.CTkFrame(self.container, fg_color="transparent")
        wrapper.grid(row=0, column=0, columnspan=2)
        return wrapper

    def _show_signed(self, pdf_path: Path):
        number = self._participant["number"]
        wrapper = self._centered()
        ctk.CTkLabel(wrapper, text="✅", font=ctk.CTkFont(size=scaled(44))).pack(pady=(0, 8))
        ctk.CTkLabel(wrapper, text="Consentimiento firmado", font=self._font(22, bold=True)).pack()
        ctk.CTkLabel(
            wrapper,
            text="¡Gracias por aceptar participar! Recuerda que puedes retirarte\n"
                 "en cualquier momento, sin dar explicaciones.",
            font=self._font(13), text_color=self.c["TEXT_MUTED"], justify="center",
        ).pack(pady=(8, 18))

        status = ctk.CTkLabel(
            wrapper, text="✉️  Enviando la copia por correo...", font=self._font(12),
            text_color=self.c["TEXT_MUTED"], wraplength=scaled(460), justify="center",
        )
        status.pack(pady=(0, 6))
        resend = ctk.CTkButton(
            wrapper, text="🔁  Reenviar copia", height=scaled(30), corner_radius=8, font=self._font(11),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
        )

        def start_send():
            status.configure(text="✉️  Enviando la copia por correo...", text_color=self.c["TEXT_MUTED"])
            resend.pack_forget()
            consent_mailer.send_consent_async(number, lambda result: self.app.after(0, on_sent, result))

        def on_sent(result: consent_mailer.SendResult):
            if not status.winfo_exists():
                return  # ya se siguió al estudio; el resultado queda en el registro
            if result.ok:
                status.configure(text=f"✅  {result.message}", text_color=self.c["SUCCESS"])
            else:
                status.configure(
                    text=f"⚠️  {result.message}\nPuedes continuar: se reintentará al abrir la app.",
                    text_color=self.c["WARNING"],
                )
                resend.pack(after=status, pady=(0, 6))

        resend.configure(command=start_send)

        buttons = ctk.CTkFrame(wrapper, fg_color="transparent")
        buttons.pack(pady=(16, 0))
        ctk.CTkButton(
            buttons, text="📄  Ver mi consentimiento", height=scaled(36), corner_radius=8,
            font=self._font(12), fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=lambda: open_consent_viewer(self.app, pdf_path, "Mi consentimiento"),
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            buttons, text="Continuar al estudio  ▶", height=scaled(36), corner_radius=8,
            font=self._font(12, bold=True), fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=lambda: self._finish(RESULT_ACCEPTED),
        ).pack(side="left")

        start_send()

    def _show_declined(self):
        wrapper = self._centered()
        ctk.CTkLabel(wrapper, text="🙏", font=ctk.CTkFont(size=scaled(44))).pack(pady=(0, 8))
        ctk.CTkLabel(wrapper, text="Gracias por tu tiempo", font=self._font(22, bold=True)).pack()
        ctk.CTkLabel(
            wrapper,
            text="Has decidido no participar en el estudio. No se guardó ningún dato tuyo\n"
                 "y esta decisión no tiene ninguna consecuencia para ti.",
            font=self._font(13), text_color=self.c["TEXT_MUTED"], justify="center",
        ).pack(pady=(8, 20))
        ctk.CTkButton(
            wrapper, text="Cerrar", height=scaled(36), width=scaled(160), corner_radius=8,
            font=self._font(12, bold=True), fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=lambda: self._finish(RESULT_DECLINED),
        ).pack()
