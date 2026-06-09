# Sistema de Estudio de Exámenes

**[Read in English](README.md)**

Una aplicación web para extraer preguntas de exámenes de Sistemas Operativos usando OCR, gestionarlas con respuestas y practicar a través de una interfaz de quiz interactiva.

## Características

- **Extracción de Texto OCR**: Subí imágenes de exámenes y extraé texto usando Tesseract
- **Gestión de Preguntas**: Organizá preguntas por parcial (1°-4°) y tema
- **Gestión de Respuestas**: Agregá respuestas correctas e incorrectas para el modo práctica
- **Modo Práctica**: Quiz interactivo con feedback inmediato
- **Analíticas de Estudio**: Rastreá tu progreso e identificá áreas débiles
- **Backup y Restauración**: Exportá todos los datos a JSON e importalos de vuelta (sincronización entre entornos, backups, compartir sets de estudio)

## Backup y Restauración

El dashboard incluye controles de exportación/importación para mover datos de exámenes entre entornos o crear backups offline.

**Exportar:** hacé clic en "⬇ Descargar backup" para descargar un archivo JSON con todos los exámenes, preguntas y respuestas.

**Importar:** elegí un archivo JSON exportado previamente y hacé clic en "Vista previa" para ver un diff en seco (cantidades de crear/actualizar/eliminar). Hacé clic en "Confirmar import" para aplicar — la importación es una **restauración completa** (la DB termina idéntica al JSON; los registros que no están en el JSON se eliminan).

**Seguridad:**
- La vista previa sin `?confirm=true` nunca toca la DB
- Entradas malformadas rechazan toda la importación (sin escrituras parciales)
- Tamaño máximo de archivo: 10 MB (configurable via `MAX_IMPORT_SIZE_MB`)
- `IntegrityError` durante la importación dispara rollback automático

## Ejecutar con Docker

La forma más rápida de poner en marcha la aplicación.

### Requisitos
- Docker Engine ≥ 24 y Compose v2

### Inicio rápido
1. Cree los directorios de datos:
   ```bash
   mkdir -p data/db data/uploads data/backups
   ```
2. Configure el entorno:
   ```bash
   cp .env.example .env
   # Edite .env y complete OPENAI_API_KEY y SECRET_KEY
   ```
3. Ajuste los permisos (solo si su usuario del host no es UID 1000):
   ```bash
   chown -R 1000:1000 ./data
   ```
4. Inicie el stack:
   ```bash
   docker compose up -d --build
   ```
5. Verifique:
   ```bash
   curl -fsS http://localhost:8000/health
   ```

El contenedor ejecuta `alembic upgrade head` automáticamente en el primer arranque y en cada arranque posterior, de modo que la base de datos se mantiene siempre actualizada.

### Modo desarrollo (recarga en vivo)
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```
Las ediciones en archivos bajo `app/` o `alembic/` disparan una recarga automática.

### Dónde se guardan los datos
- Base de datos SQLite: `./data/db/database.db`
- Imágenes subidas: `./data/uploads/`
- Backups en JSON: `./data/backups/`

### Reversión
```bash
docker compose down
docker rmi exam-qa-extractor:latest
git revert HEAD~3..HEAD   # deshace los tres commits de Docker
```
Sus datos en el host no se ven afectados.

## Requisitos Previos

- Python 3.11+
- Tesseract OCR (requiere instalación en el sistema)
- SQLite (incluido con Python)

### Instalando Tesseract

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-spa
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
Descargá el instalador desde https://github.com/UB-Mannheim/tesseract/wiki

## Instalación

1. Cloná el repositorio:
```bash
git clone <repository-url>
cd image_to_text
```

2. Creá el entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalá las dependencias:
```bash
pip install -e ".[dev]"
```

4. Copiá el archivo de entorno:
```bash
cp .env.example .env
# Editá .env con tu configuración
```

5. Inicializá la base de datos:
```bash
alembic upgrade head
```

6. Ejecutá la aplicación:
```bash
uvicorn app.main:app --reload
```

## Desarrollo

Ejecutar tests:
```bash
pytest
```

Ejecutar linting:
```bash
ruff check .
```

Ejecutar chequeo de tipos:
```bash
mypy app
```

Formatear código:
```bash
black app tests
```

## Estructura del Proyecto

```
image_to_text/
├── app/
│   ├── api/            # Rutas de API y schemas (incl. import_export.py)
│   ├── core/           # Excepciones, constantes, config
│   ├── db/             # Configuración de base de datos
│   ├── models/         # Modelos SQLAlchemy
│   ├── services/       # Lógica de negocio (incl. json_io_service.py)
│   ├── templates/      # Templates Jinja2
│   └── static/         # CSS, JS, imágenes
├── alembic/            # Migraciones de base de datos
├── tests/              # Suite de tests
├── uploads/            # Subidas de archivos (creado en runtime)
└── pyproject.toml      # Metadatos del proyecto y dependencias
```

## Licencia

MIT
