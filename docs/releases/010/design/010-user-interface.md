# Easy MCF POC Local - User Interface

## Contents

- [Purpose](#purpose)
- [References](#references)
- [Information architecture](#information-architecture)
- [Navigation structure](#navigation-structure)
- [Cross-cutting UX patterns](#cross-cutting-ux-patterns)
  - [Async run handling](#async-run-handling)
  - [Error surfacing](#error-surfacing)
  - [Confirmation modals](#confirmation-modals)
  - [Empty / loading states](#empty--loading-states)
- [Page inventory](#page-inventory)
  - [1. Tracks](#1-tracks)
  - [1b. Search Profiles](#1b-search-profiles)
  - [2. CVs](#2-cvs)
  - [3. Posts](#3-posts)
  - [4. Manual Post Entry (dialog)](#4-manual-post-entry-dialog)
  - [5. Leads](#5-leads)
  - [6. Lead Detail (panel/dialog)](#6-lead-detail-paneldialog)
  - [7. Applications](#7-applications)
  - [8. Automation](#8-automation)

## Purpose

This document is the page inventory and UX behavior for the AngularJS frontend, REQ-FE-01/02, derived from the **workflows** doc. Every page below exists to drive one or more of that document's workflows, and every field or action on a page maps to an entity in the **data model**. This is a conceptual, wireframe-level spec covering structure, states, and interactions. It carries no layout grid, color, or component-library decisions. The **frontend app design** elaborates this page inventory into the actual AngularJS module, routing, and controller structure and the API calls each page makes. Read that alongside this document once building.

010 is a single local user on their own desktop machine. There is no responsive or mobile requirement, and no multi-user affordances. There is no login screen beyond the MCF session flow below, and no offline mode.

## References

- **workflows** [010-workflows.md](010-workflows.md): the business logic and process flows this page inventory drives.
- **data model** [010-data-model.md](010-data-model.md): the entities every field or action on a page maps to.
- **frontend app design** [010-frontend-app.md](010-frontend-app.md): elaborates this page inventory into the AngularJS module, routing, and controller structure and the API calls each page makes.
- **prototype extraction** [010-prototype.md](010-prototype.md): the `jobsearch` prototype's observed run durations this UI's async-run handling accounts for.

## Information architecture

The nav is organized around **domain entities**, the things the user owns and comes back to check on, rather than around the workflow numbers used to spec them. A user thinks "let me check my leads" or "what did today's search turn up," rather than "let me go do workflow 5." Four of the five nav destinations are exactly the nouns in the glossary: **Tracks**, **Posts**, **Leads**, **Applications**. Match score, stage, and apply status, the mechanics workflows.md is precise about, show up as state *within* these entity views rather than as separate destinations.

The fifth destination, **Automation**, is deliberately not an entity the user curates. It's the operational machinery underneath the other four:

1. run history, which answers whether the last search or apply run actually worked.
2. MCF session status, which answers whether the credential the apply run depends on is still valid.

Neither is something the user "manages" day to day the way they manage a lead or a track. They're checked occasionally, usually when something looks wrong elsewhere. Bundling them into one admin-adjacent nav item keeps the primary nav to the four things the user actually works with, rather than diluting it with two ops or diagnostic screens that would otherwise sit as peers to "Leads."

This makes the page count line up with the nav count. Every nav destination is exactly one page. The contextual views, CVs, Search Profiles, Manual Post Entry, and Lead Detail, are reached *from* a page rather than sitting in the nav themselves.

## Navigation structure

A persistent left sidebar, or a top nav as an implementation detail, with five destinations, plus an always-visible session-status indicator:

1. **Tracks**: Workflow 1
2. **Posts**: Workflows 2, 3, 4
3. **Leads**: Workflow 5
4. **Applications**: Workflow 6
5. **Automation**: Workflows 8, 9

**Session status badge**, top-right, always visible, and not a nav destination: shows `valid`, `expired`, or `missing` for the MCF session, Workflow 8, and is clickable to open the session panel from anywhere. This is deliberately not buried behind the Automation nav item. An expired session is the single most common reason an apply run will abort, REQ-APPLY-06, so REQ-FE-02's principle of surfacing failures rather than burying them argues for it being always on screen regardless of where the user is. Clicking it opens the same session panel described under Automation below. That section explains why it's one component reached two ways rather than two separate implementations.

## Cross-cutting UX patterns

### Async run handling

Search runs and apply runs are not instantaneous. The `jobsearch` prototype observed full sweeps around 15 minutes for cards and 3 to 5 minutes for profiles, per the **prototype extraction**. The UI must not block on these:

- Triggering a run, from Posts or Applications, immediately returns a `run_log` id and switches that page into a **running** state: a progress indicator plus live-updating counts, for example "42 postings found, page 6," polled from the backend rather than the user needing to babysit a blocking request.
- The user can navigate away while a run is in progress. The session-status-badge area also carries a small persistent "run in progress" indicator so it's visible from any page, per REQ-FE-02, linking into Automation's Runs tab.
- On completion, whether success, partial, or failed, the triggering page updates in place and a toast or banner summarizes the outcome, for example "Search complete: 14 new postings, 2 errors, see Automation."

### Error surfacing

- Run-level errors, meaning a search or apply run that failed or partially failed, surface both inline on the page that triggered it and as an entry in Automation's Runs tab, per REQ-FE-02 and REQ-PLAT-03. They are never surfaced only to a console or log file.
- Field-level validation errors, such as incomplete track config or a missing CV before queueing an apply, block the action with an inline message at the point of entry rather than a generic toast.
- A missing or expired session is treated as a blocking error on the Applications page specifically, where it prevents triggering a run, but only a passive badge state elsewhere.

### Confirmation modals

Reserved for actions that are destructive or hard to reverse: closing a lead, submitting an application batch, which mutates MCF-side application state per REQ-APPLY-03, and overwriting an existing valid session. Routine stage transitions, such as `PROSPECT` → `TOAPPLY`, do not need a confirmation. They're reversible within the app.

### Empty / loading states

Every list-bearing page, meaning Posts, Leads, Applications, and Automation, defines an explicit empty state with a call to action rather than a bare empty table. For example, an empty Leads page shows "Promote a posting from Posts to get started." Seed and demo data availability, per REQ-DEV-02, means these states will be seen often during development.

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

**Purpose:** configure the tracks a user is pursuing, Workflow 1, and their identity/lifecycle. This is the root config everything else hangs off — a lead cannot exist without a track (REQ-CRM-01).

- List of existing tracks, role plus seniority. Each row shows a read-only summary of its search profile — keywords, minimum salary, maximum age, minimum match score, and, if scheduled, when its next run fires — with a "Configure search" link to that track's Search Profiles page (1b). The search criteria are edited there, not on this page.
- Create or edit a track: role name and seniority fields only. A newly created track has no search profile until the user configures one on Search Profiles (1b); it simply cannot run a search yet.
- Default CV picker per track, sourced from the CV catalog, the data model's `cv` table. A "Manage CVs" link opens page 2 for adding or editing labels. If the catalog is empty, the picker itself surfaces that link inline rather than leaving the user stuck on an empty dropdown.
- Archive action per track, a soft delete per REQ-SRCH-10: archived tracks drop out of the active list and out of every track selector elsewhere in the app, including Posts, promote-to-lead, and apply default CV, by default, with a toggle on this page to show archived tracks and unarchive one. Historical posts, leads, and applications tied to an archived track remain intact and browsable.
- No on-demand search-trigger action lives here, and no search-profile editing either. Triggering a run on demand happens from Posts, scoped to a track selected there. This page is exclusively track identity and lifecycle.

### 1b. Search Profiles

**Purpose:** configure the search criteria for one track, REQ-SRCH-01. Reached from the "Configure search" row action on Tracks (page 1) rather than a standalone nav entry — the same reached-from-a-page pattern as CVs (page 2), since a search profile has no lifecycle independent of its owning track (Information architecture above).

- One form per track, 1:1 by `track_id`: keywords, minimum salary, maximum post age, minimum match score, and employment type, defaulting to Full Time.
- Schedule fields, REQ-SRCH-11: an on/off switch, an interval, and the next run time. Off by default for a new track. These are plain fields on this same form, not a separate dialog, since REQ-SRCH-11 keeps schedule configuration in the same place as the rest of the search criteria.
- No track-identity fields here. Role, seniority, default CV, and archive state stay on Tracks (page 1); this page cannot delete or archive the owning track.
- No on-demand search-trigger action here either, for the same reason it isn't on Tracks: triggering a run happens from Posts, scoped to a track selected there.

### 2. CVs

**Purpose:** maintain the CV/resume label catalog that Tracks draws from as a default and Applications draws from as an override, per REQ-APPLY-02.

- A simple list of `cv` rows, just a label each. Per the **data model**, the actual file lives on the user's MCF profile. This table only stores the substring the apply run matches against MCF's resume-selector options.
- Add, rename, or remove a CV label. Removing a label that's in use, as a track default or an application override, is blocked with an inline explanation and a list of what references it, rather than silently orphaning those references.
- Reached from the "Manage CVs" link on Tracks, and from the CV override control on Applications. There is no standalone nav entry, since it's a small supporting catalog rather than an entity with its own workflow or lifecycle, per Information architecture above.
- No delete/archive ambiguity here the way there is for tracks: an unused CV label can simply be removed.

### 3. Posts

**Purpose:** the primary daily-use screen. Review postings for a track and act on them, Workflow 2 and 4.

- Track selector at the top. Postings are always viewed in the context of one track, since match score is per-track.
- "Run search" button → enters the async running state described above.
- Results table: title, company, salary, posted date, match score, age, closing date if known, and an `already promoted` indicator if a lead already exists for this post under this track. Results are sorted by score descending by default so the highest-priority postings surface first. This is the entire point of REQ-SRCH-09.
- Filters: match-score threshold, defaulting to the track's configured `min_match_score` but adjustable per view, max age, and an "include below-threshold" toggle to see what's screened out.
- Manual entries and scraped postings share this same list once persisted. Manual entries carry a small "manual" tag rather than living in a separate view, Workflow 3, since they fold into the same review flow per the requirements' framing.
- Row action: **Promote to lead.** If the post matches more than one track, this opens a small track-picker, Decision 2 and Workflow 4, defaulting to the track currently being viewed. Confirming it creates the lead, and the row updates to an `already promoted` state with the promote action disabled. A post can be promoted into at most one lead.
- "Add posting manually" button opens page 4 as a dialog.

### 4. Manual Post Entry (dialog)

**Purpose:** capture a posting MCF search didn't surface, Workflow 3 and REQ-SRCH-07.

- Form fields mirror `post`: position title, company, URL/reference, salary, and posted date, defaulting to today.
- Matching tracks are auto-assigned on save using the same match-scoring logic as a search run. This feeds `post_track` with `search_match = false`, per the data model. An inline track-assignment editor lets the user adjust it afterward.
- On save, returns the user to Posts with the new posting visible (tagged "manual"), immediately promotable.

### 5. Leads

**Purpose:** the CRM view. Every open lead, organized by stage, and the entry point to close or queue actions, Workflow 5.

Sub-navigation: tabs across the top of the page: **Pipeline**, **Applied**, **Callbacks**, **Interviews**, **Offers**, **Closed**. All six are filtered views of the same `lead` list by stage rather than separate entities. A lead simply appears under whichever tab matches its current stage, moving itself when the stage changes, so there is no per-tab data to keep in sync.

The split follows how the two halves of a lead's life actually get used. `PROSPECT` and `TOAPPLY` are high-volume and triage-y, involving scanning many leads at once and queuing a batch for apply, which a board suits. `APPLIED` through `OFFER` are lower-volume and detail-y, involving one specific callback, one specific interview slot, or one specific offer to weigh, where a focused list surfacing the stage's one relevant date beats a generic card.

**Pipeline tab board**: `PROSPECT` and `TOAPPLY`:

- Board layout, one column per stage. Each card shows title, company, track, deadline, highlighted if approaching or passed, and days since last activity.
- A card's days-since-last-activity indicator shifts into a warning state as it approaches the 28-day auto-expiry threshold, REQ-CRM-05, so the user isn't surprised when a stale lead moves itself to Closed. Last activity is the latest entry in the lead's activity log, REQ-CRM-08, rather than a bare timestamp, and this indicator applies across every tab on this page, including the board.
- Manual stage transitions happen via a control on the card: a "move to next stage" button plus a dropdown for jumping stages. Transitions are button and dropdown driven rather than drag-and-drop.
- `TOAPPLY`-stage cards show a "select for apply queue" checkbox, feeding bulk selection into Workflow 6's queue step. This is the only page from which leads enter Applications.

**Applied / Callbacks / Interviews / Offers tabs**: one flat list per stage, each row showing the most recent activity-log entry, REQ-CRM-08, rather than a column position:

- **Applied**: title, company, track, applied date, days since applied. The waiting-to-hear-back list.
- **Callbacks**: title, company, track, last logged contact, notes preview. The user logs the callback, writing a `contact_logged` event and updating last-contact date and notes, and advances the lead to `INTERVIEW` from here once one is scheduled.
- **Interviews**: title, company, track, last logged activity, notes. There is no dedicated interview-date field. The interview's date and time is captured as free text in notes or the logged event's detail, and the lead's `deadline` field keeps its one consistent meaning rather than being repurposed per stage.
- **Offers**: title, company, track, deadline, notes. The action-heavy tab: most rows here end in a close, `offer_accepted`, `rejected`, or `withdrawn`, rather than a further stage advance.
- Every row on these four tabs carries a "move to next stage" / close control the same as a board card. A list row remains interactive. It's the board card's fields reordered for the stage.

**Closed tab:**

- `CLOSED` leads, listing `close_reason`, satisfying REQ-CRM-06's "removed from active pipeline view while history is preserved."
- A lead auto-closed as `expired` or `apply failed`, Workflow 5 and 7, appears here with that reason pre-filled and a subtle "auto-closed" marker distinguishing it from a manual close, so the user isn't confused about why it moved.

Clicking a card or row on any tab opens the Lead Detail panel.

### 6. Lead Detail (panel/dialog)

**Purpose:** the day-to-day working surface for one lead. Everything REQ-CRM-03 lists that doesn't fit on a board card.

- Deadline, applied date, first-attempt date, last-contact date (editable date fields).
- Last-activity indicator, derived from the lead's activity log, REQ-CRM-08: days since the latest logged event and the resulting auto-expiry date, REQ-CRM-05, so the user can see at a glance whether a lead is at risk of expiring.
- Free-text notes. This is also where scheduled-interview and callback details, date/time, who, and what was discussed, live, since those aren't dedicated structured fields.
- Link back to the underlying post's full detail/description (read-only, since post data isn't user-editable).
- Title/company override fields, explicitly labeled as overrides so it's clear the underlying post is untouched, per REQ-CRM-04.
- Manual `CLOSED` action with a required reason picker, one of the following. This sits behind the confirmation-modal pattern above.
  01. offer accepted
  02. rejected
  03. withdrawn
  04. expired
  05. cancelled
  06. duplicate
  07. apply failed
- Activity history for this lead, REQ-CRM-08: a reverse-chronological list of logged events, such as stage changes, contact logged, notes edited, and deadline changed, interleaved with any `application` attempts and their status and timestamp. A user investigating "why is this stuck at TOAPPLY" or "when did I last hear from them" doesn't have to leave the panel to check Automation.

### 7. Applications

**Purpose:** review and execute a batch apply run, Workflow 6.

- List of `queued` applications, created when leads were selected from Leads, each showing the lead's title, company, track, and its CV assignment, defaulting to the track's default CV per REQ-APPLY-02, with an inline override control drawing on the same CV catalog as page 2. A "manage CVs" link is available from the override control for adding a label on the fly.
- Applications with an unresolved problem from a prior attempt, for example `cv_not_found` needing a fixed CV per Workflow 7, are visually flagged and blocked from re-queueing until the CV override is set.
- Remove-from-queue action per row, for anything the user changes their mind about before running, per REQ-APPLY-11: discards the queued `application` row and closes the owning lead with reason `withdrawn`. This does not revert the lead to `PROSPECT`, and it is not available to re-queue later. It sits behind the confirmation-modal pattern like any other lead close, since at a glance it can look like a reversible dequeue when it isn't.
- Session status inline, mirroring the global badge. If invalid, the "Run" button is disabled with an explanation rather than allowing a doomed run to start, per REQ-APPLY-06.
- "Run apply batch" button, behind the confirmation modal since this mutates real MCF-side state, → async running state as described above, with per-application progress such as "3 of 8 processed."
- **Results view**, same page, post-run: each application's outcome, per REQ-APPLY-04's full vocabulary, with a per-outcome next action surfaced inline per Workflow 7's table. For example, a `cv_not_found` row gets a "fix CV and retry" action right there, a `post_closed` row shows "lead auto-closed" with a link to it, and an `applied` row shows "lead moved to Applied."

### 8. Automation

**Purpose:** the operational and diagnostic hub for the machinery underneath Posts and Applications. It isn't a thing the user curates. It's where they check on it and fix it when something's broken. Two tabs:

**Runs tab**, REQ-PLAT-03 and REQ-FE-02: diagnose a run without re-running it:

- Reverse-chronological list of `run_log` rows: type, search or apply, track if applicable, start and end time, status, and outcome counts.
- Expand a row for full error detail. For apply runs this also links to the resulting applications. For search runs it links back to Posts filtered to that run's discoveries.
- This is the page the "run in progress" nav badge indicator links to.

**Session tab**, REQ-APPLY-06: establish or refresh the session apply runs depend on, Workflow 8:

- Current status, valid, expired, or missing, and, if valid, when it was uploaded.
- "Log in to MCF" button: opens MCF's Singpass login flow in an external browser context. The app does not attempt to automate or observe this step, per the out-of-scope boundary on login, MFA, and CAPTCHA automation.
- "Upload session" control: paste or upload the exported cookie data. On submit, the backend validates the domain match and updates status. A failed validation shows an inline error explaining the cookie wasn't recognized rather than failing as a silent no-op.
- Overwriting an existing valid session goes through the confirmation-modal pattern, since it invalidates the current one.
- This tab is the same component the top-right session badge opens as an overlay from any page. It's one implementation with two entry points, so an expired session noticed mid-Applications-review can be fixed without losing place, while the same content is still reachable with full context, including last-upload history sitting next to Runs, via the nav.
