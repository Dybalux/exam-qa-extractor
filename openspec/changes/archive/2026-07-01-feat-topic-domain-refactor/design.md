# Design: Topic Domain Refactoring

Technical design for transitioning from hardcoded OS topics to database-backed dynamic Subjects and Topics in the exam study system.

## Technical Approach

We will replace the static `TopicEnum` with `Subject` and `Topic` tables. A `Subject` represents a course (e.g., "Sistemas Operativos"), and has many `Topic`s. A `Topic` holds a name and a unique slug. The `Question` model's string `topic` column will be refactored to a `topic_id` foreign key referencing the `topics` table. To minimize changes to API responses and frontend templates, `Question.topic` is kept as a property returning the topic's slug.

## Architecture Decisions

| Option | Tradeoffs | Decision |
| :--- | :--- | :--- |
| **Topic access on Question** | Property returning slug string vs. removing the field in favor of relationship. | **Property**: Keeps frontend templates and serialization schemas unmodified and backward compatible. |
| **Slug validation / resolution** | DB-level unique constraint vs. Service-level checks. | **Both**: Validate name slugification and unique slugs at API schema/service level; enforce via unique database index. |
| **Topic lookup on batch import** | Eager bulk select of topics in O(1) vs. fetching topic on each record (N+1 queries). | **Bulk select**: Fetch all topic slugs into a Python dict at start of import to avoid N+1 queries. |

## Data Flow

```
[YAML Seed File] ──(db seed)──→ [Subject & Topic Tables]
                                      │
[New Question / Import] ──(resolve slug)──→ [questions.topic_id]
                                      │
[Frontend / API Response] ←─(property: topic.slug)── [question.topic]
```

## File Changes

| File | Action | Description |
|---|---|---|
| `app/models/subject.py` | Create | Defines the `Subject` model. |
| `app/models/topic.py` | Create | Defines the `Topic` model and automatic slug generation logic. |
| `app/models/question.py` | Modify | Replaces `topic` field with `topic_id` foreign key, adds `topic_relation` relationship, and exposes `topic` property. |
| `app/core/slug.py` | Create | Shared utility function for converting string to clean URL slug. |
| `app/db/init_db.py` | Modify | Implements YAML seed loader using PyYAML to populate default subjects and topics. |
| `app/services/question_service.py` | Modify | Adapts CRUD operations to look up and validate topic using DB topics instead of `TopicEnum`. |
| `app/services/search_service.py` | Modify | Adjusts searches to join the `topics` table and filter by `Topic.slug`. |
| `app/services/json_io_service.py` | Modify | Pre-fetches all topics to resolve slugs to ids in import flow, avoiding N+1 queries. |
| `app/schemas/subject.py` | Create | Defines Subject Pydantic schemas (`SubjectCreate`, `SubjectResponse`). |
| `app/schemas/topic.py` | Create | Defines Topic Pydantic schemas (`TopicCreate`, `TopicResponse`). |
| `app/api/v1/endpoints/subjects.py` | Create | New endpoints for managing subjects and topics dynamically. |

## Interfaces / Contracts

```python
# app/core/slug.py
import re
import unicodedata

def slugify(value: str) -> str:
    """Normalize and convert string to a URL-friendly slug."""
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\\w\\s-]', '', value).strip().lower()
    return re.sub(r'[-\\s]+', '-', value)
```

```python
# app/schemas/topic.py
from pydantic import BaseModel, Field

class TopicCreate(BaseModel):
    name: str = Field(..., min_length=1)
    slug: str | None = None  # Auto-generated if not provided

class TopicResponse(BaseModel):
    id: int
    name: str
    slug: str
    subject_id: int
```

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Migration | Schema upgrades/downgrades and backfills | Private transaction tests in pytest verifying migration doesn't orphan or lose existing question topics. |
| Unit | Custom slugification & collision detection | Unit tests for helper and validation logic. |
| Integration | REST API end-to-end import and CRUD | Test bulk import and CRUD endpoints mapping dynamic topics. |

## Migration / Rollout

The SQLite database migration is performed using Alembic:
1. **Upgrades**: Create `subjects` and `topics` tables. Seed "Sistemas Operativos" (Subject) and existing `TopicEnum` values (Topics). Add `topic_id` column to `questions` as nullable. Backfill `questions.topic_id` matching `questions.topic` to new topic IDs. Enforce `questions.topic_id` NOT NULL and drop `questions.topic` column.
2. **Downgrades**: Add `questions.topic` column. Populate from `topics.slug` using join. Enforce `topic` column NOT NULL and drop `questions.topic_id` column. Drop `topics` and `subjects` tables.

## Open Questions

None.
