from flask import Flask, request, jsonify, render_template
import sqlite3
import os
import json
from datetime import datetime
import time
import logging
from logging.handlers import RotatingFileHandler

# Configuración de la aplicación
app = Flask(__name__)
DATABASE = 'fall_detector.db'
UPLOAD_FOLDER = 'uploads'
LOG_FOLDER = 'logs'

# Asegurar que existan las carpetas necesarias
for folder in [UPLOAD_FOLDER, LOG_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Configuración de logging
handler = RotatingFileHandler(f'{LOG_FOLDER}/app.log', maxBytes=10000, backupCount=3)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Inicialización de la base de datos
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Tabla para datos de acelerómetro
    c.execute('''
    CREATE TABLE IF NOT EXISTS accelerometer_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        timestamp INTEGER,
        x REAL,
        y REAL,
        z REAL,
        received_at INTEGER
    )
    ''')
    
    # Tabla para eventos de caída
    c.execute('''
    CREATE TABLE IF NOT EXISTS fall_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        timestamp INTEGER,
        latitude REAL,
        longitude REAL,
        altitude REAL,
        accuracy REAL,
        battery_level INTEGER,
        event_type TEXT,
        description TEXT,
        received_at INTEGER
    )
    ''')
    
    # Tabla para dispositivos registrados
    c.execute('''
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT UNIQUE,
        user_name TEXT,
        user_age INTEGER,
        emergency_contact TEXT,
        registered_at INTEGER
    )
    ''')
    
    conn.commit()
    conn.close()

# Rutas de la API

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/device/register', methods=['POST'])
def register_device():
    """Registrar un nuevo dispositivo"""
    data = request.json
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Verificar si el dispositivo ya está registrado
        c.execute("SELECT device_id FROM devices WHERE device_id = ?", (data['device_id'],))
        if c.fetchone() is not None:
            # Actualizar información existente
            c.execute('''
            UPDATE devices SET 
                user_name = ?,
                user_age = ?,
                emergency_contact = ?
            WHERE device_id = ?
            ''', (data['user_name'], data['user_age'], data['emergency_contact'], data['device_id']))
        else:
            # Insertar nuevo dispositivo
            c.execute('''
            INSERT INTO devices (device_id, user_name, user_age, emergency_contact, registered_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (data['device_id'], data['user_name'], data['user_age'], 
                  data['emergency_contact'], int(time.time())))
        
        conn.commit()
        conn.close()
        logger.info(f"Dispositivo registrado: {data['device_id']}")
        return jsonify({"status": "success", "message": "Device registered successfully"})
    
    except Exception as e:
        logger.error(f"Error al registrar dispositivo: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/data/accelerometer', methods=['POST'])
def receive_accelerometer_data():
    """Recibir datos del acelerómetro"""
    data = request.json
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        for reading in data['readings']:
            c.execute('''
            INSERT INTO accelerometer_data 
            (device_id, timestamp, x, y, z, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (data['device_id'], reading['timestamp'], 
                  reading['x'], reading['y'], reading['z'], 
                  int(time.time())))
        
        conn.commit()
        conn.close()
        logger.info(f"Datos de acelerómetro recibidos: {len(data['readings'])} lecturas de {data['device_id']}")
        return jsonify({"status": "success", "message": f"Received {len(data['readings'])} accelerometer readings"})
    
    except Exception as e:
        logger.error(f"Error al recibir datos del acelerómetro: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/event/fall', methods=['POST'])
def record_fall_event():
    """Registrar un evento de caída"""
    data = request.json
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('''
        INSERT INTO fall_events 
        (device_id, timestamp, latitude, longitude, altitude, accuracy, 
        battery_level, event_type, description, received_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['device_id'], data['timestamp'], 
              data.get('latitude'), data.get('longitude'), 
              data.get('altitude'), data.get('accuracy'),
              data.get('battery_level'), data.get('event_type', 'fall'), 
              data.get('description', ''), int(time.time())))
        
        conn.commit()
        
        # Obtener información de contacto de emergencia
        c.execute("SELECT emergency_contact, user_name FROM devices WHERE device_id = ?", 
                  (data['device_id'],))
        result = c.fetchone()
        conn.close()
        
        if result:
            emergency_contact, user_name = result
            logger.warning(f"ALERTA: Caída detectada para {user_name} (ID: {data['device_id']}). Contacto: {emergency_contact}")
            # Aquí podrías implementar un sistema para notificar al contacto de emergencia
            
        logger.info(f"Evento de caída registrado para el dispositivo {data['device_id']}")
        return jsonify({"status": "success", "message": "Fall event recorded"})
    
    except Exception as e:
        logger.error(f"Error al registrar evento de caída: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/upload/file', methods=['POST'])
def receive_file():
    """Recibir archivos de datos"""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
    
    try:
        # Guardar archivo con timestamp para evitar sobrescritura
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        device_id = request.form.get('device_id', 'unknown')
        logger.info(f"Archivo recibido: {filename} del dispositivo {device_id}")
        
        return jsonify({
            "status": "success", 
            "message": "File uploaded successfully",
            "filename": filename
        })
    
    except Exception as e:
        logger.error(f"Error al recibir archivo: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Rutas para consultas y visualización

@app.route('/dashboard')
def dashboard():
    """Página del dashboard"""
    return render_template('dashboard.html')

@app.route('/api/stats/summary', methods=['GET'])
def get_stats():
    """Obtener estadísticas generales"""
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Total de dispositivos
        c.execute("SELECT COUNT(*) FROM devices")
        device_count = c.fetchone()[0]
        
        # Total de eventos de caída
        c.execute("SELECT COUNT(*) FROM fall_events")
        fall_count = c.fetchone()[0]
        
        # Caídas en las últimas 24 horas
        cutoff = int(time.time()) - (24 * 60 * 60)
        c.execute("SELECT COUNT(*) FROM fall_events WHERE timestamp > ?", (cutoff,))
        recent_falls = c.fetchone()[0]
        
        # Total de datos de acelerómetro
        c.execute("SELECT COUNT(*) FROM accelerometer_data")
        accel_count = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            "device_count": device_count,
            "total_falls": fall_count,
            "recent_falls": recent_falls,
            "accelerometer_readings": accel_count
        })
    
    except Exception as e:
        logger.error(f"Error al obtener estadísticas: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/events/recent', methods=['GET'])
def get_recent_events():
    """Obtener eventos recientes"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row  # Para obtener resultados como diccionarios
        c = conn.cursor()
        
        c.execute('''
        SELECT fe.*, d.user_name 
        FROM fall_events fe
        LEFT JOIN devices d ON fe.device_id = d.device_id
        ORDER BY fe.timestamp DESC LIMIT ?
        ''', (limit,))
        
        events = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify(events)
    
    except Exception as e:
        logger.error(f"Error al obtener eventos recientes: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Iniciar la aplicación
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)