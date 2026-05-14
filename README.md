# Exam Study System

A web application for extracting questions from Operating Systems exam images using OCR, managing them with answers, and practicing through an interactive quiz interface.

## Features

- **OCR Text Extraction**: Upload exam images and extract text using Tesseract
- **Question Management**: Organize questions by partial (1°-4°) and topic
- **Answer Management**: Add correct and incorrect answers for practice mode
- **Practice Mode**: Interactive quiz with immediate feedback
- **Study Analytics**: Track progress and identify weak areas

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
pip install -r requirements.txt
pip install -r requirements-dev.txt
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
│   ├── api/            # API routes and schemas
│   ├── core/           # Exceptions, constants, config
│   ├── db/             # Database configuration
│   ├── models/         # SQLAlchemy models
│   ├── services/       # Business logic
│   ├── templates/      # Jinja2 templates
│   └── static/         # CSS, JS, images
├── alembic/            # Database migrations
├── tests/              # Test suite
├── uploads/            # File uploads (created at runtime)
└── requirements.txt    # Dependencies
```

## License

MIT
