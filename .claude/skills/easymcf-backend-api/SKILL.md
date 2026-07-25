---
name: easymcf-backend-api
description: Domain knowledge for easymcf's backend/data platform (REQ-PLAT-01..04) — the generic schema-validated CRUD endpoint pattern, SQLite as the single data store, and run-logging requirements. Use when implementing or reviewing Flask routes, the database layer, or run/execution logging.
---

# Backend / data platform

Implements [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Backend / data platform" section (REQ-PLAT-01..04).

## Generic CRUD, not bespoke endpoints per feature

Per `mcfpipe`'s Database API design (reference, not a fixed spec — see [010-prototype.md](../../../docs/releases/010/010-prototype.md)), expose one schema-validated CRUD interface per entity/table rather than a bespoke endpoint per feature:

```
GET    /{table}/{id}
PUT    /{table}/{id}
DELETE /{table}/{id}
POST   /{table}
POST   /{table}/batch
GET    /{table}/search
POST   /{table}/delete
```

Validate each request against the entity's schema. `mcfpipe/docs/validation.md`'s documented test cases are a useful checklist even though its implementation (DynamoDB-backed) doesn't carry forward: required-field enforcement (400 + field name), type validation, strict date-format validation, and 404 with a descriptive message for a missing record or unknown table name.

## Runtime shape (REQ-PLAT-01)

Plain local Python process (Flask reference), not behind API Gateway/Lambda or any request-routing indirection — this is a `flask run`-equivalent process the user starts locally. See the [Flask quickstart](https://flask.palletsprojects.com/en/stable/quickstart/) for routing/request-handling basics if unfamiliar with the framework.

## Storage (REQ-PLAT-02)

All domain data — postings, leads, tracks/search profiles, match scores, run history — lives in one local SQLite database. This replaces Google Sheets as *both* config store and data store (the prototype's coupling this release specifically removes); don't reintroduce a second config file/sheet as a parallel source of truth for anything that belongs in the schema.

## Run logging (REQ-PLAT-03)

Every automated run (search, scoring, apply) must log start/end time, outcome counts, and any errors durably (a database table, not `print`/bare `except`) — a failure must be diagnosable from the log without re-running the operation. This is the fix for the prototype's biggest observability gap; see [webscraping](../webscraping/SKILL.md)'s note on not swallowing per-record failures silently.

## No cloud dependency (REQ-PLAT-04)

The whole system runs on the user's machine. Don't add a cloud SDK, credential file, or network call to an external service as part of this feature area — cloud deployment is explicitly out of scope for `010` (see [010-claude-agent.md](../../../docs/releases/010/010-claude-agent.md) out-of-scope section).
