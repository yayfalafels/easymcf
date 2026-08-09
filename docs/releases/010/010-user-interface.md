# Easy MCF POC Local - User Interface

## Purpose

Page inventory and UX behavior for the AngularJS frontend (REQ-FE-01/02), derived from [010-workflows.md](010-workflows.md) — every page below exists to drive one or more of that document's workflows, and every field/action on a page maps to an entity in [010-data-model.md](010-data-model.md). This is a conceptual/wireframe-level spec (structure, states, interactions), not a visual design — no layout grid, color, or component-library decisions. [010-frontend-app.md](010-frontend-app.md) elaborates this page inventory into the actual AngularJS module/routing/controller structure and the API calls each page makes — read that alongside this document once building, not instead of it.

010 is a single local user on their own desktop machine — no responsive/mobile requirement, no multi-user affordances. There is no login screen beyond the MCF session flow below, nor any offline mode.

## Information architecture

The nav is organized around **domain entities** — the things the user owns and comes back to check on — not around the workflow numbers used to spec them. A user thinks "let me check my leads" or "what did today's search turn up," never "let me go do workflow 5." Four of the five nav destinations are exactly the nouns in the glossary: **Tracks**, **Posts**, **Leads**, **Applications**. Match score, stage, apply status — the mechanics workflows.md is precise about — show up as state *within* these entity views, not as separate destinations.

The fifth destination, **Automation**, is deliberately not an entity the user curates. It's the operational machinery underneath the other four: 

1. run history, which addresses the questions such as did the last search/apply actually work?
2. MCF session status, which addresses questions such as whether the credential the apply run depends on still valid?. 

Neither is something the user "manages" day to day the way they manage a lead or a track — they're checked occasionally, usually when something looks wrong elsewhere. Bundling them into one admin-adjacent nav item keeps the primary nav to the four things the user actually works with, rather than diluting it with two ops/diagnostic screens that would otherwise sit as peers to "Leads."

This makes the page count line up with the nav count. Every nav destination is exactly one page; the two contextual views (Manual Post Entry, Lead Detail) are reached *from* a page rather than sitting in the nav themselves. 

## Navigation structure

A persistent left sidebar (or top nav — implementation detail) with five destinations, plus an always-visible session-status indicator:

1. **Tracks** — Workflow 1
2. **Posts** — Workflows 2, 3, 4
3. **Leads** — Workflow 5
4. **Applications** — Workflow 6
5. **Automation** — Workflows 8, 9

**Session status badge** (top-right, always visible, not a nav destination): shows `valid` / `expired` / `missing` for the MCF session (Workflow 8), clickable to open the session panel from anywhere. This is deliberately not buried behind the Automation nav item — an expired session is the single most common reason an apply run will abort (REQ-APPLY-06), so REQ-FE-02 (surface failures, don't bury them) argues for it being always on screen regardless of where the user is. Clicking it opens the same session panel described under Automation below (see that section for why it's one component reached two ways, not two implementations).

## Cross-cutting UX patterns

### Async run handling

Search runs and apply runs are not instantaneous — the `jobsearch` prototype observed full sweeps around 15 minutes for cards and 3–5 minutes for profiles (see [010-prototype.md](010-prototype.md)). The UI must not block on these:

- Triggering a run (from Posts or Applications) immediately returns a `run_log` id and switches that page into a **running** state — a progress indicator plus live-updating counts (e.g. "42 postings found, page 6"), polled from the backend rather than the user needing to babysit a blocking request.
- The user can navigate away while a run is in progress; the session-status-badge area also carries a small persistent "run in progress" indicator so it's visible from any page (REQ-FE-02), linking into Automation's Runs tab.
- On completion (success, partial, or failed), the triggering page updates in place and a toast/banner summarizes the outcome (e.g. "Search complete: 14 new postings, 2 errors — see Automation").

### Error surfacing

- Run-level errors (a search or apply run that failed or partially failed) surface both inline on the page that triggered it and as an entry in Automation's Runs tab (REQ-FE-02, REQ-PLAT-03) — never only to a console/log file.
- Field-level validation errors (e.g. incomplete track config, missing CV before queueing an apply) block the action with an inline message at the point of entry, not a generic toast.
- A missing/expired session is treated as a blocking error on the Applications page specifically (can't trigger a run) but only a passive badge state elsewhere.

### Confirmation modals

Reserved for actions that are destructive or hard to reverse: closing a lead, submitting an application batch (mutates MCF-side application state, REQ-APPLY-03), and overwriting an existing valid session. Routine stage transitions (e.g. `PROSPECT` → `TOAPPLY`) do not need a confirmation — they're reversible within the app.

### Empty / loading states

Every list-bearing page (Posts, Leads, Applications, Automation) defines an explicit empty state with a call to action (e.g. Leads empty → "Promote a posting from Posts to get started") rather than a bare empty table, since seed/demo data availability (REQ-DEV-02) means these states will be seen often during development.

## Page inventory

| #  | Page                          | Nav destination | Primary requirement(s)                 |
| -- | ------------------------------ | ---------------- | --------------------------------------- |
| 1  | Tracks                          | Tracks            | REQ-SRCH-01, REQ-APPLY-02, REQ-FE-01   |
| 2  | CVs (page, from Tracks)         | —                 | REQ-APPLY-02                            |
| 3  | Posts                            | Posts             | REQ-SRCH-02..09, REQ-FE-01              |
| 4  | Manual Post Entry (dialog, from Posts) | —          | REQ-SRCH-07                             |
| 5  | Leads                            | Leads             | REQ-CRM-01..07, REQ-FE-01               |
| 6  | Lead Detail (panel, from Leads)  | —                 | REQ-CRM-03, REQ-CRM-04                  |
| 7  | Applications                     | Applications      | REQ-APPLY-01..09, REQ-FE-01             |
| 8  | Automation (Runs / Session tabs) | Automation        | REQ-PLAT-03, REQ-FE-02, REQ-APPLY-06    |

### 1. Tracks

**Purpose:** configure the tracks a user is pursuing (Workflow 1) — the root config everything else hangs off.

- List of existing tracks (role + seniority), each showing its search profile summary (keywords, min salary, max age, min match score) and assigned default CV inline.
- Create/edit a track: role name + seniority fields, and the search-profile fields in the same form (they're 1:1, no reason to split into two steps).
- Default CV picker per track, sourced from the CV catalog (data model `cv` table) — a "Manage CVs" link opens page 2 for adding/editing labels; if the catalog is empty, the picker itself surfaces that link inline rather than leaving the user stuck on an empty dropdown.
- Archive action per track (soft delete, REQ-SRCH-10): archived tracks drop out of the active list and out of every track selector elsewhere in the app (Posts, promote-to-lead, apply default CV) by default, with a toggle on this page to show archived tracks and unarchive one. Historical posts, leads, and applications tied to an archived track remain intact and browsable.
- No search-trigger action lives here — triggering a run happens from Posts, scoped to a track selected there, keeping "configure" and "run" separate.

### 2. CVs

**Purpose:** maintain the CV/resume label catalog that Tracks (default) and Applications (override) both draw from (REQ-APPLY-02).

- Simple list of `cv` rows (just a label each — see [010-data-model.md](010-data-model.md), the actual file lives on the user's MCF profile, this table only stores the substring the apply run matches against MCF's resume-selector options).
- Add/rename/remove a CV label. Removing a label that's in use (as a track default or an application override) is blocked with an inline explanation and a list of what references it, rather than silently orphaning those references.
- Reached from the "Manage CVs" link on Tracks, and from the CV override control on Applications — no standalone nav entry, since it's a small supporting catalog rather than an entity with its own workflow/lifecycle (see Information architecture).
- No delete/archive ambiguity here the way there is for tracks: an unused CV label can simply be removed.

### 3. Posts

**Purpose:** the primary daily-use screen — review postings for a track and act on them (Workflow 2, 4).

- Track selector at the top (postings are always viewed in the context of one track, since match score is per-track).
- "Run search" button → enters the async running state described above.
- Results table: title, company, salary, posted date, match score (sorted by score desc by default so the highest-priority postings surface first — this is the entire point of REQ-SRCH-09), age, closing date if known, and an `already promoted` indicator if a lead already exists for this post under this track.
- Filters: match-score threshold (defaults to the track's configured `min_match_score` but adjustable per view), max age, "include below-threshold" toggle to see what's screened out.
- Manual entries and scraped postings share this same list once persisted — manual entries carry a small "manual" tag rather than living in a separate view (Workflow 3), since they fold into the same review flow per the requirements' framing.
- Row action: **Promote to lead.** If the post matches more than one track, this opens a small track-picker (Decision 2, Workflow 4) defaulting to the track currently being viewed; confirms, creates the lead, and the row updates to an `already promoted` state with the promote action disabled — a post can be promoted into at most one lead.
- "Add posting manually" button opens page 4 as a dialog.

### 4. Manual Post Entry (dialog)

**Purpose:** capture a posting MCF search didn't surface (Workflow 3, REQ-SRCH-07).

- Form fields mirror `post`: position title, company, URL/reference, salary, posted date (defaults today).
- Matching track(s) are auto-assigned on save using the same match-scoring logic as a search run (feeds `post_track` with `search_match = false`, see data model); an inline track-assignment editor lets the user adjust it afterward.
- On save, returns the user to Posts with the new posting visible (tagged "manual"), immediately promotable.

### 5. Leads

**Purpose:** the CRM view — every open lead, organized by stage, and the entry point to close/queue actions (Workflow 5).

Sub-navigation: tabs across the top of the page — **Pipeline**, **Applied**, **Callbacks**, **Interviews**, **Offers**, **Closed**. All six are filtered views of the same `lead` list by stage, not separate entities — a lead simply appears under whichever tab matches its current stage, moving itself when the stage changes (no per-tab data to keep in sync).

The split follows how the two halves of a lead's life actually get used: `PROSPECT`/`TOAPPLY` are high-volume and triage-y (scanning many leads at once, queuing a batch for apply), which a board suits; `APPLIED` through `OFFER` are lower-volume and detail-y (one specific callback, one specific interview slot, one specific offer to weigh), where a focused list surfacing the stage's one relevant date beats a generic card.

**Pipeline tab board** — `PROSPECT` and `TOAPPLY`:

- Board layout, one column per stage; each card shows title, company, track, deadline (highlighted if approaching/passed), and days since last activity.
- A card's days-since-last-activity indicator shifts into a warning state as it approaches the 28-day auto-expiry threshold (REQ-CRM-05), so the user isn't surprised when a stale lead moves itself to Closed. Last activity is the latest entry in the lead's activity log (REQ-CRM-08), not a bare timestamp, and this indicator applies across every tab on this page, not just the board.
- Manual stage transitions happen via a control on the card (a "move to next stage" button plus a dropdown for jumping stages) — button/dropdown-driven, not drag-and-drop.
- `TOAPPLY`-stage cards show a "select for apply queue" checkbox, feeding bulk selection into Workflow 6's queue step — this is the only page from which leads enter Applications.

**Applied / Callbacks / Interviews / Offers tabs** — one flat list per stage, each row showing the most recent activity-log entry (REQ-CRM-08) rather than a column position:

- **Applied** — title, company, track, applied date, days since applied. The waiting-to-hear-back list.
- **Callbacks** — title, company, track, last logged contact, notes preview. The user logs the callback (writes a `contact_logged` event, updating last-contact date + notes) and advances the lead to `INTERVIEW` from here once one is scheduled.
- **Interviews** — title, company, track, last logged activity, notes. There is no dedicated interview-date field: the interview's date/time is captured as free text in notes or the logged event's detail, and the lead's `deadline` field keeps its one consistent meaning rather than being repurposed per stage.
- **Offers** — title, company, track, deadline, notes. The action-heavy tab: most rows here end in a close (`offer_accepted`, `rejected`, or `withdrawn`) rather than a further stage advance.
- Every row on these four tabs carries a "move to next stage" / close control same as a board card — a list row is not read-only, it's the board card's fields reordered for the stage.

**Closed tab:**

- `CLOSED` leads, listing `close_reason`, satisfying REQ-CRM-06's "removed from active pipeline view while history is preserved."
- A lead auto-closed as `expired` or `apply failed` (Workflow 5/7) appears here with that reason pre-filled and a subtle "auto-closed" marker distinguishing it from a manual close, so the user isn't confused about why it moved.

Clicking a card or row on any tab opens the Lead Detail panel.

### 6. Lead Detail (panel/dialog)

**Purpose:** the day-to-day working surface for one lead — everything REQ-CRM-03 lists that doesn't fit on a board card.

- Deadline, applied date, first-attempt date, last-contact date (editable date fields).
- Last-activity indicator, derived from the lead's activity log (REQ-CRM-08): days since the latest logged event and the resulting auto-expiry date (REQ-CRM-05), so the user can see at a glance whether a lead is at risk of expiring.
- Free-text notes — this is also where scheduled-interview and callback details (date/time, who, what was discussed) live, since those aren't dedicated structured fields.
- Link back to the underlying post's full detail/description (read-only, since post data isn't user-editable).
- Title/company override fields, explicitly labeled as overrides so it's clear the underlying post is untouched (REQ-CRM-04).
- Manual `CLOSED` action with a required reason picker (offer accepted / rejected / withdrawn / expired / cancelled / duplicate / apply failed) — behind the confirmation-modal pattern above.
- Activity history for this lead (REQ-CRM-08): a reverse-chronological list of logged events (stage changes, contact logged, notes edited, deadline changed) interleaved with any `application` attempts and their status/timestamp, so a user investigating "why is this stuck at TOAPPLY" or "when did I last hear from them" doesn't have to leave the panel to check Automation.

### 7. Applications

**Purpose:** review and execute a batch apply run (Workflow 6).

- List of `queued` applications (created when leads were selected from Leads), each showing the lead's title/company/track and its CV assignment (defaulting to the track's default CV, REQ-APPLY-02) with an inline override control drawing on the same CV catalog as page 2 (a "manage CVs" link is available from the override control for adding a label on the fly).
- Applications with an unresolved problem from a prior attempt (e.g. `cv_not_found` needing a fixed CV, Workflow 7) are visually flagged and blocked from re-queueing until the CV override is set.
- Remove-from-queue action per row, for anything the user changes their mind about before running (REQ-APPLY-11): discards the queued `application` row and closes the owning lead with reason `withdrawn` — it does not revert to `PROSPECT` and is not available to re-queue later. Behind the confirmation-modal pattern like any other lead close, since it's not the reversible dequeue it might look like at a glance.
- Session status inline (mirrors the global badge) — if invalid, the "Run" button is disabled with an explanation rather than allowing a doomed run to start (REQ-APPLY-06).
- "Run apply batch" button, behind the confirmation modal (this mutates real MCF-side state) → async running state as described above, per-application progress ("3 of 8 processed").
- **Results view** (same page, post-run): each application's outcome (REQ-APPLY-04's full vocabulary), with a per-outcome next action surfaced inline per Workflow 7's table — e.g. a `cv_not_found` row gets a "fix CV and retry" action right there, a `post_closed` row shows "lead auto-closed" with a link to it, an `applied` row shows "lead moved to Applied."

### 8. Automation

**Purpose:** the operational/diagnostic hub for the machinery underneath Posts and Applications — not a thing the user curates, but where they check on it and fix it when something's broken. Two tabs:

**Runs tab** (REQ-PLAT-03, REQ-FE-02) — diagnose a run without re-running it:

- Reverse-chronological list of `run_log` rows: type (search/apply), track (if applicable), start/end time, status, outcome counts.
- Expand a row for full error detail and, for apply runs, a link to the resulting applications; for search runs, a link back to Posts filtered to that run's discoveries.
- This is the page the "run in progress" nav badge indicator links to.

**Session tab** (REQ-APPLY-06) — establish/refresh the session apply runs depend on (Workflow 8):

- Current status (valid / expired / missing) and, if valid, when it was uploaded.
- "Log in to MCF" button — opens MCF's Singpass login flow (external browser context; the app does not attempt to automate or observe this step, per the out-of-scope boundary on login/MFA/CAPTCHA automation).
- "Upload session" control — paste or upload the exported cookie data; on submit, backend validates the domain match and updates status. A failed validation shows an inline error explaining the cookie wasn't recognized, not a silent no-op.
- Overwriting an existing valid session goes through the confirmation-modal pattern (it invalidates the current one).
- This tab is the same component the top-right session badge opens as an overlay from any page — one implementation, two entry points, so an expired session noticed mid-Applications-review can be fixed without losing place, while the same content is still reachable with full context (last-upload history, sitting next to Runs) via the nav.

