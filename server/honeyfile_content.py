"""Contenido REAL de los honeyfiles.

Antes un honeyfile era texto plano guardado con extensión .pdf o .docx:
al abrirlo daba error, lo que delata la trampa. Ahora el servidor genera
un archivo válido del tipo indicado a partir del texto de la plantilla,
y el agente lo escribe tal cual (bytes).

Nada en los archivos menciona ALFA-Sentinel ni "señuelo": autor, título
y contenido son los de un documento institucional común.

Formato del texto de la plantilla ('honeyfile_templates.content'):
- PDF, DOCX, TXT, CSV: cada línea es un párrafo; la primera es el título.
- XLSX: cada línea es una fila y las celdas se separan con '|'; la
  primera fila es el encabezado.
- ZIP: el texto va en un .txt con el mismo nombre dentro del ZIP.
- JPG, PNG: se dibuja como un documento escaneado o fotografiado.
"""

import hashlib
import io
import os
import zipfile
from datetime import datetime
from functools import lru_cache
from xml.sax.saxutils import escape

SUPPORTED_TYPES = ("PDF", "DOCX", "XLSX", "TXT", "CSV", "ZIP", "JPG", "PNG")

# Metadatos de documento de oficina comunes (no identifican al sistema).
DOCUMENT_AUTHOR = "Unidad Administrativa"
# Fecha fija: el mismo texto produce siempre el mismo archivo.
_FIXED_DATE = datetime(2026, 8, 14, 9, 30, 0)


def _lines(text):
    return [line.rstrip() for line in (text or "").replace("\r\n", "\n").split("\n")]


def _title_and_body(text, file_name):
    lines = _lines(text)
    title = next((l for l in lines if l.strip()), os.path.splitext(file_name)[0].replace("_", " "))
    body = lines[lines.index(title) + 1:] if title in lines else lines
    return title, body


def _pdf(text, file_name):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    title, body = _title_and_body(text, file_name)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        title=title, author=DOCUMENT_AUTHOR, invariant=1,
    )
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 12)]
    for line in body:
        story.append(Paragraph(escape(line), styles["BodyText"]) if line.strip() else Spacer(1, 8))
    doc.build(story)
    return buffer.getvalue()


def _zip_entry(name):
    info = zipfile.ZipInfo(name, date_time=_FIXED_DATE.timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _docx(text, file_name):
    """DOCX mínimo válido (Office Open XML) armado a mano: no hace falta
    ninguna librería extra y abre en Word y LibreOffice."""

    title, body = _title_and_body(text, file_name)

    def paragraph(line, bold=False, size=None):
        props = ""
        if bold or size:
            props = "<w:rPr>" + ("<w:b/>" if bold else "") + (f'<w:sz w:val="{size}"/>' if size else "") + "</w:rPr>"
        return f'<w:p><w:r>{props}<w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>'

    paragraphs = [paragraph(title, bold=True, size=32)] + [paragraph(l) for l in body]
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(paragraphs)}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'
    )
    stamp = _FIXED_DATE.strftime("%Y-%m-%dT%H:%M:%SZ")
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '</Types>'
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '</Relationships>'
        ),
        "docProps/core.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{escape(title)}</dc:title><dc:creator>{DOCUMENT_AUTHOR}</dc:creator>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{stamp}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{stamp}</dcterms:modified>'
            '</cp:coreProperties>'
        ),
        "word/document.xml": document,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(_zip_entry(name), content.encode("utf-8"))
    return buffer.getvalue()


def _xlsx(text, file_name):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Hoja1"
    rows = [line.split("|") for line in _lines(text) if line.strip()]
    for index, cells in enumerate(rows):
        values = []
        for cell in cells:
            cell = cell.strip()
            try:
                values.append(float(cell) if "." in cell else int(cell))
            except ValueError:
                values.append(cell)
        sheet.append(values)
        if index == 0:
            for c in sheet[1]:
                c.font = Font(bold=True)
    for column in sheet.columns:
        width = max(len(str(c.value or "")) for c in column)
        sheet.column_dimensions[column[0].column_letter].width = min(max(width + 2, 10), 45)
    workbook.properties.creator = DOCUMENT_AUTHOR
    workbook.properties.lastModifiedBy = DOCUMENT_AUTHOR
    workbook.properties.created = _FIXED_DATE
    workbook.properties.modified = _FIXED_DATE
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _text(text, file_name):
    return "\r\n".join(_lines(text)).encode("utf-8")


def _zip(text, file_name):
    inner = os.path.splitext(file_name)[0] + ".txt"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(_zip_entry(inner), _text(text, inner))
    return buffer.getvalue()


def _image(text, file_name, image_format):
    """Documento escaneado: hoja clara con el texto de la plantilla."""

    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import reportlab

    fonts = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    title_font = ImageFont.truetype(os.path.join(fonts, "VeraBd.ttf"), 34)
    body_font = ImageFont.truetype(os.path.join(fonts, "Vera.ttf"), 24)

    title, body = _title_and_body(text, file_name)
    width, height = 1240, 1754  # A4 a 150 ppp
    # Escala de grises, fondo levemente gris y un poco de desenfoque:
    # aspecto de escaneo (y archivos más livianos que a color).
    image = Image.new("L", (width, height), 243)
    draw = ImageDraw.Draw(image)
    draw.rectangle([60, 60, width - 60, height - 60], outline=199, width=2)
    y = 120
    draw.text((110, y), title, font=title_font, fill=36)
    y += 80
    draw.line([110, y - 20, width - 110, y - 20], fill=150, width=2)
    for line in body:
        draw.text((110, y), line, font=body_font, fill=46)
        y += 40 if line.strip() else 24
        if y > height - 150:
            break
    image = image.filter(ImageFilter.GaussianBlur(0.6))

    buffer = io.BytesIO()
    if image_format == "JPEG":
        image.save(buffer, format="JPEG", quality=85)
    else:
        image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


_BUILDERS = {
    "PDF": _pdf,
    "DOCX": _docx,
    "XLSX": _xlsx,
    "TXT": _text,
    "CSV": _text,
    "ZIP": _zip,
    "JPG": lambda t, n: _image(t, n, "JPEG"),
    "PNG": lambda t, n: _image(t, n, "PNG"),
}


@lru_cache(maxsize=256)
def _build_cached(file_type, file_name, text_digest, text):
    return _BUILDERS[file_type](text, file_name)


def build_honeyfile_bytes(file_type, file_name, text):
    """Bytes del archivo real. Se guarda en memoria por plantilla: los
    agentes piden su política cada 45 s y no tiene sentido regenerar
    los mismos archivos cada vez."""

    file_type = (file_type or "TXT").upper()
    if file_type not in _BUILDERS:
        file_type = "TXT"
    text = text or ""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return _build_cached(file_type, file_name or "", digest, text)
