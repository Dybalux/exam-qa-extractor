## Domain: question-extraction (Modified Capability)

### Purpose
Link Question entities to dynamic Topic database entities instead of static enums.

### Requirements

#### Requirement: REQ-QEXT-1 (Database Topic Association)
Each Question entity MUST be linked to a Topic entity via a foreign key `topic_id` instead of a static string/enum.
(Previously: Questions referenced a static string/enum `TopicEnum` for topic classification.)

##### Scenario: Classify Question under Topic
- GIVEN a valid Topic database record
- WHEN a Question is extracted or saved
- THEN the Question record MUST store the correct `topic_id` corresponding to the Topic

#### Requirement: REQ-QEXT-2 (Deprecate TopicEnum)
The static `TopicEnum` class and references to it in schemas and service layers SHALL be deprecated and removed.
(Previously: API models and database queries imported and validated topics using `TopicEnum`.)

##### Scenario: API Schema Validates Topic Slug
- GIVEN an API request to extract or update a question
- WHEN the request payload is validated
- THEN the question's topic MUST be resolved dynamically against database topics rather than a static enum
