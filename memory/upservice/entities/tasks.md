---
slug: tasks
title: Tasks
status: deep
source: public
fetched_at: 2026-08-13T22:05:03+03:00
product: upservice
---

Tasks support list (paginated, optional filters), create, get by ID, update, and soft-delete. Kinds are task, meeting, agreement, acquaintance, agreement_task, and ticket; required fields depend on kind. Attachments can be listed with optional source and content-type filters. Status, planned effort (estimation, minutes), and actual effort (worklog, minutes) have dedicated update endpoints. Agreement action, agreement steps, and agreement sheet apply to agreement or agreement_task; acquaintance sheet applies to an acquaintance task; co-responsibles apply to a meeting or acquaintance task.

## Fields

- `id` (`integer`, required)
- `title` (`string`, required): Task title
- `status` (`TaskStatus`, required): One of: todo, backlog, notassigned, progress, review, completed, cancelled, rejected, deleted, pending, outdated, ai, onhold
- `description` (`string | null`, optional): Task description. Omit to leave unchanged; use null to clear.
- `kind` (`TaskKind`, optional): Task type. Defaults to 'task'. One of: task, meeting, agreement, acquaintance, agreement_task, ticket.
- `author` (`TaskPerson | null`, optional): Object fields: id, first_name, last_name, is_active, note, position, is_guest, avatar_file.
- `responsible` (`TaskPerson | null`, optional): Object fields: id, first_name, last_name, is_active, note, position, is_guest, avatar_file.
- `controller` (`TaskPerson | null`, optional): Object fields: id, first_name, last_name, is_active, note, position, is_guest, avatar_file.
- `approving_manager` (`TaskPerson | null`, optional): Object fields: id, first_name, last_name, is_active, note, position, is_guest, avatar_file.
- `project` (`TaskProjectSummary | null`, optional): Project ID. Omit to leave unchanged; use null to detach the task from a project.
- `sprint` (`SprintResponse | null`, optional): Object fields: id, lag, title, status, date_end, date_start, tasks_count, created_at, completed_at.
- `created_at` (`string | null`, optional): ISO 8601 datetime (e.g. 2025-03-16T14:30:00Z)
- `completed_at` (`string | null`, optional): ISO 8601 datetime (e.g. 2025-03-16T14:30:00Z)
- `date_end` (`string | null`, optional): Due date (ISO 8601). Required for task, meeting, agreement, agreement_task; optional for ticket.
- `date_start` (`string | null`, optional): ISO 8601 datetime (e.g. 2025-03-16T14:30:00Z)
- `updated_at` (`string | null`, optional): ISO 8601 datetime (e.g. 2025-03-16T14:30:00Z)
- `estimation` (`number | null`, optional): Planned effort in minutes
- `estimation_total` (`integer | null`, optional)
- `work_log` (`integer | null`, optional)
- `work_log_total` (`integer | null`, optional)
- `parent` (`object | null`, optional): Parent task ID (subtask)
- `access_type` (`AccessType`, optional): Access type (agreement/acquaintance) One of: public, private, restricted.
- `location` (`string | null`, optional): Location (meeting)
- `location_exact` (`string | null`, optional): Exact location address (meeting)
- `coordinates` (`TaskCoordinates | null`, optional): Object fields: lat, lon.
- `complete_require` (`string | null`, optional): Completion requirement One of: link, media, comment, document, close-order.
- `agreement_sheet` (`integer | null`, optional)
- `task_info` (`TaskInfoResponse | null`, optional): Object fields: uuid, contact, channel_uuid, channel_name, channel_kind, thread_id, operator_sla, executor_sla, client_sla, sla_is_active.
- `chats` (`array<TaskChannelChat>`, optional): Linked channel chats (room UUID, channel, etc.). Filled when Upservice returns full task payload; empty on list if backend omits it. Object fields: id, uuid, channel_uuid, channel_name, channel_kind, channel_source, channel_is_active, source, phone, telegram_username, email, status, created_at, last_message_at, is_paid, allow_ai_support, allow_ticket_support, is_group_chat, subgroup_chat_id, group_chat_id.
- `responsible_departments` (`array<integer> | null`, optional): Department IDs (task/agreement_task only; mutually exclusive with responsible)
- `file_list` (`array<integer | string> | null`, optional): Files to attach or update. Each item is an existing attachment ID (int) or an uploaded file UUID (str) from POST /v1/files/. Omit to leave unchanged.
- `co_responsibles` (`array<integer> | null`, optional): Co-responsible employee IDs (meeting attendees / acquaintance participants)
- `members` (`array<integer> | null`, optional): Task member employee IDs
- `agreement_steps` (`array<array> | null`, optional): Agreement approval steps: list of employee ID groups (agreement)
- `send_logs_to_contact` (`integer | null`, optional): Contact ID to send work logs to

Related resource fields (not on the main task payload):

- `action` (`AgreementAction`, required) on PUT agreement-action: One of: progress, approved, rejected.
- `rejection_reason` (`string | null`, optional) on PUT agreement-action: Required when action is rejected.
- `reason` (`string | null`, optional) on PUT status: Cancellation reason (required when status is 'cancelled')
- `value` (`integer`, required) on POST worklog: Actual effort in minutes
- `estimation` (`integer`, required) on PUT estimation: Planned effort in minutes
- acquaintance-sheet: `status` (`string`, required); `attachments` (`array<TaskAttachmentResponse>`, optional) object fields id, file_id, title, mime_type, file_size, created_at, preview_file_url; `steps` (`array<AcquaintanceSheetStep>`, optional) object fields status, responsible, date.
- agreement-sheet: `status` (`string`, required); `attachments` (`array<TaskAttachmentResponse>`, optional) same attachment object fields; `steps` (`array<AgreementSheetStep>`, optional) object fields step, status, employee, agreement_date, rejection_reason.
- agreement-steps GET: `employees` (`array<AgreementStepEmployee>`, optional) object fields id, first_name, last_name, is_active, note, position, is_guest, avatar_file, is_edit; `is_edit` (`boolean`, optional).
- attachments GET: `id` (`integer | string`, required); `file_id` (`string | null`, optional); `title` (`string | null`, optional); `mime_type` (`string | null`, optional); `file_size` (`integer`, optional); `created_at` (`string(date-time) | null`, optional); `preview_file_url` (`string | null`, optional). Query: `source` (`TaskAttachmentSource`, optional) one of all, entity; `content_type` (`TaskAttachmentContentType | null`, optional) one of media, docs, links; `limit`/`offset` (`integer`, optional).
- co-responsibles GET person rows: `id` (`integer`, required); `first_name`, `last_name`, `note`, `position` (`string | null`, optional); `is_active`, `is_guest` (`boolean`, optional); `avatar_file` (`object | null`, optional).
- list GET query: `limit`, `offset` (`integer`, optional); `kind` (`TaskKind | null`, optional); `project` (`array<integer> | null`, optional); `author`, `responsible` (`integer | null`, optional); `created_at_gte`/`lte`, `completed_at_gte`/`lte`, `date_end_gte`/`lte`, `date_start_gte`/`lte` (`string(date-time) | null`, optional); `tags_condition` (`TagsListCondition | null`, optional) one of contains_any, contains_all, not_contain_all, untagged, any; `tags_ids` (`array<string> | null`, optional).

## Relations

- [channels](channels.md)
- [employees](employees.md)
- [files](files.md)
- [projects](projects.md)
- [sprints](sprints.md)
- [tags](tags.md)

## Missing

- PUT `/v1/tasks/{task_id}/estimation` lists only the request field `estimation`; no response schema in the incoming draft.
- POST `/v1/tasks/{task_id}/worklog` lists only the request field `value`; no response schema in the incoming draft.
- Empty descriptions in the source for `id`, `estimation_total`, `work_log`, `work_log_total`, and `agreement_sheet`.
