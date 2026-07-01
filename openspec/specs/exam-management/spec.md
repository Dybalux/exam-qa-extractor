## Domain: exam-management (Modified Capability)

### Purpose
Link Exam entities to Subject entities under a strict N:1 relationship.

### Requirements

#### Requirement: REQ-EXAM-1 (Subject Linkage)
Every Exam entity MUST have a non-nullable relationship to a Subject entity via a foreign key `subject_id`.
(Previously: Exams were independent entities with no direct Subject association.)

##### Scenario: Enforce Subject on Exam Creation
- GIVEN a valid Subject record
- WHEN an Exam is created or updated
- THEN the system MUST associate the Exam with the specified `subject_id` and fail if it is null

#### Requirement: REQ-EXAM-2 (Legacy Exam Backfill)
The database migration script MUST backfill all existing Exam records to point to a default Subject slugged "sistemas-operativos".
(Previously: Existing Exam records lacked any subject association.)

##### Scenario: Migration Backfills Existing Exams
- GIVEN existing Exam records in the database
- WHEN the schema migration is applied
- THEN all existing Exam records MUST be updated with a foreign key pointing to the default Subject
