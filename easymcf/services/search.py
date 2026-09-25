"""REQ-SRCH-02..09 — the search-run pipeline: trigger, sweep, detail pass, promotion,
manual entry, and startup orphaned-run reconciliation (Workflow 2/3/4).

Every function a request or a background thread calls takes the user id first and
confirms visibility of every id it receives (ARCH-AUTH-04/08) — this module never trusts
a caller's own claim about which rows it may touch. `run_sweep`/`run_detail_pass` take an
`MCFBrowser` (ARCH-BOT-02) explicitly, so the oracle tests in
`tests/backend/test_search_pipeline.py` call them directly against
`easymcf/automation/fixture.py`'s known corpus with no HTTP request, no Flask route, and
no real browser involved (STRAT-SILO-05).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from datetime import date, timedelta

from .. import clock, tenancy
from ..automation import parsing
from ..automation.browser import MCFBrowser, get_browser
from ..config import Config
from ..db.connection import get_connection
from ..errors import Conflict, RunInFlight
from . import leads

logger = logging.getLogger(__name__)

_KEYWORD_RETRY_ATTEMPTS = 3
_KEYWORD_RETRY_DELAY_S = 0.2
_OUTCOME_KEYS = (
    "keywords", "pages", "cards", "new_posts", "existing_posts",
    "detailed", "closed", "detail_errors", "promoted", "promote_errors",
)


def post_id(source: str, urlid: str, posted_date: date) -> str:
    return f"{source}-{urlid[-32:]}-{posted_date.isoformat()}"


def start_run(db, uid: int, track_id: int, trigger_source: str) -> sqlite3.Row:
    """Workflow 2 step 01. The INSERT is the concurrency guard — ARCH-RUN-03's partial
    unique index on (user_id, run_type) WHERE status='running' rejects a second running
    search for this user, surfaced here as RunInFlight rather than a raw IntegrityError."""
    tenancy.require_visible(db, uid, "track", track_id)
    track = db.execute("SELECT is_active FROM track WHERE id = ?", (track_id,)).fetchone()
    if not track["is_active"]:
        raise Conflict(f"track {track_id} is archived")
    profile = db.execute("SELECT 1 FROM search_profile WHERE track_id = ?", (track_id,)).fetchone()
    if profile is None:
        raise Conflict(f"track {track_id} has no search profile")
    at = clock.stamp()
    try:
        with db:
            run_id = db.execute(
                "INSERT INTO run_log (run_type, user_id, track_id, started_at, status, trigger_source) "
                "VALUES ('search', ?, ?, ?, 'running', ?)",
                (uid, track_id, at, trigger_source),
            ).lastrowid
    except sqlite3.IntegrityError as exc:
        running = db.execute(
            "SELECT id FROM run_log WHERE user_id = ? AND run_type = 'search' AND status = 'running'", (uid,)
        ).fetchone()
        raise RunInFlight(running["id"]) from exc
    threading.Thread(target=_run_search, args=(run_id, uid, track_id), daemon=True).start()
    return db.execute("SELECT * FROM run_log WHERE id = ?", (run_id,)).fetchone()


def _fetch_cards_with_retry(browser: "MCFBrowser", keyword: str, min_salary: int | None, page: int, today: date):
    """A page fetch that raises is retried twice with an explicit bounded wait (Algorithms
    section) — never a fixed sleep loop with no bound (playwright skill)."""
    last_exc: Exception | None = None
    for attempt in range(_KEYWORD_RETRY_ATTEMPTS):
        try:
            html = browser.search_page(keyword, min_salary, page)
            return parsing.parse_cards(html, today)
        except Exception as exc:  # noqa: BLE001 — a bad page must not abort the whole sweep
            last_exc = exc
            if attempt < _KEYWORD_RETRY_ATTEMPTS - 1:
                time.sleep(_KEYWORD_RETRY_DELAY_S)
    raise last_exc  # type: ignore[misc]


def _record_keyword_failure(db, run_id: int, keyword: str, exc: Exception) -> None:
    with db:
        db.execute(
            "UPDATE run_log SET error_detail = "
            "CASE WHEN error_detail IS NULL THEN ? ELSE error_detail || '; ' || ? END WHERE id = ?",
            (f"keyword {keyword!r} fetch failed: {exc}", f"keyword {keyword!r} fetch failed: {exc}", run_id),
        )


def run_sweep(db, uid: int, track_id: int, run_id: int, browser: "MCFBrowser") -> dict:
    """Pages every keyword until an empty page; persists+commits per page (REQ-SRCH-04);
    dedups on the post id (REQ-SRCH-05); writes the fixed match_score inline (REQ-SRCH-09)."""
    profile = db.execute("SELECT * FROM search_profile WHERE track_id = ?", (track_id,)).fetchone()
    counts = {key: 0 for key in ("keywords", "pages", "cards", "new_posts", "existing_posts")}
    keywords = [k.strip() for k in profile["keywords"].split(",") if k.strip()]
    today = clock.today()
    for keyword in keywords:
        counts["keywords"] += 1
        page = 0
        while True:
            try:
                cards = _fetch_cards_with_retry(browser, keyword, profile["min_salary"], page, today)
            except Exception as exc:  # noqa: BLE001 — a third failure ends this keyword, the next still proceeds
                _record_keyword_failure(db, run_id, keyword, exc)
                break
            counts["pages"] += 1
            if not cards:
                break
            counts["cards"] += len(cards)
            with db:
                for card in cards:
                    pid = post_id("MyCareerFutures", card["urlid"], card["posted_date"])
                    existing = db.execute("SELECT 1 FROM post WHERE id = ?", (pid,)).fetchone()
                    if existing is None:
                        db.execute(
                            "INSERT INTO post (id, source, position_title, company_name, url_ref, posted_date, "
                            "salary_high, src_method, run_id) "
                            "VALUES (?, 'MyCareerFutures', ?, ?, ?, ?, ?, 'scraped', ?)",
                            (pid, card["position_title"], card["company_name"], card["url_ref"],
                             card["posted_date"].isoformat(), card["salary_high"], run_id),
                        )
                        counts["new_posts"] += 1
                    else:
                        counts["existing_posts"] += 1
                    pairing = db.execute(
                        "SELECT 1 FROM post_track WHERE post_id = ? AND track_id = ?", (pid, track_id)
                    ).fetchone()
                    if pairing is None:
                        db.execute(
                            "INSERT INTO post_track (post_id, track_id, search_match) VALUES (?, ?, 1)",
                            (pid, track_id),
                        )
                        db.execute(
                            "INSERT INTO match_score (post_id, track_id, match_score, score_method) "
                            "VALUES (?, ?, 1.0, 'search_match_v1')",
                            (pid, track_id),
                        )
                db.execute("UPDATE run_log SET outcome_counts = ? WHERE id = ?", (json.dumps(counts), run_id))
            page += 1
    return counts


def _merge_outcome_counts(db, run_id: int, partial: dict) -> None:
    row = db.execute("SELECT outcome_counts FROM run_log WHERE id = ?", (run_id,)).fetchone()
    current = json.loads(row["outcome_counts"]) if row and row["outcome_counts"] else {}
    current.update(partial)
    db.execute("UPDATE run_log SET outcome_counts = ? WHERE id = ?", (json.dumps(current), run_id))


def run_detail_pass(db, run_id: int, browser: "MCFBrowser") -> dict:
    """Candidates: src_method='scraped', is_open=1, mcf_ref IS NULL. One commit per post
    (REQ-SRCH-04/06). The open/closed marker is read first; a closed posting's other
    fields are never scraped (Detail pass Algorithms note)."""
    candidates = db.execute(
        "SELECT id, url_ref FROM post WHERE src_method = 'scraped' AND is_open = 1 AND mcf_ref IS NULL "
        "ORDER BY posted_date DESC"
    ).fetchall()
    counts = {"detailed": 0, "closed": 0, "detail_errors": 0}
    for row in candidates:
        try:
            html = browser.detail_page(row["url_ref"])
            detail = parsing.parse_detail(html)
        except Exception:  # noqa: BLE001 — the post stays a candidate for the next run's retry
            counts["detail_errors"] += 1
            continue
        with db:
            if not detail["is_open"]:
                db.execute("UPDATE post SET is_open = 0 WHERE id = ?", (row["id"],))
                counts["closed"] += 1
            else:
                db.execute(
                    "UPDATE post SET closing_date = ?, applicants = ?, industry_classification = ?, "
                    "description = ?, mcf_ref = ? WHERE id = ?",
                    (detail["closing_date"], detail["applicants"], detail["industry_classification"],
                     detail["description"], detail["mcf_ref"], row["id"]),
                )
                counts["detailed"] += 1
            _merge_outcome_counts(db, run_id, counts)
    return counts


def promote_qualifying(db, uid: int, track_id: int) -> dict:
    """Every post_track(track_id, search_match=1) with post.is_open=1, post.mcf_ref set,
    and no lead[uid] yet (Promotion Workflow 4). A promotion that raises is counted, not
    propagated — one bad post must not stop the rest (REQ-SRCH/APPLY's run-level rule)."""
    rows = db.execute(
        "SELECT pt.post_id FROM post_track pt JOIN post p ON p.id = pt.post_id "
        "WHERE pt.track_id = ? AND pt.search_match = 1 AND p.is_open = 1 AND p.mcf_ref IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM lead WHERE lead.user_id = ? AND lead.post_id = pt.post_id) "
        "ORDER BY p.posted_date", (track_id, uid),
    ).fetchall()
    promoted, errors = 0, 0
    for row in rows:
        try:
            with db:
                leads.promote(db, {"post_id": row["post_id"], "track_id": track_id})
            promoted += 1
        except Exception:  # noqa: BLE001 — one promotion failing must not block the rest (Workflow 4)
            logger.exception("MCF_DIAG promotion failed post_id=%s track_id=%s", row["post_id"], track_id)
            errors += 1
    return {"promoted": promoted, "promote_errors": errors}


def posts_for_track(db, uid: int, track_id: int, max_age_weeks: int | None) -> list[dict]:
    """Joined read: post columns (no description) + match_score, score_method, search_match
    and lead_id. An explicit max_age_weeks overrides the profile's own default, display
    only (Posts display filter) — promotion itself applies no age filter of its own."""
    tenancy.require_visible(db, uid, "track", track_id)
    if max_age_weeks is None:
        profile = db.execute("SELECT max_age_weeks FROM search_profile WHERE track_id = ?", (track_id,)).fetchone()
        max_age_weeks = profile["max_age_weeks"] if profile else None
    sql = (
        "SELECT p.id, p.source, p.position_title, p.company_name, p.url_ref, p.posted_date, p.salary_high, "
        "p.is_open, p.closing_date, p.applicants, p.industry_classification, p.mcf_ref, p.src_method, "
        "ms.match_score, ms.score_method, pt.search_match, "
        "(SELECT lead.id FROM lead WHERE lead.user_id = :uid AND lead.post_id = p.id) AS lead_id "
        "FROM post_track pt JOIN post p ON p.id = pt.post_id "
        "JOIN match_score ms ON ms.post_id = pt.post_id AND ms.track_id = pt.track_id "
        "WHERE pt.track_id = :track_id"
    )
    params = {"uid": uid, "track_id": track_id}
    if max_age_weeks is not None:
        params["cutoff"] = (clock.today() - timedelta(weeks=max_age_weeks)).isoformat()
        sql += " AND (p.posted_date IS NULL OR p.posted_date >= :cutoff)"
    sql += " ORDER BY p.posted_date DESC"
    return [dict(row) for row in db.execute(sql, params).fetchall()]


def _manual_reference(url_ref: str | None, position_title: str, company_name: str) -> tuple[str, str]:
    """A manual post matching an MCF URL takes MCF's own source+reference, so it dedups
    against the scraped copy of the same posting; otherwise Source='Manual' and the
    reference is the first 32 hex characters of a SHA-1 over title and company."""
    if url_ref and "mycareersfuture.gov.sg" in url_ref:
        path = url_ref.split("?", 1)[0]
        marker = "/job/"
        idx = path.find(marker)
        slug = path[idx + len(marker):] if idx != -1 else path.rstrip("/").rsplit("/", 1)[-1]
        return "MyCareerFutures", slug.strip("/")
    digest = hashlib.sha1(f"{position_title}{company_name}".encode("utf-8")).hexdigest()
    return "Manual", digest[:32]


def add_manual_post(db, uid: int, track_id: int, body: dict) -> dict:
    """Workflow 3. The service writes the post row on the server — users never write
    `post` directly (REQ-AUTH-06)."""
    tenancy.require_visible(db, uid, "track", track_id)
    track = db.execute("SELECT is_active FROM track WHERE id = ?", (track_id,)).fetchone()
    if not track["is_active"]:
        raise Conflict(f"track {track_id} is archived")
    posted_date = date.fromisoformat(body.get("posted_date") or clock.today().isoformat())
    source, urlid = _manual_reference(body.get("url_ref"), body["position_title"], body["company_name"])
    pid = post_id(source, urlid, posted_date)
    existing = db.execute("SELECT id FROM post WHERE id = ?", (pid,)).fetchone()
    already_visible = existing and db.execute(
        "SELECT 1 FROM post_track WHERE post_id = ? AND track_id IN (SELECT id FROM track WHERE user_id = ?)",
        (pid, uid),
    ).fetchone()
    if already_visible:
        raise Conflict(f"post {pid} already visible", post_id=pid)
    with db:
        if not existing:
            db.execute(
                "INSERT INTO post (id, source, position_title, company_name, url_ref, posted_date, "
                "salary_high, src_method) VALUES (?, ?, ?, ?, ?, ?, ?, 'manual')",
                (pid, source, body["position_title"], body["company_name"], body.get("url_ref"),
                 posted_date.isoformat(), body.get("salary_high")),
            )
        db.execute("INSERT INTO post_track (post_id, track_id, search_match) VALUES (?, ?, 0)", (pid, track_id))
        db.execute(
            "INSERT INTO match_score (post_id, track_id, match_score, score_method) VALUES (?, ?, 1.0, 'manual_v1')",
            (pid, track_id),
        )
        lead_id = leads.promote(db, {"post_id": pid, "track_id": track_id})
    return {
        "post": dict(db.execute("SELECT * FROM post WHERE id = ?", (pid,)).fetchone()),
        "post_track": {"post_id": pid, "track_id": track_id, "search_match": False},
        "match_score": {"post_id": pid, "track_id": track_id, "match_score": 1.0, "score_method": "manual_v1"},
        "lead_id": lead_id,
    }


def reconcile_orphaned_runs(db) -> None:
    """Startup reconciliation (Interrupted runs design note): every `running` row of every
    user becomes `failed`, before the server accepts requests and before the scheduler
    starts — otherwise ARCH-RUN-03's partial unique index would refuse every later search
    by a user whose previous run's process died mid-flight."""
    with db:
        db.execute(
            "UPDATE run_log SET status = 'failed', ended_at = ?, "
            "error_detail = 'interrupted: process stopped before the run finished' WHERE status = 'running'",
            (clock.stamp(),),
        )


def _final_status(db, run_id: int, counts: dict, crashed: bool) -> str:
    if crashed:
        return "failed"
    row = db.execute("SELECT error_detail FROM run_log WHERE id = ?", (run_id,)).fetchone()
    keyword_failed = bool(row["error_detail"])
    if keyword_failed and counts["pages"] == 0 and counts["new_posts"] == 0 and counts["existing_posts"] == 0:
        return "failed"  # every keyword failed outright — Run status algorithm's "failed" branch
    if keyword_failed or counts["detail_errors"] or counts["promote_errors"]:
        return "partial"
    return "success"


def _run_search(run_id: int, uid: int, track_id: int) -> None:
    """The background thread `start_run` spawns (ARCH-RUN-02): its own connection, its own
    browser context (ARCH-STO-07/ARCH-RUN-04). Every step's exceptions are counted, never
    left to crash the thread — the run always ends with a terminal status (Workflow 2
    step 06)."""
    config = Config()
    db = get_connection(config.db_path)
    browser = get_browser(config)
    counts = {key: 0 for key in _OUTCOME_KEYS}
    crashed = False
    try:
        counts.update(run_sweep(db, uid, track_id, run_id, browser))
        counts.update(run_detail_pass(db, run_id, browser))
        counts.update(promote_qualifying(db, uid, track_id))
    except Exception:  # noqa: BLE001 — every run ends with a terminal status, never a crashed thread
        logger.exception("MCF_DIAG search run %s failed", run_id)
        crashed = True
    finally:
        try:
            browser.close()
        except Exception:  # noqa: BLE001 — closing a browser that never fully started must not mask the error
            pass
    counts["mcf_mode"] = config.mcf_mode
    status = _final_status(db, run_id, counts, crashed)
    with db:
        db.execute(
            "UPDATE run_log SET status = ?, ended_at = ?, outcome_counts = ? WHERE id = ?",
            (status, clock.stamp(), json.dumps(counts), run_id),
        )
    db.close()
