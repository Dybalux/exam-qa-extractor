# Tasks: fix-mypy-baseline

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~100–130 (including new tests) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR (all fixes are tightly coupled to one goal: 0 mypy errors) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | exams.py runtime bugs + mock updates | PR 1 (only PR) | Tests included with code; standalone verification |
| 2 | pages.py helpers + adoption + shuffle + return types | PR 1 (only PR) | Depends on nothing; largest single-file change |
| 3 | session.py + json_io_service.py | PR 1 (only PR) | Independent mechanical fixes |
| 4 | Remaining mechanical fixes (6 files) | PR 1 (only PR) | All independent, can be one commit each |
| 5 | New tests + final verification | PR 1 (only PR) | Tests with code they cover |

## Phase 1: exams.py Runtime Bug Fixes + Test Mock Updates

- [x] 1.1 Add `import io` to `app/api/exams.py` and wrap `file.read()` with `io.BytesIO()` in `save_file` call (line ~189)
- [x] 1.2 Change `ocr_svc.process_image(upload_result.absolute_path)` to `ocr_svc.extract_from_path(upload_result.storage_path)` in `app/api/exams.py` (line ~192)
- [x] 1.3 Update `tests/api/test_redirect_targets.py`: rename `upload_result_mock.absolute_path` → `upload_result_mock.storage_path = Path("/tmp/test-upload.png")` (lines ~324, ~387)
- [x] 1.4 Update `tests/api/test_redirect_targets.py`: rename `ocr_mock.process_image` → `ocr_mock.extract_from_path = AsyncMock(return_value=OCRResult(...))` (lines ~328, ~391)
- [x] 1.5 Verify: `uv run pytest tests/api/test_redirect_targets.py` — existing upload tests pass with updated mocks

## Phase 2: pages.py Form Helpers + Adoption + Return Types + Shuffle Fix

- [x] 2.1 Add `from fastapi import UploadFile` to existing fastapi import in `app/api/pages.py`
- [x] 2.2 Add `_form_str(form, key, default)` and `_form_str_or_none(form, key)` helpers after existing helpers (~line 50)
- [x] 2.3 Adopt helpers at 28 `form.get()` + 3 bracket-access sites across 9 POST handlers in `app/api/pages.py` (pattern: `int(_form_str(...))`, `_form_str_or_none(...)`, etc.)
- [x] 2.4 Fix mixed bracket + guard at line 614: two-step `s = _form_str_or_none(form, "x"); exam_id = int(s) if s else None`
- [x] 2.5 Fix shuffle: wrap `answer_service.list_answers()` result in `list()` before `random.shuffle()` (~line 657-660)
- [x] 2.6 Broaden return types on 11 GET handlers: change `-> HTMLResponse:` to `-> HTMLResponse | RedirectResponse:` (exam_detail, exam_edit, question_detail, question_correct, bulk_upload_page, manual_question_form, answer_new, answer_edit, answer_manage, practice_play, practice_results)
- [x] 2.7 Verify: `uv run mypy app/api/pages.py --ignore-missing-imports` — 0 errors on this file

## Phase 3: session.py + json_io_service.py

- [x] 3.1 In `app/db/session.py`: replace `sessionmaker` with `async_sessionmaker` (remove `class_=AsyncSession`, `autocommit=False`), add `AsyncGenerator` import, change `get_db()` return type to `AsyncGenerator[AsyncSession, None]`
- [x] 3.2 In `app/services/json_io_service.py`: add return annotation `-> Subject` to `_resolve_default_subject` (line 354)
- [x] 3.3 In `app/services/json_io_service.py`: rename `existing` → `existing_question` (line ~705) and `existing` → `existing_answer` (line ~745)
- [x] 3.4 Verify: `uv run mypy app/db/session.py app/services/json_io_service.py --ignore-missing-imports` — 0 errors

## Phase 4: Remaining Mechanical Fixes (6 files)

- [x] 4.1 In `app/api/import_export.py` line 97: add `| JSONResponse` to return type union
- [x] 4.2 In `app/services/ocr_service.py` line 303: change `[pix.width, pix.height]` to `(pix.width, pix.height)` (list → tuple)
- [x] 4.3 In `app/services/exam_service.py` line 258: add type annotation `dict[str, int]` to `topic_counts = {}`
- [x] 4.4 In `app/db/init_db.py`: add `from typing import Any, cast` and wrap `yaml.safe_load(f)` with `cast(dict[str, Any], ...)` at line 46
- [x] 4.5 In migration 004: import `cast`, annotate all untyped function params, cast `subject_id` where passed to seed/backfill, fix `existing[0]` with `cast(int, existing[0])`
- [x] 4.6 In migration 005: fix `nulls` scalar with `if (nulls or 0) > 0:` pattern (line 53)
- [x] 4.7 In `pyproject.toml`: remove `[[tool.mypy.overrides]]` block for `cv2` (lines 119-121) and add `"types-PyYAML>=6.0"` to `[dependency-groups].dev`
- [x] 4.8 Verify: `uv run mypy app --ignore-missing-imports` — 0 errors across all files

## Phase 5: New Tests + Final Verification

- [x] 5.1 Create `tests/api/test_form_helpers.py` with parametrized tests for `_form_str` and `_form_str_or_none`: str input, whitespace-only → default/None, None field, UploadFile under text-field name
- [x] 5.2 Add OCR-failure integration test to `tests/api/test_redirect_targets.py`: mock storage success + OCR raises `OCRProcessingError`, assert 303 redirect, flash contains "Archivo guardado pero OCR falló", file persisted
- [x] 5.3 Run full verification suite in order:
  1. `uv run mypy app --ignore-missing-imports` — 0 errors
  2. `uv run pytest` — 157 passed (142 existing + 15 new)
  3. `uv run ruff check app tests` — clean
  4. `uv run ruff format --check app tests` — clean
- [x] 5.4 If any check fails, fix and re-run until all pass
