"""ARCH-NET-03/04 — the real mycareersfuture.gov.sg/singpass.gov.sg hosts, only under MCF_MODE=live.

Reached only through `singpass_browser.get_browser()`, which never selects this class unless `Config.mcf_mode`
is explicitly "live" (ARCH-RUN-08 — the default is always fixture). No test tier ever imports this module.
"""

from __future__ import annotations

from .singpass_browser import BaseSingpassBrowser


class LiveSingpassBrowser(BaseSingpassBrowser):
    """No routing override: real navigation against the real MCF and Singpass hosts."""
