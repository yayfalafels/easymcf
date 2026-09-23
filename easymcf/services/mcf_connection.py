"""REQ-APPLY-06 — the mcf_attempt coordinator (ARCH-BOT-02's SingpassBrowser seam).

The connection-attempt workflow runs entirely inside the Flask process, one background thread per attempt
(ARCH-RUN-02's pattern), one headless Chromium context per attempt through SingpassBrowser. The thread opens
its own SQLite connection (ARCH-STO-07's one-connection-per-thread rule) rather than sharing the request's.

17.IS.04: Playwright's sync API is thread-bound — a browser/context/page created on one thread cannot be
called from another (`greenlet.error: cannot switch to a different thread`). The background thread therefore
owns its SingpassBrowser instance for the attempt's entire life, including the wait for the user's own
confirm/reject decision; a Flask request thread never touches the browser object directly. `confirm()` and
`cancel()` hand a decision to the waiting thread through a small per-attempt control object (an Event plus a
decision flag) instead, the same shape a producer/consumer queue would use with a single item.

The QR image and its own decoded link stay in this module's in-memory registry while an attempt is
unconfirmed, keyed by attempt id — short-lived, sensitive handling, never written to disk until the user
accepts. Only the confirmed outcome persists: the account email once accepted, and the exported storage state
once the attempt reaches `connected`, both written to `mcf_session`.
"""

from __future__ import annotations

import logging
import json
import os
import threading
import time
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .. import clock
from ..automation.singpass_browser import get_browser
from ..config import Config
from ..db.connection import get_connection
from ..errors import Conflict, RecordNotFound
from ..errors import ValidationFailed

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("starting", "awaiting_approval", "verifying", "account_confirmation_required")
CONFIRMATION_WAIT_S = 600
POLL_FOR_TERMINAL_S = 5.0
MCF_HOST = "mycareersfuture.gov.sg"

_REGISTRY: dict[int, dict] = {}
_LOCK = threading.Lock()


class _Cancelled(Exception):
    """Raised inside _run_attempt's own thread once it notices cancel() set the control flag."""


def get_qr_bytes(attempt_id: int) -> bytes | None:
    with _LOCK:
        entry = _REGISTRY.get(attempt_id)
    return entry["qr_bytes"] if entry else None


def get_qr_link(attempt_id: int) -> str | None:
    with _LOCK:
        entry = _REGISTRY.get(attempt_id)
    return entry["qr_link"] if entry else None


def _row(db, attempt_id: int) -> dict:
    return dict(db.execute("SELECT * FROM mcf_attempt WHERE id = ?", (attempt_id,)).fetchone())


def _set_status(db, attempt_id: int, status: str, **fields) -> None:
    assignments = "".join(f", {key} = ?" for key in fields)
    with db:
        db.execute(
            f"UPDATE mcf_attempt SET status = ?{assignments}, updated_at = ? WHERE id = ?",
            (status, *fields.values(), clock.now().isoformat(), attempt_id),
        )


def _poll_for_terminal(db, attempt_id: int, timeout_s: float = POLL_FOR_TERMINAL_S) -> dict:
    """confirm()/cancel() hand their decision to the waiting thread and cannot call the browser themselves
    (17.IS.04); this gives the common case a snappy synchronous response anyway, falling back to whatever the
    row currently holds once the budget runs out — the frontend's own poll picks up a later transition either way."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        row = _row(db, attempt_id)
        if row["status"] != "account_confirmation_required":
            return row
        time.sleep(0.05)
    return _row(db, attempt_id)


def start_attempt(db, config: Config, uid: int) -> dict:
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    existing = db.execute(
        f"SELECT * FROM mcf_attempt WHERE user_id = ? AND status IN ({placeholders})",
        (uid, *ACTIVE_STATUSES),
    ).fetchone()
    if existing:
        with _LOCK:
            runner_active = existing["id"] in _REGISTRY
        if runner_active:
            return dict(existing)
        _set_status(db, existing["id"], "failed", error_code="runner_unavailable")
    now = clock.now().isoformat()
    with db:
        cursor = db.execute(
            "INSERT INTO mcf_attempt (user_id, status, created_at, updated_at) VALUES (?, 'starting', ?, ?)",
            (uid, now, now),
        )
        attempt_id = cursor.lastrowid
    control = {"event": threading.Event(), "decision": None, "cancel_requested": False, "logout_requested": False}
    with _LOCK:
        _REGISTRY[attempt_id] = {"qr_bytes": None, "qr_link": None, "control": control}
    thread = threading.Thread(target=_run_attempt, args=(config, attempt_id, uid, control), daemon=True)
    thread.start()
    return _row(db, attempt_id)


def _check_account_match(db, uid: int, found_email: str) -> str | None:
    """A mismatch against an already-confirmed identity is blocked rather than silently overwritten, per
    scope item 06. Returns the error_code to record, or None when there is nothing to block."""
    prior = db.execute("SELECT confirmed_account_email FROM mcf_session WHERE user_id = ?", (uid,)).fetchone()
    if prior and prior["confirmed_account_email"] and prior["confirmed_account_email"] != found_email:
        return "account_mismatch"
    return None


def _confirmed_account_email(db, uid: int) -> str | None:
    row = db.execute("SELECT confirmed_account_email FROM mcf_session WHERE user_id = ?", (uid,)).fetchone()
    return row["confirmed_account_email"] if row else None


def _write_mcf_session(db, uid: int, cookie_ref: str | None, account_email: str) -> None:
    now = clock.now().isoformat()
    with db:
        db.execute(
            "INSERT INTO mcf_session (user_id, status, uploaded_at, cookie_ref, confirmed_account_email, confirmed_at) "
            "VALUES (?, 'valid', ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET status = 'valid', uploaded_at = excluded.uploaded_at, "
            "cookie_ref = excluded.cookie_ref, confirmed_account_email = excluded.confirmed_account_email, "
            "confirmed_at = excluded.confirmed_at",
            (uid, now, cookie_ref, account_email, now),
        )


def _run_attempt(config: Config, attempt_id: int, uid: int, control: dict) -> None:
    db = get_connection(config.db_path)
    browser = get_browser(config)
    stage = "open_qr_login"

    def _checkpoint() -> None:
        if control["cancel_requested"]:
            raise _Cancelled()

    def _update_qr(qr_bytes: bytes, qr_link: str | None) -> None:
        with _LOCK:
            entry = _REGISTRY.get(attempt_id)
            if entry is not None:
                entry["qr_bytes"] = qr_bytes
                entry["qr_link"] = qr_link

    try:
        browser.open_qr_login()
        _checkpoint()
        stage = "read_qr"
        qr_bytes, qr_link = browser.read_qr()
        _update_qr(qr_bytes, qr_link)
        _set_status(db, attempt_id, "awaiting_approval")
        _checkpoint()

        try:
            stage = "wait_for_authenticated"
            browser.wait_for_authenticated(_update_qr)
        except PlaywrightTimeoutError:
            # the QR's own approval window lapsed with no phone action, an ordinary outcome distinct from a
            # hard failure — 17.IS.02.
            browser.close()
            if not control["cancel_requested"]:
                _set_status(db, attempt_id, "expired")
            return
        _checkpoint()
        _set_status(db, attempt_id, "verifying")

        stage = "read_account_email"
        email = browser.read_account_email()
        _checkpoint()
        mismatch = _check_account_match(db, uid, email)
        if mismatch:
            browser.close()
            _set_status(db, attempt_id, "interaction_required", account_email=email, error_code=mismatch)
            return
        if _confirmed_account_email(db, uid) == email:
            stage = "export_previously_confirmed_session"
            cookie_ref = browser.export_storage_state(uid)
            browser.close()
            _write_mcf_session(db, uid, cookie_ref, email)
            _set_status(db, attempt_id, "connected", account_email=email)
            return
        _set_status(db, attempt_id, "account_confirmation_required", account_email=email)

        control["event"].wait(timeout=CONFIRMATION_WAIT_S)
        if control["cancel_requested"] and control["logout_requested"]:
            try:
                browser.logout()
            except Exception:  # noqa: BLE001 — local disconnect must still complete if MCF logout rejects the action
                pass
            browser.close()
        elif control["decision"] is True and not control["cancel_requested"]:
            cookie_ref = browser.export_storage_state(uid)
            browser.close()
            _write_mcf_session(db, uid, cookie_ref, email)
            _set_status(db, attempt_id, "connected")
        else:
            browser.close()
            if not control["cancel_requested"]:
                # an explicit reject, or the confirmation wait itself timed out with no decision either way
                _set_status(db, attempt_id, "cancelled")
            # else: cancel() already wrote 'cancelled' to the row itself; nothing left to do here
    except _Cancelled:
        browser.close()
        # cancel() already wrote 'cancelled' to the row before setting cancel_requested
    except Exception as exc:  # noqa: BLE001 — every failure mode lands in error_code, not a crashed thread
        logger.exception("MCF_DIAG attempt=%s failed stage=%s", attempt_id, stage)
        try:
            browser.close()
        except Exception:  # noqa: BLE001 — closing a browser that never fully opened must not mask the real error
            pass
        if not control["cancel_requested"]:
            _set_status(db, attempt_id, "failed", error_code=type(exc).__name__)
    finally:
        with _LOCK:
            _REGISTRY.pop(attempt_id, None)
        db.close()


def confirm(db, config: Config, uid: int, attempt_id: int, accept: bool) -> dict:
    row = db.execute("SELECT * FROM mcf_attempt WHERE id = ? AND user_id = ?", (attempt_id, uid)).fetchone()
    if row is None:
        raise RecordNotFound("attempt not found")
    if row["status"] != "account_confirmation_required":
        raise Conflict("attempt is not awaiting confirmation")

    with _LOCK:
        entry = _REGISTRY.get(attempt_id)
    if entry is None:
        raise Conflict("attempt is not awaiting confirmation")
    entry["control"]["decision"] = accept
    entry["control"]["event"].set()
    return _poll_for_terminal(db, attempt_id)


def cancel(db, config: Config, uid: int, attempt_id: int) -> dict:
    """Cancels an in-flight attempt, or disconnects an established one, per closure item 17.CK.09. The row
    flips to 'cancelled' immediately either way; a still-running background thread notices at its next
    checkpoint and closes its own browser rather than being touched from this thread (17.IS.04)."""
    row = db.execute("SELECT * FROM mcf_attempt WHERE id = ? AND user_id = ?", (attempt_id, uid)).fetchone()
    if row is None:
        raise RecordNotFound("attempt not found")

    if row["status"] == "connected":
        session = db.execute("SELECT cookie_ref FROM mcf_session WHERE user_id = ?", (uid,)).fetchone()
        if session and session["cookie_ref"]:
            _remove_cookie_file(config, session["cookie_ref"])
        with db:
            db.execute("UPDATE mcf_session SET status = 'missing', cookie_ref = NULL WHERE user_id = ?", (uid,))
        _set_status(db, attempt_id, "cancelled")
        return _row(db, attempt_id)

    with _LOCK:
        entry = _REGISTRY.get(attempt_id)
    if entry is not None:
        entry["control"]["cancel_requested"] = True
        entry["control"]["logout_requested"] = row["status"] == "account_confirmation_required"
        entry["control"]["event"].set()
    _set_status(db, attempt_id, "cancelled")
    return _row(db, attempt_id)


def _remove_cookie_file(config: Config, cookie_ref: str) -> None:
    paths = [
        os.path.join(config.secrets_dir, cookie_ref),
        os.path.join(config.secrets_dir, f"{os.path.splitext(cookie_ref)[0]}.session.json"),
    ]
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass  # a disconnect must succeed even if the file is already gone


def _validated_mcf_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == MCF_HOST or host.endswith("." + MCF_HOST)):
        raise ValidationFailed("url must be an HTTPS MyCareersFuture URL", field="url")
    return url


def _session_storage_script(storage_path: str) -> str | None:
    sidecar_path = f"{os.path.splitext(storage_path)[0]}.session.json"
    try:
        with open(sidecar_path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return None
    encoded = json.dumps(state).replace("</", "<\\/")
    return (
        "(() => { const all = " + encoded + "; const values = all[location.origin] || {}; "
        "for (const [key, value] of Object.entries(values)) sessionStorage.setItem(key, value); })();"
    )


def _restored_page_is_authenticated(page) -> bool:
    from ..automation.singpass_browser import ACCOUNT_MENU_TRIGGER, LOGIN_LOCATORS, QR_RENDER_TIMEOUT_MS

    deadline = time.monotonic() + QR_RENDER_TIMEOUT_MS / 1000
    while time.monotonic() < deadline:
        if page.locator(ACCOUNT_MENU_TRIGGER).first.is_visible():
            return True
        for _, build in LOGIN_LOCATORS:
            if build(page).first.is_visible():
                return False
        page.wait_for_timeout(250)
    return False


def _run_interactive_browser(config: Config, uid: int, storage_path: str, url: str) -> None:
    from playwright.sync_api import Error as PlaywrightError, sync_playwright

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False, channel="chromium")
            context = browser.new_context(storage_state=storage_path)
            session_script = _session_storage_script(storage_path)
            if session_script:
                context.add_init_script(script=session_script)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            if _restored_page_is_authenticated(page):
                logger.warning("MCF_DIAG interactive browser authenticated url=%s", page.url)
            else:
                db = get_connection(config.db_path)
                try:
                    mark_reauthentication_required(db, uid)
                finally:
                    db.close()
                logger.warning("MCF_DIAG interactive browser requires reauthentication url=%s", page.url)
            while True:
                pages = [page for page in context.pages if not page.is_closed()]
                if not pages:
                    break
                try:
                    pages[0].wait_for_timeout(250)
                except PlaywrightError:
                    if pages[0].is_closed():
                        break
                    raise
            browser.close()
    except Exception:  # noqa: BLE001 — failure is logged after the request has already returned
        logger.exception("MCF_DIAG interactive browser failed url=%s", url)


def _start_interactive_browser(config: Config, uid: int, storage_path: str, url: str) -> None:
    threading.Thread(target=_run_interactive_browser, args=(config, uid, storage_path, url), daemon=True).start()


def open_interactive_session(db, config: Config, uid: int, url: str) -> dict:
    target = _validated_mcf_url(url)
    session = db.execute(
        "SELECT status, cookie_ref FROM mcf_session WHERE user_id = ?", (uid,)
    ).fetchone()
    if session is None or session["status"] != "valid":
        return {"mode": "redirect", "url": target}
    cookie_ref = session["cookie_ref"]
    valid_ref = cookie_ref and os.path.basename(cookie_ref) == cookie_ref
    storage_path = os.path.join(config.secrets_dir, cookie_ref) if valid_ref else None
    if not storage_path or not os.path.isfile(storage_path):
        with db:
            db.execute(
                "UPDATE mcf_session SET status = 'missing', cookie_ref = NULL WHERE user_id = ?",
                (uid,),
            )
        return {"mode": "redirect", "url": target}
    _start_interactive_browser(config, uid, storage_path, target)
    return {"mode": "authenticated", "url": target}


def reconcile_local_sessions(config: Config, db=None) -> None:
    owns_connection = db is None
    db = db or get_connection(config.db_path)
    try:
        rows = db.execute("SELECT user_id, cookie_ref FROM mcf_session WHERE status = 'valid'").fetchall()
        for row in rows:
            cookie_ref = row["cookie_ref"]
            valid_ref = cookie_ref and os.path.basename(cookie_ref) == cookie_ref
            if valid_ref and os.path.isfile(os.path.join(config.secrets_dir, cookie_ref)):
                continue
            with db:
                db.execute(
                    "UPDATE mcf_session SET status = 'missing', cookie_ref = NULL WHERE user_id = ?",
                    (row["user_id"],),
                )
    finally:
        if owns_connection:
            db.close()


def mark_reauthentication_required(db, user_id: int) -> None:
    """The internal call apply automation's own service makes when a restored context lands on MCF's login
    page unexpectedly (REQ-APPLY-06). No endpoint of its own — the existing search polls surface the result."""
    with db:
        db.execute("UPDATE mcf_session SET status = 'expired' WHERE user_id = ?", (user_id,))
        db.execute(
            "UPDATE mcf_attempt SET status = 'reauthentication_required', updated_at = ? "
            "WHERE user_id = ? AND id = (SELECT id FROM mcf_attempt WHERE user_id = ? ORDER BY id DESC LIMIT 1)",
            (clock.now().isoformat(), user_id, user_id),
        )
