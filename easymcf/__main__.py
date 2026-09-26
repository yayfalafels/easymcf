"""Entry point: `python -m easymcf` (ARCH-RUN-07)."""

from __future__ import annotations

import threading

from dotenv import load_dotenv

# Must run before Config() is built (ENV-CFG-03/07.02.03) — load_dotenv()
# populates os.environ, and Config's fields re-read os.environ per call.
load_dotenv()

from easymcf import create_app  # noqa: E402
from easymcf.config import Config  # noqa: E402
from easymcf.db.connection import get_connection  # noqa: E402
from easymcf.services import scheduler  # noqa: E402

if __name__ == "__main__":
    config = Config()
    app = create_app(config)
    # ARCH-SCHED-06: the tick thread starts here, at the process entry point, never inside
    # create_app() itself — create_app() also runs under the test client, where a live tick
    # thread would be a leftover timer across tests. Governed by SCHEDULER_ENABLED/
    # SCHEDULER_TICK_S (easymcf/config.py, 10.EL.07).
    if config.scheduler_enabled:
        stop_event = threading.Event()
        threading.Thread(
            target=scheduler.run_forever,
            args=(lambda: get_connection(config.db_path), config.scheduler_tick_s, stop_event),
            daemon=True,
        ).start()
    app.run(host="127.0.0.1", port=config.port, threaded=True)
