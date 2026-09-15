-- Easy MCF POC local — schema (ARCH-STO-02, single hand-maintained file, no migrations).
--
-- Milestone 07 (local dev/test env) owns only the `meta` table below — enough for
-- scripts/envcheck.py's schema_version check and scripts/resetdb.py's reset flow to
-- have something real to apply. The full data model (role, track, search_profile, cv,
-- post, post_track, lead, lead_event, application, run_log, session — ARCH-STO-01) is
-- milestones 09-11's build-out, added to this same file as those milestones land.
--
-- Bump `schema_version` by hand whenever this file changes (ARCH-STO-03); the backend
-- refuses to start on a mismatch rather than failing later with an obscure SQL error.

CREATE TABLE meta (
    schema_version INTEGER NOT NULL
);

INSERT INTO meta (schema_version) VALUES (1);
