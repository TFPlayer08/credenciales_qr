"""Crea (o actualiza) un usuario.  Uso: python crear_admin.py correo@ejemplo.com contraseña [admin|consulta]"""
import sys
from werkzeug.security import generate_password_hash
from db import query

if len(sys.argv) < 3:
    sys.exit("Uso: python crear_admin.py correo contraseña [admin|consulta]")
email, pwd = sys.argv[1], sys.argv[2]
rol = sys.argv[3] if len(sys.argv) > 3 else "admin"
query("""INSERT INTO usuarios (email, password_hash, rol) VALUES (%s,%s,%s)
         ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), rol=VALUES(rol)""",
      (email, generate_password_hash(pwd), rol), commit=True)
print(f"Usuario listo ({rol}):", email)
