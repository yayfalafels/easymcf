-- Easy MCF POC local - schema (ARCH-STO-02, single hand-maintained file, no migrations).
-- schema_version 2 adds the release-010 data model to the milestone-07 base.
-- schema_version 3 adds `user`, `match_score`, `lead_note`, and explicit `user_id`
-- ownership columns on `track`/`cv`/`session` (see docs/releases/010/design/010-data-model.md).
-- schema_version 4 adds `search_schedule` and `field_edited` in lead_event.event_type
-- (see docs/releases/010/design/010-data-model.md, Schema versions).

CREATE TABLE meta (
    schema_version INTEGER NOT NULL
);

INSERT INTO meta (schema_version) VALUES (4);

CREATE TABLE role (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE cv (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user(id),
    label TEXT NOT NULL UNIQUE
);

CREATE TABLE track (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user(id),
    role_id INTEGER NOT NULL REFERENCES role(id),
    seniority TEXT NOT NULL,
    default_cv_id INTEGER REFERENCES cv(id),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE search_profile (
    track_id INTEGER PRIMARY KEY REFERENCES track(id),
    keywords TEXT NOT NULL,
    min_salary INTEGER,
    max_age_weeks INTEGER,
    min_match_score REAL NOT NULL,
    employment_type TEXT NOT NULL DEFAULT 'Full Time'
);

CREATE TABLE search_schedule (
    track_id INTEGER PRIMARY KEY REFERENCES track(id),
    schedule_enabled INTEGER NOT NULL DEFAULT 0 CHECK (schedule_enabled IN (0, 1)),
    schedule_interval_hours INTEGER NOT NULL DEFAULT 24 CHECK (schedule_interval_hours > 0),
    next_run_at TEXT
);

CREATE TABLE run_log (
    id INTEGER PRIMARY KEY,
    run_type TEXT NOT NULL CHECK (run_type IN ('search', 'apply')),
    track_id INTEGER REFERENCES track(id),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
    outcome_counts TEXT,
    error_detail TEXT
);
CREATE INDEX idx_run_log_type_status ON run_log(run_type, status);
CREATE UNIQUE INDEX ux_run_log_running ON run_log(run_type) WHERE status = 'running';

CREATE TABLE post (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    position_title TEXT NOT NULL,
    company_name TEXT NOT NULL,
    url_ref TEXT,
    posted_date TEXT,
    salary_high INTEGER,
    is_open INTEGER NOT NULL DEFAULT 1 CHECK (is_open IN (0, 1)),
    closing_date TEXT,
    applicants INTEGER,
    industry_classification TEXT,
    description TEXT,
    mcf_ref TEXT,
    src_method TEXT NOT NULL CHECK (src_method IN ('scraped', 'manual')),
    run_id INTEGER REFERENCES run_log(id)
);
CREATE INDEX idx_post_is_open ON post(is_open);
CREATE INDEX idx_post_run_id ON post(run_id);

CREATE TABLE post_track (
    post_id TEXT NOT NULL REFERENCES post(id),
    track_id INTEGER NOT NULL REFERENCES track(id),
    search_match INTEGER NOT NULL CHECK (search_match IN (0, 1)),
    PRIMARY KEY (post_id, track_id)
);
CREATE INDEX idx_post_track_track_id ON post_track(track_id);

CREATE TABLE match_score (
    post_id TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    match_score REAL NOT NULL CHECK (match_score >= 0 AND match_score <= 1),
    score_method TEXT NOT NULL,
    PRIMARY KEY (post_id, track_id),
    FOREIGN KEY (post_id, track_id) REFERENCES post_track(post_id, track_id)
);

CREATE TABLE lead (
    id INTEGER PRIMARY KEY,
    post_id TEXT NOT NULL UNIQUE REFERENCES post(id),
    track_id INTEGER NOT NULL REFERENCES track(id),
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED')),
    stage TEXT NOT NULL CHECK (stage IN ('PROSPECT', 'TOAPPLY', 'APPLIED', 'CALLBACK', 'INTERVIEW', 'OFFER', 'CLOSED')),
    close_reason TEXT CHECK (close_reason IN ('offer_accepted', 'rejected', 'withdrawn', 'expired', 'cancelled', 'duplicate', 'apply_failed')),
    title_override TEXT,
    company_override TEXT,
    deadline TEXT,
    applied_date TEXT,
    first_attempt_date TEXT,
    last_contact_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_lead_track_id ON lead(track_id);
CREATE INDEX idx_lead_status_stage ON lead(status, stage);

CREATE TABLE lead_note (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES lead(id),
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_lead_note_lead_id ON lead_note(lead_id);

CREATE TABLE lead_event (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES lead(id),
    event_type TEXT NOT NULL CHECK (event_type IN ('stage_change', 'contact_logged', 'note_edited', 'deadline_changed', 'field_edited')),
    detail TEXT,
    occurred_at TEXT NOT NULL
);
CREATE INDEX idx_lead_event_lead_id ON lead_event(lead_id);

CREATE TABLE application (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES lead(id),
    cv_id INTEGER REFERENCES cv(id),
    status TEXT NOT NULL CHECK (status IN ('applied', 'questionnaire_required', 'cv_selector_error', 'unable_to_apply', 'post_unavailable', 'cv_not_found', 'post_closed', 'invalid_input')),
    error_detail TEXT,
    attempted_at TEXT NOT NULL,
    run_id INTEGER NOT NULL REFERENCES run_log(id)
);
CREATE INDEX idx_application_lead_id ON application(lead_id);
CREATE INDEX idx_application_run_id ON application(run_id);

CREATE TABLE session (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    user_id INTEGER NOT NULL REFERENCES user(id),
    status TEXT NOT NULL CHECK (status IN ('valid', 'expired', 'missing')),
    uploaded_at TEXT,
    cookie_ref TEXT
);
