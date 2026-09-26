"""REQ-AUTH-08 - the profile photo pipeline and storage (ARCH-AUTH-07)."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

from ..errors import UnsupportedMedia

Image.MAX_IMAGE_PIXELS = 25_000_000
ALLOWED = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _photo_dir(config) -> str:
    """Resolve a relative photo directory from the repository root."""
    return config.photo_dir if os.path.isabs(config.photo_dir) else os.path.join(_REPO_ROOT, config.photo_dir)


def to_avatar(data: bytes, declared: str | None) -> bytes:
    """Decode, validate, center-crop to a square, resize to 256 by 256, and re-encode as PNG (drops metadata)."""
    try:
        image = Image.open(io.BytesIO(data))
        detected = image.format
        image.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        raise UnsupportedMedia("The file is not an accepted image.")
    if detected not in ALLOWED or (declared and declared != ALLOWED[detected]):
        raise UnsupportedMedia("Upload a JPEG, PNG, or WebP image.")
    square = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGBA"), (256, 256), Image.LANCZOS)
    out = io.BytesIO()
    square.save(out, "PNG")
    return out.getvalue()


def store(config, user_id: int, png: bytes) -> str:
    """Write <PHOTO_DIR>/<user_id>/avatar-<sha8>.png (file 0600, directory 0700) and return its reference."""
    ref = f"{user_id}/avatar-{hashlib.sha256(png).hexdigest()[:8]}.png"
    directory = os.path.join(_photo_dir(config), str(user_id))
    os.makedirs(directory, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    fd, tmp = tempfile.mkstemp(dir=directory)
    with os.fdopen(fd, "wb") as handle:
        handle.write(png)
    os.chmod(tmp, 0o600)
    os.replace(tmp, os.path.join(_photo_dir(config), ref))
    return ref


def path_of(config, ref: str) -> str:
    return os.path.join(_photo_dir(config), ref)


def _current(db, user_id: int) -> str | None:
    return db.execute("SELECT photo_ref FROM user WHERE id = ?", (user_id,)).fetchone()["photo_ref"]


def replace(db, config, user_id: int, png: bytes) -> None:
    old = _current(db, user_id)
    ref = store(config, user_id, png)
    with db:
        db.execute("UPDATE user SET photo_ref = ? WHERE id = ?", (ref, user_id))
    if old and old != ref and os.path.exists(path_of(config, old)):
        os.remove(path_of(config, old))


def remove(db, config, user_id: int) -> None:
    old = _current(db, user_id)
    with db:
        db.execute("UPDATE user SET photo_ref = NULL WHERE id = ?", (user_id,))
    if old and os.path.exists(path_of(config, old)):
        os.remove(path_of(config, old))


def import_from_url(db, config, user_id: int, url: str) -> None:
    """Best effort: a picture problem never fails a sign-in."""
    try:
        response = requests.get(url, timeout=5, stream=True)
        data = response.raw.read(config.photo_max_bytes + 1, decode_content=True)
        if response.status_code == 200 and len(data) <= config.photo_max_bytes:
            replace(db, config, user_id, to_avatar(data, None))
    except Exception:  # noqa: BLE001 - any failure leaves the user without a photo
        pass
