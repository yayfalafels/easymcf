"""REQ-PLAT-01 — one Resource per table, seven generic shapes served for all of them."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Callable

import jsonschema
from flask import Blueprint, jsonify, request

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
    defaults: Callable | None = None      # (db) -> dict merged beneath the request body on create
    create_fn: Callable | None = None     # (db, body) -> new row id
    update_fn: Callable | None = None     # (db, row_id, body) -> None
    before_read: Callable | None = None   # (db) -> None
    batch_schema: dict | None = None      # per-row schema for a hook-backed batch of updates
    batch_fn: Callable | None = None      # (db, rows) -> list of row ids, applied in one transaction


def register(resource: Resource) -> None:
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


def _select(resource: Resource) -> str:
    return resource.select_sql or f"SELECT {resource.table}.* FROM {resource.table}"


def _serialize(resource: Resource, row: sqlite3.Row) -> dict:
    data = dict(row)
    for column in resource.bool_columns:
        data[column] = bool(data[column])
    return data


def _coerce(resource: Resource, body: dict) -> dict:
    return {k: int(v) if k in resource.bool_columns else v for k, v in body.items()}


def _fetch(db, resource: Resource, row_id) -> dict:
    row = db.execute(f"{_select(resource)} WHERE {resource.table}.{resource.pk} = ?", (row_id,)).fetchone()
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
    return jsonify(_fetch(db, resource, row_id))


@bp.get("/<table>/search")
def search(table: str):
    resource, db = _resource(table, "search"), get_db()
    if resource.before_read:
        resource.before_read(db)
    columns = {r["name"] for r in db.execute(f"PRAGMA table_info({resource.table})")}
    clauses, params = [], []
    for key, value in request.args.items():
        if key not in columns:
            raise ValidationFailed(f"unknown filter: {key}", field=key)
        clauses.append(f"{resource.table}.{key} = ?")
        params.append(value)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(f"{_select(resource)}{where} ORDER BY {resource.table}.{resource.pk}", params).fetchall()
    return jsonify([_serialize(resource, r) for r in rows])


@bp.post("/<table>")
def create(table: str):
    resource, db = _resource(table, "create"), get_db()
    body = request.get_json(silent=True)
    if resource.defaults and isinstance(body, dict):
        body = {**resource.defaults(db), **body}
    _validate(body, resource.create_schema)
    with db:
        row_id = resource.create_fn(db, body) if resource.create_fn else _guarded(_insert, db, resource, body)
        row = _fetch(db, resource, row_id)
    return jsonify(row), 201


@bp.put("/<table>/<row_id>")
def update(table: str, row_id: str):
    resource, db = _resource(table, "update"), get_db()
    body = request.get_json(silent=True)
    _validate(body, resource.update_schema)
    with db:
        _fetch(db, resource, row_id)
        if resource.update_fn:
            resource.update_fn(db, row_id, body)
        elif body:
            body = _coerce(resource, body)
            sets = ", ".join(f"{k} = ?" for k in body)
            _guarded(db.execute, f"UPDATE {resource.table} SET {sets} WHERE {resource.pk} = ?", (*body.values(), row_id))
        row = _fetch(db, resource, row_id)
    return jsonify(row)


@bp.delete("/<table>/<row_id>")
def delete(table: str, row_id: str):
    resource, db = _resource(table, "delete"), get_db()
    with db:
        _fetch(db, resource, row_id)
        _guarded(db.execute, f"DELETE FROM {resource.table} WHERE {resource.pk} = ?", (row_id,))
    return "", 204


@bp.post("/<table>/batch")
def batch(table: str):
    resource, db = _resource(table, "batch"), get_db()
    rows = (request.get_json(silent=True) or {}).get("rows")
    if not isinstance(rows, list):
        raise ValidationFailed("rows must be a list", field="rows")
    if resource.batch_fn:
        return _batch_update(resource, db, rows)
    created = []
    with db:
        for body in rows:
            _validate(body, resource.create_schema)
            created.append(_fetch(db, resource, _guarded(_insert, db, resource, body)))
    return jsonify(created), 201


def _batch_update(resource: Resource, db, rows: list):
    """The `batch` shape on a hook-backed table: every row is an update, applied all-or-nothing (REQ-CRM-11)."""
    for body in rows:
        try:
            _validate(body, resource.batch_schema)
        except ValidationFailed as exc:
            raise ValidationFailed(exc.message, field="rows") from exc
    with db:
        ids = resource.batch_fn(db, rows)
    return jsonify([_fetch(db, resource, row_id) for row_id in ids])


@bp.post("/<table>/delete")
def bulk_delete(table: str):
    resource, db = _resource(table, "bulk_delete"), get_db()
    where = (request.get_json(silent=True) or {}).get("filter")
    if not isinstance(where, dict) or not where:
        raise ValidationFailed("filter must be a non-empty object", field="filter")
    columns = {r["name"] for r in db.execute(f"PRAGMA table_info({resource.table})")}
    if not set(where) <= columns:
        raise ValidationFailed("filter names an unknown column", field="filter")
    clause = " AND ".join(f"{k} = ?" for k in where)
    with db:
        count = _guarded(db.execute, f"DELETE FROM {resource.table} WHERE {clause}", tuple(where.values())).rowcount
    return jsonify({"deleted": count})
