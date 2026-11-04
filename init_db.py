"""Crea la base de datos, las tablas, el admin y 10 trabajadores de prueba."""
import uuid
from datetime import date, timedelta
from werkzeug.security import generate_password_hash
from db import get_conn

conn = get_conn(with_db=False)
cur = conn.cursor()
with open("database/schema.sql", encoding="utf-8") as f:
    sql = "\n".join(l for l in f if not l.strip().startswith("--"))
for stmt in sql.split(";"):
    if stmt.strip():
        cur.execute(stmt)
conn.commit()
cur.execute("USE credenciales_db")

cur.execute("INSERT IGNORE INTO usuarios (email, password_hash) VALUES (%s,%s)",
            ("admin@empresa.com", generate_password_hash("Admin123!")))

cur.execute("SELECT COUNT(*) FROM trabajadores")
if cur.fetchone()[0] == 0:
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
        # Variedad de estados para probar: 8 vigentes, 1 vencida, 1 inactiva
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
conn.close()
print("Base de datos lista. Admin: admin@empresa.com / Admin123!")
