# 🪪 NovaTech · Sistema de Credencialización Web con Código QR (Reto 3)

Sistema web responsivo desarrollado con **Python (Flask)** y base de datos relacional **SQL (MySQL)** para administrar trabajadores, generar credenciales digitales e imprimibles en formato horizontal (anverso y reverso) con código QR único, verificar su autenticidad y vigencia en tiempo real desde dispositivos móviles, emitir reportes en PDF y enviar notificaciones automáticas por correo electrónico.

🌐 **Demo en vivo (Producción 24/7 en Railway):** [https://web-production-a9c0c.up.railway.app](https://web-production-a9c0c.up.railway.app)
- **Administrador:** `admin@empresa.com` / `Admin123!`
- **Solo consulta:** `consulta@novatech.com` / `Consulta123!`

---

## 🛠️ Tecnologías utilizadas
- **Backend:** Python 3.10+ con **Flask** y **Gunicorn** (producción)
- **Base de datos SQL:** **MySQL 8.0** / MariaDB (`mysql-connector-python`) con esquema relacional en [`database/schema.sql`](database/schema.sql)
- **Frontend:** HTML5, CSS3 responsivo (adaptable a PC, tablet y celular) y JavaScript
- **Códigos QR e imágenes:** `qrcode` y `Pillow` (validación real de imagen y dimensiones)
- **Generación de PDFs:** `reportlab` (reportes ejecutivos y credenciales vectoriales listas para imprimir)
- **Notificaciones por correo:** Híbrido **HTTPS Webhook (Google Apps Script)** para entornos cloud y **SMTP TLS/SSL (`smtplib`)** para entorno local, con auditoría persistente en SQL (`notificaciones`)

---

## ✨ Funcionalidades principales

1. **Administración de trabajadores y credenciales:**
   - Registro, consulta, búsqueda (por nombre, N° de trabajador o N° de tarjeta), edición y filtro por estado.
   - Asignación automática o manual de número de trabajador único (`T-0001`, `T-0002`, etc.) y validación de no duplicidad en N° de tarjeta y CURP.
   - Fotografía individual por trabajador (con recorte automático o avatar con inicial).
   - Activación y desactivación de credenciales **sin eliminar** el registro del trabajador de la base de datos.

2. **Control automático de vigencias y estados:**
   - Calculado dinámicamente en MySQL mediante la vista `v_credenciales`:
     - **Vigente:** credencial activa y fecha actual dentro del periodo `fecha_inicio` – `fecha_vencimiento`.
     - **Inactiva:** credencial desactivada por el administrador.
     - **Vencida:** fecha actual posterior a `fecha_vencimiento`.
     - **No vigente:** fecha actual anterior a `fecha_inicio`.

3. **Credenciales digitales y en PDF (formato horizontal, anverso y reverso):**
   - **Anverso:** logotipo y nombre institucional (**NovaTech**), fotografía, nombre completo, N° de trabajador, cargo y área de adscripción.
   - **Reverso:** código QR único, N° de tarjeta, fecha de vencimiento e información institucional.
   - Descarga e impresión directa en **PDF tamaño A4** (individual o por lote filtrado).

4. **Verificación pública mediante escaneo de QR (`/verificar/<token>`):**
   - Al escanear el QR con la cámara de cualquier teléfono celular (sin instalar ninguna app), muestra el estado de validez (**Vigente**, **Inactiva**, **Vencida** o **No vigente**) y los datos públicos del trabajador.
   - Si el código QR no existe en la base de datos, muestra **`✖ Credencial no encontrada`** (HTTP 404).
   - **Privacidad y seguridad:** oculta la CURP y los datos de contacto de emergencia en la consulta pública.
   - Al modificar datos administrativos del trabajador, la página del QR muestra la información actualizada al instante sin necesidad de regenerar el QR.

5. **Control de acceso y roles de usuario (`admin` vs `consulta`):**
   - Acceso protegido mediante inicio de sesión con contraseñas cifradas (`werkzeug.security`).
   - **Rol `admin`:** acceso total para registrar, editar y activar/desactivar credenciales.
   - **Rol `consulta` (solo lectura):** puede consultar trabajadores, credenciales y reportes, pero el servidor bloquea cualquier intento de crear, editar o desactivar registros.

6. **Reportes en pantalla y en PDF (`/reportes` y `/reportes/pdf`):**
   - **Reporte general de credenciales**
   - **Reporte por área de adscripción**
   - **Reporte por estado de credencial** (*Vigentes*, *Inactivas*, *Vencidas*, *No vigentes*) y búsqueda por nombre.

7. **Notificaciones automáticas por correo electrónico:**
   - Envía automáticamente un correo al email personal registrado en la ficha del trabajador cuando:
     1. Se genera una nueva credencial.
     2. El administrador desactiva la credencial.
     3. Se modifica su fecha de vencimiento.
   - Incluye: **Nombre del trabajador**, **N° de trabajador**, **N° de tarjeta**, **Tipo de notificación**, **Vigencia de la credencial** y **Estado actualizado**.

---

## 🚀 Guía de instalación paso a paso (desde cero)

### 1. Requisitos previos
- Tener instalado **Python 3.10 o superior** y **MySQL Server 8.0** (o MariaDB) corriendo localmente.

### 2. Clonar el repositorio e instalar dependencias
```bash
git clone https://gitlab.com/DorianAlejandro/credenciales_qr.git
cd credenciales_qr
pip install -r requirements.txt
```

### 3. Configurar las variables de entorno (opcional o mediante `.env`)
Por seguridad, el repositorio **no incluye archivos `.env` ni contraseñas**.

El sistema funciona creando un archivo llamado **`.env`** en la raíz del proyecto con los datos de tu propio entorno local:

```ini
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=TU_PASSWORD_DE_MYSQL
DB_NAME=credenciales_db
SECRET_KEY=clave-secreta-local
INSTITUCION=NovaTech
BASE_URL=http://localhost:5000

# Opcional: configuración SMTP para envío real de correos
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
```

> **Nota si tu MySQL local no tiene contraseña:** si tu usuario `root` de MySQL en `localhost` no usa contraseña, ni siquiera necesitas crear el archivo `.env`; el sistema usará por defecto `host=localhost`, `user=root`, `password=""` y `database=credenciales_db`.

### 4. Inicializar la base de datos y datos de prueba
Ejecuta el script de inicialización:
```bash
python init_db.py
```
Este comando ejecuta automáticamente [`database/schema.sql`](database/schema.sql), crea la base de datos `credenciales_db`, las tablas (`usuarios`, `trabajadores`, `credenciales`, `notificaciones`), la vista `v_credenciales`, **10 trabajadores de prueba** (con estados vigentes, vencida e inactiva) y dos cuentas de demostración:

| Tipo de cuenta | Correo | Contraseña de demostración | Permisos |
|---|---|---|---|
| **Administrador** | `admin@empresa.com` | `Admin123!` | Crear, editar, activar/desactivar, reportes y PDFs |
| **Solo consulta** | `consulta@novatech.com` | `Consulta123!` | Solo lectura (bloquea crear, editar y desactivar) |

También puedes crear o actualizar usuarios adicionales desde la terminal con:
```bash
python crear_admin.py correo@ejemplo.com TuPasswordSeguro admin
python crear_admin.py lector@ejemplo.com TuPasswordSeguro consulta
```

### 5. Ejecutar la aplicación
```bash
python app.py
```
Abre en tu navegador: **http://localhost:5000**

---

## 📱 Cómo probar el escaneo de códigos QR desde un celular
1. Conecta tu computadora y el teléfono celular a la **misma red Wi-Fi**.
2. Consulta la dirección IPv4 local de tu computadora (en Windows ejecuta `ipconfig` en la terminal, por ejemplo `192.168.1.50`).
3. En tu archivo `.env`, define:
   ```ini
   BASE_URL=http://192.168.1.50:5000
   ```
4. Reinicia `python app.py` y asegúrate de permitir Python en el **Firewall de Windows (Redes privadas)**.
5. Escanea cualquier código QR desde la pantalla o desde el PDF impreso con la cámara del celular; abrirá directamente la página pública de verificación.

---

## 🗄️ Arquitectura de Base de Datos SQL (`database/schema.sql`)
El sistema utiliza una base de datos relacional **SQL (MySQL)** compuesta por 4 tablas y 1 vista dinámica:
1. **`usuarios`**: Cuentas de acceso con contraseñas cifradas (`password_hash`) y rol (`admin` o `consulta`).
2. **`trabajadores`**: Datos personales y laborales (`numero_trabajador`, `nombre_completo`, `edad`, `sexo`, `curp` única, `area`, `cargo`, `foto_path`, `email`, contacto de emergencia).
3. **`credenciales`**: Relación `1:N` con `trabajadores` (`numero_tarjeta` único, `qr_token` único UUID, `fecha_inicio`, `fecha_vencimiento`, bandera `activa`).
4. **`notificaciones`**: Bitácora de auditoría SQL que almacena cada notificación emitida (`credencial_id`, `tipo`, `enviada_a`, `asunto`, `vigencia`, `estado_actualizado`, `cuerpo` y `enviada_en`).
5. **Vista SQL `v_credenciales`**: Calcula en tiempo real el estado (`Vigente`, `Inactiva`, `Vencida`, `No vigente`) comparando `CURDATE()` contra `fecha_inicio`, `fecha_vencimiento` y `activa`.

> **Auto-inicialización:** Al iniciar `app.py`, el sistema verifica automáticamente si las tablas existen en MySQL; si la base de datos está vacía, ejecuta `init_db.py` de forma transparente para crear las tablas, la vista y los registros de demostración.

---

## ✉️ Cómo activar el envío de correos reales (opcional)
Todas las notificaciones se guardan siempre en la tabla SQL `notificaciones`. Además, para entregar correos reales a la bandeja de cualquier trabajador:

### Opción A — En la nube (Railway / Hosting sin puertos SMTP):
Configura la variable `GMAIL_WEBHOOK_URL` apuntando a un Web App de **Google Apps Script** (`MailApp.sendEmail`), el cual envía correos desde tu cuenta Gmail por **HTTPS (puerto 443)** a cualquier destinatario sin bloqueos de red.

### Opción B — En entorno local (SMTP directo):
1. En una cuenta Gmail emisora, activa la *Verificación en 2 pasos* y genera una **Contraseña de aplicación** de 16 letras en https://myaccount.google.com/apppasswords.
2. Completa en tu `.env` local:
   ```ini
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=tu_correo_emisor@gmail.com
   SMTP_PASSWORD=las16letrasgeneradas
   ```

---

## 📁 Estructura del proyecto
```text
├── app.py                  # Servidor Flask, rutas, autenticación, roles, QR y correos
├── db.py                   # Conexión a MySQL (soporta variables locales DB_* y Railway MYSQL*)
├── init_db.py              # Creación automática de BD, tablas SQL, usuarios demo y 10 trabajadores
├── crear_admin.py          # Utilidad CLI para crear usuarios admin o de solo consulta
├── reporte_pdf.py          # Generador de PDFs con ReportLab (reportes y credenciales A4)
├── Procfile                # Configuración de servidor Gunicorn para producción en Railway
├── requirements.txt        # Dependencias de Python
├── database/
│   └── schema.sql          # Esquema SQL completo (4 tablas relacionales + vista v_credenciales)
├── templates/              # Plantillas HTML (Jinja2)
│   ├── base.html           # Barra de navegación, indicador de rol y alertas
│   ├── login.html          # Pantalla de acceso
│   ├── index.html          # Panel principal, contadores, búsqueda y tarjetas
│   ├── form.html           # Formulario de alta y edición de trabajador/credencial
│   ├── credencial.html     # Vista detallada de credencial individual
│   ├── _card.html          # Componente visual de credencial (anverso y reverso)
│   ├── imprimir.html       # Búsqueda, filtro e impresión de credenciales
│   ├── reportes.html       # Reportes general, por área y por estado
│   └── verificar.html      # Página pública de verificación por código QR
└── static/
    ├── css/style.css       # Diseño responsivo NovaTech
    ├── js/app.js           # Menú móvil, vista previa de foto y confirmaciones
    ├── img/                # Logotipos institucionales de NovaTech
    └── uploads/            # Fotografías subidas localmente (ignoradas en Git)
```
