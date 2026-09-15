"""Entry point: `python -m easymcf` (ARCH-RUN-07)."""

from __future__ import annotations

from dotenv import load_dotenv

# Must run before Config() is built (ENV-CFG-03/07.02.03) — load_dotenv()
# populates os.environ, and Config's fields re-read os.environ per call.
load_dotenv()

from easymcf import create_app  # noqa: E402
from easymcf.config import Config  # noqa: E402

if __name__ == "__main__":
    config = Config()
    create_app(config).run(host="127.0.0.1", port=config.port, threaded=True)
