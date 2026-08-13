---
slug: projects
title: Projects
status: deep
source: public
fetched_at: 2026-08-13T22:10:24+03:00
product: upservice
---

Projects support list (paginated, optional filters), create, get by ID, update of title and description, and soft-delete (204, no body). Managers and members are employee IDs on create; list and get responses use ProjectPerson objects for managers and assignments. Dedicated POST endpoints replace managers or members and guests by employee IDs; changing members returns an Employee array rather than ProjectResponse. PUT completed marks a project as completed. Status is one of active, completed, or deleted.

## Fields

- `id` (`integer`, required)
- `title` (`string`, required): Project title. Create: string, maxLength 512, required. Update: string maxLength 512 or null, optional.
- `description` (`string | null`, optional): Description (plain text). Create: string, maxLength 5200, required. Update: string maxLength 5200 or null, optional. Response: string or null.
- `description_text` (`string | null`, optional)
- `managers` (`array<ProjectPerson>`, optional): Create request: array of integer employee IDs (managers), minItems 1, required. Response: array of ProjectPerson (object fields: id, first_name, last_name, is_active, note, position, is_guest, avatar_file).
- `members` (`array<integer>`, required): Employee IDs (members and guests). Create request only; minItems 1. Not on ProjectResponse (response uses assignments).
- `assignments` (`array<ProjectPerson>`, optional): Response only. Object fields: id, first_name, last_name, is_active, note, position, is_guest, avatar_file.
- `sprints_count` (`integer`, optional): Default 0.
- `tasks_active_count` (`integer | null`, optional)
- `tasks_backlog_count` (`integer | null`, optional)
- `status` (`ProjectStatus`, required): One of: active, completed, deleted.
- `created_at` (`string | null`, optional)
- `permissions` (`object | null`, optional): Map of permission name to boolean.
- `employees` (`array<integer>`, required): Employee IDs. POST `/v1/projects/{project_id}/managers`: who will become project managers (minItems 1). POST `/v1/projects/{project_id}/members`: members and guests, replaces membership set (minItems 1).

Related resource fields (not on the main project payload):

- list GET query: `limit` (`integer`, optional, page size, default 25, min 1, max 100); `offset` (`integer`, optional, default 0); `status` (`array<ProjectStatus> | null`, optional); `tags_condition` (`TagsListCondition | null`, optional) one of contains_any, contains_all, not_contain_all, untagged, any; `tags_ids` (`array<string(uuid)> | null`, optional, tag UUIDs, repeat parameter for multiple values).
- list GET wrapper GetProjectsResponse: `count` (`integer`, required); `next` (`string | null`); `previous` (`string | null`); `results` (`array<ProjectResponse>`, required). POST 201 body is ProjectResponse.
- path: `project_id` (`integer`, required) on `/v1/projects/{project_id}` and nested managers, members, and completed paths.

## Relations

- [employees](employees.md)
- [sprints](sprints.md)
- [tags](tags.md)
- [tasks](tasks.md)

## Missing

- PUT `/v1/projects/{project_id}/completed` has an empty 200 response schema and no request body in OpenAPI.
- Empty descriptions in the source for `id`, `description_text`, `tasks_active_count`, `tasks_backlog_count`, and `created_at`.
