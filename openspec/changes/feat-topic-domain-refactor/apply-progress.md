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

## Status
Phase 1 (9 tasks) + Phase 2 (6 tasks) all complete. All 106 tests pass, zero lint issues.
Ready for Phase 3 (API & Pages).
