# Verification Report: feat-topic-domain-refactor (RE-VERIFY)

**Change**: feat-topic-domain-refactor
**Branch**: feat/topic-domain-foundation (stacked-to-main, PR 3 of 3)
**Date**: 2026-06-30
**Mode**: Full artifacts (proposal, specs, design, tasks)
**Type**: Re-verify after 6 fix commits addressing 2 CRITICAL + 4 WARNING findings from initial verify

---

## Verdict: PASS

---

## Build & Test Evidence

| Check | Result | Details |
|-------|--------|---------|
| `pytest -v` | ✅ PASS | 123/123 tests passed (4.22s), 1 deprecation warning (Starlette HTTP_413 — pre-existing, unrelated) |
| `ruff check` | ✅ PASS | Zero issues across all project files |
| `ruff format --check` | ✅ PASS | 80 files formatted correctly |

---

## Previous Findings — Resolution Status

### CRITICAL

| ID | Finding | Status | Evidence |
|----|---------|--------|----------|
| C1 | TopicEnum not deprecated (REQ-QEXT-2) | ✅ RESOLVED | `TopicEnum` import removed from `app/models/question.py` and `app/schemas/question.py`. Schema defaults changed from `TopicEnum.OTHER.value` to `"other"` string literal. Deprecation comment added to `TopicEnum` in `app/core/constants.py`. Tests updated to use string `"other"`. Grep confirms TopicEnum only appears in: (1) the deprecated class definition itself, (2) migration 004 comment, (3) docstrings/comments in endpoints and tests referencing the deprecation. |
| C2 | `questions.topic` column not dropped (Design compliance) | ✅ RESOLVED | Migration `005_drop_topic_column.py` created. Live DB `PRAGMA table_info(questions)` confirms `topic` column is GONE (14 columns, no `topic`). `topic_id` has `notnull=1`. `Question` model: removed `_topic` mapped column, removed `idx_question_topic` index, replaced hybrid property with simple `@property` returning `topic_relation.slug`, `__init__` pops deprecated `topic` kwarg silently. Alembic version: `005_drop_topic_column`. |

### WARNING

| ID | Finding | Status | Evidence |
|----|---------|--------|----------|
| W1 | Exam creation ignores subject_id (REQ-EXAM-1) | ✅ RESOLVED | `ExamService.create_exam()` now accepts `subject_id` parameter. `_resolve_subject_id()` defaults to `"sistemas-operativos"` if not provided; validates explicit IDs exist. `ExamCreate` schema includes `subject_id: int | None`. DB enforces `NOT NULL` (notnull=1 confirmed via PRAGMA). `JsonIOService.apply_import()` assigns default subject to imported exams. |
| W2 | `topic_id`/`subject_id` nullable | ✅ RESOLVED | Addressed by migration 005. Live DB confirms: `questions.topic_id` notnull=1, `exams.subject_id` notnull=1. Models: `topic_id: Mapped[int]` with `nullable=False`, `subject_id: Mapped[int]` with `nullable=False`. Both use `ondelete="RESTRICT"`. |
| W3 | Subject CRUD incomplete (REQ-SUBJ-2) | ✅ RESOLVED | `PUT /subjects/{subject_id}` endpoint added (updates name/slug with uniqueness check). `DELETE /subjects/{subject_id}` endpoint added (cascade deletes topics, raises 409 if exams reference subject via FK RESTRICT). `SubjectUpdate` Pydantic schema created. All 4 CRUD operations now available: List, Get, Create, Update, Delete. |
| W4 | Scratch scripts with lint issues | ✅ RESOLVED | `.gitignore` now includes: `parse_engram.py`, `save_verify_report.py`, `engram-export.json`, `database_backup_*.json`. `ruff check` passes with zero issues. `ruff format --check` passes with zero issues. |

---

## Task Completion: 20/20 ✅

### Phase 1: Models & Core Foundation (9/9)
| Task | Status | Evidence |
|------|--------|----------|
| 1.1 `app/core/slug.py` | ✅ | `slugify()` with NFKD normalization, regex cleanup |
| 1.2 `app/models/subject.py` | ✅ | Subject model with id, uuid, name, slug, relationships |
| 1.3 `app/models/topic.py` | ✅ | Topic model with id, uuid, name, slug, subject_id FK |
| 1.4 `app/models/question.py` | ✅ | topic_id FK (NOT NULL), topic_relation relationship, simple property topic (no hybrid) |
| 1.5 `app/models/exam.py` | ✅ | subject_id FK (NOT NULL), subject relationship |
| 1.6 `app/models/__init__.py` | ✅ | Exports Subject and Topic |
| 1.7 `app/schemas/subject.py` | ✅ | SubjectCreate, SubjectResponse, SubjectUpdate |
| 1.8 `app/schemas/topic.py` | ✅ | TopicCreate, TopicResponse |
| 1.9 Unit tests | ✅ | 4 tests in `tests/models/test_subject_topic.py` |

### Phase 2: DB Migrations, Seeding & Services (6/6)
| Task | Status | Evidence |
|------|--------|----------|
| 2.1 Alembic migration | ✅ | `004_add_subjects_topics.py` (tables, seed, backfill) + `005_drop_topic_column.py` (drop column, NOT NULL) |
| 2.2 YAML seeding | ✅ | `init_db.py` loads `seeds.yaml` idempotently |
| 2.3 QuestionService refactor | ✅ | `_resolve_topic_id()` with dynamic lookup |
| 2.4 SearchService refactor | ✅ | Joins topics table, filters by Topic.slug |
| 2.5 JsonIOService refactor | ✅ | `_load_topics_map()` bulk select, `_resolve_or_create_topic()` |
| 2.6 Service integration tests | ✅ | 11 tests in `tests/test_topic_services.py` |

### Phase 3: REST API & Pages Integration (5/5)
| Task | Status | Evidence |
|------|--------|----------|
| 3.1 Subject endpoints | ✅ | 9 endpoints (CRUD subjects + topics, including PUT and DELETE) |
| 3.2 Router registration | ✅ | Registered in `app/api/__init__.py` |
| 3.3 Dynamic pages | ✅ | `get_all_topics` dependency in pages.py |
| 3.4 Template updates | ✅ | 3 templates iterate dynamic topics |
| 3.5 Integration tests | ✅ | 17 tests in `tests/api/test_subject_endpoints.py` |

---

## Spec Compliance Matrix

### subject-management (New Capability)

| Requirement | Status | Notes |
|-------------|--------|-------|
| REQ-SUBJ-1 (YAML Seeding) | ✅ COMPLIANT | Seeds from `seeds.yaml` via `init_db.py` |
| REQ-SUBJ-2 (Subject CRUD) | ✅ COMPLIANT | Full CRUD: List, Get, Create, Update, Delete endpoints |

### topic-management (New Capability)

| Requirement | Status | Notes |
|-------------|--------|-------|
| REQ-TOPIC-1 (Topic Seeding) | ✅ COMPLIANT | Topics seeded under parent Subject from YAML |
| REQ-TOPIC-2 (Dynamic Topic Creation) | ✅ COMPLIANT | `_resolve_or_create_topic()` in JsonIOService |

### exam-management (Modified Capability)

| Requirement | Status | Notes |
|-------------|--------|-------|
| REQ-EXAM-1 (Subject Linkage) | ✅ COMPLIANT | `subject_id` NOT NULL in DB; `create_exam()` resolves/defaults subject; validated on explicit ID |
| REQ-EXAM-2 (Legacy Backfill) | ✅ COMPLIANT | Migration 004 backfills all existing exams to default subject |

### question-extraction (Modified Capability)

| Requirement | Status | Notes |
|-------------|--------|-------|
| REQ-QEXT-1 (DB Topic Association) | ✅ COMPLIANT | `topic_id` NOT NULL FK, service validates on create |
| REQ-QEXT-2 (Deprecate TopicEnum) | ✅ COMPLIANT | TopicEnum removed from models and schemas; deprecation comment on class; string defaults used |

### import-export (Modified Capability)

| Requirement | Status | Notes |
|-------------|--------|-------|
| REQ-IMP-1 (Legacy Schema Parsing) | ✅ COMPLIANT | Parses legacy JSON, maps topic strings to DB entities |
| REQ-IMP-2 (Dynamic Topic Resolution) | ✅ COMPLIANT | Creates missing topics under default Subject |

---

## Design Compliance

| Design Decision | Status | Notes |
|-----------------|--------|-------|
| Topic access via property | ✅ | Simple property returns `topic_relation.slug`, fallback `"other"` (hybrid replaced) |
| Slug validation: Both DB + service | ✅ | Unique index + service-level checks |
| Bulk select for topic lookup | ✅ | `_load_topics_map()` fetches all topics in O(1) |
| Drop `questions.topic` column | ✅ | Migration 005 drops column via SQLite table rebuild |
| Make `topic_id` NOT NULL | ✅ | Migration 005 enforces NOT NULL after verifying backfill |
| Make `subject_id` NOT NULL | ✅ | Migration 005 enforces NOT NULL after verifying backfill |

---

## Migration Integrity

| Aspect | Status | Notes |
|--------|--------|-------|
| Table creation | ✅ | IF NOT EXISTS guards for subjects/topics (migration 004) |
| Data seeding | ✅ | Default subject + 9 OS topics seeded (migration 004) |
| topic_id backfill | ✅ | Matches questions.topic → topics.slug; re-runnable (migration 004) |
| subject_id backfill | ✅ | All existing exams → default subject; re-runnable (migration 004) |
| Index creation | ✅ | Indexes on topic_id and subject_id |
| Column drop | ✅ | Migration 005 drops `questions.topic` via batch_alter_table rebuild |
| NOT NULL enforcement | ✅ | Migration 005 enforces NOT NULL on `topic_id` and `subject_id` with backfill verification |
| Downgrade path | ✅ | Migration 005 downgrade restores topic column, relaxes NOT NULL constraints |
| Alembic version | ✅ | `005_drop_topic_column` confirmed via `SELECT version_num FROM alembic_version` |

---

## DB Schema Verification (Live)

### questions table
```
0|id|INTEGER|1||1
1|exam_id|INTEGER|1||0
2|image_id|INTEGER|0||0
3|question_text|TEXT|1||0
4|extracted_text|TEXT|0||0
5|confidence_score|FLOAT|0||0
6|order_in_exam|INTEGER|0||0
7|is_corrected|BOOLEAN|1||0
8|correction_notes|TEXT|0||0
9|has_code_in_answers|BOOLEAN|1||0
10|created_at|DATETIME|1||0
11|updated_at|DATETIME|1||0
12|uuid|VARCHAR(36)|1||0
13|topic_id|INTEGER|1||0
```
- ✅ `topic` column: GONE
- ✅ `topic_id`: notnull=1 (NOT NULL enforced)

### exams table
```
0|id|INTEGER|1||1
1|partial_number|INTEGER|1||0
2|exam_date|DATE|0||0
3|topic_tags|TEXT|0||0
4|created_at|DATETIME|1||0
5|updated_at|DATETIME|1||0
6|uuid|VARCHAR(36)|1||0
7|subject_id|INTEGER|1||0
```
- ✅ `subject_id`: notnull=1 (NOT NULL enforced)

### alembic_version
```
005_drop_topic_column
```
- ✅ Correct migration version

---

## No-Regressions Check

| Feature | Status | Evidence |
|---------|--------|----------|
| OCR extraction | ✅ | QuestionService.create_question() resolves topic dynamically |
| Exam upload | ✅ | Existing import/export tests pass (17 tests) |
| Practice mode | ✅ | Dynamic topic filters in practice start page |
| JSON import/export | ✅ | Round-trip tests pass; dynamic topic resolution on import |
| Question listing | ✅ | Dynamic topic filter via `get_all_topics` dependency |
| Search | ✅ | SearchService joins topics table |

---

## New Issues Check

| Area | Status | Notes |
|------|--------|-------|
| Hybrid property replacement | ✅ No issues | Simple property works correctly; `__init__` gracefully handles deprecated `topic` kwarg |
| Exam creation flow | ✅ No issues | `subject_id` properly resolved and validated; NOT NULL enforced at DB level |
| Subject CRUD endpoints | ✅ No issues | PUT/DELETE properly handle edge cases (404, 409 slug conflict, 409 FK restrict) |
| Migration 005 safety | ✅ No issues | Backfill verification runs before destructive changes; downgrade path tested |
| Test stability | ✅ No issues | All 123 tests pass; no flaky or skipped tests |

---

## Issues

### CRITICAL

None.

### WARNING

None.

### SUGGESTION

**S1: Dynamic topic creation uses slug as name**
- `_resolve_or_create_topic()` creates topics with `name=topic_slug` (e.g., name="processes")
- Consider generating a display name or using the raw topic string from the import
- Non-blocking; cosmetic improvement

---

## Summary

All 6 findings from the initial verify (2 CRITICAL, 4 WARNING) are confirmed RESOLVED with real code and schema evidence:

1. **C1** — TopicEnum removed from models/schemas; deprecation comment added; string defaults used
2. **C2** — Migration 005 drops `questions.topic` column; NOT NULL enforced on `topic_id` and `subject_id`
3. **W1** — Exam creation accepts and validates `subject_id`; defaults to "sistemas-operativos"
4. **W2** — Both FK columns are NOT NULL at DB and model level
5. **W3** — Full CRUD for subjects: List, Get, Create, Update, Delete
6. **W4** — Scratch scripts in `.gitignore`; ruff passes clean

No new issues introduced. No regressions. All 123 tests pass. Ruff clean. Schema verified.
