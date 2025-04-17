# Guía de Integración: Sistema de Backend para Detector de Caídas

Esta guía explica cómo integrar tu aplicación Android de detección de caídas con el backend en Python que recibe, almacena y visualiza los datos de caídas.

## Requisitos Previos

- Python 3.7+ instalado en el servidor
- Conocimientos básicos de:
  - Desarrollo Android (Kotlin)
  - Python y Flask
  - SQLite
  - Redes (HTTP/HTTPS)

## Paso 1: Configurar el Backend

### Instalación

1. Clona o descarga el código fuente del backend
2. Instala las dependencias:

```bash
pip install flask sqlite3
```

3. Configura el servidor:

```bash
# Cambiar el directorio a donde está fall-detector-backend.py
cd /ruta/al/backend

# Crear directorios necesarios
mkdir -p uploads logs

# Ejecutar el servidor
python fall-detector-backend.py
```

Por defecto, el servidor se ejecutará en el puerto 5000. Para producción, se recomienda usar un servidor WSGI como Gunicorn y un proxy inverso como Nginx.

### Configuración para Producción

Para un entorno de producción, crea un archivo `config.py` con:

```python
DEBUG = False
SERVER_NAME = "tu-dominio.com"  # Reemplaza con tu dominio real
SECRET_KEY = "clave-secreta-aleatoria"  # Cambiar esto por una clave segura
DATABASE = "ruta/absoluta/a/fall_detector.db"
UPLOAD_FOLDER = "ruta/absoluta/a/uploads"
LOG_FOLDER = "ruta/absoluta/a/logs"
```

## Paso 2: Integrar el Cliente Android

1. Añade el archivo `ServerAdapter.kt` a tu proyecto en el paquete `altermarkive.guardian.storage`

2. Agrega las dependencias necesarias en tu archivo `build.gradle` a nivel de módulo:

```gradle
dependencies {
    // OkHttp para subir archivos
    implementation 'com.squareup.okhttp3:okhttp:4.9.3'
    
    // Coroutines para operaciones asíncronas
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.6.0'
}
```

3. Actualiza tu AndroidManifest.xml para incluir permisos de internet:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
```

4. Inicializa el adaptador en tu clase `Guardian.kt`:

```kotlin
// En el método onCreate()
ServerAdapter.getInstance().initializeScheduledUploads(this)
```

5. Modifica la clase `Detector.kt` para enviar eventos de caída:

```kotlin
// En el método donde detectas la caída
if (lying[at] = 1.0) {
    // Código existente para alerta local
    Guardian.say(context, android.util.Log.WARN, TAG, "Detected a fall")
    alert(context)
    
    // Añadir: Reportar al servidor
    val position = Positioning.getLastLocation() // Método que deberías crear para obtener la ubicación
    ServerAdapter.reportFallEvent(
        context,
        position?.latitude,
        position?.longitude,
        Battery.level(context)
    )
}
```

6. Modifica la clase `Sampler.kt` para enviar datos del acelerómetro:

```kotlin
// En el método onSensorChanged
override fun onSensorChanged(event: SensorEvent) {
    // Código existente
    data?.dispatch(event.sensor.type, event.timestamp, event.values)
    
    // Añadir: Enviar al servidor cuando es acelerómetro
    if (event.sensor.type == Sensor.TYPE_ACCELEROMETER) {
        val deviceId = Report.id(context())
        ServerAdapter.addAccelerometerReading(
            deviceId,
            event.timestamp,
            event.values[0],
            event.values[1],
            event.values[2]
        )
    }
}
```

7. Modifica la clase `Upload.kt` para subir archivos también al nuevo servidor:

```kotlin
// En el método de subida
internal fun go(context: Context, root: String) {
    // Código existente para IPFS
    
    // Añadir: Subir también al nuevo servidor
    val zipped: Array<String>? = Storage.list(root, Storage.FILTER_ZIP)
    if (zipped != null && zipped.isNotEmpty()) {
        Arrays.sort(zipped)
        for (file in zipped) {
            val filePath = File(root, file).absolutePath
            ServerAdapter.uploadFile(context, filePath)
        }
    }
}
```

8. Actualiza la URL del servidor en `ServerAdapter.kt`:

```kotlin
private const val SERVER_URL = "https://tu-servidor.com"  // Cambia a tu dominio o IP real
```

## Paso 3: Configurar HTTPS (Recomendado)

Para seguridad en producción, configura HTTPS:

1. Obtén un certificado SSL (puedes usar Let's Encrypt que es gratuito)
2. Configura un proxy inverso como Nginx para manejar TLS/SSL

## Paso 4: Probar la Integración

1. Inicia el servidor backend
2. Ejecuta la aplicación Android en un dispositivo o emulador
3. Verifica en logs del servidor que recibe los datos
4. Comprueba el Dashboard web visitando http://tu-servidor:5000/dashboard

## Notas de Implementación

- **Modo por lotes**: El sistema acumula lecturas del acelerómetro y las envía por lotes para reducir el consumo de batería y datos.
- **Caché**: Si hay problemas de conectividad, los datos se almacenan temporalmente y se reintenta más tarde.
- **Seguridad**: Las comunicaciones deben usar HTTPS en producción.
- **Personalización**: Ajusta la frecuencia de envío de datos según tus necesidades específicas.

## Solución de Problemas

- **Errores de conexión**: Verifica la URL del servidor y que el dispositivo tenga conectividad.
- **Datos no aparecen**: Revisa los logs del servidor para identificar posibles errores en el formato de datos.
- **Alto consumo de batería**: Ajusta los intervalos de envío y el tamaño de los lotes.

## Siguientes Pasos

1. Implementa autenticación para proteger la API
2. Añade notificaciones por email o SMS cuando se detecta una caída
3. Desarrolla un panel de administración más completo
4. Implementa análisis avanzado de datos para mejorar la detección de caídas