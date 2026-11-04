-- Reto 3: Sistema de credencialización web
CREATE DATABASE IF NOT EXISTS credenciales_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE credenciales_db;

CREATE TABLE IF NOT EXISTS usuarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(120) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  rol ENUM('admin','consulta') NOT NULL DEFAULT 'admin',
  creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trabajadores (
  id INT AUTO_INCREMENT PRIMARY KEY,
  numero_trabajador VARCHAR(20) NOT NULL UNIQUE,
  nombre_completo VARCHAR(150) NOT NULL,
  edad TINYINT UNSIGNED NOT NULL,
  sexo ENUM('M','F','Otro') NOT NULL,
  curp CHAR(18) NOT NULL UNIQUE,
  area VARCHAR(100) NOT NULL,
  cargo VARCHAR(100) NOT NULL,
  foto_path VARCHAR(255),
  email VARCHAR(120),
  emergencia_nombre VARCHAR(150),
  emergencia_telefono VARCHAR(20),
  creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- El estado (Vigente/Inactiva/Vencida/No vigente) NO se guarda: se calcula en la vista.
CREATE TABLE IF NOT EXISTS credenciales (
  id INT AUTO_INCREMENT PRIMARY KEY,
  trabajador_id INT NOT NULL,
  numero_tarjeta VARCHAR(30) NOT NULL UNIQUE,
  qr_token CHAR(36) NOT NULL UNIQUE,
  fecha_inicio DATE NOT NULL,
  fecha_vencimiento DATE NOT NULL,
  activa BOOLEAN NOT NULL DEFAULT TRUE,
  creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_cred_trab FOREIGN KEY (trabajador_id)
    REFERENCES trabajadores(id) ON DELETE CASCADE,
  CONSTRAINT chk_fechas CHECK (fecha_vencimiento >= fecha_inicio)
);

CREATE TABLE IF NOT EXISTS notificaciones (
  id INT AUTO_INCREMENT PRIMARY KEY,
  credencial_id INT NOT NULL,
  tipo ENUM('generada','desactivada','vencimiento_modificado') NOT NULL,
  enviada_a VARCHAR(120),
  asunto VARCHAR(180),
  nombre_completo VARCHAR(150),
  numero_trabajador VARCHAR(20),
  numero_tarjeta VARCHAR(30),
  vigencia VARCHAR(60),
  estado_actualizado VARCHAR(30),
  cuerpo TEXT,
  enviada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (credencial_id) REFERENCES credenciales(id) ON DELETE CASCADE
);

CREATE OR REPLACE VIEW v_credenciales AS
SELECT c.*, t.numero_trabajador, t.nombre_completo, t.area, t.cargo, t.foto_path, t.email,
  CASE
    WHEN c.activa = 0 THEN 'Inactiva'
    WHEN CURDATE() < c.fecha_inicio THEN 'No vigente'
    WHEN CURDATE() > c.fecha_vencimiento THEN 'Vencida'
    ELSE 'Vigente'
  END AS estado
FROM credenciales c JOIN trabajadores t ON t.id = c.trabajador_id;
