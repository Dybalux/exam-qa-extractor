## Exploration: Error Review Practice Mode

### Current State

The app tracks every answer via `PracticeResponse` (`is_correct: bool | None`, `answered_at: datetime`, `session_id`). A user's history is reconstructible by joining `PracticeSession.user_session_id` → `PracticeResponse.session_id`. Today there are four modes: `random`, `by_partial`, `by_topic`, `exam_simulation`. The `_get_available_questions()` helper filters by `exam_id` and `topic`, then returns a random question in `get_next_question()`. There is **no schema change required** to identify failed questions — they are already queryable.

### Affected Areas

| File | Why affected |
|------|-------------|
| `app/core/constants.py` | Add `ERROR_REVIEW = "error_review"` to `PracticeMode` enum |
| `app/models/practice_session.py` | Update DB `CheckConstraint` to include `error_review`; Alembic migration needed |
| `app/services/practice_service.py` | New helper `_get_failed_question_ids()` + mode branch in `_get_available_questions` / `create_session` |
| `app/api/practice.py` | No change (schema already accepts any `str` mode via `SessionCreate`) |
| `app/api/pages.py` | `practice_create` passes mode through; no logic change needed |
| `app/templates/practice/start.html` | Add radio option for error review |
| `app/templates/practice/results.html` | Optional: add "▶ Revisar errores" CTA when `incorrect_count > 0` |
| `app/db/migrations/versions/` | New migration to expand `check_valid_practice_mode` |

### Approaches

#### 1. Simple — Binary failed / not failed
Query all `PracticeResponse` where `is_correct = False` for this `user_session_id`, deduplicate by `question_id`, optionally filter by `exam_id`/`topic`, then randomly select among them.

- **Pros:** Zero schema migration beyond the mode constraint; 1 new helper method (~15 lines); intuitive UX; no statistical complexity.
- **Cons:** A question failed 5 times has the same weight as one failed once; does not surface "recently learned" vs "still struggling".
- **Effort:** Low

#### 2. Advanced — Weighted by failure count
Aggregate `COUNT(CASE WHEN is_correct = False THEN 1 END)` per question, weight selection probability by that count (or by `failure_count - success_count`).

- **Pros:** Prioritizes the user's weakest questions automatically.
- **Cons:** Requires weighted random selection (or ORDER BY count DESC then random); SQL query is heavier; over-weighting can make sessions feel repetitive.
- **Effort:** Medium

#### 3. Time-decay — Recent failures weighted higher
Same as Advanced but multiply each failure by a decay factor based on `answered_at` (e.g., exponential half-life of 7 days).

- **Pros:** Adapts to learning progress; recently cleared questions drop out naturally.
- **Cons:** Significantly more complex SQL/SQLAlchemy; tuning the decay constant is arbitrary; over-engineering for current use case.
- **Effort:** High

### Recommendation

**Implement Approach 1 (Simple) first.**

Rationale:
- The analytics dashboard already surfaces weak *topics* at an aggregate level. The user explicitly asked for a way to practice *specifically failed questions* — that is a binary need.
- We have all data needed today; no new tables or columns.
- Adding weighting later is a non-breaking enhancement: we swap `random.choice()` for a weighted picker without changing the mode contract.
- The `retry_of` column on `PracticeResponse` already hints at future retry tracking; we can leverage that if we ever want to build a smarter spaced-repetition layer.

**Definition of "failed question" for the simple approach:**
> A question is eligible for `error_review` if the user has submitted **at least one `is_correct=False` response** for it, regardless of whether they later answered it correctly in another mode. (This matches the common mental model: "show me questions I've ever gotten wrong.")

If desired, a future enhancement can mark questions as "cleared" once the user answers them correctly *inside* an `error_review` session itself, but that is out of scope for the initial feature.

### Edge Cases & Handling

| Edge case | Handling |
|-----------|----------|
| **No failed questions yet** | `_get_available_questions` returns empty list → `create_session` raises `ValidationError` with message "No questions with previous errors found." The frontend (`start.html` or `pages.py`) can catch this and flash "Todavía no tenés errores para revisar." |
| **Fewer failed questions than requested** | `actual_total = min(total_questions, len(available))` — already handled by existing logic. |
| **Filters (exam/topic) leave zero matches** | Same as above — validation error with clear message. |
| **Cleared all errors** (hypothetical) | Not a current feature. If added later, clearing errors would mean deleting or archiving `PracticeResponse` rows, which would naturally empty the pool. |
| **Skipped questions** | Skipped responses have `is_correct=None`, so they do **not** count as failed. This is correct. |

### Risks

- **DB migration:** Expanding the `CheckConstraint` is straightforward but must be accompanied by an Alembic migration. Risk is low; rollback is a simple downgrade.
- **UX confusion:** Users may expect `error_review` to only show questions they *keep* getting wrong. A short tooltip or subtitle in the UI ("Preguntas que alguna vez respondiste mal") mitigates this.
- **Performance at scale:** Querying all user responses to build the failed set could become slow if a user has thousands of responses. An index on `(user_session_id, is_correct)` or a future materialized view would solve this, but is not needed for current scale.

### Ready for Proposal

**Yes.** The orchestrator can move to `sdd-propose`. The user should be told:
- The simple approach requires no schema changes beyond a minor enum/constraint expansion.
- The initial implementation adds ~1 new helper, 1 enum value, 1 HTML radio option, and 1 migration.
- Weighted and time-decay variants are reserved for future enhancement.
