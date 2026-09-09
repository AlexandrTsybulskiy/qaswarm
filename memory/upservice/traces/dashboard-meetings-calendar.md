---
slug: dashboard-meetings-calendar
title: Виджет встреч на личном дашборде (сегодня/завтра)
product: upservice
task_id: none
requirement: none
status: ready
fetched_at: 2026-09-09T12:00:00+03:00
source: code
---

## Summary

На личном дашборде (вкладка Feed/notifications) виджет встреч — это `MeetingsWidget`: табы «сегодня»/«завтра», список до 3 ближайших calendar-записей текущего employee за окно today→tomorrow end-of-day. Данные грузятся через Redux `fetchEmployeeRecords` → `POST .../calendar/record-attendees/`; клиентская фильтрация в `filterAndSortUpcomingMeetings` (день таба, ещё не закончившиеся, только с linked task, без google-only). Участники подтягиваются из attendees списка или через `fetchOneEmployeeRecord`.

## Backend

- none (поиск только frontend по запросу)

## Frontend

- `frontend:src/components/dashboard-view/views/notifications/index.js:60` — mount: рендерит `MeetingsWidget` в ряду виджетов личного дашборда
- `frontend:src/components/dashboard-view/views/notifications/widgets/MeetingsWidget/MeetingsWidget.tsx:23` — component: `WidgetCard` с toggle TODAY/TOMORROW, список `MeetingRow`, ссылка на calendar view
- `frontend:src/components/dashboard-view/views/notifications/widgets/MeetingsWidget/useUpcomingMeetings.ts:34` — hook: employeeId из workspace, fetch диапазона dateStart=startOfToday…dateEnd=endOfTomorrow, refresh через DashboardWidgetsRefresh
- `frontend:src/components/dashboard-view/views/notifications/widgets/MeetingsWidget/upcomingMeetingsUtils.ts:16` — util: `getDayByTab` (today vs +1 day)
- `frontend:src/components/dashboard-view/views/notifications/widgets/MeetingsWidget/upcomingMeetingsUtils.ts:128` — util: `filterAndSortUpcomingMeetings` (ongoing/upcoming, same day, linked task, sort, slice 3)
- `frontend:src/components/dashboard-view/views/notifications/widgets/MeetingsWidget/useUpcomingMeetings.types.ts:1` — types: `TMeetingsDayTabValues` today/tomorrow, record/participant shapes
- `frontend:src/components/dashboard-view/views/notifications/widgets/MeetingsWidget/MeetingRow/MeetingRow.tsx:28` — component: строка встречи (время, title→task details, join URL, avatars)
- `frontend:src/store/calendar/actions.js:200` — store thunk: `fetchEmployeeRecords` → `apiV1.calendar.fetchEmployeeRecords`
- `frontend:src/store/calendar/actions.js:241` — store thunk: `fetchOneEmployeeRecord` (детали attendees при пустом списке)
- `frontend:src/api/v1/calendar.js:94` — API client: POST `/v1/{workspaceId}/calendar/record-attendees/`
- `frontend:src/api/v1/calendar.js:114` — API client: GET `/v1/{workspaceId}/calendar/record-attendees/{id}/`

## API alignment

Клиент вызывает calendar employee-record endpoints (не public_api catalog paths найдены в `catalog/api.md` для `record-attendees`):

- list: `POST /v1/{workspaceId}/calendar/record-attendees/` с body `employee`, query `date_start` / `date_end` / `limit`
- detail: `GET /v1/{workspaceId}/calendar/record-attendees/{id}/`

Backend handlers не искались (frontend-only trace).

## Gaps

- i18n-ключи Dashboard (`Meetings`, `TodayBtn`, `TomorrowBtn`, …) не сверены с файлами локалей (путь locales не найден под `src/`).
- Полный dashboard calendar view (`views/calendar/`) и tasks `MeetingCalendar` — соседние фичи, не сам виджет «сегодня/завтра».
- Не проверено, фильтрует ли backend уже kind=meeting или отдаёт все record-attendees (клиент режет по `relation.type === task` и `!isGoogleOnlyRecord`).

Did not modify product repositories.
