"""13.TC.08, 13.TC.09, 13.TC.22, and 13.TC.35 - the profile photo pipeline, storage, and owner-only access."""

from __future__ import annotations

import io
import os
import sqlite3
import stat

import pytest
from PIL import Image

from easymcf.auth import photo
from easymcf.config import Config
from tests.support import images

pytestmark = pytest.mark.backend


@pytest.fixture()
def env(isolated_db, tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_DIR", str(tmp_path / "photos"))
    from easymcf import create_app
    from tests.conftest import signed_in

    app = create_app(Config(db_path=isolated_db))
    return {"a": signed_in(app, "seed_a"), "b": signed_in(app, "seed_b"), "db": isolated_db,
            "config": Config(db_path=isolated_db)}


def _upload(client, name, user_id=1, content_type=None, path=None):
    path = path or images.path(name)
    with open(path, "rb") as handle:
        data = {"photo": (handle, os.path.basename(path), content_type or _type(path))}
        return client.put(f"/api/v1/users/{user_id}/photo", data=data, content_type="multipart/form-data")


def _type(path):
    return {".png": "image/png", ".jpg": "image/jpeg"}.get(os.path.splitext(path)[1], "application/octet-stream")


def _ref(env, user_id=1):
    return sqlite3.connect(env["db"]).execute("SELECT photo_ref FROM user WHERE id = ?", (user_id,)).fetchone()[0]


def test_upload_returns_the_user_with_a_photo_url(env):
    response = _upload(env["a"], "photo_ok.png")
    body = response.get_json()
    assert response.status_code == 200 and body["photo_url"].startswith("/api/v1/users/1/photo?v=") and len(body["photo_url"].split("v=")[1]) == 8
    assert env["a"].get("/api/v1/auth/me").get_json()["photo_url"] == body["photo_url"]


def test_stored_file_is_a_256_square_png_with_private_permissions_outside_the_web_root(env):
    _upload(env["a"], "photo_wide.jpg")
    path = photo.path_of(env["config"], _ref(env))
    with Image.open(path) as image:
        assert image.size == (256, 256) and image.format == "PNG"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600 and stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode) == 0o700
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert not os.path.abspath(path).startswith(os.path.join(repo, "frontend"))
    assert path.startswith(env["config"].photo_dir) and f"{os.sep}1{os.sep}" in path


def test_relative_photo_dir_is_independent_of_the_process_working_directory(isolated_db, monkeypatch, tmp_path):
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    monkeypatch.chdir(tmp_path)
    config = Config(db_path=isolated_db, photo_dir="data/photos")
    ref = photo.store(config, 1, b"avatar")
    path = photo.path_of(config, ref)
    try:
        assert path.startswith(os.path.join(repo, "data", "photos"))
        assert os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_size_boundary_one_byte_over_is_413_and_at_the_limit_is_accepted(env, tmp_path):
    limit = env["config"].photo_max_bytes
    assert _upload(env["a"], None, path=images.make_oversize(limit, str(tmp_path / "over.png"))).status_code == 413
    at_limit = images.make_oversize(limit - 1, str(tmp_path / "at.png"))
    assert os.path.getsize(at_limit) == limit
    assert _upload(env["a"], None, path=at_limit).status_code == 200


def test_fake_image_and_mismatched_type_are_415(env):
    assert _upload(env["a"], "photo_fake.png").status_code == 415
    assert _upload(env["a"], "photo_ok.png", content_type="image/jpeg").status_code == 415
    assert _upload(env["a"], "photo_ok.png", content_type="image/gif").status_code == 415
    assert _ref(env) is None


def test_a_gif_and_an_svg_are_not_accepted(env, tmp_path):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, "GIF")
    gif = tmp_path / "x.gif"
    gif.write_bytes(buffer.getvalue())
    assert _upload(env["a"], None, content_type="image/gif", path=str(gif)).status_code == 415
    svg = tmp_path / "x.svg"
    svg.write_text("<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>")
    assert _upload(env["a"], None, content_type="image/svg+xml", path=str(svg)).status_code == 415


def test_missing_part_is_400(env):
    response = env["a"].put("/api/v1/users/1/photo", data={}, content_type="multipart/form-data")
    assert response.status_code == 400 and response.get_json()["field"] == "photo"


def test_replace_deletes_the_previous_file_and_remove_clears_everything(env, tmp_path):
    _upload(env["a"], "photo_ok.png")
    first = photo.path_of(env["config"], _ref(env))
    _upload(env["a"], "photo_wide.jpg")
    second = photo.path_of(env["config"], _ref(env))
    assert first != second and not os.path.exists(first) and os.path.exists(second)
    removed = env["a"].delete("/api/v1/users/1/photo")
    assert removed.status_code == 200 and removed.get_json()["photo_url"] is None
    assert _ref(env) is None and not os.path.exists(second)
    assert env["a"].get("/api/v1/users/1/photo").status_code == 404


def test_the_owner_reads_the_photo_with_a_private_immutable_cache_header(env):
    _upload(env["a"], "photo_ok.png")
    response = env["a"].get("/api/v1/users/1/photo")
    assert response.status_code == 200 and response.mimetype == "image/png"
    assert response.headers["Cache-Control"] == "private, max-age=31536000, immutable"
    assert Image.open(io.BytesIO(response.data)).size == (256, 256)


def test_another_user_gets_404_for_every_verb(env):
    _upload(env["a"], "photo_ok.png")
    assert env["b"].get("/api/v1/users/1/photo").status_code == 404
    assert _upload(env["b"], "photo_ok.png", user_id=1).status_code == 404
    assert env["b"].delete("/api/v1/users/1/photo").status_code == 404
    assert _ref(env) is not None and _ref(env, 2) is None


def test_a_signed_out_request_is_401(env, anon_client):
    assert anon_client.get("/api/v1/users/1/photo").status_code == 401


def test_a_hostile_filename_never_leaves_the_user_directory(env):
    with open(images.path("photo_ok.png"), "rb") as handle:
        env["a"].put("/api/v1/users/1/photo", data={"photo": (handle, "../../../evil.png", "image/png")}, content_type="multipart/form-data")
    path = os.path.abspath(photo.path_of(env["config"], _ref(env)))
    assert path.startswith(os.path.abspath(os.path.join(env["config"].photo_dir, "1")) + os.sep)


def test_the_database_holds_only_a_reference(env):
    _upload(env["a"], "photo_ok.png")
    assert _ref(env).startswith("1/avatar-") and _ref(env).endswith(".png")
