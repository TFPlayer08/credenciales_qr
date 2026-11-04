"""Generador de reportes en PDF (A4 vertical) con la marca NovaTech."""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

NAVY = colors.HexColor("#221b45")
PINK = colors.HexColor("#e5287d")
MUTED = colors.HexColor("#6b6f8d")
LINE = colors.HexColor("#e8e9f3")
ZEBRA = colors.HexColor("#f4f5fb")

ESTADO_COLORES = {  # (fondo, texto)
    "Vigente": ("#d1fae5", "#065f46"),
    "Inactiva": ("#e2e8f0", "#334155"),
    "Vencida": ("#ffe4e6", "#9f1239"),
    "No vigente": ("#fef3c7", "#92400e"),
}


def _fmt(d):
    return d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)


def construir_pdf(titulo, filtro_txt, rows, resumen, logo_path, institucion):
    buf = io.BytesIO()
    ahora = datetime.now()
    generado = ahora.strftime("%d/%m/%Y %H:%M")
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=18 * mm,
        title=f"{titulo} - {institucion}", author=institucion,
    )
    ancho = A4[0] - 30 * mm

    h_titulo = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=17, textColor=colors.white, leading=21)
    h_sub = ParagraphStyle("s", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#d9d6ee"), leading=13)
    c_head = ParagraphStyle("ch", fontName="Helvetica-Bold", fontSize=8.5, textColor=colors.white, leading=11)
    c_txt = ParagraphStyle("c", fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#1e1b3a"), leading=11)
    c_bold = ParagraphStyle("cb", parent=c_txt, fontName="Helvetica-Bold")
    c_center = ParagraphStyle("cc", parent=c_txt, alignment=TA_CENTER)
    chip = ParagraphStyle("chip", fontName="Helvetica-Bold", fontSize=8.5, leading=11, alignment=TA_CENTER)

    story = []

    # ---- Encabezado con logo ----
    logo = Image(logo_path, width=34 * mm, height=34 * mm * 327 / 457)
    texto = [Paragraph(titulo, h_titulo), Spacer(1, 2), Paragraph(filtro_txt, h_sub),
             Paragraph(f"Generado el {generado} · {len(rows)} registro(s)", h_sub)]
    cab = Table([[logo, texto]], colWidths=[40 * mm, ancho - 40 * mm])
    cab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 4 * mm), ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ("LINEBELOW", (0, 0), (-1, -1), 2.5, PINK),
    ]))
    story += [cab, Spacer(1, 6 * mm)]

    # ---- Resumen por estado ----
    orden = ["Vigente", "Inactiva", "Vencida", "No vigente"]
    celdas, estilos = [], []
    for i, e in enumerate(orden):
        bg, fg = ESTADO_COLORES[e]
        celdas.append(Paragraph(f'<font color="{fg}">{e}: {resumen.get(e, 0)}</font>', chip))
        estilos.append(("BACKGROUND", (i, 0), (i, 0), colors.HexColor(bg)))
    celdas.append(Paragraph(f'<font color="#ffffff">Total: {len(rows)}</font>', chip))
    estilos.append(("BACKGROUND", (4, 0), (4, 0), NAVY))
    res = Table([celdas], colWidths=[ancho / 5] * 5, rowHeights=[8 * mm])
    res.setStyle(TableStyle(estilos + [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEAFTER", (0, 0), (-2, 0), 3, colors.white),
    ]))
    story += [res, Spacer(1, 6 * mm)]

    # ---- Tabla de datos ----
    encabezados = ["Trabajador", "N° trabajador", "N° tarjeta", "Área", "Vigencia", "Estado"]
    data = [[Paragraph(h, c_head) for h in encabezados]]
    est = []
    for i, r in enumerate(rows, start=1):
        bg, fg = ESTADO_COLORES.get(r["estado"], ("#ffffff", "#000000"))
        data.append([
            Paragraph(r["nombre_completo"], c_bold),
            Paragraph(r["numero_trabajador"], c_txt),
            Paragraph(r["numero_tarjeta"], c_txt),
            Paragraph(f'{r["area"]}<br/><font size="7" color="#6b6f8d">{r["cargo"]}</font>', c_txt),
            Paragraph(_fmt(r["fecha_vencimiento"]), c_txt),
            Paragraph(f'<font color="{fg}"><b>{r["estado"]}</b></font>', c_center),
        ])
        est.append(("BACKGROUND", (5, i), (5, i), colors.HexColor(bg)))
        if i % 2 == 0:
            est.append(("BACKGROUND", (0, i), (4, i), ZEBRA))
    if not rows:
        data.append([Paragraph("Sin resultados para el filtro seleccionado.", c_txt), "", "", "", "", ""])
        est.append(("SPAN", (0, 1), (-1, 1)))

    anchos = [47 * mm, 24 * mm, 24 * mm, 41 * mm, 22 * mm, ancho - 158 * mm]
    tabla = Table(data, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
    ] + est))
    story.append(tabla)

    def pie(canvas, d):
        canvas.saveState()
        w, _ = A4
        canvas.setStrokeColor(PINK)
        canvas.setLineWidth(1.2)
        canvas.line(15 * mm, 13 * mm, w - 15 * mm, 13 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(15 * mm, 8.5 * mm, f"{institucion} · Sistema de credencialización")
        canvas.drawRightString(w - 15 * mm, 8.5 * mm, f"Página {d.page}")
        canvas.drawCentredString(w / 2, 8.5 * mm, generado)
        canvas.restoreState()

    doc.build(story, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()



def _ajustar_foto(path, ratio=24 / 31):
    from PIL import Image as PILImage
    im = PILImage.open(path).convert("RGB")
    w, h = im.size
    if w / h > ratio:
        nw = int(h * ratio)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / ratio)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    b = io.BytesIO()
    im.save(b, format="JPEG", quality=92)
    b.seek(0)
    return b


def _dibujar_par_credencial(c, r, x_front, x_back, y, logo_icon_path, uploads_dir, base_url, institucion):
    import os
    import qrcode
    from reportlab.lib.utils import ImageReader, simpleSplit

    W, H, R = 86 * mm, 54 * mm, 3.5 * mm
    INK = colors.HexColor("#1e1b3a")
    SOFT_PINK = colors.HexColor("#ffe9f3")

    # ================= ANVERSO (IZQUIERDA) =================
    c.saveState()
    p = c.beginPath()
    p.roundRect(x_front, y, W, H, R)
    c.clipPath(p, stroke=0, fill=0)

    # Fondo blanco
    c.setFillColor(colors.white)
    c.rect(x_front, y, W, H, stroke=0, fill=1)

    # Franja superior azul marino
    hh = 11.5 * mm
    c.setFillColor(NAVY)
    c.rect(x_front, y + H - hh, W, hh, stroke=0, fill=1)
    if os.path.exists(logo_icon_path):
        c.drawImage(logo_icon_path, x_front + 3.5 * mm, y + H - 9.2 * mm, width=9 * mm, height=6.8 * mm, mask="auto")
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(x_front + 14 * mm, y + H - 7.3 * mm, institucion)

    # Franja inferior rosa/morada
    c.setFillColor(PINK)
    c.rect(x_front, y, W, 2.2 * mm, stroke=0, fill=1)

    # Foto o inicial
    px, py, pw, ph = x_front + 4.5 * mm, y + 6.5 * mm, 24 * mm, 31 * mm
    foto_file = os.path.join(uploads_dir, r["foto_path"]) if r.get("foto_path") else None
    if foto_file and os.path.exists(foto_file):
        c.saveState()
        pf = c.beginPath()
        pf.roundRect(px, py, pw, ph, 2.5 * mm)
        c.clipPath(pf, stroke=0, fill=0)
        c.drawImage(ImageReader(_ajustar_foto(foto_file)), px, py, width=pw, height=ph)
        c.restoreState()
        c.setStrokeColor(SOFT_PINK)
        c.setLineWidth(1)
        c.roundRect(px, py, pw, ph, 2.5 * mm, stroke=1, fill=0)
    else:
        c.setFillColor(PINK)
        c.roundRect(px, py, pw, ph, 2.5 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 24)
        inicial = (r["nombre_completo"] or "?")[0].upper()
        c.drawCentredString(px + pw / 2, py + ph / 2 - 3 * mm, inicial)

    # Datos del trabajador (derecha del anverso)
    tx = x_front + 32 * mm
    max_tw = W - 35 * mm
    lineas_nom = simpleSplit(r["nombre_completo"], "Helvetica-Bold", 9.5, max_tw)[:2]
    ty = y + 32.5 * mm if len(lineas_nom) > 1 else y + 30.5 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9.5)
    for ln in lineas_nom:
        c.drawString(tx, ty, ln)
        ty -= 4 * mm

    ty -= 1 * mm
    c.setFillColor(PINK)
    c.setFont("Helvetica-Bold", 8.8)
    c.drawString(tx, ty, f"N° {r['numero_trabajador']}")

    ty -= 5 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8)
    for ln in simpleSplit(r["cargo"], "Helvetica-Bold", 8, max_tw)[:1]:
        c.drawString(tx, ty, ln)

    ty -= 4 * mm
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.8)
    for ln in simpleSplit(r["area"], "Helvetica", 7.8, max_tw)[:1]:
        c.drawString(tx, ty, ln)

    c.restoreState()
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.roundRect(x_front, y, W, H, R, stroke=1, fill=0)

    # ================= REVERSO (DERECHA) =================
    c.saveState()
    p2 = c.beginPath()
    p2.roundRect(x_back, y, W, H, R)
    c.clipPath(p2, stroke=0, fill=0)

    c.setFillColor(colors.white)
    c.rect(x_back, y, W, H, stroke=0, fill=1)

    # Pie institucional rosa suave
    fh = 6.5 * mm
    c.setFillColor(SOFT_PINK)
    c.rect(x_back, y, W, fh, stroke=0, fill=1)
    c.setFillColor(PINK)
    c.setFont("Helvetica-Bold", 6)
    c.drawCentredString(x_back + W / 2, y + 2.3 * mm, f"{institucion} · Credencial personal e intransferible")

    # Código QR
    qx, qy, qs = x_back + 5 * mm, y + 10.5 * mm, 35 * mm
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.roundRect(qx, qy, qs, qs, 2 * mm, stroke=1, fill=0)
    qr_img = qrcode.make(f"{base_url}/verificar/{r['qr_token']}", box_size=8, border=1)
    qbuf = io.BytesIO()
    qr_img.save(qbuf, format="PNG")
    qbuf.seek(0)
    c.drawImage(ImageReader(qbuf), qx + 1.2 * mm, qy + 1.2 * mm, width=qs - 2.4 * mm, height=qs - 2.4 * mm)

    # Datos del reverso
    bx = x_back + 43.5 * mm
    max_bw = W - 46.5 * mm
    by = y + 38 * mm

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6)
    c.drawString(bx, by, "TARJETA")
    by -= 3.8 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.8)
    c.drawString(bx, by, str(r["numero_tarjeta"]))

    by -= 5.2 * mm
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6)
    c.drawString(bx, by, "VENCE")
    by -= 3.8 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.8)
    c.drawString(bx, by, _fmt(r["fecha_vencimiento"]))

    by -= 5.5 * mm
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.5)
    for ln in simpleSplit("Escanee el QR para verificar la vigencia de esta credencial.", "Helvetica", 6.5, max_bw):
        c.drawString(bx, by, ln)
        by -= 3.1 * mm

    c.restoreState()
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.roundRect(x_back, y, W, H, R, stroke=1, fill=0)


def construir_credenciales_pdf(rows, logo_path, logo_icon_path, uploads_dir, base_url, institucion, subtitulo="Todas las credenciales"):
    from reportlab.pdfgen import canvas as pdfcanvas

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    pw, ph = A4
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    por_pagina = 3
    total_pags = max(1, (len(rows) + por_pagina - 1) // por_pagina)

    for pag in range(total_pags):
        lote = rows[pag * por_pagina:(pag + 1) * por_pagina]

        # Encabezado de página
        c.setFillColor(NAVY)
        c.rect(15 * mm, ph - 38 * mm, pw - 30 * mm, 24 * mm, stroke=0, fill=1)
        c.setStrokeColor(PINK)
        c.setLineWidth(2.5)
        c.line(15 * mm, ph - 38 * mm, pw - 15 * mm, ph - 38 * mm)
        c.drawImage(logo_path, 19 * mm, ph - 36 * mm, width=28 * mm, height=20 * mm, mask="auto")

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(52 * mm, ph - 23 * mm, "Credenciales de identificación")
        c.setFillColor(colors.HexColor("#d9d6ee"))
        c.setFont("Helvetica", 9)
        c.drawString(52 * mm, ph - 28.5 * mm, f"{subtitulo} · Formato horizontal (anverso y reverso)")
        c.drawString(52 * mm, ph - 33.5 * mm, f"Generado el {ahora} · {len(rows)} credencial(es)")

        # Etiquetas de columna Anverso / Reverso
        x_front, x_back = 16 * mm, 108 * mm
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(x_front + 43 * mm, ph - 44.5 * mm, "ANVERSO (FRENTE)")
        c.drawCentredString(x_back + 43 * mm, ph - 44.5 * mm, "REVERSO (CÓDIGO QR)")

        # Pares de credenciales
        y_positions = [ph - 102 * mm, ph - 165 * mm, ph - 228 * mm]
        for idx, r in enumerate(lote):
            _dibujar_par_credencial(c, r, x_front, x_back, y_positions[idx],
                                    logo_icon_path, uploads_dir, base_url, institucion)

        if not lote:
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 10)
            c.drawCentredString(pw / 2, ph / 2, "No se encontraron credenciales con el filtro seleccionado.")

        # Pie de página
        c.setStrokeColor(PINK)
        c.setLineWidth(1.2)
        c.line(15 * mm, 13 * mm, pw - 15 * mm, 13 * mm)
        c.setFont("Helvetica", 8)
        c.setFillColor(MUTED)
        c.drawString(15 * mm, 8.5 * mm, f"{institucion} · Sistema de credencialización")
        c.drawCentredString(pw / 2, 8.5 * mm, ahora)
        c.drawRightString(pw - 15 * mm, 8.5 * mm, f"Página {pag + 1} de {total_pags}")
        c.showPage()

    c.save()
    return buf.getvalue()
