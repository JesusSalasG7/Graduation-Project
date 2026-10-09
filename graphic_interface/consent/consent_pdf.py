"""Render y llenado de la carta de consentimiento (PDF) con PyMuPDF.

El original (`paths.CONSENT_PDF`) nunca se modifica: `build_filled()` lo
abre, escribe sobre esa copia en memoria y el llamador la guarda en otra
ruta. Cada dato se ubica buscando su etiqueta con `page.search_for()` y
la línea en blanco que le sigue -- no hay coordenadas fijas, así que si
la carta cambia de formato y una etiqueta deja de encontrarse, falla con
un `ConsentTemplateError` que dice cuál.
"""

import io
from pathlib import Path
from typing import Optional

# `import fitz` es el nombre histórico del mismo paquete (PyMuPDF); en las
# versiones actuales ese alias imprime un aviso de obsolescencia.
import pymupdf
from PIL import Image

from paths import CONSENT_PDF

LABEL_GREETING = "Estimado/a"
LABEL_CI = "C.I.:"
LABEL_NAME = "Nombre completo:"
LABEL_SIGNATURE = "Firma:"
LABEL_DATE = "Fecha:"

FONT_NAME = "helv"
FONT_SIZE = 11
MIN_FONT_SIZE = 7
TEXT_COLOR = (0.05, 0.1, 0.35)
# El texto se apoya un punto por encima de la línea base del renglón,
# para que quede "sobre" el subrayado y no pisándolo.
BASELINE_LIFT = 1.0
TEXT_PADDING = 3.0
# Alto de la firma respecto a la línea base de "Firma:": casi todo por
# encima del renglón y un poco por debajo, como una firma manuscrita.
SIGNATURE_ABOVE = 25.0
SIGNATURE_BELOW = 5.0


class ConsentTemplateError(RuntimeError):
    """La carta no tiene la estructura esperada (falta una etiqueta o su
    línea en blanco)."""


def _find_label(doc: pymupdf.Document, label: str) -> tuple[pymupdf.Page, pymupdf.Rect]:
    hits = [(page, rect) for page in doc for rect in page.search_for(label)]
    if not hits:
        raise ConsentTemplateError(
            f'No se encontró la etiqueta "{label}" en la carta de consentimiento '
            f"({CONSENT_PDF.name}). Revisa que el PDF sea el correcto."
        )
    if len(hits) > 1:
        raise ConsentTemplateError(
            f'La etiqueta "{label}" aparece {len(hits)} veces en la carta de '
            "consentimiento; se esperaba una sola."
        )
    return hits[0]


def _baseline(page: pymupdf.Page, label_rect: pymupdf.Rect) -> float:
    """Línea base real del renglón de la etiqueta (origen del span)."""
    for block in page.get_text("dict", clip=label_rect)["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    return span["origin"][1]
    return label_rect.y1 - 0.21 * label_rect.height


def _blanks_after(page: pymupdf.Page, label: str, label_rect: pymupdf.Rect, count: int) -> list[pymupdf.Rect]:
    """Las `count` líneas en blanco (palabras hechas solo de "_") que
    siguen a la etiqueta en su mismo renglón."""
    center_y = (label_rect.y0 + label_rect.y1) / 2
    blanks = sorted(
        (
            pymupdf.Rect(x0, y0, x1, y1)
            for x0, y0, x1, y1, word, *_ in page.get_text("words")
            if word and set(word) == {"_"} and y0 <= center_y <= y1 and x0 >= label_rect.x1 - 1
        ),
        key=lambda r: r.x0,
    )
    if len(blanks) < count:
        raise ConsentTemplateError(
            f'Se encontró la etiqueta "{label}" pero no la línea en blanco que '
            f"debería seguirla (se esperaban {count}, hay {len(blanks)})."
        )
    return blanks[:count]


def _write_on_blank(page: pymupdf.Page, blank: pymupdf.Rect, baseline: float, text: str, center: bool = False) -> None:
    size = FONT_SIZE
    available = blank.width - 2 * TEXT_PADDING
    while size > MIN_FONT_SIZE and pymupdf.get_text_length(text, FONT_NAME, size) > available:
        size -= 0.5
    width = pymupdf.get_text_length(text, FONT_NAME, size)
    x = blank.x0 + ((blank.width - width) / 2 if center else TEXT_PADDING)
    page.insert_text(
        (x, baseline - BASELINE_LIFT), text,
        fontname=FONT_NAME, fontsize=size, color=TEXT_COLOR,
    )


def trim_signature(image: Image.Image) -> Optional[Image.Image]:
    """Recorta la firma (RGBA, fondo transparente) a la tinta. None si
    está vacía."""
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return None
    return image.crop(bbox)


def _signature_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_filled(
    nombre: str,
    ci: str,
    fecha: str,
    signature: Optional[Image.Image] = None,
    source: Path = CONSENT_PDF,
) -> pymupdf.Document:
    """Devuelve una copia en memoria de la carta con los datos puestos.

    `fecha` va como "DD / MM / AAAA". Los campos vacíos se dejan en
    blanco (vista previa mientras se escribe); `signature` es la imagen
    RGBA de la firma, o None si todavía no firmó.
    """
    if not Path(source).exists():
        raise ConsentTemplateError(f"No se encontró la carta de consentimiento en {source}.")
    doc = pymupdf.open(source)

    # Se ubican todos los campos ANTES de escribir nada: el texto que se
    # inserta no debe poder confundirse con una etiqueta.
    fields = {}
    for label, count in (
        (LABEL_GREETING, 1), (LABEL_CI, 1), (LABEL_NAME, 1), (LABEL_SIGNATURE, 1), (LABEL_DATE, 3),
    ):
        page, rect = _find_label(doc, label)
        fields[label] = (page, _baseline(page, rect), _blanks_after(page, label, rect, count))

    for label, text in ((LABEL_GREETING, nombre), (LABEL_NAME, nombre), (LABEL_CI, ci)):
        if text:
            page, baseline, blanks = fields[label]
            _write_on_blank(page, blanks[0], baseline, text)

    date_parts = [part.strip() for part in fecha.split("/")]
    if len(date_parts) != 3:
        raise ValueError(f'Fecha con formato inesperado: "{fecha}" (se esperaba DD / MM / AAAA).')
    page, baseline, blanks = fields[LABEL_DATE]
    for blank, part in zip(blanks, date_parts):
        _write_on_blank(page, blank, baseline, part, center=True)

    trimmed = trim_signature(signature) if signature is not None else None
    if trimmed is not None:
        page, baseline, blanks = fields[LABEL_SIGNATURE]
        blank = blanks[0]
        max_height = SIGNATURE_ABOVE + SIGNATURE_BELOW
        max_width = blank.width - 2 * TEXT_PADDING
        scale = min(max_width / trimmed.width, max_height / trimmed.height)
        width, height = trimmed.width * scale, trimmed.height * scale
        x0 = blank.x0 + TEXT_PADDING
        y1 = baseline + SIGNATURE_BELOW
        page.insert_image(
            pymupdf.Rect(x0, y1 - height, x0 + width, y1),
            stream=_signature_png(trimmed), keep_proportion=True, overlay=True,
        )

    return doc


def save_filled(doc: pymupdf.Document, destination: Path) -> Path:
    """Guarda la copia firmada. Se niega a escribir sobre el original."""
    destination = Path(destination)
    if destination.resolve() == CONSENT_PDF.resolve():
        raise ValueError("La copia firmada no puede sobrescribir la carta original.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    doc.save(destination, garbage=3, deflate=True)
    return destination


def render_pages(doc: pymupdf.Document, zoom: float = 1.5) -> list[Image.Image]:
    """Páginas del documento como imágenes Pillow, para mostrarlas en la app."""
    matrix = pymupdf.Matrix(zoom, zoom)
    pages = []
    for page in doc:
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        pages.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    return pages


def page_width(source: Path = CONSENT_PDF) -> float:
    with pymupdf.open(source) as doc:
        return doc[0].rect.width
