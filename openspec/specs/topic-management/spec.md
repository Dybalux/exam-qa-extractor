## Domain: topic-management (New Capability)

### Purpose
Manage Topic database entities, including CRUD operations, seeding, and dynamic generation.

### Requirements

#### Requirement: REQ-TOPIC-1 (Topic Seeding)
The system MUST seed Topic records under their parent Subject using definitions specified in the seed YAML file.

##### Scenario: Seeding Topics from YAML
- GIVEN a seeded Subject record in the database
- WHEN database initialization processes the topics in the YAML file
- THEN each Topic MUST be persisted and linked to its parent Subject

#### Requirement: REQ-TOPIC-2 (Dynamic Topic Creation)
The system SHALL support the on-the-fly resolution and creation of Topic entities when requested by external services.

##### Scenario: Resolve or Create Topic
- GIVEN a topic display name and a default parent Subject
- WHEN a resolution request is made for a non-existing topic
- THEN a new Topic record MUST be created with a slugified version of the display name
