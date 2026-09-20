#!/usr/bin/env python3
"""Generate deterministic seed or sample SQL from the exported CSV tabs."""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta

sys.path.insert(0, ROOT := os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from easymcf.db.connection import get_connection

SOURCE_DIR = os.path.join(ROOT, "test-data")
SCHEMA_PATH = os.path.join(ROOT, "easymcf", "db", "schema.sql")
TABLES = [
    "role", "user", "cv", "track", "search_profile", "search_schedule", "run_log", "post",
    "post_track", "match_score", "lead", "lead_note", "lead_event", "offer", "application", "session",
]
STAGES = ["TOAPPLY", "APPLIED", "CALLBACK", "INTERVIEW", "OFFER", "CLOSED"]
CLOSE_REASONS = ["offer_accepted", "rejected", "withdrawn", "expired", "cancelled", "duplicate", "apply_failed", "dropped"]
APPLICATION_STATUSES = [
    "applied", "questionnaire_required", "cv_selector_error", "unable_to_apply",
    "post_unavailable", "cv_not_found", "post_closed", "invalid_input",
]


CLOSED_FROM = {"offer_accepted": "OFFER", "rejected": "APPLIED", "withdrawn": "APPLIED", "expired": "APPLIED",
               "cancelled": "TOAPPLY", "duplicate": "TOAPPLY", "apply_failed": "TOAPPLY", "dropped": "TOAPPLY"}
MANUAL_POST_ID = "manual-seed-1"


def stage_path(stage: str, close_reason: str | None, manual: bool = False, reopened: bool = False) -> list[str]:
    """Stages a lead passes through, creation first. A closed lead ends with CLOSED, and a re-opened OFFER lead
    runs OFFER, CLOSED, INTERVIEW, OFFER (its first offer was rejected)."""
    start = STAGES.index("APPLIED") if manual else 0
    if stage == "CLOSED":
        return STAGES[start: STAGES.index(CLOSED_FROM[close_reason]) + 1] + ["CLOSED"]
    path = STAGES[start: STAGES.index(stage) + 1]
    return path + ["CLOSED", "INTERVIEW", "OFFER"] if reopened else path


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
    users = [{"id": 1, "name": "Taylor Hickem", "email": "yayfalafels@gmail.com", "status": "active"}]
    cvs = [{"id": 1, "user_id": 1, "label": "13.2"}, {"id": 2, "user_id": 1, "label": "11.4"}]
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
    schedules = [{"track_id": t["id"], "schedule_enabled": 0, "schedule_interval_hours": 24, "next_run_at": None}
                 for t in tracks]
    sql = {table: "" for table in TABLES}
    for row in roles:
        sql["role"] += insert("role", row)
    for row in users:
        sql["user"] += insert("user", row)
    for row in cvs:
        sql["cv"] += insert("cv", row)
    for row in tracks:
        sql["track"] += insert("track", row)
    for row in profiles:
        sql["search_profile"] += insert("search_profile", row)
    for row in schedules:
        sql["search_schedule"] += insert("search_schedule", row, "synthetic schedule default")

    run_rows = [
        {"id": 1, "run_type": "search", "track_id": 1, "started_at": f"{anchor} 08:00:00", "ended_at": f"{anchor} 08:02:00", "status": "success", "outcome_counts": '{"new_posts": 3}', "error_detail": None},
        {"id": 2, "run_type": "search", "track_id": 2, "started_at": f"{anchor} 08:03:00", "ended_at": f"{anchor} 08:05:00", "status": "partial", "outcome_counts": '{"new_posts": 1}', "error_detail": "one fixture detail page was unavailable"},
        {"id": 3, "run_type": "apply", "track_id": None, "started_at": f"{anchor} 09:00:00", "ended_at": f"{anchor} 09:03:00", "status": "success", "outcome_counts": '{"applied": 1}', "error_detail": None},
        {"id": 4, "run_type": "apply", "track_id": None, "started_at": f"{anchor} 09:04:00", "ended_at": f"{anchor} 09:05:00", "status": "failed", "outcome_counts": '{"failed": 1}', "error_detail": "synthetic failure fixture"},
        {"id": 5, "run_type": "search", "track_id": 1, "started_at": f"{anchor} 10:00:00", "ended_at": None, "status": "running", "outcome_counts": '{"new_posts": 0}', "error_detail": None},
    ]
    for row in run_rows:
        sql["run_log"] += insert("run_log", row, "synthetic run-log coverage")

    posts = list(source)
    for index, stage in enumerate(STAGES[:-1], start=1):
        posts.append({"id": f"synthetic-{index}", "source": "Synthetic", "position_title": f"Seed {stage} role", "company_name": "Synthetic Company", "url_ref": f"https://www.mycareersfuture.gov.sg/job/synthetic-{index}", "posted_date": (anchor - timedelta(days=index)).isoformat(), "salary_high": 10000, "is_open": 1, "closing_date": None, "applicants": 0, "description": None, "score": 0.8})
    posts.append({"id": "synthetic-closed", "source": "Synthetic", "position_title": "Seed closed role", "company_name": "Synthetic Company", "url_ref": "https://www.mycareersfuture.gov.sg/job/synthetic-closed", "posted_date": (anchor - timedelta(days=10)).isoformat(), "salary_high": 10000, "is_open": 0, "closing_date": (anchor - timedelta(days=1)).isoformat(), "applicants": 0, "description": None, "score": 0.8})
    while len(posts) < 13:
        index = len(posts) + 1
        posts.append({"id": f"synthetic-close-{index}", "source": "Synthetic", "position_title": "Seed close reason role", "company_name": "Synthetic Company", "url_ref": f"https://www.mycareersfuture.gov.sg/job/synthetic-close-{index}", "posted_date": (anchor - timedelta(days=index)).isoformat(), "salary_high": 10000, "is_open": 1, "closing_date": None, "applicants": 0, "description": None, "score": 0.8})
    for name, closing in (("future", anchor + timedelta(days=14)), ("nodate", None), ("past", anchor - timedelta(days=2))):
        posts.append({"id": f"synthetic-promote-{name}", "source": "Synthetic", "position_title": f"Seed promote {name} role", "company_name": "Synthetic Company", "url_ref": f"https://www.mycareersfuture.gov.sg/job/synthetic-promote-{name}", "posted_date": (anchor - timedelta(days=3)).isoformat(), "salary_high": 10000, "is_open": 1, "closing_date": closing.isoformat() if closing else None, "applicants": 0, "description": None, "score": 0.8})
    posts.append({"id": MANUAL_POST_ID, "source": "Manual", "position_title": "Seed manual role", "company_name": "Manual Company", "url_ref": "https://www.mycareersfuture.gov.sg/job/manual-seed-1", "posted_date": (anchor - timedelta(days=2)).isoformat(), "salary_high": 10000, "is_open": 1, "closing_date": None, "applicants": 0, "description": None, "score": 0.8})
    for post in posts:
        fields = {key: post[key] for key in ("id", "source", "position_title", "company_name", "url_ref", "posted_date", "salary_high", "is_open", "closing_date", "applicants", "description")}
        fields.update({"industry_classification": None, "mcf_ref": None, "src_method": "manual" if post["source"] in ("Synthetic", "Manual") else "scraped", "run_id": None if post["source"] in ("Synthetic", "Manual") else 1})
        sql["post"] += insert("post", fields, "synthetic below-threshold or lifecycle fixture" if post["source"] == "Synthetic" else None)

    for index, post in enumerate(posts):
        track_id = 1 if index else 2
        search_match = 0 if post["source"] in ("Synthetic", "Manual") else 1
        sql["post_track"] += insert("post_track", {"post_id": post["id"], "track_id": track_id, "search_match": search_match})
        sql["match_score"] += insert("match_score", {"post_id": post["id"], "track_id": track_id, "match_score": post["score"], "score_method": "title_keyword_v1"})
        if index == 0:
            sql["post_track"] += insert("post_track", {"post_id": post["id"], "track_id": 1, "search_match": 1})
            sql["match_score"] += insert("match_score", {"post_id": post["id"], "track_id": 1, "match_score": post["score"], "score_method": "title_keyword_v1"})

    leads = []
    for index, stage in enumerate(STAGES, start=1):
        post_id = MANUAL_POST_ID if stage == "APPLIED" else posts[index - 1]["id"]
        close_reason = None if stage != "CLOSED" else CLOSE_REASONS[0]
        leads.append({"id": index, "post_id": post_id, "track_id": 1, "status": "CLOSED" if stage == "CLOSED" else "OPEN", "stage": stage, "close_reason": close_reason, "title_override": None, "company_override": None, "deadline": anchor.isoformat() if stage == "CLOSED" else (anchor + timedelta(days=28)).isoformat(), "applied_date": anchor.isoformat() if stage != "TOAPPLY" else None, "first_attempt_date": None, "last_contact_date": None, "expected_salary_sgd": 10000, "created_at": f"{anchor} 07:00:00", "updated_at": f"{anchor} 07:00:00"})
    for index, reason in enumerate(CLOSE_REASONS[1:], start=len(STAGES) + 1):
        post = posts[index - 1]
        leads.append({"id": index, "post_id": post["id"], "track_id": 1, "status": "CLOSED", "stage": "CLOSED", "close_reason": reason, "title_override": None, "company_override": None, "deadline": anchor.isoformat(), "applied_date": anchor.isoformat(), "first_attempt_date": None, "last_contact_date": None, "expected_salary_sgd": 10000, "created_at": f"{anchor} 07:00:00", "updated_at": f"{anchor} 07:00:00"})
    for row in leads:
        if row["stage"] == "CALLBACK":
            row["last_contact_date"] = anchor.isoformat()
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

    callback_id = next(row["id"] for row in leads if row["stage"] == "CALLBACK")
    for lead_id, event_type, detail, stage, minute in (
        (1, "field_edited", "company_override: None -> Seed Co", "TOAPPLY", 31),
        (callback_id, "contact_logged", f"last_contact_date: None -> {anchor}", "CALLBACK", 40),
        (callback_id, "deadline_changed", f"deadline: {anchor} -> {anchor + timedelta(days=28)}", "CALLBACK", 41),
    ):
        sql["lead_event"] += insert("lead_event", {"id": event_id, "lead_id": lead_id, "event_type": event_type, "detail": detail,
                                                   "stage_from": stage, "stage_to": stage, "occurred_at": f"{anchor} 07:{minute}:00"},
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

    apply_failed_lead = next(row["id"] for row in leads if row["close_reason"] == "apply_failed")
    app_id = 1
    for status in APPLICATION_STATUSES:
        lead_id = 3 if status == "applied" else 1
        if status in ("post_closed", "post_unavailable"):
            lead_id = apply_failed_lead
        sql["application"] += insert("application", {"id": app_id, "lead_id": lead_id, "cv_id": 1, "status": status, "error_detail": None if status == "applied" else f"synthetic {status} fixture", "attempted_at": f"{anchor} 09:00:00", "run_id": 3 if status == "applied" else 4}, "synthetic apply outcome coverage")
        app_id += 1
    for attempt in range(2):
        sql["application"] += insert("application", {"id": app_id, "lead_id": 3, "cv_id": 1, "status": "applied", "error_detail": None, "attempted_at": f"{anchor} 09:0{attempt + 1}:00", "run_id": 3}, "synthetic retry pair")
        app_id += 1
    sql["session"] = insert("session", {"id": 1, "user_id": 1, "status": "missing", "uploaded_at": None, "cookie_ref": None})
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
                conn.executescript(sql_by_table[table])
            except sqlite3.Error as exc:
                raise RuntimeError(f"seed validation failed in {table}: {exc}") from exc
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