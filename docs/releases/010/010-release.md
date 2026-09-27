# Easy MCF Version 0.1.0

## About

Easy MCF streamlines the job search and application process for job seekers in Singapore using MyCareersFuture. The release runs locally and keeps all user data on the machine that hosts the app. The app includes a Flask backend, a SQLite database, and a vendored AngularJS frontend served from the same origin.

## Release notes

This release is the initial local Proof of Concept for Easy MCF. It is intended for local use on a clean machine and for demonstration and validation within the repo's seeded data model. The app supports an end-to-end workflow from profile setup and session handling through keyword search, lead management, and batch application follow-up.

## As-built scope

The `0.1.0` release covers the local development environment, schema seed data, validation utilities, job-lead tracking, OAuth login, MCF website session handling, keyword search, and apply automation.

| id | feature              | 
| -- | -------------------- | 
| 07 | local dev env        | 
| 08 | schema seed data     | 
| 12 | validation utilities | 
| 09 | job leads tracking   |
| 13 | OAuth login          |
| 17 | MCF website session  | 
| 10 | search by keywords   |
| 11 | apply automation     | 

Features 14, 15, and 16 were moved to release `020` and are listed in the `020` milestones tracker.

## Documentation

- Site: https://yayfalafels.github.io/easymcf/
- Developer guide: [../../developer-guide/index.md](../../developer-guide/index.md)
- User guide: [../../user-guide/index.md](../../user-guide/index.md)







