"""ARCH-BOT-02 / ARCH-TEST-06 — the live ApplyBrowser: BaseApplyBrowser against the real MCF site, restoring the
signed-in user's exported storage state into a fresh Chromium context (ARCH-BOT-03). A bug here submits real job
applications, so it is selected only when `MCF_MODE=live`, a human's own deliberate per-invocation choice
(CLAUDE.md's live-site boundary, REQ-DEV-03/04). No routing: every request reaches mycareersfuture.gov.sg.
"""

from __future__ import annotations

from .apply_browser import BaseApplyBrowser


class LiveApplyBrowser(BaseApplyBrowser):
    pass
