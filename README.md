# Sistema de credencialización web (Reto 3)

Flask + MySQL + HTML/CSS/JS responsivo.

## Instalación
1. `pip install -r requirements.txt`
2. Crea un archivo `.env` con DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, SECRET_KEY, INSTITUCION, BASE_URL (y SMTP_* opcional).
3. `python init_db.py` (crea la BD, un admin `admin@empresa.com` / `Admin123!` y 10 trabajadores de prueba)
4. `python app.py` y abre http://localhost:5000

Para que el QR funcione desde celulares, pon la IP de tu PC en `BASE_URL`.
