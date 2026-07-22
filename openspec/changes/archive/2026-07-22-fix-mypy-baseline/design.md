# Design: fix-mypy-baseline

## Technical Approach

Fix all 79 mypy errors across 10 files (79/79 fixes specified in this design — amended after gate review found 2 fixes missing). Minimal-diff, per-file changes. No architectural refactors. Three errors are latent runtime bugs in a live endpoint (`/api/v1/exams/{id}/upload`). Strictly mechanical fixes for the rest.

## Architecture Decisions

| # | Option | Tradeoff | Decision |
|---|--------|----------|----------|
| 1 | `_form_str` helper vs 41 individual casts | Helper: 4 lines, all sites consistent. Casts: repetitive, error-prone | Single helper in `pages.py` |
| 2 | `HTMLResponse \| RedirectResponse` vs `Response` for GET handlers | Union is precise but verbose; `Response` is loose | `HTMLResponse \| RedirectResponse` — precise, stays strict |
| 3 | `async_sessionmaker` vs per-module `# type: ignore` | async_sessionmaker: 2-line change, SQLAlchemy 2.0 standard. Ignore: hides future errors | `async_sessionmaker` |
| 4 | Rename `existing` vs `cast()` at each reassignment | Rename: 6 lines, clear. Cast: brittle, misleading | Rename to `existing_question`/`existing_answer` |

## File Changes

### 1. `app/api/exams.py` (3 lines changed — lines 187-195)

Current (broken):
```python
upload_result = await storage_svc.save_file(
    file_data=await file.read(),        # bytes → BinaryIO wrong
    ...
)
ocr_result = await ocr_svc.process_image(upload_result.absolute_path)
# process_image doesn't exist; absolute_path doesn't exist
```

Fixed:
```python
import io  # add to imports

upload_result = await storage_svc.save_file(
    file_data=io.BytesIO(await file.read()),  # wrap bytes
    ...
)
ocr_result = await ocr_svc.extract_from_path(upload_result.storage_path)
```

The flash/redirect flow (lines 196-230) is preserved unchanged — only the save and OCR calls change.

### 2. `app/api/pages.py` (~55 lines changed)

**Add helpers** (after existing helpers, ~line 50):
```python
from fastapi import UploadFile  # add to existing fastapi import

def _form_str(form, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile) or value is None:
        return default
    return str(value).strip()

def _form_str_or_none(form, key: str) -> str | None:
    value = form.get(key)
    if isinstance(value, UploadFile):
        return None
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()
```

**Adopt at 28 `form.get()` + 3 bracket-access sites** (9 POST handlers). Pattern:
- `int(form.get("x", 1))` → `int(_form_str(form, "x", "1"))`
- `form.get("x") or None` → `_form_str_or_none(form, "x")`
- `form.get("x", "").strip()` → `_form_str(form, "x")`
- `int(form["x"])` → `int(_form_str(form, "x"))`
- `form.get("x") == "on"` → `_form_str(form, "x") == "on"`
- `int(form["x"]) if form.get("x") else None` (line 614 — mixed bracket + guard) → two-step:
  ```python
  s = _form_str_or_none(form, "x")
  exam_id = int(s) if s else None
  ```

**Bracket-access semantics (accepted change)**: `int(form["x"])` → `int(_form_str(form, "x"))` changes missing-field failure from `KeyError` to `ValueError` (lines 683, 684, 702). Both are unhandled 500 today — no behavioral regression, but documented as a deliberate semantic shift.

**Shuffle fix** (line 657-660): `answer_service.list_answers` returns `Sequence[Answer]` (line 120 of answer_service.py); `random.shuffle` requires `MutableSequence`. Fix:
```python
answers = list(await a_svc.list_answers(question.id))
random.shuffle(answers)
```

**Broaden return types on 11 GET handlers** that return `RedirectResponse` on error paths: `exam_detail`, `exam_edit`, `question_detail`, `question_correct`, `bulk_upload_page`, `manual_question_form`, `answer_new`, `answer_edit`, `answer_manage`, `practice_play`, `practice_results`. Change `-> HTMLResponse:` to `-> HTMLResponse | RedirectResponse:`.

**Whitespace→None semantics (accepted behavior change):** `_form_str_or_none` maps whitespace-only strings (`"  "`) to `None`, whereas the current `form.get("x") or None` preserves them. Affected sites: `topic_tags` (lines 131, 203), `notes` (line 322), `topic` (line 615). These fields propagate to service-layer `topic_tags`/`notes` params which already handle `str | None` — trimming whitespace before it reaches services is a correctness improvement, not a regression.

### 3. `app/db/session.py` (3 lines changed)

Before:
```python
from sqlalchemy.orm import sessionmaker
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, ...)
async def get_db() -> AsyncSession:
```

After:
```python
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import async_sessionmaker
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
```
Remove `class_=AsyncSession` (implicit in `async_sessionmaker`), `autocommit=False` (default). The `future=True` parameter on `create_async_engine` (session.py line 14) stays deliberately — it is **not** deprecated at the engine level, only `sessionmaker`/`Session`'s `future=True` was removed in SQLAlchemy 2.0.

### 4. `app/services/json_io_service.py` (7 lines changed)

- Line 354: `async def _resolve_default_subject(self, slug: str = "sistemas-operativos") -> Subject:` (add return annotation)
- Line 705: rename `existing` → `existing_question`
- Line 745: rename `existing` → `existing_answer`

### 5. `app/api/import_export.py` (1 line)

Line 97: `-> ImportPreviewSchema | ImportApplyResultSchema | JSONResponse:` (adds `JSONResponse` for the error path at line 238).

### 6. `app/services/ocr_service.py:303` (1 line)

```python
# Before: Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
# After:  Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
```

### 7. `app/services/exam_service.py:258` (1 line)

```python
# Before: topic_counts = {}
# After:  topic_counts: dict[str, int] = {}
```

### 8. `app/db/init_db.py` (2 lines)

```python
from typing import Any, cast
# Line 46: return cast(dict[str, Any], yaml.safe_load(f))
```
Add `types-PyYAML` to dev dependencies.

### 9. Migrations 004/005 (~15 lines)

**004**: Import `from typing import cast`. Annotate all untyped function params — `_seed_subject(conn, uuid_str: str) -> int | None`, `_seed_topics(conn, subject_id: int) -> None`, `_backfill_topic_id(conn) -> None`, `_backfill_subject_id(conn, subject_id: int) -> None`, `_table_exists(table: str) -> bool`, `_existing_columns(table: str) -> set[str]`, `_create_index_if_missing(table: str, column: str) -> None`. Cast `subject_id` (`int | None`) where passed to `_seed_topics`/`_backfill_subject_id`. Line 67 (`return existing[0]`): `Row.first()` returns `Row | None`; indexing returns `Any` under SQLAlchemy stubs. Fix: `return cast(int, existing[0])`.

**005**: Line 53 — `nulls = conn.execute(...).scalar()` is `Any | None`. Fix: `if (nulls or 0) > 0:` or wrap in `int()`.

### 10. `pyproject.toml` (2 lines)

Remove `[[tool.mypy.overrides]]` block for `cv2` (lines 119-121). Add `"types-PyYAML>=6.0"` to `[dependency-groups].dev`.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `_form_str` / `_form_str_or_none` helpers | **New** — parametrized test covering: str input, whitespace-only, `None` field, and `UploadFile` sent under text-field name (REQ-TYPE-2 scenario 2). File: `tests/api/test_form_helpers.py`. Assert: `_form_str` returns default for UploadFile/None; `_form_str_or_none` returns `None` for whitespace/UploadFile/None. |
| Integration | Upload endpoint — OCR success (REQ-TYPE-1 scenario 1) | Update 2 existing test mocks in `tests/api/test_redirect_targets.py`: `upload_result_mock.absolute_path` → `upload_result_mock.storage_path = Path("/tmp/test-upload.png")`; `ocr_mock.process_image` → `ocr_mock.extract_from_path = AsyncMock(return_value=OCRResult(...))`. Lines 324/387 and 328/391. |
| Integration | Upload endpoint — OCR failure (REQ-TYPE-1 scenario 2) | **New** — test that uploads an image, mocks storage to succeed but OCR to raise `OCRServiceError`. Assert: 303 redirect, flash contains "Archivo guardado pero OCR falló", file persisted on disk (storage.save_file was called). File: `tests/api/test_redirect_targets.py`. |
| Regression | Full suite | `pytest` — 142 existing tests must pass plus new tests. |

**New tests required**: 2 (`test_form_helpers.py` with ~4 parametrized cases + 1 OCR-failure test). The endpoint was broken at runtime (real `FileUploadResult` interface mismatched mocks), so 2 existing upload tests are test-only fixes — they asserted behavior that couldn't run. All 3 REQ-TYPE-1/REQ-TYPE-2 spec scenarios now have asserting tests.

## Migration / Rollout

No migration required. `git revert` for rollback. No data changes, no schema changes.

## Verification Plan

```bash
uv run mypy app --ignore-missing-imports     # 0 errors
uv run pytest                                 # 142 passed
uv run ruff check                             # clean
uv run ruff format --check                    # clean
```

## Open Questions

None.
