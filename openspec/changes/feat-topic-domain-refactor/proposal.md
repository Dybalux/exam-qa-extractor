# Proposal: Topic Normalization Refactoring

## Intent
Normalize the domain schema by replacing the static `TopicEnum` and denormalized exam `topic_tags` string with dynamic `Subject` and `Topic` database entities. This supports multiple subjects (starting with "Sistemas Operativos"), dynamic topic management, and structured question classifications.

## Scope

### In Scope
- Database schema migration introducing `subjects` and `topics` tables.
- Model classes `Subject` and `Topic` with relationships: Exam N:1 Subject, Question N:1 Topic, Subject 1:N Topic.
- Data migration script/Alembic backfilling existing exams to default subject and questions to corresponding topics.
- YAML seeding capability (using `operating_systems.yaml`) defining subjects and topics.
- Updating `JsonIOService` to handle legacy JSON (v1.0) imports by dynamically creating missing topics under the default subject.
- Updating API schemas (`QuestionCreate`, `QuestionResponse`, etc.) and page routes to resolve/expose topics dynamically.

### Out of Scope
- Frontend UI for creating/deleting subjects or topics (rely on YAML seeds and dynamic imports).
- Support for multiple subjects in the legacy import file shape (legacy format remains bound to "sistemas-operativos").

## Capabilities

### New Capabilities
- `subject-management`: CRUD and seed capability for subjects.
- `topic-management`: CRUD and seed capability for topics, with dynamic creation logic for imports.

### Modified Capabilities
- `exam-management`: Add strict N:1 association with `Subject`.
- `question-extraction`: Classify questions under database `Topic` entities instead of static enums.
- `import-export`: Parse legacy JSON v1.0, matching raw topics and dynamically creating missing ones.

## Approach
1. **Models**: Add `Subject` and `Topic` SQLAlchemy models. Add FKs to `Exam` (`subject_id`) and `Question` (`topic_id`).
2. **YAML Seeds**: Implement a YAML loader in `app/db/init_db.py` to parse seed definitions using `slug` and `display_name` only.
3. **Migration**: Alembic migration creating tables, seeding default "Sistemas Operativos" (slug: `sistemas-operativos`), and backfilling existing DB rows.
4. **Service Integration**:
   - `JsonIOService`: Map legacy topic string to database `Topic`. If not found, dynamically create `Topic` with generated slug.
   - `QuestionService`: Resolve topic strings/slugs to `topic_id`.
5. **API & Templates**: Return topic slug for `QuestionResponse.topic`. Update template context to query dynamic topics.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/models/` | Modified | Add `subject.py`, `topic.py`; modify `exam.py`, `question.py`. |
| `app/db/init_db.py` | Modified | Add seed loader for YAML. |
| `app/core/constants.py` | Modified | Deprecate `TopicEnum`. |
| `app/services/` | Modified | Update `json_io_service.py` and `question_service.py` to use dynamic topics. |
| `app/schemas/` | Modified | Adapt `json_io.py` and `question.py` to support legacy shape and dynamic lookups. |
| `app/api/pages.py` | Modified | Fetch and render topics dynamically. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Import fails on duplicate slug creation | Low | Ensure slug generation is deterministic and sanitized (e.g. lowercase, alphanumeric + hyphens). |
| Migration lock on SQLite | Med | Run migration inside a single atomic transaction with backup. |

## Rollback Plan
Run alembic downgrade to revert schema changes. Restore database from pre-migration backup database file.

## Dependencies
- PyYAML (already in dependencies or needs to be added).

## Success Criteria
- [ ] Seeds populate `subjects` and `topics` tables from YAML.
- [ ] Existing questions and exams successfully migrated to new schemas.
- [ ] Legacy JSON imports succeed, dynamically creating unrecognized topics.
- [ ] API endpoints and page routes function correctly without regression.
