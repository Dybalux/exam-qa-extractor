# Exam Study System

**[Leer en español](README.es.md)**

A web application for extracting questions from Operating Systems exam images using OCR, managing them with answers, and practicing through an interactive quiz interface.

## Features

- **OCR Text Extraction**: Upload exam images and extract text using Tesseract
- **Question Management**: Organize questions by partial (1°-4°) and topic
- **Answer Management**: Add correct and incorrect answers for practice mode
- **Practice Mode**: Interactive quiz with immediate feedback
- **Study Analytics**: Track progress and identify weak areas
- **Backup & Restore**: Export all data to JSON and import it back (cross-environment sync, backups, sharing study sets)

## Backup & Restore

The dashboard includes export/import controls to move exam data between environments or create offline backups.

**Export:** click "⬇ Descargar backup" to download a JSON file with all exams, questions, and answers.

**Import:** pick a previously exported JSON file and click "Vista previa" to see a dry-run diff (create/update/delete counts). Click "Confirmar import" to apply — the import is a **full restore** (the DB ends up identical to the JSON; records not in the JSON are deleted).

**Safety:**
- Preview without `?confirm=true` never touches the DB
- Malformed entries reject the entire import (no partial writes)
- Max file size: 10 MB (configurable via `MAX_IMPORT_SIZE_MB`)
- `IntegrityError` mid-import triggers automatic rollback

## Run with Docker

The fastest way to get the app running.

### Prerequisites
- Docker Engine ≥ 24 and Compose v2

### Quickstart
1. Create data directories:
   ```bash
   mkdir -p data/db data/uploads data/backups
   ```
2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env and fill in OPENAI_API_KEY and SECRET_KEY
   ```
3. Fix permissions (only if your host user is not UID 1000):
   ```bash
   chown -R 1000:1000 ./data
   ```
4. Start the stack:
   ```bash
   docker compose up -d --build
   ```
5. Verify:
   ```bash
   curl -fsS http://localhost:8000/health
   ```

The container runs `alembic upgrade head` automatically on first start and on every subsequent startup, so your database is always up to date.

### Development mode (live reload)
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```
Edits to files under `app/` or `alembic/` trigger an automatic reload.

### Where data lives
- SQLite database: `./data/db/database.db`
- Uploaded images: `./data/uploads/`
- JSON backups: `./data/backups/`

### Rollback
```bash
docker compose down
docker rmi exam-qa-extractor:latest
git revert HEAD~3..HEAD   # undo the three Docker commits
```
Your data on the host is untouched.

## Prerequisites

- Python 3.11+
- Tesseract OCR (system installation required)
- SQLite (included with Python)

### Installing Tesseract

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-spa
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
Download installer from https://github.com/UB-Mannheim/tesseract/wiki

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd image_to_text
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e ".[dev]"
```

4. Copy environment file:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Initialize database:
```bash
alembic upgrade head
```

6. Run the application:
```bash
uvicorn app.main:app --reload
```

## Development

Run tests:
```bash
pytest
```

Run linting:
```bash
ruff check .
```

Run type checking:
```bash
mypy app
```

Format code:
```bash
black app tests
```

## Project Structure

```
image_to_text/
├── app/
│   ├── api/            # API routes and schemas (incl. import_export.py)
│   ├── core/           # Exceptions, constants, config
│   ├── db/             # Database configuration
│   ├── models/         # SQLAlchemy models
│   ├── services/       # Business logic (incl. json_io_service.py)
│   ├── templates/      # Jinja2 templates
│   └── static/         # CSS, JS, images
├── alembic/            # Database migrations
├── tests/              # Test suite
├── uploads/            # File uploads (created at runtime)
└── pyproject.toml      # Project metadata and dependencies
```

## License

MIT
