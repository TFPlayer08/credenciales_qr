import io
import os
import re
import smtplib
import uuid
from datetime import date
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
EXT = {"png", "jpg", "jpeg", "webp"}
CURP_RE = re.compile(r"^[A-Z0-9]{18}$")


@app.context_processor
def inject():
    return {"INSTITUCION": os.getenv("INSTITUCION", "Institución")}


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "uid" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


# ---------- Correo / notificaciones ----------
def notificar(cred_id, tipo):
    c = query("SELECT * FROM v_credenciales WHERE id=%s", (cred_id,), one=True)
    if not c:
        return
    etiquetas = {"generada": "Nueva credencial generada",
                 "desactivada": "Credencial desactivada",
                 "vencimiento_modificado": "Fecha de vencimiento modificada"}
    cuerpo = (f"Nombre: {c['nombre_completo']}\nNúmero de trabajador: {c['numero_trabajador']}\n"
              f"Número de tarjeta: {c['numero_tarjeta']}\nTipo de notificación: {etiquetas[tipo]}\n"
              f"Vigencia: {c['fecha_inicio']} al {c['fecha_vencimiento']}\nEstado actualizado: {c['estado']}\n")
    host = os.getenv("SMTP_HOST")
    if c["email"] and host:
        try:
            msg = EmailMessage()
            msg["Subject"], msg["To"] = etiquetas[tipo], c["email"]
            msg["From"] = os.getenv("SMTP_USER")
            msg.set_content(cuerpo)
            with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", 587))) as s:
                s.starttls()
                s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                s.send_message(msg)
        except Exception as e:
            print("Error enviando correo:", e)
    else:
        print(f"[CORREO SIMULADO a {c['email']}]\n{cuerpo}")
    query("INSERT INTO notificaciones (credencial_id,tipo,enviada_a) VALUES (%s,%s,%s)",
          (cred_id, tipo, c["email"]), commit=True)


# ---------- Auth ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = query("SELECT * FROM usuarios WHERE email=%s", (request.form["email"],), one=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session["uid"] = u["id"]
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


def _guardar_foto():
    f = request.files.get("foto")
    if f and f.filename:
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in EXT:
            raise ValueError("La foto debe ser PNG, JPG o WEBP")
        name = f"{uuid.uuid4().hex}.{ext}"
        f.save(os.path.join(UPLOADS, secure_filename(name)))
        return name
    return None


def _validar(form):
    curp = form["curp"].strip().upper()
    if not CURP_RE.match(curp):
        raise ValueError("La CURP debe tener 18 caracteres alfanuméricos")
    if form["fecha_vencimiento"] < form["fecha_inicio"]:
        raise ValueError("El vencimiento no puede ser anterior al inicio")
    return curp


def _siguiente_numero():
    r = query("SELECT COUNT(*) n FROM trabajadores", one=True)["n"] + 1
    while query("SELECT 1 FROM trabajadores WHERE numero_trabajador=%s", (f"T-{r:04d}",), one=True):
        r += 1
    return f"T-{r:04d}"


@app.route("/trabajadores/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    if request.method == "POST":
        f = request.form
        try:
            curp = _validar(f)
            foto = _guardar_foto()
            tid = query(
                """INSERT INTO trabajadores (numero_trabajador,nombre_completo,edad,sexo,curp,area,cargo,
                   foto_path,email,emergencia_nombre,emergencia_telefono)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (f["numero_trabajador"].strip() or _siguiente_numero(), f["nombre_completo"], f["edad"],
                 f["sexo"], curp, f["area"], f["cargo"], foto, f["email"] or None,
                 f["emergencia_nombre"], f["emergencia_telefono"]), commit=True)
            cid = query(
                """INSERT INTO credenciales (trabajador_id,numero_tarjeta,qr_token,fecha_inicio,fecha_vencimiento)
                   VALUES (%s,%s,%s,%s,%s)""",
                (tid, f["numero_tarjeta"].strip(), str(uuid.uuid4()), f["fecha_inicio"],
                 f["fecha_vencimiento"]), commit=True)
            notificar(cid, "generada")
            flash("Trabajador y credencial creados", "ok")
            return redirect(url_for("credencial", cid=cid))
        except mysql.connector.IntegrityError:
            flash("Número de tarjeta, número de trabajador o CURP duplicado", "error")
        except ValueError as e:
            flash(str(e), "error")
        return render_template("form.html", w=f, c=f, nuevo=True, hoy=date.today())
    return render_template("form.html", w={}, c={}, nuevo=True, hoy=date.today())


@app.route("/credenciales/<int:cid>/editar", methods=["GET", "POST"])
@login_required
def editar(cid):
    c = query("SELECT * FROM v_credenciales WHERE id=%s", (cid,), one=True) or abort(404)
    w = query("SELECT * FROM trabajadores WHERE id=%s", (c["trabajador_id"],), one=True)
    if request.method == "POST":
        f = request.form
        try:
            curp = _validar(f)
            foto = _guardar_foto() or w["foto_path"]
            query(
                """UPDATE trabajadores SET nombre_completo=%s,edad=%s,sexo=%s,curp=%s,area=%s,cargo=%s,
                   foto_path=%s,email=%s,emergencia_nombre=%s,emergencia_telefono=%s WHERE id=%s""",
                (f["nombre_completo"], f["edad"], f["sexo"], curp, f["area"], f["cargo"], foto,
                 f["email"] or None, f["emergencia_nombre"], f["emergencia_telefono"], w["id"]), commit=True)
            query("UPDATE credenciales SET numero_tarjeta=%s,fecha_inicio=%s,fecha_vencimiento=%s WHERE id=%s",
                  (f["numero_tarjeta"].strip(), f["fecha_inicio"], f["fecha_vencimiento"], cid), commit=True)
            if str(c["fecha_vencimiento"]) != f["fecha_vencimiento"]:
                notificar(cid, "vencimiento_modificado")
            flash("Cambios guardados", "ok")
            return redirect(url_for("index"))
        except mysql.connector.IntegrityError:
            flash("Número de tarjeta o CURP duplicado", "error")
        except ValueError as e:
            flash(str(e), "error")
    return render_template("form.html", w=w, c=c, nuevo=False)


@app.route("/credenciales/<int:cid>/toggle", methods=["POST"])
@login_required
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
    t = query("SELECT curp,edad,sexo,emergencia_nombre,emergencia_telefono FROM trabajadores WHERE id=%s",
              (c["trabajador_id"],), one=True)
    return render_template("credencial.html", c=c, t=t,
                           url_qr=os.getenv("BASE_URL", request.host_url.rstrip("/")) + "/verificar/" + c["qr_token"])


@app.route("/imprimir")
@login_required
def imprimir():
    return render_template("imprimir.html", rows=query("SELECT * FROM v_credenciales ORDER BY numero_trabajador"))


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
