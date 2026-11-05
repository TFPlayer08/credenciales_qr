"""Crea la base de datos, las tablas, el admin y 10 trabajadores de prueba."""
import os
import uuid
from datetime import date, timedelta
from werkzeug.security import generate_password_hash
from db import get_conn


def inicializar_si_es_necesario():
    try:
        conn = get_conn(with_db=True)
    except Exception:
        conn = get_conn(with_db=False)
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS credenciales_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        cur.close()
        conn.close()
        conn = get_conn(with_db=True)

    cur = conn.cursor()
    cur.execute("SHOW TABLES LIKE 'trabajadores'")
    hay_tablas = cur.fetchone() is not None

    if not hay_tablas:
        with open("database/schema.sql", encoding="utf-8") as f:
            sql = "\n".join(l for l in f if not l.strip().startswith("--"))
        for stmt in sql.split(";"):
            s = stmt.strip()
            if s and not s.upper().startswith("CREATE DATABASE") and not s.upper().startswith("USE "):
                cur.execute(s)
        conn.commit()

        cur.execute("INSERT IGNORE INTO usuarios (email, password_hash, rol) VALUES (%s,%s,'admin')",
                    ("admin@empresa.com", generate_password_hash("Admin123!")))
        cur.execute("INSERT IGNORE INTO usuarios (email, password_hash, rol) VALUES (%s,%s,'consulta')",
                    ("consulta@novatech.com", generate_password_hash("Consulta123!")))

        datos = [
            ("Ana López Martínez", 29, "F", "Recursos Humanos", "Analista"),
            ("Carlos Ramírez Soto", 41, "M", "Sistemas", "Desarrollador"),
            ("María Hernández Cruz", 35, "F", "Finanzas", "Contadora"),
            ("Luis Torres Vega", 52, "M", "Operaciones", "Supervisor"),
            ("Sofía Morales Díaz", 26, "F", "Marketing", "Diseñadora"),
            ("Jorge Castillo Ruiz", 38, "M", "Sistemas", "Administrador de redes"),
            ("Elena Ortiz Pérez", 45, "F", "Dirección", "Coordinadora"),
            ("Miguel Flores Luna", 31, "M", "Logística", "Almacenista"),
            ("Paola Mendoza Rey", 33, "F", "Recursos Humanos", "Reclutadora"),
            ("Diego Navarro Gil", 24, "M", "Soporte", "Técnico"),
        ]
        hoy = date.today()
        for i, (nom, edad, sexo, area, cargo) in enumerate(datos, 1):
            cur.execute(
                """INSERT INTO trabajadores (numero_trabajador,nombre_completo,edad,sexo,curp,area,cargo,
                   email,emergencia_nombre,emergencia_telefono) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (f"T-{i:04d}", nom, edad, sexo, f"DEMO{i:02d}HDFXXX{i:02d}A1"[:18].ljust(18, "0"), area, cargo,
                 f"trabajador{i}@empresa.com", "Contacto Demo", "5512345678"))
            tid = cur.lastrowid
            ini, ven, act = hoy - timedelta(days=30), hoy + timedelta(days=365), True
            if i == 9:
                ini, ven = hoy - timedelta(days=400), hoy - timedelta(days=10)
            if i == 10:
                act = False
            cur.execute(
                """INSERT INTO credenciales (trabajador_id,numero_tarjeta,qr_token,fecha_inicio,fecha_vencimiento,activa)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (tid, f"TJ-{1000 + i}", str(uuid.uuid4()), ini, ven, act))
        conn.commit()
        print("Base de datos auto-inicializada en Railway con 10 trabajadores y usuarios demo.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    inicializar_si_es_necesario()
    print("Base de datos lista. Admin: admin@empresa.com / Admin123!")
