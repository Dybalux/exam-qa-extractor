# Delta for Type-Correctness & Latent Bug Fixes

## ADDED Requirements

### Requirement: REQ-TYPE-1 (Exam Image Upload Persistence)

The system MUST persist uploaded exam image bytes via `StorageService.save_file` as a binary stream (`BinaryIO`), not raw `bytes`. The saved file MUST be accessible via `FileUploadResult.storage_path`.

#### Scenario: Valid image upload persists and triggers OCR

- GIVEN a valid exam exists and a user uploads a valid image file
- WHEN POST `/api/v1/exams/{exam_id}/upload` is called with the image
- THEN `StorageService.save_file` receives a `BinaryIO` stream and saves the file
- AND `OCRService.extract_from_path` is called with `FileUploadResult.storage_path`
- AND on success, the user is redirected with a flash message confirming questions created

#### Scenario: OCR failure does not discard saved file

- GIVEN a valid exam exists and an image is uploaded
- WHEN `OCRService.extract_from_path` raises an exception
- THEN the uploaded file is already saved on disk (not rolled back)
- AND a warning is logged with the storage path and error
- AND the user is redirected with a warning flash message ("Archivo guardado pero OCR falló")

### Requirement: REQ-TYPE-2 (Safe Form Field Extraction)

Page handlers MUST safely extract text fields from `FormData` where `form.get(key)` returns `str | UploadFile | None`. Text-field names MUST NOT receive `UploadFile` values; if they do, the system MUST fall back to the configured default instead of crashing.

#### Scenario: Normal text form submission

- GIVEN an HTML form submission with standard text fields
- WHEN a page handler reads a text field via the form helper
- THEN the string value is returned (trimmed)
- AND type conversions (`int()`, `date.fromisoformat()`) succeed on the result

#### Scenario: Malicious file sent under text-field name

- GIVEN a request that sends a file under a field name expected to be text
- WHEN the page handler reads that field
- THEN the helper returns the configured default value (not the `UploadFile` object)
- AND the handler continues without raising `AttributeError` or `TypeError`

### Requirement: REQ-TYPE-3 (Mypy Quality Gate)

The codebase MUST pass `uv run mypy app --ignore-missing-imports` with 0 errors. All source files under `app/` MUST be type-correct under the project's strict mypy configuration (`disallow_untyped_defs`, `disallow_incomplete_defs`, `check_untyped_defs`).

#### Scenario: CI mypy step passes

- GIVEN all type fixes are applied
- WHEN `uv run mypy app --ignore-missing-imports` is executed
- THEN the exit code is 0
- AND no error messages are printed

#### Scenario: No unused mypy overrides

- GIVEN the `pyproject.toml` `[tool.mypy]` section
- WHEN mypy runs
- THEN no override is listed for a module that is not imported anywhere under `app/`
- AND the `cv2` override is absent (no file imports `cv2`)
