# Tasks: Topic Normalization Refactoring (feat-topic-domain-refactor)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 600-800 lines |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Foundation) → PR 2 (Core & Services) → PR 3 (API & Pages) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Create Subject and Topic models, schemas, and slug utility. | PR 1 | Base branch: main; tests/docs included |
| 2 | DB migration, YAML seeding, and question/search service refactoring. | PR 2 | Base branch: PR 1 branch |
| 3 | Subject API endpoints and frontend page router/templates. | PR 3 | Base branch: PR 2 branch |

## Phase 1: Models & Core Foundation (PR 1)

- [x] 1.1 Create `app/core/slug.py` implementing `slugify(value: str) -> str` for URL-friendly slugs.
- [x] 1.2 Create `app/models/subject.py` with `Subject` table (`id`, `uuid`, `name`, `slug`).
- [x] 1.3 Create `app/models/topic.py` with `Topic` table (`id`, `uuid`, `name`, `slug`, `subject_id`).
- [x] 1.4 Modify `app/models/question.py` to add `topic_id` foreign key, `topic_relation` relationship, and `topic` property returning `topic_relation.slug`.
- [x] 1.5 Modify `app/models/exam.py` to add `subject_id` foreign key and `subject` relationship.
- [x] 1.6 Update `app/models/__init__.py` to expose `Subject` and `Topic` models.
- [x] 1.7 Create `app/schemas/subject.py` defining `SubjectCreate` and `SubjectResponse` Pydantic models.
- [x] 1.8 Create `app/schemas/topic.py` defining `TopicCreate` and `TopicResponse` Pydantic models.
- [x] 1.9 Write unit tests in `tests/models/test_subject_topic.py` to verify slug generation and models relationships.

## Phase 2: DB Migrations, Seeding & Services (PR 2)

- [x] 2.1 Create an Alembic migration script in `app/db/migrations/versions/` implementing schema changes, seeding default subject/topics, and backfilling `exam.subject_id` and `question.topic_id`.
- [x] 2.2 Update `app/db/init_db.py` to seed `Subject` and `Topic` records from `app/db/seeds.yaml` (using PyYAML).
- [x] 2.3 Refactor `QuestionService` in `app/services/question_service.py` to look up/validate `Topic` records dynamically.
- [x] 2.4 Refactor `SearchService` in `app/services/search_service.py` to join `topics` table and filter by `Topic.slug`.
- [x] 2.5 Refactor `JsonIOService` in `app/services/json_io_service.py` to pre-fetch topics and dynamically resolve them in legacy import/export flows.
- [x] 2.6 Write service integration tests in `tests/test_topic_services.py` to verify CRUD operations, search filters, and import/export flows.

## Phase 3: REST API & Pages Integration (PR 3)

- [ ] 3.1 Create `app/api/v1/endpoints/subjects.py` exposing CRUD endpoints for subjects/topics.
- [ ] 3.2 Register endpoints in `app/api/__init__.py` or main router.
- [ ] 3.3 Refactor `app/api/pages.py` to query dynamic topics for dashboard/exam filters.
- [ ] 3.4 Update Jinja2 HTML templates under `app/templates/` to list topics dynamically instead of using hardcoded values.
- [ ] 3.5 Write integration tests in `tests/api/test_subject_endpoints.py` to verify REST API calls and page rendering.
