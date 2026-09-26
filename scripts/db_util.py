#!/usr/bin/env python3
"""ENV-SCRIPT-03 (STRAT-SILO-01) — direct CRUD against any table, stdlib
sqlite3, no Flask involved. The narrowest, fastest signal in the test-strategy
doc's silo table.

    python scripts/db_util.py <table> <op> [json]

`op` is one of `get`/`insert`/`update`/`delete`/`search`. `json` shape
depends on `op` (identifiers are always equality filters, ANDed together):

    insert '{"col": val, ...}'                         -> the row as inserted
    get    '{"col": val, ...}'                          -> first matching row
    search '{"col": val, ...}'  (omit/'{}' = all rows)  -> list of rows
    update '{"where": {...}, "set": {"col": val, ...}}' -> the row as updated
    delete '{"col": val, ...}'                          -> rows deleted (count)

Prints the result as JSON on success (exit 0); prints the raw SQL error
(constraint name, column) on failure (exit 1) — this is deliberately closer
to the metal than the API's `400`/`404` shapes, so a defect can be narrowed
to "the database itself rejects this" before Flask or scoring code is ever
suspected. Also importable as a module — `db_util.get`/`insert`/`update`/
`delete`/`search` are reused by `tests/backend/` fixtures rather than each
re-implementing CRUD.
"""

from __future__ import annotations

import argparse
import json as json_module
import os
import re
import sqlite3
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()  # before Config() is built — ENV-CFG-03/07.02.03

from easymcf.config import Config  # noqa: E402

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DbUtilError(ValueError):
    """Raised for a malformed call before any SQL is issued (bad table/column name)."""


def _check_identifier(name: str, kind: str) -> None:
    if not _IDENTIFIER.match(name):
        raise DbUtilError(f"invalid {kind} name: {name!r}")


def _where_clause(filters: dict) -> tuple[str, list]:
    if not filters:
        return "", []
    for col in filters:
        _check_identifier(col, "column")
    clause = " WHERE " + " AND ".join(f"{col} = ?" for col in filters)
    return clause, list(filters.values())


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def insert(conn: sqlite3.Connection, table: str, fields: dict) -> dict:
    _check_identifier(table, "table")
    for col in fields:
        _check_identifier(col, "column")
    cols = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    row = conn.execute(
        f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING *", list(fields.values())
    ).fetchone()
    conn.commit()
    return _row_to_dict(row)


def get(conn: sqlite3.Connection, table: str, filters: dict) -> dict | None:
    _check_identifier(table, "table")
    clause, params = _where_clause(filters)
    row = conn.execute(f"SELECT * FROM {table}{clause} LIMIT 1", params).fetchone()
    return _row_to_dict(row) if row else None


def search(conn: sqlite3.Connection, table: str, filters: dict) -> list[dict]:
    _check_identifier(table, "table")
    clause, params = _where_clause(filters)
    rows = conn.execute(f"SELECT * FROM {table}{clause}", params).fetchall()
    return [_row_to_dict(r) for r in rows]


def update(conn: sqlite3.Connection, table: str, where: dict, set_: dict) -> dict | None:
    _check_identifier(table, "table")
    if not where:
        raise DbUtilError("update requires a non-empty 'where'")
    if not set_:
        raise DbUtilError("update requires a non-empty 'set'")
    for col in set_:
        _check_identifier(col, "column")
    where_clause, where_params = _where_clause(where)
    set_clause = ", ".join(f"{col} = ?" for col in set_)
    # RETURNING * (not a re-query by `where`) — `where` may target the very
    # column `set` just changed, which would no longer match post-update.
    row = conn.execute(
        f"UPDATE {table} SET {set_clause}{where_clause} RETURNING *", list(set_.values()) + where_params
    ).fetchone()
    conn.commit()
    return _row_to_dict(row) if row else None


def delete(conn: sqlite3.Connection, table: str, filters: dict) -> int:
    _check_identifier(table, "table")
    if not filters:
        raise DbUtilError("delete requires a non-empty filter")
    clause, params = _where_clause(filters)
    cur = conn.execute(f"DELETE FROM {table}{clause}", params)
    conn.commit()
    return cur.rowcount


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("table")
    parser.add_argument("op", choices=["get", "insert", "update", "delete", "search"])
    parser.add_argument("json", nargs="?", default="{}")
    parser.add_argument("--db-path", default=None, help="overrides DB_PATH")
    args = parser.parse_args()

    db_path = args.db_path or Config().db_path

    try:
        payload = json_module.loads(args.json)
    except json_module.JSONDecodeError as exc:
        print(f"[FAIL] invalid json argument: {exc}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if args.op == "insert":
            result = insert(conn, args.table, payload)
        elif args.op == "get":
            result = get(conn, args.table, payload)
            if result is None:
                print("[FAIL] not found", file=sys.stderr)
                return 1
        elif args.op == "search":
            result = search(conn, args.table, payload)
        elif args.op == "update":
            result = update(conn, args.table, payload.get("where", {}), payload.get("set", {}))
        elif args.op == "delete":
            result = {"deleted": delete(conn, args.table, payload)}
        else:  # pragma: no cover - argparse already restricts choices
            raise DbUtilError(f"unknown op: {args.op}")
    except (sqlite3.Error, DbUtilError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(json_module.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
