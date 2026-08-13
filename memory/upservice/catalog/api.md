# API catalog

Fetched at: `2026-08-13T21:51:37+03:00`
Channel: `public`
Base URL: `https://public.upservice.io/`

| Resource | Methods | Channel | Entity | fetched_at |
|----------|---------|---------|--------|------------|
| `/v1/files/{channel_unique_identifier}/` | POST | public | [external-channels](../entities/external-channels.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/files/{channel_unique_identifier}/{file_id}/url` | GET | public | [external-channels](../entities/external-channels.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/channels/messages` | GET, POST | public | [channels](../entities/channels.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/channels/messages/{channel_id}/chat/{room_uuid}/` | POST | public | [channels](../entities/channels.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/channels/messages/{channel_unique_identifier}/` | POST | public | [external-channels](../entities/external-channels.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/channels/messages/{channel_unique_identifier}/chat/{room_uuid}/` | GET | public | [external-channels](../entities/external-channels.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/files/` | POST | public | [files](../entities/files.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/files/{file_id}/url` | GET | public | [files](../entities/files.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/employees` | GET | public | [employees](../entities/employees.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/projects` | GET, POST | public | [projects](../entities/projects.md) | 2026-08-13T22:10:24+03:00 |
| `/v1/projects/{project_id}` | GET, PUT, DELETE | public | [projects](../entities/projects.md) | 2026-08-13T22:10:24+03:00 |
| `/v1/projects/{project_id}/managers` | POST | public | [projects](../entities/projects.md) | 2026-08-13T22:10:24+03:00 |
| `/v1/projects/{project_id}/members` | POST | public | [projects](../entities/projects.md) | 2026-08-13T22:10:24+03:00 |
| `/v1/projects/{project_id}/completed` | PUT | public | [projects](../entities/projects.md) | 2026-08-13T22:10:24+03:00 |
| `/v1/sprints` | GET, POST | public | [sprints](../entities/sprints.md) | 2026-08-13T22:13:27+03:00 |
| `/v1/sprints/{sprint_id}` | GET, PUT, DELETE | public | [sprints](../entities/sprints.md) | 2026-08-13T22:13:27+03:00 |
| `/v1/sprints/{sprint_id}/complete` | POST | public | [sprints](../entities/sprints.md) | 2026-08-13T22:13:27+03:00 |
| `/v1/sprints/{sprint_id}/activate` | POST | public | [sprints](../entities/sprints.md) | 2026-08-13T22:13:27+03:00 |
| `/v1/sprints/{sprint_id}/add-tasks` | POST | public | [sprints](../entities/sprints.md) | 2026-08-13T22:13:27+03:00 |
| `/v1/tags` | GET, POST | public | [tags](../entities/tags.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/tags/{tag_id}` | PUT, DELETE | public | [tags](../entities/tags.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/tags/assign` | POST | public | [tags](../entities/tags.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/tags/assign/{entity_type}/{entity_id}/{tag_id}` | DELETE | public | [tags](../entities/tags.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/tasks` | GET, POST | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/tasks/{task_id}` | GET, PATCH, DELETE | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/tasks/{task_id}/attachments` | GET | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/tasks/{task_id}/status` | PUT | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/tasks/{task_id}/estimation` | PUT | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/tasks/{task_id}/worklog` | POST | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/tasks/{task_id}/agreement-action` | PUT | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/tasks/{task_id}/agreement-steps` | GET | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/tasks/{task_id}/co-responsibles` | GET | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/tasks/{task_id}/agreement-sheet` | GET | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/tasks/{task_id}/acquaintance-sheet` | GET | public | [tasks](../entities/tasks.md) | 2026-08-13T22:05:03+03:00 |
| `/v1/directories` | GET, POST | public | [directories](../entities/directories.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/directories/{directory_id}` | GET, PUT, DELETE | public | [directories](../entities/directories.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/directory-records` | GET, POST | public | [directories](../entities/directories.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/directory-records/{record_id}` | GET, PATCH, DELETE | public | [directories](../entities/directories.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/directory-records/{record_id}/relations` | GET | public | [directories](../entities/directories.md) | 2026-08-13T21:51:37+03:00 |
| `/v1/directory-records/{record_id}/relations/bulk-update` | POST | public | [directories](../entities/directories.md) | 2026-08-13T21:51:37+03:00 |
