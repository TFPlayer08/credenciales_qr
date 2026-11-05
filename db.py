import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_conn(with_db=True):
    host = os.getenv("DB_HOST") or os.getenv("MYSQLHOST") or "localhost"
    user = os.getenv("DB_USER") or os.getenv("MYSQLUSER") or "root"
    password = os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD") or ""
    port = int(os.getenv("DB_PORT") or os.getenv("MYSQLPORT") or 3306)

    cfg = dict(
        host=host,
        user=user,
        password=password,
        port=port,
    )
    if with_db:
        cfg["database"] = os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE") or "credenciales_db"
    return mysql.connector.connect(**cfg)


def query(sql, params=(), one=False, commit=False):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        if commit:
            conn.commit()
            return cur.lastrowid
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()
