#!/usr/bin/env python3
"""Generate deterministic seed or sample SQL from the exported CSV tabs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta

sys.path.insert(0, ROOT := os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from easymcf.db.connection import get_connection

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from render_seed import PUBLIC_DEFAULTS, render_text  # noqa: E402

SOURCE_DIR = os.path.join(ROOT, "test-data")
SCHEMA_PATH = os.path.join(ROOT, "easymcf", "db", "schema.sql")
TABLES = [
    "role", "user", "cv", "track", "search_profile", "search_schedule", "run_log", "post",
    "post_track", "match_score", "lead", "lead_note", "lead_event", "offer", "application", "mcf_session",
    "mcf_attempt",
]
SCRYPT_N, SCRYPT_R, SCRYPT_P = 32768, 8, 1
# Fake local test credentials (TESTDATA-GEN user table). Never a production store.
# User 1's identity is a {{TOKEN}} that scripts/render_seed.py fills from .env when the seed is applied (18.EL.01).
ACCOUNTS = [
    {"id": 1, "name": "{{INITIAL_USER_NAME}}", "email": "{{INITIAL_USER_EMAIL}}", "password": "Seed-Password-1!", "salt": "seed-salt-1"},
    {"id": 2, "name": "Sam Second", "email": "second.user@example.test", "password": "Seed-Password-2!", "salt": "seed-salt-2"},
]
STAGES = ["TOAPPLY", "APPLIED", "CALLBACK", "INTERVIEW", "OFFER", "CLOSED"]
CLOSE_REASONS = ["offer_accepted", "rejected", "withdrawn", "expired", "cancelled", "duplicate", "apply_failed",
                 "dropped", "track_not_matched"]
APPLICATION_STATUSES = [
    "applied", "questionnaire_required", "cv_selector_error", "unable_to_apply",
    "post_unavailable", "cv_not_found", "post_closed", "invalid_input",
]


CLOSED_FROM = {"offer_accepted": "OFFER", "rejected": "APPLIED", "withdrawn": "APPLIED", "expired": "APPLIED",
               "cancelled": "TOAPPLY", "duplicate": "TOAPPLY", "apply_failed": "TOAPPLY", "dropped": "TOAPPLY",
               "track_not_matched": "TOAPPLY"}
MANUAL_POST_ID = "manual-seed-1"


def stage_path(stage: str, close_reason: str | None, manual: bool = False, reopened: bool = False) -> list[str]:
    """Stages a lead passes through, creation first. A closed lead ends with CLOSED, and a re-opened OFFER lead
    runs OFFER, CLOSED, INTERVIEW, OFFER (its first offer was rejected)."""
    start = STAGES.index("APPLIED") if manual else 0
    if stage == "CLOSED":
        return STAGES[start: STAGES.index(CLOSED_FROM[close_reason]) + 1] + ["CLOSED"]
    path = STAGES[start: STAGES.index(stage) + 1]
    return path + ["CLOSED", "INTERVIEW", "OFFER"] if reopened else path


def scrypt_hash(password: str, salt: str) -> str:
    """Werkzeug's scrypt format with a fixed salt, so two generations are byte-identical."""
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                            maxmem=132 * SCRYPT_N * SCRYPT_R * SCRYPT_P).hex()
    return f"scrypt:{SCRYPT_N}:{SCRYPT_R}:{SCRYPT_P}${salt}${digest}"


def read_csv(name: str) -> list[list[str]]:
    with open(os.path.join(SOURCE_DIR, name), newline="", encoding="utf-8-sig") as handle:
        return list(csv.reader(handle))[1:]


def first_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def sql_value(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert(table: str, fields: dict, comment: str | None = None) -> str:
    columns = ", ".join(fields)
    values = ", ".join(sql_value(value) for value in fields.values())
    prefix = f"-- {comment}\n" if comment else ""
    return f"{prefix}INSERT INTO {table} ({columns}) VALUES ({values});\n"


def source_rows(anchor: date, limit: int) -> tuple[list[dict], timedelta]:
    screened = read_csv("screened.csv")
    all_dates = [first_date(row[index]) for row in screened for index in (10, 11)]
    all_dates = [value for value in all_dates if value]
    shift = anchor - max(all_dates)
    posts = []
    seen = set()
    for row in screened:
        if len(row) < 16 or not row[4] or row[4] in seen:
            continue
        seen.add(row[4])
        posted = first_date(row[10])
        closing = first_date(row[11])
        score = float(row[1] or 0) / 100 if row[1] else 0.5
        posts.append({
            "id": row[4],
            "source": row[4].split("-", 1)[0],
            "position_title": row[13] or row[12] or row[2] or "Imported posting",
            "company_name": row[3] or "Imported company",
            "url_ref": row[5] or f"https://www.mycareersfuture.gov.sg/job/{row[4]}",
            "posted_date": (posted + shift).isoformat() if posted else None,
            "salary_high": int(float(row[6])) if row[6] else None,
            "is_open": 0 if closing and closing + shift < anchor else 1,
            "closing_date": (closing + shift).isoformat() if closing else None,
            "applicants": int(row[9]) if row[9].isdigit() else None,
            "description": None,
            "score": min(max(score, 0), 1),
        })
        if len(posts) >= limit:
            break
    return posts, shift


def build_sql(anchor: date, mode: str) -> dict[str, str]:
    source, shift = source_rows(anchor, 8 if mode == "sample" else 3)
    roles = [{"id": 1, "name": "Data Analyst", "description": None},
             {"id": 2, "name": "Sustainability Consultant", "description": None}]
    users = [{"id": a["id"], "name": a["name"], "email": a["email"], "status": "active",
              "password_hash": scrypt_hash(a["password"], a["salt"]), "google_sub": None, "photo_ref": None,
              "created_at": f"{anchor} 06:00:00"} for a in ACCOUNTS]
    cvs = [{"id": 1, "user_id": 1, "label": "13.2"}, {"id": 2, "user_id": 1, "label": "11.4"},
           {"id": 3, "user_id": 2, "label": "S-1"}]
    tracks = [
        {"id": 1, "user_id": 1, "role_id": 1, "seniority": "mid", "default_cv_id": 1, "is_active": 1},
        {"id": 2, "user_id": 1, "role_id": 2, "seniority": "mid", "default_cv_id": 1, "is_active": 0},
    ]
    profiles = [
        {"track_id": 1, "keywords": "Data Analyst", "min_salary": 10000, "max_age_weeks": 4, "min_match_score": 0.3, "employment_type": "Full Time"},
        {"track_id": 2, "keywords": "Sustainability Consultant", "min_salary": 10000, "max_age_weeks": 4, "min_match_score": 0.3, "employment_type": "Full Time"},
    ]
    roles += [{"id": i, "name": name, "description": None} for i, name in
              ((3, "Data Engineer"), (4, "Data Scientist"), (5, "Software Developer"), (6, "Gen AI Developer"))]
    for role in roles[2:]:
        tracks.append({"id": role["id"], "user_id": 1, "role_id": role["id"], "seniority": "mid",
                       "default_cv_id": 1, "is_active": 1})
        profiles.append({"track_id": role["id"], "keywords": role["name"], "min_salary": 10000,
                         "max_age_weeks": 4, "min_match_score": 0.3, "employment_type": "Full Time"})
    tracks += [
        {"id": 7, "user_id": 2, "role_id": 1, "seniority": "mid", "default_cv_id": 3, "is_active": 1},
        {"id": 8, "user_id": 2, "role_id": 4, "seniority": "mid", "default_cv_id": 3, "is_active": 1},
    ]
    profiles += [
        {"track_id": 7, "keywords": "Data Analyst", "min_salary": 9000, "max_age_weeks": 4, "min_match_score": 0.3, "employment_type": "Full Time"},
        {"track_id": 8, "keywords": "Data Scientist", "min_salary": 9000, "max_age_weeks": 4, "min_match_score": 0.3, "employment_type": "Full Time"},
    ]
    schedules = [{"track_id": t["id"], "schedule_enabled": 0, "schedule_interval_hours": 24, "next_run_at": None}
                 for t in tracks]
    sql = {table: "" for table in TABLES}
    for row in roles:
        sql["role"] += insert("role", row)
    for row in users:
        sql["user"] += insert("user", row)
    cv_label = {row["id"]: row["label"] for row in cvs}
    for row in cvs:
        sql["cv"] += insert("cv", row)
    for row in tracks:
        sql["track"] += insert("track", row)
    for row in profiles:
        sql["search_profile"] += insert("search_profile", row)
    for row in schedules:
        sql["search_schedule"] += insert("search_schedule", row, "synthetic schedule default")

    run_rows = [
        {"id": 1, "run_type": "search", "user_id": 1, "track_id": 1, "started_at": f"{anchor} 08:00:00", "ended_at": f"{anchor} 08:02:00", "status": "success", "outcome_counts": '{"new_posts": 3}', "error_detail": None, "trigger_source": "manual"},
        {"id": 2, "run_type": "search", "user_id": 1, "track_id": 2, "started_at": f"{anchor} 08:03:00", "ended_at": f"{anchor} 08:05:00", "status": "partial", "outcome_counts": '{"new_posts": 1}', "error_detail": "one fixture detail page was unavailable", "trigger_source": "manual"},
        {"id": 3, "run_type": "apply", "user_id": 1, "track_id": None, "started_at": f"{anchor} 09:00:00", "ended_at": f"{anchor} 09:03:00", "status": "success", "outcome_counts": None, "error_detail": None, "trigger_source": "manual"},
        {"id": 4, "run_type": "apply", "user_id": 1, "track_id": None, "started_at": f"{anchor} 09:04:00", "ended_at": f"{anchor} 09:05:00", "status": "failed", "outcome_counts": None, "error_detail": "RuntimeError: synthetic worker failure after 1 of 1 queued leads", "trigger_source": "manual"},
        {"id": 5, "run_type": "search", "user_id": 1, "track_id": 1, "started_at": f"{anchor} 10:00:00", "ended_at": None, "status": "running", "outcome_counts": '{"new_posts": 0}', "error_detail": None, "trigger_source": "manual"},
        {"id": 6, "run_type": "search", "user_id": 2, "track_id": 7, "started_at": f"{anchor} 11:00:00", "ended_at": f"{anchor} 11:02:00", "status": "success", "outcome_counts": '{"new_posts": 1}', "error_detail": None, "trigger_source": "scheduled"},
        {"id": 7, "run_type": "apply", "user_id": 1, "track_id": None, "started_at": f"{anchor} 09:10:00", "ended_at": f"{anchor} 09:12:00", "status": "success", "outcome_counts": None, "error_detail": None, "trigger_source": "manual"},
        {"id": 8, "run_type": "apply", "user_id": 2, "track_id": None, "started_at": f"{anchor} 11:10:00", "ended_at": f"{anchor} 11:12:00", "status": "success", "outcome_counts": None, "error_detail": None, "trigger_source": "manual"},
    ]
    # Apply attempts, one per (run, lead), each landing its lead in the Workflow 7 state the lead is seeded at
    # (11.IS.03). Leads 19/20 are appended after user 2's so no pre-existing lead id moves. An apply run's
    # outcome_counts is derived from its own attempts below, never hand-typed.
    apply_attempts = [
        (3, 3, 1, "questionnaire_required", "09:00:30"),  # then advanced by hand to APPLIED (11.CK.08)
        (3, 4, 1, "applied", "09:01:00"),
        (3, 5, 1, "unable_to_apply", "09:01:30"),
        (3, 12, 1, "post_unavailable", "09:02:00"),
        (3, 1, 1, "cv_not_found", "09:02:30"),           # repaired by lead 1's cv_id override to cv 2
        (4, 1, 2, "cv_selector_error", "09:04:30"),      # the run then fails at run level
        (7, 5, 1, "applied", "09:10:30"),                # retry history: unable_to_apply, then applied
        (7, 10, 1, "invalid_input", "09:11:00"),         # then cancelled by the user
        (7, 19, 1, "post_closed", "09:11:30"),
        (8, 15, 3, "cv_not_found", "11:10:30"),          # unrepaired: effective cv is still the one that failed
        (8, 16, 3, "applied", "11:11:00"),
    ]
    error_details = {
        "questionnaire_required": "final submit failed: review page reported required questions",
        "cv_selector_error": "TimeoutError: resume-card lookup timed out",
        "unable_to_apply": "apply button unresolved after 5 attempts",
        "post_unavailable": "Error: posting navigation failed with HTTP 404",
        "post_closed": "This job is no longer available",
        "invalid_input": "missing field: url_ref",
    }
    for row in run_rows:
        if row["run_type"] == "apply":
            counts: dict[str, int] = {}
            for run_id, _lead, _cv, status, _at in apply_attempts:
                if run_id == row["id"]:
                    counts[status] = counts.get(status, 0) + 1
            row["outcome_counts"] = json.dumps(counts, sort_keys=True)
        sql["run_log"] += insert("run_log", row, "synthetic run-log coverage")

    posts = list(source)
    for index, stage in enumerate(STAGES[:-1], start=1):
        posts.append({"id": f"synthetic-{index}", "source": "Synthetic", "position_title": f"Seed {stage} role", "company_name": "Synthetic Company", "url_ref": f"https://www.mycareersfuture.gov.sg/job/synthetic-{index}", "posted_date": (anchor - timedelta(days=index)).isoformat(), "salary_high": 10000, "is_open": 1, "closing_date": None, "applicants": 0, "description": None, "score": 0.8})
    posts.append({"id": "synthetic-closed", "source": "Synthetic", "position_title": "Seed closed role", "company_name": "Synthetic Company", "url_ref": "https://www.mycareersfuture.gov.sg/job/synthetic-closed", "posted_date": (anchor - timedelta(days=10)).isoformat(), "salary_high": 10000, "is_open": 0, "closing_date": (anchor - timedelta(days=1)).isoformat(), "applicants": 0, "description": None, "score": 0.8})
    # padded so posts[0 .. len(STAGES)+len(CLOSE_REASONS)-2] always exists: the close-reason lead loop
    # below consumes one post per non-`offer_accepted` reason, and a fixed "13" silently drifted onto
    # the reserved synthetic-promote-* posts the last time a reason was added (10.IS.01).
    while len(posts) < len(STAGES) + len(CLOSE_REASONS) - 1:
        index = len(posts) + 1
        posts.append({"id": f"synthetic-close-{index}", "source": "Synthetic", "position_title": "Seed close reason role", "company_name": "Synthetic Company", "url_ref": f"https://www.mycareersfuture.gov.sg/job/synthetic-close-{index}", "posted_date": (anchor - timedelta(days=index)).isoformat(), "salary_high": 10000, "is_open": 1, "closing_date": None, "applicants": 0, "description": None, "score": 0.8})
    for name, closing in (("future", anchor + timedelta(days=14)), ("nodate", None), ("past", anchor - timedelta(days=2))):
        posts.append({"id": f"synthetic-promote-{name}", "source": "Synthetic", "position_title": f"Seed promote {name} role", "company_name": "Synthetic Company", "url_ref": f"https://www.mycareersfuture.gov.sg/job/synthetic-promote-{name}", "posted_date": (anchor - timedelta(days=3)).isoformat(), "salary_high": 10000, "is_open": 1, "closing_date": closing.isoformat() if closing else None, "applicants": 0, "description": None, "score": 0.8})
    posts.append({"id": MANUAL_POST_ID, "source": "Manual", "position_title": "Seed manual role", "company_name": "Manual Company", "url_ref": "https://www.mycareersfuture.gov.sg/job/manual-seed-1", "posted_date": (anchor - timedelta(days=2)).isoformat(), "salary_high": 10000, "is_open": 1, "closing_date": None, "applicants": 0, "description": None, "score": 0.8})
    base_posts = list(posts)
    for number in (1, 2, 3):
        posts.append({"id": f"synthetic-u2-{number}", "source": "Synthetic", "position_title": f"Second user role {number}", "company_name": "Second Company", "url_ref": f"https://www.mycareersfuture.gov.sg/job/synthetic-u2-{number}", "posted_date": (anchor - timedelta(days=number)).isoformat(), "salary_high": 9000, "is_open": 1, "closing_date": None, "applicants": 0, "description": None, "score": 0.7})
    # apply-queue fixtures (11.IS.03): a post MCF reported closed at apply time, and a fresh queued post
    apply_posts = (("synthetic-apply-closed", "Seed apply closed role", 1, 0), ("synthetic-apply-queued", "Seed apply queued role", 3, 1))
    for post_id, title, _track, is_open in apply_posts:
        posts.append({"id": post_id, "source": "Synthetic", "position_title": title, "company_name": "Synthetic Company", "url_ref": f"https://www.mycareersfuture.gov.sg/job/{post_id}", "posted_date": (anchor - timedelta(days=4)).isoformat(), "salary_high": 10000, "is_open": is_open, "closing_date": None if is_open else anchor.isoformat(), "applicants": 0, "description": None, "score": 0.8})
    for post in posts:
        fields = {key: post[key] for key in ("id", "source", "position_title", "company_name", "url_ref", "posted_date", "salary_high", "is_open", "closing_date", "applicants", "description")}
        fields.update({"industry_classification": None, "mcf_ref": None, "src_method": "manual" if post["source"] in ("Synthetic", "Manual") else "scraped", "run_id": None if post["source"] in ("Synthetic", "Manual") else 1})
        sql["post"] += insert("post", fields, "synthetic below-threshold or lifecycle fixture" if post["source"] == "Synthetic" else None)

    for index, post in enumerate(base_posts):
        track_id = 1 if index else 2
        search_match = 0 if post["source"] in ("Synthetic", "Manual") else 1
        sql["post_track"] += insert("post_track", {"post_id": post["id"], "track_id": track_id, "search_match": search_match})
        sql["match_score"] += insert("match_score", {"post_id": post["id"], "track_id": track_id, "match_score": post["score"], "score_method": "title_keyword_v1"})
        if index == 0:
            sql["post_track"] += insert("post_track", {"post_id": post["id"], "track_id": 1, "search_match": 1})
            sql["match_score"] += insert("match_score", {"post_id": post["id"], "track_id": 1, "match_score": post["score"], "score_method": "title_keyword_v1"})

    post_by_id = {post["id"]: post for post in posts}

    def copies(post_id: str) -> dict:
        post = post_by_id[post_id]
        return {"position_title": post["position_title"], "company_name": post["company_name"], "url_ref": post["url_ref"]}

    for post_id, track_id, match in ((posts[0]["id"], 7, 1), ("synthetic-u2-1", 7, 0), ("synthetic-u2-2", 8, 0), ("synthetic-u2-3", 8, 0),
                                     *((post_id, track, 0) for post_id, _title, track, _open in apply_posts)):
        score = post_by_id[post_id]["score"]
        comment = "apply-queue fixture match" if post_id.startswith("synthetic-apply-") else "second user shared or private match"
        sql["post_track"] += insert("post_track", {"post_id": post_id, "track_id": track_id, "search_match": match}, comment)
        sql["match_score"] += insert("match_score", {"post_id": post_id, "track_id": track_id, "match_score": score, "score_method": "title_keyword_v1"})

    leads = []
    for index, stage in enumerate(STAGES, start=1):
        post_id = MANUAL_POST_ID if stage == "APPLIED" else posts[index - 1]["id"]
        close_reason = None if stage != "CLOSED" else CLOSE_REASONS[0]
        leads.append({"id": index, "user_id": 1, "post_id": post_id, "track_id": 1, "cv_id": None, "status": "CLOSED" if stage == "CLOSED" else "OPEN", "stage": stage, "close_reason": close_reason, **copies(post_id), "deadline": anchor.isoformat() if stage == "CLOSED" else (anchor + timedelta(days=28)).isoformat(), "applied_date": anchor.isoformat() if stage != "TOAPPLY" else None, "first_attempt_date": None, "last_contact_date": None, "expected_salary_sgd": 10000, "created_at": f"{anchor} 07:00:00", "updated_at": f"{anchor} 07:00:00"})
    for index, reason in enumerate(CLOSE_REASONS[1:], start=len(STAGES) + 1):
        post = posts[index - 1]
        leads.append({"id": index, "user_id": 1, "post_id": post["id"], "track_id": 1, "cv_id": None, "status": "CLOSED", "stage": "CLOSED", "close_reason": reason, **copies(post["id"]), "deadline": anchor.isoformat(), "applied_date": anchor.isoformat(), "first_attempt_date": None, "last_contact_date": None, "expected_salary_sgd": 10000, "created_at": f"{anchor} 07:00:00", "updated_at": f"{anchor} 07:00:00"})
    leads[0]["company_name"] = "Seed Co"
    user1_lead_count = len(leads)
    u2_stages = (("TOAPPLY", None, 7, posts[0]["id"]), ("APPLIED", None, 7, "synthetic-u2-1"),
                 ("CALLBACK", None, 8, "synthetic-u2-2"), ("CLOSED", "rejected", 8, "synthetic-u2-3"))
    for offset, (stage, reason, track_id, post_id) in enumerate(u2_stages, start=1):
        leads.append({"id": user1_lead_count + offset, "user_id": 2, "post_id": post_id, "track_id": track_id, "cv_id": None,
                      "status": "CLOSED" if stage == "CLOSED" else "OPEN", "stage": stage, "close_reason": reason,
                      **copies(post_id), "deadline": anchor.isoformat() if stage == "CLOSED" else (anchor + timedelta(days=28)).isoformat(),
                      "applied_date": anchor.isoformat() if stage != "TOAPPLY" else None, "first_attempt_date": None,
                      "last_contact_date": None, "expected_salary_sgd": 9000,
                      "created_at": f"{anchor} 07:00:00", "updated_at": f"{anchor} 07:00:00"})
    for (post_id, _title, track_id, _open), (stage, reason) in zip(apply_posts, (("CLOSED", "apply_failed"), ("TOAPPLY", None))):
        leads.append({"id": len(leads) + 1, "user_id": 1, "post_id": post_id, "track_id": track_id, "cv_id": None,
                      "status": "CLOSED" if stage == "CLOSED" else "OPEN", "stage": stage, "close_reason": reason,
                      **copies(post_id), "deadline": anchor.isoformat() if stage == "CLOSED" else (anchor + timedelta(days=28)).isoformat(),
                      "applied_date": None, "first_attempt_date": None, "last_contact_date": None, "expected_salary_sgd": 10000,
                      "created_at": f"{anchor} 07:00:00", "updated_at": f"{anchor} 07:00:00"})
    leads[0]["cv_id"] = 2  # lead 1's CV override, set after its cv_not_found attempt (REQ-APPLY-02)
    next(row for row in leads if row["close_reason"] == "cancelled")["url_ref"] = None  # its invalid_input cause
    attempted = {lead_id for _run, lead_id, _cv, _status, _at in apply_attempts}
    for row in leads:
        if row["stage"] == "CALLBACK":
            row["last_contact_date"] = anchor.isoformat()
        if row["id"] in attempted:
            row["first_attempt_date"] = anchor.isoformat()
    note_id = 1
    event_id = 1
    for row in leads:
        sql["lead"] += insert("lead", row, "synthetic stage or close-reason coverage")
        previous = None
        manual = row["post_id"] == MANUAL_POST_ID
        for step, stage in enumerate(stage_path(row["stage"], row["close_reason"], manual, reopened=row["stage"] == "OFFER")):
            if previous is None:
                detail = f"added manually at {stage}" if manual else "promoted to TOAPPLY"
            elif stage == "CLOSED":
                detail = f"close_reason: None -> {'rejected' if row['stage'] == 'OFFER' else row['close_reason']}"
            elif previous == "CLOSED":
                detail = "re-opened from an offer"
            else:
                detail = None
            sql["lead_event"] += insert("lead_event", {
                "id": event_id, "lead_id": row["id"], "event_type": "stage_change", "detail": detail,
                "stage_from": previous, "stage_to": stage, "occurred_at": f"{anchor} 07:{step:02d}:00"},
                "synthetic stage history")
            previous, event_id = stage, event_id + 1
        if row["stage"] == "INTERVIEW":
            sql["lead_note"] += insert("lead_note", {"id": note_id, "lead_id": row["id"], "note": "Interview scheduled with hiring manager", "created_at": f"{anchor} 07:30:00"}, "synthetic note-history coverage")
            sql["lead_event"] += insert("lead_event", {"id": event_id, "lead_id": row["id"], "event_type": "note_edited", "detail": "note added", "stage_from": "INTERVIEW", "stage_to": "INTERVIEW", "occurred_at": f"{anchor} 07:30:00"}, "synthetic note-history coverage")
            note_id, event_id = note_id + 1, event_id + 1

    for row in leads:
        if row["user_id"] == 2 and row["stage"] in ("APPLIED", "CALLBACK"):
            sql["lead_note"] += insert("lead_note", {"id": note_id, "lead_id": row["id"], "note": "Second user follow-up note", "created_at": f"{anchor} 07:30:00"}, "second user note")
            sql["lead_event"] += insert("lead_event", {"id": event_id, "lead_id": row["id"], "event_type": "note_edited", "detail": "note added", "stage_from": row["stage"], "stage_to": row["stage"], "occurred_at": f"{anchor} 07:30:00"}, "second user note")
            note_id, event_id = note_id + 1, event_id + 1

    callback_id = next(row["id"] for row in leads if row["stage"] == "CALLBACK")
    for lead_id, event_type, detail, stage, minute in (
        (1, "field_edited", f"company_name: {posts[0]['company_name']} -> Seed Co", "TOAPPLY", 31),
        (1, "field_edited", "cv_id: None -> 2", "TOAPPLY", None),
        (callback_id, "contact_logged", f"last_contact_date: None -> {anchor}", "CALLBACK", 40),
        (callback_id, "deadline_changed", f"deadline: {anchor} -> {anchor + timedelta(days=28)}", "CALLBACK", 41),
    ):
        sql["lead_event"] += insert("lead_event", {"id": event_id, "lead_id": lead_id, "event_type": event_type, "detail": detail,
                                                   "stage_from": stage, "stage_to": stage,
                                                   "occurred_at": f"{anchor} 07:{minute}:00" if minute else f"{anchor} 09:03:30"},
                                    "synthetic event coverage")
        event_id += 1

    lead_deadline = anchor + timedelta(days=28)
    offer_rows = [
        {"id": 1, "lead_id": 5, "offer_date": anchor.isoformat(), "deadline": (anchor + timedelta(days=14)).isoformat(),
         "amount_sgd": 11000, "status": "rejected", "created_at": f"{anchor} 07:04:00", "updated_at": f"{anchor} 07:05:00"},
        {"id": 2, "lead_id": 5, "offer_date": anchor.isoformat(), "deadline": lead_deadline.isoformat(),
         "amount_sgd": 12000, "status": "open", "created_at": f"{anchor} 07:07:00", "updated_at": f"{anchor} 07:07:00"},
        {"id": 3, "lead_id": 6, "offer_date": anchor.isoformat(), "deadline": anchor.isoformat(),
         "amount_sgd": 11500, "status": "accepted", "created_at": f"{anchor} 07:04:00", "updated_at": f"{anchor} 07:05:00"},
    ]
    for row in offer_rows:
        sql["offer"] += insert("offer", row, "synthetic offer history coverage")

    for app_id, (run_id, lead_id, cv_id, status, at) in enumerate(apply_attempts, start=1):
        sql["application"] += insert("application", {"id": app_id, "lead_id": lead_id, "cv_id": cv_id, "status": status,
                                                     "error_detail": error_details.get(status, f"no resume option matched CV label '{cv_label[cv_id]}'" if status == "cv_not_found" else None),
                                                     "attempted_at": f"{anchor} {at}", "run_id": run_id},
                                     "synthetic apply attempt, Workflow 7 coherent")
    for account in ACCOUNTS:
        previously_confirmed = account["id"] == 1
        sql["mcf_session"] += insert("mcf_session", {
            "id": account["id"], "user_id": account["id"],
            "status": "missing",
            "uploaded_at": None,
            "cookie_ref": None,
            "confirmed_account_email": account["email"] if previously_confirmed else None,
            "confirmed_at": f"{anchor} 12:00:00" if previously_confirmed else None,
        }, "no real cookie payload is ever seeded; a seeded row must not claim an authenticated session")

    attempt_rows = [
        {"id": 1, "user_id": 1, "status": "connected", "account_email": ACCOUNTS[0]["email"], "error_code": None,
         "created_at": f"{anchor} 11:58:00", "updated_at": f"{anchor} 12:00:00"},
        {"id": 2, "user_id": 2, "status": "failed", "account_email": None, "error_code": "SingpassTimeoutError",
         "created_at": f"{anchor} 11:58:00", "updated_at": f"{anchor} 11:59:00"},
    ]
    for row in attempt_rows:
        sql["mcf_attempt"] += insert("mcf_attempt", row, "synthetic connection-attempt history")
    return sql


def validate(sql_by_table: dict[str, str]) -> None:
    fd, path = tempfile.mkstemp(prefix="easymcf-seed-", suffix=".db")
    os.close(fd)
    os.remove(path)
    conn = get_connection(path)
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as handle:
            conn.executescript(handle.read())
        for table in TABLES:
            try:
                conn.executescript(render_text(sql_by_table[table], PUBLIC_DEFAULTS, table))  # 18.IS.01
            except sqlite3.Error as exc:
                raise RuntimeError(f"seed validation failed in {table}: {exc}") from exc
        mismatched = conn.execute("SELECT COUNT(*) FROM lead JOIN track ON track.id = lead.track_id WHERE lead.user_id != track.user_id").fetchone()[0]
        empty = conn.execute("SELECT COUNT(*) FROM lead WHERE position_title = '' OR company_name = ''").fetchone()[0]
        if mismatched or empty:
            raise RuntimeError(f"seed ownership invalid: {mismatched} mismatched lead owners, {empty} empty lead copies")
        conn.commit()
    finally:
        conn.close()
        if os.path.exists(path):
            os.remove(path)


def write_output(sql_by_table: dict[str, str], mode: str, out: str) -> None:
    if mode == "seed":
        os.makedirs(out, exist_ok=True)
        for old in os.listdir(out):
            if old.endswith(".sql"):
                os.remove(os.path.join(out, old))
        for index, table in enumerate(TABLES, start=1):
            with open(os.path.join(out, f"{index:02d}_{table}.sql"), "w", encoding="utf-8") as handle:
                handle.write(sql_by_table[table])
    else:
        parent = os.path.dirname(out)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out, "w", encoding="utf-8") as handle:
            for table in TABLES:
                handle.write(sql_by_table[table])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("seed", "sample"), required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--rand-seed", type=int, required=True)
    parser.add_argument("--anchor", default=None)
    args = parser.parse_args()
    anchor = date.fromisoformat(args.anchor) if args.anchor else date.today()
    sql_by_table = build_sql(anchor, args.mode)
    validate(sql_by_table)
    write_output(sql_by_table, args.mode, args.out)
    print(f"[PASS] {args.mode} generated - {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())