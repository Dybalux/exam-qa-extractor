# Tasks: Error Review Practice Mode

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~180-250 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes (resolved — ask-on-risk, single PR accepted, low risk)
Chained PRs recommended: No
Chain strategy: N/A (single PR)
400-line budget risk: Low

## Phase 1: Foundation (Constants + Model Constraint)

- [x] 1.1 Add `ERROR_REVIEW = "error_review"` to `PracticeMode` enum in `app/core/constants.py`
- [x] 1.2 Expand `check_valid_practice_mode` in `app/models/practice_session.py` to include `'error_review'`
- [x] 1.3 Create Alembic migration `app/db/migrations/versions/006_add_error_review_mode.py` — drop and recreate CHECK constraint with `batch_alter_table(recreate='always')` including `'error_review'`; include reversible `downgrade()`

## Phase 2: Core Implementation (Service Layer)

- [x] 2.1 Add `_get_failed_question_ids(self, user_session_id: str) -> list[int]` to `PracticeService` in `app/services/practice_service.py` — query `PracticeResponse` JOIN `practice_sessions` WHERE `user_session_id = ? AND is_correct = 0`, return deduplicated IDs
- [x] 2.2 Add `question_ids: list[int] | None = None` parameter to `_get_available_questions()` in `app/services/practice_service.py` — when provided, filter results to `WHERE id IN (question_ids)`
- [x] 2.3 Branch in `create_session()` for `mode == "error_review"`: call `_get_failed_question_ids()`, pass result as `question_ids` to `_get_available_questions()`, raise `ValidationError("No questions with previous errors found.")` if empty
- [x] 2.4 Branch in `get_next_question()` for `mode == "error_review"`: apply same `question_ids` filter when selecting next question

## Phase 3: Frontend Wiring

- [x] 3.1 Add radio option `('error_review', '🔁 Errores', 'Preguntas que alguna vez respondiste mal')` to mode selection in `app/templates/practice/start.html`
- [x] 3.2 Wrap `practice_create()` in `app/api/pages.py` with try/except `ValidationError` — on catch, redirect to `/practice` with flash message `"Todavía no tenés errores para revisar."`

## Phase 4: Testing

- [x] 4.1 Create `tests/unit/services/test_practice_service.py` — test `_get_failed_question_ids` returns correct deduplicated IDs (mix of correct/incorrect/skipped responses), excludes correct and skipped
- [x] 4.2 Add unit test: `create_session` with `error_review` and no failures raises `ValidationError` with expected message
- [x] 4.3 Create `tests/integration/api/test_practice.py` — test POST `/practice` with `mode=error_review` + existing failures → redirect to `/practice/{id}/play`, session contains only failed questions
- [x] 4.4 Add integration test: POST `/practice` with `mode=error_review` + no failures → redirect to `/practice` with flash message
- [x] 4.5 Add integration test: POST `/practice` with `mode=error_review` + `exam_id` filter → session restricted to failed questions from that exam only
