"""REQ-PLAT-01 — one Resource per table, seven generic shapes served for all of them."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Callable

import jsonschema
from flask import Blueprint, g, jsonify, request

from .. import tenancy
from ..errors import Conflict, RecordNotFound, ValidationFailed
from .db import get_db

bp = Blueprint("api", __name__, url_prefix="/api/v1")
REGISTRY: dict[str, "Resource"] = {}
GENERIC = frozenset({"get", "search", "create", "update", "delete", "batch", "bulk_delete"})


@dataclass(frozen=True)
class Resource:
    table: str
    create_schema: dict
    update_schema: dict
    verbs: frozenset = GENERIC
    pk: str = "id"
    select_sql: str | None = None
    bool_columns: tuple = ()
    parents: tuple = ()                   # ((body_field, parent_table), ...) each must be visible to the caller
    owned: Callable | None = None         # (db, uid) -> server-set columns, merged over the body after validation
    create_fn: Callable | None = None     # (db, body) -> new row id
    update_fn: Callable | None = None     # (db, row_id, body) -> None
    before_read: Callable | None = None   # (db) -> None
    batch_schema: dict | None = None      # per-row schema for a hook-backed batch of updates
    batch_fn: Callable | None = None      # (db, rows, uid) -> list of row ids, applied in one transaction
    delete_fn: Callable | None = None     # (db, row_id) -> dict | None; a returned row answers 200 instead of 204
    search_fn: Callable | None = None     # (db, uid, args) -> list[dict]; overrides the raw-column filter+select
                                           # below for a search that must join across tables rather than filter the
                                           # resource's own columns (a hook, same URL/verb, per the api design's
                                           # generic-shaped-but-hook-backed classification — e.g. post's
                                           # track-scoped, match-score-joined read, 10.EL.13's search.posts_for_track)


def register(resource: Resource) -> None:
    if resource.table not in tenancy.SCOPES and resource.table not in tenancy.UNSCOPED:
        raise RuntimeError(f"resource {resource.table} has no ownership declaration in easymcf/tenancy.py")
    REGISTRY[resource.table] = resource


def _resource(table: str, verb: str) -> Resource:
    resource = REGISTRY.get(table)
    if resource is None or verb not in resource.verbs:
        raise RecordNotFound(f"unknown table or unsupported operation: {table}")
    return resource


def _validate(body, schema: dict) -> None:
    if not isinstance(body, dict):
        raise ValidationFailed("request body must be a JSON object")
    error = jsonschema.exceptions.best_match(jsonschema.Draft202012Validator(schema).iter_errors(body))
    if error is None:
        return
    field = error.path[0] if error.path else None
    if error.validator == "required":
        field = re.search(r"'([^']+)'", error.message).group(1)
        raise ValidationFailed(f"{field} is required", field=field)
    if error.validator == "additionalProperties":
        field = re.search(r"\('([^']+)' was unexpected", error.message).group(1)
        raise ValidationFailed(f"{field} is not a writable field", field=field)
    raise ValidationFailed(error.message, field=field)


def _uid() -> int:
    return g.user_id


def _scope_sql(resource: Resource) -> str | None:
    return tenancy.SCOPES.get(resource.table)


def _check_parents(db, resource: Resource, body: dict, uid: int, updating: bool = False) -> None:
    """A create or update that names a parent row (a track, a lead, a post) needs that row visible to the caller.
    A parent that is missing or not visible answers 404 on create and 400 on the field on update, with one message
    for both, so a request never reveals whether another user's row exists."""
    for field, table in resource.parents:
        if body.get(field) is not None:
            pk = REGISTRY[table].pk if table in REGISTRY else "id"
            try:
                tenancy.require_visible(db, uid, table, body[field], pk)
            except RecordNotFound:
                if updating:
                    raise ValidationFailed(f"{table} {body[field]} not found", field=field)
                raise


def _select(resource: Resource) -> str:
    return resource.select_sql or f"SELECT {resource.table}.* FROM {resource.table}"


def _serialize(resource: Resource, row: sqlite3.Row) -> dict:
    data = dict(row)
    for column in resource.bool_columns:
        data[column] = bool(data[column])
    return data


def _coerce(resource: Resource, body: dict) -> dict:
    return {k: int(v) if k in resource.bool_columns else v for k, v in body.items()}


def _fetch(db, resource: Resource, row_id, uid: int) -> dict:
    scope = _scope_sql(resource)
    sql = f"{_select(resource)} WHERE {resource.table}.{resource.pk} = :id" + (f" AND ({scope})" if scope else "")
    row = db.execute(sql, {"id": row_id, "uid": uid}).fetchone()
    if row is None:
        raise RecordNotFound(f"{resource.table} {row_id} not found")
    return _serialize(resource, row)


def _insert(db, resource: Resource, body: dict) -> int:
    body = _coerce(resource, body)
    cols, marks = ", ".join(body), ", ".join("?" for _ in body)
    cursor = db.execute(f"INSERT INTO {resource.table} ({cols}) VALUES ({marks})", tuple(body.values()))
    return body.get(resource.pk, cursor.lastrowid)


def _guarded(fn, *args):
    try:
        return fn(*args)
    except sqlite3.IntegrityError as exc:
        raise Conflict(str(exc)) from exc


@bp.get("/<table>/<row_id>")
def get_one(table: str, row_id: str):
    resource, db = _resource(table, "get"), get_db()
    if resource.before_read:
        resource.before_read(db)
    return jsonify(_fetch(db, resource, row_id, _uid()))


@bp.get("/<table>/search")
def search(table: str):
    resource, db = _resource(table, "search"), get_db()
    if resource.before_read:
        resource.before_read(db)
    if resource.search_fn:
        return jsonify(resource.search_fn(db, _uid(), request.args))
    columns = {r["name"] for r in db.execute(f"PRAGMA table_info({resource.table})")}
    clauses, params = [], {"uid": _uid()}
    for i, (key, value) in enumerate(request.args.items()):
        if key not in columns:
            raise ValidationFailed(f"unknown filter: {key}", field=key)
        clauses.append(f"{resource.table}.{key} = :f{i}")
        params[f"f{i}"] = value
    if _scope_sql(resource):
        clauses.append(f"({_scope_sql(resource)})")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(f"{_select(resource)}{where} ORDER BY {resource.table}.{resource.pk}", params).fetchall()
    return jsonify([_serialize(resource, r) for r in rows])


def _prepare(db, resource: Resource, body, uid: int) -> dict:
    """Validate the client body, check its parents, then add the server-owned columns, which the body can never set."""
    _validate(body, resource.create_schema)
    _check_parents(db, resource, body, uid)
    return {**body, **(resource.owned(db, uid) if resource.owned else {})}


@bp.post("/<table>")
def create(table: str):
    resource, db = _resource(table, "create"), get_db()
    body, uid = request.get_json(silent=True), _uid()
    body = _prepare(db, resource, body, uid)
    with db:
        row_id = resource.create_fn(db, body) if resource.create_fn else _guarded(_insert, db, resource, body)
        row = _fetch(db, resource, row_id, uid)
    return jsonify(row), 201


@bp.put("/<table>/<row_id>")
def update(table: str, row_id: str):
    resource, db = _resource(table, "update"), get_db()
    body, uid = request.get_json(silent=True), _uid()
    _validate(body, resource.update_schema)
    with db:
        _fetch(db, resource, row_id, uid)
        _check_parents(db, resource, body, uid, updating=True)
        if resource.update_fn:
            resource.update_fn(db, row_id, body)
        elif body:
            body = _coerce(resource, body)
            sets = ", ".join(f"{k} = ?" for k in body)
            _guarded(db.execute, f"UPDATE {resource.table} SET {sets} WHERE {resource.pk} = ?", (*body.values(), row_id))
        row = _fetch(db, resource, row_id, uid)
    return jsonify(row)


def _referenced_by(db, table: str, row_id) -> dict[str, int]:
    """Every `child_table.column` whose foreign key points at this row, with its row count. The FK-guard 409 names
    them, so a user sees what still uses the row instead of SQLite's bare "FOREIGN KEY constraint failed"."""
    found = {}
    tables = [r["name"] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    for child in tables:
        for fk in db.execute(f"PRAGMA foreign_key_list({child})").fetchall():
            if fk["table"] != table:
                continue
            count = db.execute(f"SELECT COUNT(*) FROM {child} WHERE {fk['from']} = ?", (row_id,)).fetchone()[0]
            if count:
                found[f"{child}.{fk['from']}"] = count
    return found


@bp.delete("/<table>/<row_id>")
def delete(table: str, row_id: str):
    resource, db = _resource(table, "delete"), get_db()
    with db:
        _fetch(db, resource, row_id, _uid())
        if resource.delete_fn:
            kept = resource.delete_fn(db, row_id)
            if kept is not None:
                return jsonify(_fetch(db, resource, row_id, _uid()))
            return "", 204
        try:
            db.execute(f"DELETE FROM {resource.table} WHERE {resource.pk} = ?", (row_id,))
        except sqlite3.IntegrityError as exc:
            refs = _referenced_by(db, resource.table, row_id)
            if not refs:
                raise Conflict(str(exc)) from exc
            names = ", ".join(f"{name} ({count})" for name, count in refs.items())
            raise Conflict(f"{resource.table} {row_id} is still referenced by {names}", referenced_by=refs) from exc
    return "", 204


@bp.post("/<table>/batch")
def batch(table: str):
    resource, db = _resource(table, "batch"), get_db()
    rows = (request.get_json(silent=True) or {}).get("rows")
    if not isinstance(rows, list):
        raise ValidationFailed("rows must be a list", field="rows")
    if resource.batch_fn:
        return _batch_update(resource, db, rows)
    created, uid = [], _uid()
    with db:
        for body in rows:
            body = _prepare(db, resource, body, uid)
            created.append(_fetch(db, resource, _guarded(_insert, db, resource, body), uid))
    return jsonify(created), 201


def _batch_update(resource: Resource, db, rows: list):
    """The `batch` shape on a hook-backed table: every row is an update, applied all-or-nothing (REQ-CRM-11)."""
    for body in rows:
        try:
            _validate(body, resource.batch_schema)
        except ValidationFailed as exc:
            raise ValidationFailed(exc.message, field="rows") from exc
    uid = _uid()
    with db:
        ids = resource.batch_fn(db, rows, uid)   # the hook checks each row is visible after its own shape checks
        return jsonify([_fetch(db, resource, row_id, uid) for row_id in ids])


@bp.post("/<table>/delete")
def bulk_delete(table: str):
    resource, db = _resource(table, "bulk_delete"), get_db()
    where = (request.get_json(silent=True) or {}).get("filter")
    if not isinstance(where, dict) or not where:
        raise ValidationFailed("filter must be a non-empty object", field="filter")
    columns = {r["name"] for r in db.execute(f"PRAGMA table_info({resource.table})")}
    if not set(where) <= columns:
        raise ValidationFailed("filter names an unknown column", field="filter")
    params = {f"f{i}": v for i, v in enumerate(where.values())} | {"uid": _uid()}
    clause = " AND ".join(f"{k} = :f{i}" for i, k in enumerate(where))
    visible = tenancy.SCOPES.get(resource.table, "1 = 1")
    sql = (f"DELETE FROM {resource.table} WHERE {clause} AND {resource.pk} IN "
           f"(SELECT {resource.pk} FROM {resource.table} WHERE {visible})")
    with db:
        count = _guarded(db.execute, sql, params).rowcount
    return jsonify({"deleted": count})
