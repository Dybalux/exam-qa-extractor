# Apply Progress: feat-topic-domain-refactor

## Completed Tasks
- [x] 1.1 Create app/core/slug.py implementing slugify(value: str) -> str
- [x] 1.2 Create app/models/subject.py with Subject table
- [x] 1.3 Create app/models/topic.py with Topic table
- [x] 1.4 Modify app/models/question.py (topic_id, topic_relation, hybrid property topic)
- [x] 1.5 Modify app/models/exam.py (subject_id, subject relationship)
- [x] 1.6 Update app/models/__init__.py to export new models
- [x] 1.7 Create app/schemas/subject.py
- [x] 1.8 Create app/schemas/topic.py
- [x] 1.9 Write unit tests in tests/models/test_subject_topic.py
- [x] 2.1 Create Alembic migration 004_add_subjects_topics.py
- [x] 2.2 Update app/db/init_db.py to seed from seeds.yaml
- [x] 2.3 Refactor QuestionService for dynamic topic resolution
- [x] 2.4 Refactor SearchService to join topics table
- [x] 2.5 Refactor JsonIOService for topic pre-fetch + dynamic creation
- [x] 2.6 Write integration tests in tests/test_topic_services.py (11 tests)
- [x] 3.1 Create app/api/v1/endpoints/subjects.py with CRUD endpoints (7 endpoints)
- [x] 3.2 Register subjects router in app/api/__init__.py
- [x] 3.3 Refactor app/api/pages.py to query dynamic topics via get_all_topics dependency
- [x] 3.4 Update templates (manual_form, questions/list, practice/start) for dynamic topics
- [x] 3.5 Write integration tests in tests/api/test_subject_endpoints.py (17 tests)

## Verify Fixes Applied

### C1 — TopicEnum deprecated (REQ-QEXT-2) ✅
- Removed `TopicEnum` import from `app/models/question.py` and `app/schemas/question.py`
- Changed `QuestionCreate.topic` default from `TopicEnum.OTHER.value` to `"other"`
- Changed `BulkQuestionItem.topic` default from `TopicEnum.OTHER.value` to `"other"`
- Added deprecation comment to `TopicEnum` class in `app/core/constants.py`
- Updated `tests/api/test_import_export_endpoints.py` to use `"other"` string

### C2 — questions.topic column dropped (Design compliance) ✅
- Created migration `005_drop_topic_column.py` that:
  - Drops legacy `questions.topic` column (SQLite table rebuild)
  - Sets `questions.topic_id` NOT NULL (verified all rows backfilled)
  - Sets `exams.subject_id` NOT NULL (verified all rows backfilled)
- Updated `Question` model:
  - Removed `_topic` mapped column and `idx_question_topic` index
  - Replaced hybrid property with simple property returning `topic_relation.slug`
  - Removed topic setter; `__init__` pops deprecated `topic` kwarg silently
  - Changed `topic_id` to `Mapped[int]` with `nullable=False`, `ondelete="RESTRICT"`
- Updated `Exam` model: `subject_id` NOT NULL, `ondelete="RESTRICT"`
- Updated `QuestionService` and `JsonIOService`: removed `topic=` kwargs and setter calls
- Updated all tests for NOT NULL constraints (subject/topic fixtures)

### W1 — Exam creation enforces Subject linkage (REQ-EXAM-1) ✅
- Added `subject_id` parameter to `ExamService.create_exam()`
- Defaults to `"sistemas-operativos"` subject if not provided
- Validates that explicit subject_id exists
- Added `subject_id` to `ExamCreate` Pydantic schema
- Updated exam API endpoint to pass `subject_id`
- `JsonIOService.apply_import()` assigns default subject to imported exams

### W2 — topic_id/subject_id nullable ✅
- Addressed by C2 migration 005 (NOT NULL constraints enforced)

### W3 — Subject CRUD complete (REQ-SUBJ-2) ✅
- Added `PUT /subjects/{subject_id}` (update subject name/slug)
- Added `DELETE /subjects/{subject_id}` (delete subject, cascades topics, restricted if exams exist)
- Added `SubjectUpdate` Pydantic schema

### W4 — Scratch scripts cleaned up ✅
- Added `parse_engram.py`, `save_verify_report.py`, `engram-export.json`, `database_backup_*.json` to `.gitignore`

## Verify Results
- Migration 005 applied successfully: `questions.topic` column gone, `topic_id` NOT NULL, `subject_id` NOT NULL
- 123/123 tests pass
- `ruff format` and `ruff check` pass with zero issues

## Status
All 20 tasks complete + all 6 verify findings resolved.
Branch: feat/topic-domain-foundation (stacked-to-main, PR 3 of 3).
