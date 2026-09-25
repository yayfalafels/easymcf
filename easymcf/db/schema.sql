-- Easy MCF POC local - schema (ARCH-STO-02, single hand-maintained file, no migrations).
-- schema_version 2 adds the release-010 data model to the milestone-07 base.
-- schema_version 3 adds `user`, `match_score`, `lead_note`, and explicit `user_id`
-- ownership columns on `track`/`cv`/`session` (see docs/releases/010/design/010-data-model.md).
-- schema_version 4 adds `search_schedule` and `field_edited` in lead_event.event_type
-- (see docs/releases/010/design/010-data-model.md, Schema versions).
-- schema_version 5 adds `stage_from` and `stage_to` to lead_event (REQ-CRM-08).
-- schema_version 6 (task 09.13) drops PROSPECT from the stage values, adds `dropped` to
-- lead.close_reason, adds lead.expected_salary_sgd (REQ-CRM-09), and adds `offer` (REQ-CRM-10).
-- schema_version 7 (feature 13) adds accounts and ownership: sign-in fields on `user`, `auth_session`,
-- `mcf_session` (renamed from `session`, one row per user), `lead.user_id`, the lead's own
-- `position_title`, `company_name`, and `url_ref`, and `run_log.user_id`.
-- schema_version 8 (feature 17) adds `mcf_attempt` and `mcf_session.confirmed_account_email`/`confirmed_at`.
-- schema_version 9 (milestone 10) adds `run_log.trigger_source` and `lead.close_reason`
-- `track_not_matched` (see docs/releases/010/design/010-data-model.md, Schema versions).

CREATE TABLE meta (
    schema_version INTEGER NOT NULL
);

INSERT INTO meta (schema_version) VALUES (9);

CREATE TABLE role (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE CHECK (email = lower(email)),
    status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
    password_hash TEXT,
    google_sub TEXT UNIQUE,
    photo_ref TEXT,
    created_at TEXT NOT NULL,
    CHECK (password_hash IS NOT NULL OR google_sub IS NOT NULL)
);

CREATE TABLE auth_session (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX idx_auth_session_user_id ON auth_session(user_id);

CREATE TABLE cv (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user(id),
    label TEXT NOT NULL,
    UNIQUE (user_id, label)
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
    user_id INTEGER NOT NULL REFERENCES user(id),
    track_id INTEGER REFERENCES track(id),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
    outcome_counts TEXT,
    error_detail TEXT,
    trigger_source TEXT NOT NULL DEFAULT 'manual' CHECK (trigger_source IN ('manual', 'scheduled'))
);
CREATE INDEX idx_run_log_type_status ON run_log(run_type, status);
CREATE INDEX idx_run_log_user_id ON run_log(user_id);
CREATE UNIQUE INDEX ux_run_log_running ON run_log(user_id, run_type) WHERE status = 'running';

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
    user_id INTEGER NOT NULL REFERENCES user(id),
    post_id TEXT NOT NULL REFERENCES post(id),
    track_id INTEGER NOT NULL REFERENCES track(id),
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED')),
    stage TEXT NOT NULL CHECK (stage IN ('TOAPPLY', 'APPLIED', 'CALLBACK', 'INTERVIEW', 'OFFER', 'CLOSED')),
    close_reason TEXT CHECK (close_reason IN ('offer_accepted', 'rejected', 'withdrawn', 'expired', 'cancelled', 'duplicate', 'apply_failed', 'dropped', 'track_not_matched')),
    position_title TEXT NOT NULL,
    company_name TEXT NOT NULL,
    url_ref TEXT CHECK (url_ref IS NULL OR url_ref GLOB 'http://*' OR url_ref GLOB 'https://*'),
    deadline TEXT,
    applied_date TEXT,
    first_attempt_date TEXT,
    last_contact_date TEXT,
    expected_salary_sgd INTEGER CHECK (expected_salary_sgd IS NULL OR expected_salary_sgd >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, post_id)
);
CREATE INDEX idx_lead_user_id ON lead(user_id);
CREATE INDEX idx_lead_track_id ON lead(track_id);
CREATE INDEX idx_lead_status_stage ON lead(status, stage);

CREATE TRIGGER lead_owner_matches_track_insert BEFORE INSERT ON lead
WHEN NEW.user_id != (SELECT user_id FROM track WHERE id = NEW.track_id)
BEGIN SELECT RAISE(ABORT, 'lead.user_id must equal its track owner'); END;

CREATE TRIGGER lead_owner_matches_track_update BEFORE UPDATE OF user_id, track_id ON lead
WHEN NEW.user_id != (SELECT user_id FROM track WHERE id = NEW.track_id)
BEGIN SELECT RAISE(ABORT, 'lead.user_id must equal its track owner'); END;

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
    stage_from TEXT CHECK (stage_from IN ('TOAPPLY', 'APPLIED', 'CALLBACK', 'INTERVIEW', 'OFFER', 'CLOSED')),
    stage_to TEXT NOT NULL CHECK (stage_to IN ('TOAPPLY', 'APPLIED', 'CALLBACK', 'INTERVIEW', 'OFFER', 'CLOSED')),
    occurred_at TEXT NOT NULL,
    CHECK ((event_type = 'stage_change' AND stage_from IS NOT stage_to)
        OR (event_type <> 'stage_change' AND stage_from IS stage_to))
);
CREATE INDEX idx_lead_event_lead_id ON lead_event(lead_id);

CREATE TABLE offer (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES lead(id),
    offer_date TEXT NOT NULL,
    deadline TEXT,
    amount_sgd INTEGER NOT NULL CHECK (amount_sgd > 0),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'accepted', 'rejected', 'withdrawn', 'expired')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_offer_lead_id ON offer(lead_id);
CREATE UNIQUE INDEX ux_offer_open ON offer(lead_id) WHERE status = 'open';

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

CREATE TABLE mcf_session (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES user(id),
    status TEXT NOT NULL CHECK (status IN ('valid', 'expired', 'missing')),
    uploaded_at TEXT,
    cookie_ref TEXT,
    confirmed_account_email TEXT,
    confirmed_at TEXT
);

CREATE TABLE mcf_attempt (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user(id),
    status TEXT NOT NULL CHECK (status IN (
        'starting', 'awaiting_approval', 'verifying', 'account_confirmation_required',
        'connected', 'expired', 'cancelled', 'failed', 'interaction_required', 'reauthentication_required'
    )),
    account_email TEXT,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_mcf_attempt_user_id ON mcf_attempt(user_id);
CREATE UNIQUE INDEX ux_mcf_attempt_active ON mcf_attempt(user_id)
    WHERE status IN ('starting', 'awaiting_approval', 'verifying', 'account_confirmation_required');
