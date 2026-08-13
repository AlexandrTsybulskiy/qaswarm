---
slug: sprints
title: Sprints
status: deep
source: public
fetched_at: 2026-08-13T22:13:27+03:00
product: upservice
---

Sprints support list (paginated, optional filters), create in a project, get by ID, update of title and dates, and soft-delete (204, no body). Dedicated POST endpoints complete or activate a sprint (no request body; 200 body is SprintResponse). Tasks are added by task IDs. Status is one of active, planned, completed, or deleted.

## Fields

- `id` (`integer`, required): Sprint id. Response only (SprintResponse).
- `lag` (`integer`, optional): Default 0. Response only (SprintResponse).
- `title` (`string`, required): Sprint title. Create: string, maxLength 1024, required. Update: string maxLength 1024 or null, optional. Response: string, required.
- `status` (`SprintStatus`, required): One of: active, planned, completed, deleted. Response only (SprintResponse).
- `date_end` (`string | null`, required): End date (YYYY-MM-DD). Create: string, required. Update: string or null, optional. Response: string or null.
- `date_start` (`string | null`, required): Start date (YYYY-MM-DD). Create: string, required. Update: string or null, optional. Response: string or null.
- `tasks_count` (`integer`, optional): Default 0. Response only (SprintResponse).
- `created_at` (`string | null`, optional): Response only (SprintResponse).
- `completed_at` (`string | null`, optional): Response only (SprintResponse).
- `project` (`integer`, required): Project ID. Create request only (CreateSprintRequest).
- `tasks` (`array<integer>`, required): Task IDs to add to the sprint. POST `/v1/sprints/{sprint_id}/add-tasks` request: array of integer, minItems 1, required. Response: array of integer, required.

Related resource fields (not on the main sprint payload):

- list GET query: `limit` (`integer`, optional, page size, default 25, min 1, max 100); `offset` (`integer`, optional, default 0); `project` (`array<integer> | null`, optional, filter by project ID, repeat for multiple); `status` (`array<SprintStatus> | null`, optional, filter by sprint status; one of active, planned, completed, deleted); `is_lag` (`boolean | null`, optional; True: only delayed sprints; False: on-time sprints).
- list GET wrapper GetSprintsResponse: `count` (`integer`, required); `next` (`string | null`); `previous` (`string | null`); `results` (`array<SprintResponse>`, required). POST 201 body is SprintResponse.
- path: `sprint_id` (`integer`, required) on `/v1/sprints/{sprint_id}` and nested complete, activate, and add-tasks paths.

## Relations

- [projects](projects.md)
- [tasks](tasks.md)

## Missing

- Incoming draft listed no fetch errors for this slug.
