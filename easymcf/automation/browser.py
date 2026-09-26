"""ARCH-BOT-02 — the MCFBrowser seam search (and this milestone's own two-method slice of
the future apply pipeline) run behind. Two methods only: each returns raw page HTML for
`parsing.py` to parse — no DOM inspection happens outside `live.py`'s own navigation/wait
logic. `live.py` and `fixture.py` implement this same interface (10.EL.11/.12), selected
by `get_browser()` per `config.mcf_mode`, so `easymcf/services/search.py` never imports
either concrete class directly ("services obtain them through factories" — ARCH-BOT-02).
Search needs no MCF session, so neither implementation reads one.
"""

from __future__ import annotations

from typing import Protocol

from ..config import Config


class MCFBrowser(Protocol):
    def search_page(self, keyword: str, min_salary: int | None, page: int) -> str: ...

    def detail_page(self, url_ref: str) -> str: ...

    def close(self) -> None: ...


def get_browser(config: Config | None = None) -> MCFBrowser:
    config = config or Config()
    if config.mcf_mode == "live":
        from .live import LiveMCFBrowser

        return LiveMCFBrowser(config)
    from .fixture import FixtureMCFBrowser

    return FixtureMCFBrowser(config)
