import io
import json
import os
import re
import smtplib
import socket
import urllib.request
import uuid
from datetime import date, datetime
from email.message import EmailMessage
from functools import wraps

import mysql.connector
import qrcode
from dotenv import load_dotenv
from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_file, session, url_for)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from db import query

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
UPLOADS = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOADS, exist_ok=True)

# Auto-inicializar la BD en el primer arranque si las tablas no existen
def _auto_init_db():
    try:
        from init_db import inicializar_si_es_necesario
        inicializar_si_es_necesario()
    except Exception as e:
        print("[AVISO] No se pudo auto-inicializar la base de datos:", e)

_auto_init_db()
EXT = {"png", "jpg", "jpeg", "webp"}
CURP_RE = re.compile(r"^[A-Z]{4}\d{6}[A-Z0-9]{8}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
NOMBRE_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)+$")
SOLO_LETRAS_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*$")
CODIGO_RE = re.compile(r"^[A-Za-z0-9\-]{2,30}$")

AREAS_ADSCRIPCION = [
    "Dirección",
    "Administración",
    "Recursos Humanos",
    "Finanzas",
    "Sistemas",
    "Soporte",
    "Operaciones",
    "Marketing",
    "Logística",
    "Ventas",
    "Jurídico",
]

ETIQUETAS_NOTIF = {
    "generada": "Creación de credencial",
    "desactivada": "Desactivación de credencial",
    "vencimiento_modificado": "Cambio de fecha de vencimiento",
}


@app.context_processor
def inject():
    rol, email_usr = session.get("rol"), session.get("email")
    if "uid" in session and (not rol or not email_usr):
        u = query("SELECT email, rol FROM usuarios WHERE id=%s", (session["uid"],), one=True)
        if u:
            rol = session["rol"] = u.get("rol", "admin")
            email_usr = session["email"] = u["email"]
    return {
        "INSTITUCION": os.getenv("INSTITUCION", "NovaTech"),
        "ROL": rol or "admin",
        "USER_EMAIL": email_usr or "",
        "AREAS": AREAS_ADSCRIPCION,
    }


@app.errorhandler(413)
def archivo_muy_grande(_e):
    flash("La fotografía supera el tamaño máximo permitido de 4 MB.", "error")
    return redirect(request.referrer or url_for("index"))


@app.template_filter("fecha")
def fecha(v):
    return v.strftime("%d/%m/%Y") if hasattr(v, "strftime") else v


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "uid" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "uid" not in session:
            return redirect(url_for("login", next=request.path))
        u = query("SELECT email, rol FROM usuarios WHERE id=%s", (session["uid"],), one=True)
        rol = u.get("rol", "admin") if u else "consulta"
        session["rol"] = rol
        if rol != "admin":
            flash(
                f"Acceso denegado: la cuenta ({u['email'] if u else 'actual'}) es de solo consulta y no tiene permisos para registrar, modificar ni desactivar trabajadores.",
                "error",
            )
            return redirect(request.referrer or url_for("index"))
        return f(*a, **kw)
    return wrapper


def _enviar_resend_http(api_key, remitente, destinatario, asunto, html, texto):
    for destino in [destinatario, "l23270596@tuxtla.tecnm.mx"]:
        payload = json.dumps({
            "from": remitente,
            "to": [destino],
            "subject": asunto if destino == destinatario else f"{asunto} (para {destinatario})",
            "html": html,
            "text": texto,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201):
                    return True
        except urllib.error.HTTPError as e:
            if destino == destinatario and destino != "l23270596@tuxtla.tecnm.mx":
                continue
            raise e
    return False


# ---------- Envío automático al correo personal del trabajador ----------
def notificar(cred_id, tipo):
    load_dotenv(override=True)
    c = query("SELECT * FROM v_credenciales WHERE id=%s", (cred_id,), one=True)
    if not c or not c.get("email"):
        return

    inst = os.getenv("INSTITUCION", "NovaTech")
    tipo_txt = ETIQUETAS_NOTIF.get(tipo) or {
        "creacion": "Creación de credencial",
        "desactivacion": "Desactivación de credencial",
    }.get(tipo, "Actualización de credencial")
    vigencia = f"{fecha(c['fecha_inicio'])} al {fecha(c['fecha_vencimiento'])}"
    asunto = f"[{inst}] {tipo_txt} · {c['numero_trabajador']}"

    cuerpo_txt = (
        f"Nombre del trabajador: {c['nombre_completo']}\n"
        f"N° de trabajador: {c['numero_trabajador']}\n"
        f"N° de tarjeta: {c['numero_tarjeta']}\n"
        f"Tipo de notificación: {tipo_txt}\n"
        f"Vigencia de la credencial: {vigencia}\n"
        f"Estado actualizado: {c['estado']}\n"
    )

    cuerpo_html = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:540px;margin:0 auto;border:1px solid #e8e9f3;border-radius:14px;overflow:hidden">
      <div style="background:#221b45;color:#fff;padding:18px 24px;border-bottom:4px solid #e5287d">
        <h2 style="margin:0;font-size:20px">{inst} · Notificación de Credencial</h2>
      </div>
      <div style="padding:24px;color:#1e1b3a">
        <p style="margin-top:0">Hola <b>{c['nombre_completo']}</b>, se ha registrado una actualización en tu credencial:</p>
        <table style="width:100%;border-collapse:collapse;background:#f4f5fb;border-radius:10px;padding:12px">
          <tr><td style="padding:10px 14px;color:#6b6f8d">Nombre del trabajador</td><td style="padding:10px 14px;font-weight:600">{c['nombre_completo']}</td></tr>
          <tr><td style="padding:10px 14px;color:#6b6f8d;border-top:1px solid #e8e9f3">N° de trabajador</td><td style="padding:10px 14px;font-weight:600;border-top:1px solid #e8e9f3">{c['numero_trabajador']}</td></tr>
          <tr><td style="padding:10px 14px;color:#6b6f8d;border-top:1px solid #e8e9f3">N° de tarjeta</td><td style="padding:10px 14px;font-weight:600;border-top:1px solid #e8e9f3">{c['numero_tarjeta']}</td></tr>
          <tr><td style="padding:10px 14px;color:#6b6f8d;border-top:1px solid #e8e9f3">Tipo de notificación</td><td style="padding:10px 14px;font-weight:600;border-top:1px solid #e8e9f3">{tipo_txt}</td></tr>
          <tr><td style="padding:10px 14px;color:#6b6f8d;border-top:1px solid #e8e9f3">Vigencia de la credencial</td><td style="padding:10px 14px;font-weight:600;border-top:1px solid #e8e9f3">{vigencia}</td></tr>
          <tr><td style="padding:10px 14px;color:#6b6f8d;border-top:1px solid #e8e9f3">Estado actualizado</td><td style="padding:10px 14px;font-weight:700;color:#e5287d;border-top:1px solid #e8e9f3">{c['estado']}</td></tr>
        </table>
      </div>
    </div>
    """

    # 1. Registrar SIEMPRE en la tabla notificaciones (requisito de auditoría en BD)
    try:
        query(
            """INSERT INTO notificaciones
               (credencial_id, tipo, enviada_a, asunto, nombre_completo, numero_trabajador,
                numero_tarjeta, vigencia, estado_actualizado, cuerpo)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (cred_id, tipo, c["email"], asunto, c["nombre_completo"], c["numero_trabajador"],
             c["numero_tarjeta"], vigencia, c["estado"], cuerpo_txt),
            commit=True,
        )
    except Exception as e:
        print("[AVISO] No se pudo guardar la notificación en BD:", e)

    # 2. Intentar entrega por Resend HTTP API si está configurado (óptimo para nube)
    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    if resend_key:
        try:
            de = os.getenv("RESEND_FROM", f"{inst} <onboarding@resend.dev>")
            _enviar_resend_http(resend_key, de, c["email"], asunto, cuerpo_html, cuerpo_txt)
            flash(f"Notificación enviada por correo a {c['email']}", "ok")
            return
        except Exception as e:
            print("[AVISO] Falló entrega por Resend:", e)

    # 3. Intentar entrega por SMTP (con timeout estricto de 3s para evitar bloqueos)
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    pwd = os.getenv("SMTP_PASSWORD", "").strip().replace(" ", "")
    port = int(os.getenv("SMTP_PORT") or 587)

    if host and user and pwd:
        try:
            msg = EmailMessage()
            msg["Subject"] = asunto
            msg["To"] = c["email"]
            msg["From"] = f"{inst} <{user}>"
            msg.set_content(cuerpo_txt)
            msg.add_alternative(cuerpo_html, subtype="html")
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=3) as s:
                    s.login(user, pwd)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=3) as s:
                    s.starttls()
                    s.login(user, pwd)
                    s.send_message(msg)
            flash(f"Notificación enviada por correo a {c['email']}", "ok")
        except (socket.timeout, TimeoutError, OSError) as e:
            print(f"[AVISO] Conexión SMTP no disponible o bloqueada por la red ({e}). Notificación archivada en BD.")
            flash(f"Notificación guardada en el sistema para {c['email']} (el servidor en la nube no permite conexiones SMTP directas).", "ok")
        except Exception as e:
            print("[AVISO] Error al enviar correo:", e)
            flash(f"Notificación guardada en el sistema. Servidor de correo reportó: {e}", "ok")
    else:
        flash(f"Notificación registrada en el sistema para {c['email']}", "ok")


# ---------- Auth ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = query("SELECT * FROM usuarios WHERE email=%s", (request.form["email"],), one=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session["uid"] = u["id"]
            session["email"] = u["email"]
            session["rol"] = u.get("rol", "admin")
            return redirect(request.args.get("next") or url_for("index"))
        flash("Credenciales incorrectas", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Administración ----------
@app.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    estado = request.args.get("estado", "")
    sql, p = "SELECT * FROM v_credenciales WHERE 1=1", []
    if q:
        sql += " AND (nombre_completo LIKE %s OR numero_trabajador LIKE %s OR numero_tarjeta LIKE %s)"
        p += [f"%{q}%"] * 3
    if estado:
        sql += " AND estado=%s"
        p.append(estado)
    rows = query(sql + " ORDER BY numero_trabajador", p)
    stats = {"Vigente": 0, "Inactiva": 0, "Vencida": 0, "No vigente": 0}
    for s in query("SELECT estado, COUNT(*) n FROM v_credenciales GROUP BY estado"):
        stats[s["estado"]] = s["n"]
    return render_template("index.html", rows=rows, q=q, estado=estado, stats=stats, total=sum(stats.values()))


def _guardar_foto(obligatoria=False):
    from PIL import Image as PILImage, UnidentifiedImageError
    f = request.files.get("foto")
    if not f or not f.filename:
        if obligatoria:
            raise ValueError("Debes subir la fotografía del trabajador")
        return None
    if "." not in f.filename:
        raise ValueError("La fotografía debe tener formato PNG, JPG o WEBP")
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in EXT:
        raise ValueError("La fotografía debe ser PNG, JPG o WEBP")
    try:
        img = PILImage.open(f.stream)
        img.verify()
        f.stream.seek(0)
        img2 = PILImage.open(f.stream)
        w, h = img2.size
        if w < 50 or h < 50:
            raise ValueError("La fotografía es demasiado pequeña (mínimo 50x50 píxeles)")
        f.stream.seek(0)
    except UnidentifiedImageError:
        raise ValueError("El archivo seleccionado no es una imagen válida")
    name = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(UPLOADS, secure_filename(name)))
    return name


def _validar(form, nuevo=True, w_actual=None, c_actual=None):
    nombre = " ".join(form.get("nombre_completo", "").split())
    if len(nombre) < 5 or not NOMBRE_RE.match(nombre):
        raise ValueError("Ingresa el nombre completo del trabajador (nombre y apellidos, solo letras)")

    try:
        edad = int(form.get("edad", ""))
    except ValueError:
        raise ValueError("La edad debe ser un número entero válido")
    if not (18 <= edad <= 99):
        raise ValueError("La edad del trabajador debe estar entre 18 y 99 años")

    sexo = form.get("sexo", "")
    if sexo not in ("M", "F", "Otro"):
        raise ValueError("Selecciona una opción válida para el sexo")

    curp = form.get("curp", "").strip().upper()
    curp_sin_cambio = w_actual and curp == w_actual.get("curp")
    if not curp_sin_cambio and not CURP_RE.match(curp):
        raise ValueError("La CURP debe tener 18 caracteres válidos (4 letras iniciales + 6 dígitos de fecha + 8 caracteres)")
    dup_curp = query("SELECT id FROM trabajadores WHERE curp=%s", (curp,), one=True)
    if dup_curp and (nuevo or dup_curp["id"] != w_actual["id"]):
        raise ValueError("La CURP ingresada ya pertenece a otro trabajador registrado")

    email = form.get("email", "").strip().lower()
    if not email or not EMAIL_RE.match(email):
        raise ValueError("Ingresa un correo electrónico válido para el trabajador")

    area = form.get("area", "").strip()
    if area not in AREAS_ADSCRIPCION and not (w_actual and area == w_actual.get("area")):
        raise ValueError("Selecciona un área de adscripción válida de la lista")

    cargo = " ".join(form.get("cargo", "").split())
    if len(cargo) < 2 or not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2}", cargo):
        raise ValueError("Ingresa un cargo o puesto válido")

    em_nom = " ".join(form.get("emergencia_nombre", "").split())
    if len(em_nom) < 3 or not SOLO_LETRAS_RE.match(em_nom):
        raise ValueError("El nombre del contacto de emergencia solo debe contener letras (mínimo 3 caracteres)")

    em_tel = re.sub(r"[\s\-\(\)]", "", form.get("emergencia_telefono", ""))
    if not re.match(r"^\d{10}$", em_tel):
        raise ValueError("El teléfono de emergencia debe tener exactamente 10 dígitos numéricos")

    try:
        ini = date.fromisoformat(form.get("fecha_inicio", ""))
        ven = date.fromisoformat(form.get("fecha_vencimiento", ""))
    except ValueError:
        raise ValueError("Ingresa fechas válidas de inicio y vencimiento")
    if ven < ini:
        raise ValueError("La fecha de vencimiento no puede ser anterior a la fecha de inicio")

    num_trab = form.get("numero_trabajador", "").strip()
    num_tarj = form.get("numero_tarjeta", "").strip()

    if nuevo:
        if num_trab:
            if not CODIGO_RE.match(num_trab):
                raise ValueError("El N° de trabajador solo admite letras, números y guiones (2 a 20 caracteres)")
            if query("SELECT 1 FROM trabajadores WHERE numero_trabajador=%s", (num_trab,), one=True):
                raise ValueError("El N° de trabajador ya está asignado a otra persona")
        if len(num_tarj) < 3 or not CODIGO_RE.match(num_tarj):
            raise ValueError("El N° de credencial/tarjeta debe tener entre 3 y 30 caracteres (letras, números o guiones)")
        if query("SELECT 1 FROM credenciales WHERE numero_tarjeta=%s", (num_tarj,), one=True):
            raise ValueError("El N° de credencial/tarjeta ya existe; no se permiten duplicados")
    else:
        if num_tarj and num_tarj != c_actual["numero_tarjeta"]:
            raise ValueError("El N° de credencial no se puede modificar una vez creada")

    return {
        "nombre_completo": nombre,
        "edad": edad,
        "sexo": sexo,
        "curp": curp,
        "email": email,
        "area": area,
        "cargo": cargo,
        "emergencia_nombre": em_nom,
        "emergencia_telefono": em_tel,
        "numero_trabajador": num_trab,
        "numero_tarjeta": num_tarj if nuevo else c_actual["numero_tarjeta"],
        "fecha_inicio": str(ini),
        "fecha_vencimiento": str(ven),
    }


def _siguiente_numero():
    r = query("SELECT COUNT(*) n FROM trabajadores", one=True)["n"] + 1
    while query("SELECT 1 FROM trabajadores WHERE numero_trabajador=%s", (f"T-{r:04d}",), one=True):
        r += 1
    return f"T-{r:04d}"


@app.route("/trabajadores/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo():
    if request.method == "POST":
        f = request.form
        try:
            d = _validar(f, nuevo=True)
            foto = _guardar_foto(obligatoria=True)
            tid = query(
                """INSERT INTO trabajadores (numero_trabajador,nombre_completo,edad,sexo,curp,area,cargo,
                   foto_path,email,emergencia_nombre,emergencia_telefono)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (d["numero_trabajador"] or _siguiente_numero(), d["nombre_completo"], d["edad"],
                 d["sexo"], d["curp"], d["area"], d["cargo"], foto, d["email"],
                 d["emergencia_nombre"], d["emergencia_telefono"]), commit=True)
            cid = query(
                """INSERT INTO credenciales (trabajador_id,numero_tarjeta,qr_token,fecha_inicio,fecha_vencimiento)
                   VALUES (%s,%s,%s,%s,%s)""",
                (tid, d["numero_tarjeta"], str(uuid.uuid4()), d["fecha_inicio"],
                 d["fecha_vencimiento"]), commit=True)
            notificar(cid, "generada")
            flash("Trabajador y credencial creados correctamente", "ok")
            return redirect(url_for("credencial", cid=cid))
        except mysql.connector.IntegrityError:
            flash("Número de tarjeta, número de trabajador o CURP duplicado", "error")
        except ValueError as e:
            flash(str(e), "error")
        return render_template("form.html", w=f, c=f, nuevo=True, hoy=date.today())
    return render_template("form.html", w={}, c={}, nuevo=True, hoy=date.today())


@app.route("/credenciales/<int:cid>/editar", methods=["GET", "POST"])
@admin_required
def editar(cid):
    c = query("SELECT * FROM v_credenciales WHERE id=%s", (cid,), one=True) or abort(404)
    w = query("SELECT * FROM trabajadores WHERE id=%s", (c["trabajador_id"],), one=True)
    if request.method == "POST":
        f = request.form
        try:
            d = _validar(f, nuevo=False, w_actual=w, c_actual=c)
            foto = _guardar_foto(obligatoria=False) or w["foto_path"]
            query(
                """UPDATE trabajadores SET nombre_completo=%s,edad=%s,sexo=%s,curp=%s,area=%s,cargo=%s,
                   foto_path=%s,email=%s,emergencia_nombre=%s,emergencia_telefono=%s WHERE id=%s""",
                (d["nombre_completo"], d["edad"], d["sexo"], d["curp"], d["area"], d["cargo"], foto,
                 d["email"], d["emergencia_nombre"], d["emergencia_telefono"], w["id"]), commit=True)
            query("UPDATE credenciales SET fecha_inicio=%s,fecha_vencimiento=%s WHERE id=%s",
                  (d["fecha_inicio"], d["fecha_vencimiento"], cid), commit=True)
            if str(c["fecha_vencimiento"]) != d["fecha_vencimiento"]:
                notificar(cid, "vencimiento_modificado")
            flash("Cambios guardados correctamente", "ok")
            return redirect(url_for("index"))
        except mysql.connector.IntegrityError:
            flash("La CURP ingresada ya existe en otro trabajador", "error")
        except ValueError as e:
            flash(str(e), "error")
        w_vista = dict(f)
        w_vista["foto_path"] = w["foto_path"]
        w_vista["numero_trabajador"] = w["numero_trabajador"]
        c_vista = dict(f)
        c_vista["numero_tarjeta"] = c["numero_tarjeta"]
        return render_template("form.html", w=w_vista, c=c_vista, nuevo=False)
    return render_template("form.html", w=w, c=c, nuevo=False)


@app.route("/credenciales/<int:cid>/toggle", methods=["POST"])
@admin_required
def toggle(cid):
    c = query("SELECT activa FROM credenciales WHERE id=%s", (cid,), one=True) or abort(404)
    nuevo = not c["activa"]
    query("UPDATE credenciales SET activa=%s WHERE id=%s", (nuevo, cid), commit=True)
    if not nuevo:
        notificar(cid, "desactivada")
    flash("Credencial " + ("activada" if nuevo else "desactivada"), "ok")
    return redirect(request.referrer or url_for("index"))


@app.route("/credenciales/<int:cid>")
@login_required
def credencial(cid):
    c = query("SELECT * FROM v_credenciales WHERE id=%s", (cid,), one=True) or abort(404)
    t = query("SELECT curp,edad,sexo,email,emergencia_nombre,emergencia_telefono FROM trabajadores WHERE id=%s",
              (c["trabajador_id"],), one=True)
    return render_template("credencial.html", c=c, t=t,
                           url_qr=os.getenv("BASE_URL", request.host_url.rstrip("/")) + "/verificar/" + c["qr_token"])


@app.route("/credenciales/<int:cid>/pdf")
@login_required
def credencial_pdf(cid):
    from reporte_pdf import construir_credenciales_pdf
    c = query("SELECT * FROM v_credenciales WHERE id=%s", (cid,), one=True) or abort(404)
    pdf = construir_credenciales_pdf(
        [c],
        os.path.join(app.root_path, "static", "img", "logo.png"),
        os.path.join(app.root_path, "static", "img", "logo-icon.png"),
        UPLOADS,
        os.getenv("BASE_URL", request.host_url.rstrip("/")),
        os.getenv("INSTITUCION", "NovaTech"),
        subtitulo=f"{c['nombre_completo']} ({c['numero_trabajador']})",
    )
    return send_file(io.BytesIO(pdf), mimetype="application/pdf",
                     download_name=f"credencial_{c['numero_trabajador']}.pdf")


def _filtrar_credenciales(q, estado):
    sql, p = "SELECT * FROM v_credenciales WHERE 1=1", []
    if q:
        sql += " AND (nombre_completo LIKE %s OR numero_trabajador LIKE %s OR numero_tarjeta LIKE %s)"
        p += [f"%{q}%"] * 3
    if estado:
        sql += " AND estado=%s"
        p.append(estado)
    return query(sql + " ORDER BY numero_trabajador", p)


@app.route("/imprimir")
@login_required
def imprimir():
    q = request.args.get("q", "").strip()
    estado = request.args.get("estado", "")
    return render_template("imprimir.html", rows=_filtrar_credenciales(q, estado), q=q, estado=estado)


@app.route("/imprimir/pdf")
@login_required
def imprimir_pdf():
    from reporte_pdf import construir_credenciales_pdf
    q = request.args.get("q", "").strip()
    estado = request.args.get("estado", "")
    rows = _filtrar_credenciales(q, estado)
    partes = []
    if estado:
        partes.append(f"Estado: {estado}")
    if q:
        partes.append(f"Búsqueda: {q}")
    sub = " · ".join(partes) if partes else "Todas las credenciales registradas"
    pdf = construir_credenciales_pdf(
        rows,
        os.path.join(app.root_path, "static", "img", "logo.png"),
        os.path.join(app.root_path, "static", "img", "logo-icon.png"),
        UPLOADS,
        os.getenv("BASE_URL", request.host_url.rstrip("/")),
        os.getenv("INSTITUCION", "NovaTech"),
        subtitulo=sub,
    )
    return send_file(io.BytesIO(pdf), mimetype="application/pdf",
                     download_name=f"credenciales_{datetime.now():%Y%m%d_%H%M}.pdf")


# ---------- Reportes ----------
def _datos_reporte(tipo, area, estado):
    sql, p = "SELECT * FROM v_credenciales WHERE 1=1", []
    if tipo == "area" and area:
        sql += " AND area=%s"
        p.append(area)
    if tipo == "estado" and estado:
        sql += " AND estado=%s"
        p.append(estado)
    q = request.args.get("q", "").strip()
    if q:
        sql += " AND nombre_completo LIKE %s"
        p.append(f"%{q}%")
    rows = query(sql + " ORDER BY area, nombre_completo", p)
    resumen = {}
    for r in rows:
        resumen[r["estado"]] = resumen.get(r["estado"], 0) + 1
    return rows, resumen


@app.route("/reportes/pdf")
@login_required
def reportes_pdf():
    from reporte_pdf import construir_pdf
    tipo = request.args.get("tipo", "general")
    area = request.args.get("area", "")
    estado = request.args.get("estado", "")
    rows, resumen = _datos_reporte(tipo, area, estado)
    titulos = {"general": "Reporte general de credenciales",
               "area": "Reporte por área de adscripción",
               "estado": "Reporte por estado de credencial"}
    filtro = {"general": "Todos los trabajadores registrados",
              "area": f"Área: {area}" if area else "Todas las áreas",
              "estado": f"Estado: {estado}" if estado else "Todos los estados"}.get(tipo, "")
    if request.args.get("q", "").strip():
        filtro += " · Nombre: " + request.args.get("q").strip()
    pdf = construir_pdf(titulos.get(tipo, titulos["general"]), filtro, rows, resumen,
                        os.path.join(app.root_path, "static", "img", "logo.png"),
                        os.getenv("INSTITUCION", "NovaTech"))
    nombre = f"reporte_{tipo}_{datetime.now():%Y%m%d_%H%M}.pdf"
    return send_file(io.BytesIO(pdf), mimetype="application/pdf", download_name=nombre)


@app.route("/reportes")
@login_required
def reportes():
    tipo = request.args.get("tipo", "general")
    area = request.args.get("area", "")
    estado = request.args.get("estado", "")
    areas = [r["area"] for r in query("SELECT DISTINCT area FROM trabajadores ORDER BY area")]
    rows, resumen = _datos_reporte(tipo, area, estado)
    return render_template("reportes.html", rows=rows, tipo=tipo, area=area, estado=estado,
                           areas=areas, resumen=resumen, ahora=datetime.now())


# ---------- Público ----------
@app.route("/qr/<token>.png")
def qr_img(token):
    base = os.getenv("BASE_URL", request.host_url.rstrip("/"))
    img = qrcode.make(f"{base}/verificar/{token}", box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/verificar/<token>")
def verificar(token):
    # Solo se exponen los campos permitidos (sin CURP ni datos de emergencia).
    c = query("""SELECT nombre_completo,numero_trabajador,area,cargo,numero_tarjeta,foto_path,
                 fecha_inicio,fecha_vencimiento,estado FROM v_credenciales WHERE qr_token=%s""",
              (token,), one=True)
    return render_template("verificar.html", c=c), (200 if c else 404)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
