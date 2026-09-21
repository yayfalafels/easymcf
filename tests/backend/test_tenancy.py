"""13.TC.26 to 13.TC.28 - per-user ownership, the permanent regression class (STRAT-CASE-08).

The oracle rows come from SQL written from the Design ownership table and never from easymcf.tenancy.SCOPES, so a
mistake in the scope predicates cannot hide in the check that reads them.
"""

from __future__ import annotations

import sqlite3

import pytest

from easymcf import tenancy
from easymcf.api import resources  # noqa: F401  (registers every resource)
from easymcf.api.generic import REGISTRY, Resource, register

pytestmark = pytest.mark.backend

# One row visible only to seed user 1, per registered table.
OWNER_SQL = {
    "track": "SELECT id FROM track WHERE user_id = 1 LIMIT 1",
    "cv": "SELECT id FROM cv WHERE user_id = 1 LIMIT 1",
    "search_profile": "SELECT track_id FROM search_profile WHERE track_id IN (SELECT id FROM track WHERE user_id = 1) LIMIT 1",
    "search_schedule": "SELECT track_id FROM search_schedule WHERE track_id IN (SELECT id FROM track WHERE user_id = 1) LIMIT 1",
    "lead": "SELECT id FROM lead WHERE user_id = 1 AND post_id NOT IN (SELECT post_id FROM lead WHERE user_id = 2) LIMIT 1",
    "lead_note": "SELECT id FROM lead_note WHERE lead_id IN (SELECT id FROM lead WHERE user_id = 1) LIMIT 1",
    "lead_event": "SELECT id FROM lead_event WHERE lead_id IN (SELECT id FROM lead WHERE user_id = 1) LIMIT 1",
    "application": "SELECT id FROM application WHERE lead_id IN (SELECT id FROM lead WHERE user_id = 1) LIMIT 1",
    "offer": "SELECT id FROM offer WHERE lead_id IN (SELECT id FROM lead WHERE user_id = 1) LIMIT 1",
    "post": ("SELECT pt.post_id FROM post_track pt JOIN track t ON t.id = pt.track_id WHERE t.user_id = 1 "
             "AND pt.post_id NOT IN (SELECT pt2.post_id FROM post_track pt2 JOIN track t2 ON t2.id = pt2.track_id WHERE t2.user_id = 2) "
             "AND pt.post_id NOT IN (SELECT post_id FROM lead WHERE user_id = 2) LIMIT 1"),
}
# A valid update body per table, so the answer reflects ownership and not body validation.
UPDATE_BODY = {"cv": {"label": "x"}, "post": {}}
SCOPED = sorted(t for t in REGISTRY if t not in tenancy.UNSCOPED)


def _one(db_path, sql, *args):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _pk(table):
    return REGISTRY[table].pk


# 13.TC.26 - the matrix, generated from the registry
@pytest.mark.parametrize("table", SCOPED)
def test_user_b_cannot_reach_user_a_rows(table, isolated_client_b, isolated_db):
    assert table in OWNER_SQL, f"{table} has no ownership oracle entry in OWNER_SQL"
    row_id = _one(isolated_db, OWNER_SQL[table])[0][0]
    verbs = REGISTRY[table].verbs
    if "get" in verbs:
        assert isolated_client_b.get(f"/api/v1/{table}/{row_id}").status_code == 404
    listed = isolated_client_b.get(f"/api/v1/{table}/search").get_json()
    assert row_id not in [r[_pk(table)] for r in listed]
    if "update" in verbs:
        assert isolated_client_b.put(f"/api/v1/{table}/{row_id}", json=UPDATE_BODY.get(table, {})).status_code == 404
    if "delete" in verbs:
        assert isolated_client_b.delete(f"/api/v1/{table}/{row_id}").status_code == 404
    assert _one(isolated_db, OWNER_SQL[table])[0][0] == row_id           # the row is untouched


@pytest.mark.parametrize("table", SCOPED)
def test_user_a_sees_the_same_row(table, isolated_client, isolated_db):
    row_id = _one(isolated_db, OWNER_SQL[table])[0][0]
    if "get" in REGISTRY[table].verbs:
        assert isolated_client.get(f"/api/v1/{table}/{row_id}").status_code == 200


def test_register_rejects_an_unscoped_resource():
    with pytest.raises(RuntimeError, match="no ownership declaration"):
        register(Resource("unscoped_table", create_schema={}, update_schema={}))


def test_every_registered_resource_is_declared_in_tenancy():
    assert set(REGISTRY) <= set(tenancy.SCOPES) | tenancy.UNSCOPED


def test_a_search_returns_only_the_callers_rows(isolated_client, isolated_client_b, isolated_db):
    for table in ("track", "cv", "lead"):
        mine = {r["id"] for r in isolated_client.get(f"/api/v1/{table}/search").get_json()}
        theirs = {r["id"] for r in isolated_client_b.get(f"/api/v1/{table}/search").get_json()}
        owner = {1: {r[0] for r in _one(isolated_db, f"SELECT id FROM {table} WHERE user_id = 1")},
                 2: {r[0] for r in _one(isolated_db, f"SELECT id FROM {table} WHERE user_id = 2")}}
        assert mine == owner[1] and theirs == owner[2] and not mine & theirs


def test_a_search_filter_cannot_reach_across_users(isolated_client_b):
    assert isolated_client_b.get("/api/v1/lead/search?user_id=1").get_json() == []
    assert isolated_client_b.get("/api/v1/track/search?user_id=1").get_json() == []


def test_a_body_carrying_user_id_is_refused(isolated_client):
    for table, body in (("track", {"role_id": 1, "seniority": "x", "user_id": 2}), ("cv", {"label": "Z", "user_id": 2})):
        response = isolated_client.post(f"/api/v1/{table}", json=body)
        assert response.status_code == 400 and response.get_json()["field"] == "user_id"


def test_created_rows_are_owned_by_the_caller(isolated_client_b, isolated_db):
    track = isolated_client_b.post("/api/v1/track", json={"role_id": 1, "seniority": "lead"})
    cv = isolated_client_b.post("/api/v1/cv", json={"label": "B-9"})
    assert track.status_code == cv.status_code == 201
    assert track.get_json()["user_id"] == 2 and cv.get_json()["user_id"] == 2
    assert _one(isolated_db, "SELECT user_id FROM track WHERE id = ?", track.get_json()["id"]) == [(2,)]


def test_a_child_of_another_users_row_answers_404(isolated_client_b, isolated_db):
    a_track = _one(isolated_db, OWNER_SQL["track"])[0][0]
    a_lead = _one(isolated_db, OWNER_SQL["lead"])[0][0]
    a_cv = _one(isolated_db, OWNER_SQL["cv"])[0][0]
    assert isolated_client_b.post("/api/v1/search_profile", json={"track_id": a_track, "keywords": "k", "min_match_score": 0.1, "employment_type": "Full Time"}).status_code == 404
    assert isolated_client_b.post("/api/v1/lead_note", json={"lead_id": a_lead, "note": "x"}).status_code == 404
    assert isolated_client_b.post("/api/v1/track", json={"role_id": 1, "seniority": "x", "default_cv_id": a_cv}).status_code == 404
    assert isolated_client_b.post("/api/v1/lead/manual", json={"track_id": a_track, "position_title": "t", "company_name": "c"}).status_code == 404
    post_id = _one(isolated_db, "SELECT post_id FROM lead WHERE user_id = 1 LIMIT 1")[0][0]
    assert isolated_client_b.post("/api/v1/lead", json={"post_id": post_id, "track_id": a_track}).status_code == 404


def test_moving_a_lead_to_another_users_track_answers_400_like_an_unknown_track(isolated_client_b, isolated_db):
    b_lead = _one(isolated_db, "SELECT id FROM lead WHERE user_id = 2 LIMIT 1")[0][0]
    a_track = _one(isolated_db, OWNER_SQL["track"])[0][0]
    foreign = isolated_client_b.put(f"/api/v1/lead/{b_lead}", json={"track_id": a_track})
    unknown = isolated_client_b.put(f"/api/v1/lead/{b_lead}", json={"track_id": 999})
    assert foreign.status_code == unknown.status_code == 400
    assert foreign.get_json()["field"] == unknown.get_json()["field"] == "track_id"
    assert foreign.get_json()["message"].replace(str(a_track), "N") == unknown.get_json()["message"].replace("999", "N")


def test_a_batch_naming_another_users_lead_answers_404_and_changes_nothing(isolated_client_b, isolated_db):
    a_lead = _one(isolated_db, OWNER_SQL["lead"])[0][0]
    b_lead = _one(isolated_db, "SELECT id FROM lead WHERE user_id = 2 AND stage = 'TOAPPLY' LIMIT 1")[0][0]
    before = _one(isolated_db, "SELECT id, stage FROM lead ORDER BY id")
    response = isolated_client_b.post("/api/v1/lead/batch", json={"rows": [{"id": b_lead, "stage": "APPLIED"}, {"id": a_lead, "stage": "APPLIED"}]})
    assert response.status_code == 404
    assert _one(isolated_db, "SELECT id, stage FROM lead ORDER BY id") == before


def test_a_bulk_delete_reaches_only_the_callers_rows(isolated_client_b, isolated_db, monkeypatch):
    from dataclasses import replace

    monkeypatch.setitem(REGISTRY, "cv", replace(REGISTRY["cv"], verbs=REGISTRY["cv"].verbs | {"bulk_delete"}))  # no shipped resource opens it
    before = _one(isolated_db, "SELECT COUNT(*) FROM cv")[0][0]
    a_cv = _one(isolated_db, OWNER_SQL["cv"])[0][0]
    response = isolated_client_b.post("/api/v1/cv/delete", json={"filter": {"id": a_cv}})
    assert response.status_code == 200 and response.get_json() == {"deleted": 0}
    assert _one(isolated_db, "SELECT COUNT(*) FROM cv")[0][0] == before


# 13.TC.27 - the ownership chain of each child table, from hard-coded joins
CHAINS = {
    "search_profile": ("track_id", "SELECT sp.track_id FROM search_profile sp JOIN track t ON t.id = sp.track_id WHERE t.user_id = {u}"),
    "search_schedule": ("track_id", "SELECT ss.track_id FROM search_schedule ss JOIN track t ON t.id = ss.track_id WHERE t.user_id = {u}"),
    "lead_note": ("id", "SELECT n.id FROM lead_note n JOIN lead l ON l.id = n.lead_id WHERE l.user_id = {u}"),
    "lead_event": ("id", "SELECT e.id FROM lead_event e JOIN lead l ON l.id = e.lead_id WHERE l.user_id = {u}"),
    "application": ("id", "SELECT a.id FROM application a JOIN lead l ON l.id = a.lead_id WHERE l.user_id = {u}"),
    "offer": ("id", "SELECT o.id FROM offer o JOIN lead l ON l.id = o.lead_id WHERE l.user_id = {u}"),
}


@pytest.mark.parametrize("table", sorted(CHAINS))
def test_each_child_table_resolves_to_one_owner(table, isolated_client, isolated_client_b, isolated_db):
    key, sql = CHAINS[table]
    for client, user in ((isolated_client, 1), (isolated_client_b, 2)):
        expected = {r[0] for r in _one(isolated_db, sql.format(u=user))}
        assert {r[key] for r in client.get(f"/api/v1/{table}/search").get_json()} == expected


# 13.TC.28 - shared posts are visible through the user's own tracks and leads
def test_a_shared_post_is_visible_to_both_and_a_private_post_to_one(isolated_client, isolated_client_b, isolated_db):
    def visible(user):
        return {r[0] for r in _one(isolated_db, "SELECT pt.post_id FROM post_track pt JOIN track t ON t.id = pt.track_id WHERE t.user_id = ? "
                                   "UNION SELECT post_id FROM lead WHERE user_id = ?", user, user)}
    mine = {r["id"] for r in isolated_client.get("/api/v1/post/search").get_json()}
    theirs = {r["id"] for r in isolated_client_b.get("/api/v1/post/search").get_json()}
    assert mine == visible(1) and theirs == visible(2)
    assert mine & theirs and theirs - mine and mine - theirs
    private_to_b = sorted(theirs - mine)[0]
    assert isolated_client.get(f"/api/v1/post/{private_to_b}").status_code == 404
    assert isolated_client_b.get(f"/api/v1/post/{private_to_b}").status_code == 200


def test_posts_are_read_only_to_every_user(isolated_client, isolated_db):
    post_id = _one(isolated_db, OWNER_SQL["post"])[0][0]
    before = _one(isolated_db, "SELECT * FROM post WHERE id = ?", post_id)
    assert isolated_client.put(f"/api/v1/post/{post_id}", json={"url_ref": "https://x.example"}).status_code == 404
    assert isolated_client.post("/api/v1/post", json={"id": "x"}).status_code == 404
    assert isolated_client.delete(f"/api/v1/post/{post_id}").status_code == 404
    assert _one(isolated_db, "SELECT * FROM post WHERE id = ?", post_id) == before


def test_a_user_cannot_promote_a_post_twice_even_when_another_user_holds_a_lead_on_it(isolated_client, isolated_db):
    shared = _one(isolated_db, "SELECT post_id FROM lead GROUP BY post_id HAVING COUNT(DISTINCT user_id) = 2")[0][0]
    a_track = _one(isolated_db, "SELECT id FROM track WHERE user_id = 1 AND is_active = 1 LIMIT 1")[0][0]
    again = isolated_client.post("/api/v1/lead", json={"post_id": shared, "track_id": a_track})
    assert again.status_code == 409 and again.get_json()["error"] == "conflict"


def test_each_user_promotes_a_fresh_shared_post_once(isolated_client, isolated_client_b, isolated_db):
    conn = sqlite3.connect(isolated_db)
    conn.execute("INSERT INTO post (id, source, position_title, company_name, url_ref, src_method) VALUES ('shared-new', 's', 'T', 'C', 'https://x.example/j', 'scraped')")
    a_track = conn.execute("SELECT id FROM track WHERE user_id = 1 AND is_active = 1 LIMIT 1").fetchone()[0]
    b_track = conn.execute("SELECT id FROM track WHERE user_id = 2 AND is_active = 1 LIMIT 1").fetchone()[0]
    for track_id in (a_track, b_track):
        conn.execute("INSERT INTO post_track (post_id, track_id, search_match) VALUES ('shared-new', ?, 1)", (track_id,))
        conn.execute("INSERT INTO match_score (post_id, track_id, match_score, score_method) VALUES ('shared-new', ?, 0.5, 'title_keyword_v1')", (track_id,))
    conn.commit()
    conn.close()
    first = isolated_client.post("/api/v1/lead", json={"post_id": "shared-new", "track_id": a_track})
    second = isolated_client_b.post("/api/v1/lead", json={"post_id": "shared-new", "track_id": b_track})
    assert first.status_code == second.status_code == 201
    assert first.get_json()["user_id"] == 1 and second.get_json()["user_id"] == 2
    assert first.get_json()["id"] != second.get_json()["id"]
    assert isolated_client.post("/api/v1/lead", json={"post_id": "shared-new", "track_id": a_track}).status_code == 409
    assert _one(isolated_db, "SELECT COUNT(*) FROM lead WHERE post_id = 'shared-new'") == [(2,)]
    assert first.get_json()["position_title"] == "T" == second.get_json()["position_title"]
