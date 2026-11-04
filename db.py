import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_conn(with_db=True):
    cfg = dict(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    if with_db:
        cfg["database"] = os.getenv("DB_NAME", "credenciales_db")
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
