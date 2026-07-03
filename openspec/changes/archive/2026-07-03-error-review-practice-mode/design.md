# Design: Error Review Practice Mode

## Technical Approach

Additive change: new `PracticeMode.ERROR_REVIEW` enum value, new helper querying `PracticeResponse` for failed question IDs, and a filter parameter on `_get_available_questions`. No schema change beyond expanding the check constraint — all data comes from existing tables.

## Architecture Decisions

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| Where to compute failed IDs | In `_get_available_questions` (pass mode) | In `create_session`/`get_next_question`, pass `question_ids: list[int] \| None` | **B** | Keeps `_get_available_questions` mode-agnostic; reusable for future ID-based filters |
| Re-query vs store failed IDs in session | Store in `filters` dict on creation | Re-compute on each call | **B** | Simpler, no mutation of persistent data; minor performance hit is negligible at current scale |
| Migration approach | New `PRAGMA`-based migration (006) | Modify initial migration (001) | **New (006)** | Idempotent, follows existing convention (`002`-`005`), safe to roll back |

## Data Flow

```
POST /practice (mode=error_review)
  └─ pages.practice_create()
       └─ service.create_session(user_session_id, mode="error_review", ...)
            ├─ mode == "error_review"?
            │    └─ _get_failed_question_ids(user_session_id)
            │         └─ SELECT DISTINCT question_id FROM practice_responses
            │              JOIN practice_sessions ON session_id = practice_sessions.id
            │              WHERE user_session_id = ? AND is_correct = 0
            └─ _get_available_questions(question_ids=[...])
                 └─ SELECT * FROM questions WHERE id IN (...) [AND exam_id=?] [AND topic=?]
                      └─ filter by is_ready_for_practice
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/core/constants.py` | Modify | Add `ERROR_REVIEW = "error_review"` to `PracticeMode` |
| `app/models/practice_session.py` | Modify | Expand `check_valid_practice_mode` to include `'error_review'` |
| `app/services/practice_service.py` | Modify | Add `_get_failed_question_ids(user_session_id)` method; add `question_ids` param to `_get_available_questions`; branch in `create_session` and `get_next_question` for error_review mode |
| `app/api/pages.py` | Modify | Wrap `practice_create` in try/except `ValidationError` → redirect with flash |
| `app/templates/practice/start.html` | Modify | Add radio option tuple `('error_review', '🔁 Errores', 'Preguntas que alguna vez respondiste mal')` |
| `app/db/migrations/versions/006_add_error_review_mode.py` | Create | Alembic migration expanding `check_valid_practice_mode` — drops and recreates constraint using `batch_alter_table` with `recreate='always'` (SQLite-safe) |

## Key Signatures

```python
# app/services/practice_service.py — new method
async def _get_failed_question_ids(self, user_session_id: str) -> list[int]:
    """Return deduplicated IDs of questions this user has ever answered incorrectly."""

# app/services/practice_service.py — modified signature
async def _get_available_questions(
    self,
    exam_id: int | None,
    filters: dict,
    question_ids: list[int] | None = None,  # NEW
) -> list[Question]:
```

## Migration Strategy

**Alembic revision `006_add_error_review_mode`** — uses SQLite batch_alter_table to safely modify the CHECK constraint:

1. `upgrade()`: Drop existing `check_valid_practice_mode`, recreate with `IN ('random', 'by_partial', 'by_topic', 'exam_simulation', 'error_review')`
2. `downgrade()`: Drop constraint, recreate without `'error_review'` — idempotent, no data loss.

## Empty State Handling

When no failed questions exist, `_get_available_questions` returns `[]`. `create_session` raises `ValidationError` with message `"No questions with previous errors found."`. `pages.py` catches it and redirects to `/practice` with flash `"Todavía no tenés errores para revisar."`.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_get_failed_question_ids` returns correct IDs | `tests/unit/services/test_practice_service.py` — new file. Create test user with mix of correct/incorrect/skipped responses, verify returned IDs exclude correct and skipped. |
| Unit | `create_session` with error_review and no failures raises `ValidationError` | Same file. Call with empty DB, assert `ValidationError` raised with expected message. |
| Integration | POST /practice with `mode=error_review` when failures exist → session created with questions | `tests/integration/api/test_practice.py` — new file. Seed DB with 3 questions, 2 failed responses for 1 question. Assert redirect to `/practice/{id}/play`, session has 1 question. |
| Integration | POST /practice with `mode=error_review` when no failures → flash redirect | Same file. Assert redirect to `/practice`, query params contain flash message. |
| Integration | POST /practice with `mode=error_review` + exam filter | Same file. 2 exams, failures only in exam 1. Assert session restricts to exam 1. |

## Open Questions

None — all design decisions are resolved.
