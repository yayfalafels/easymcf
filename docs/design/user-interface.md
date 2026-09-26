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
  - [9. Offers](#9-offers)
  - [10. Sign in](#10-sign-in)
  - [11. Sign up](#11-sign-up)

## Purpose

This document is the page inventory and UX behavior for the AngularJS frontend, REQ-FE-01/02, derived from the **workflows** doc. Every page below exists to drive one or more of that document's workflows, and every field or action on a page maps to an entity in the **data model**. This is a conceptual, wireframe-level spec covering structure, states, and interactions. It carries no layout grid, color, or component-library decisions. The **frontend app design** elaborates this page inventory into the actual AngularJS module, routing, and controller structure and the API calls each page makes. Read that alongside this document once building.

010 serves users on their own desktop machine, each signed in to their own account. There is no responsive or mobile requirement and no offline mode. Every page except Sign in and Sign up requires a signed-in user and shows only that user's data, REQ-AUTH-05 and REQ-AUTH-06. The MCF session flow below is separate from signing in to easymcf.

## References

- **workflows** [workflows.md](workflows.md): the business logic and process flows this page inventory drives.
- **data model** [data-model.md](data-model.md): the entities every field or action on a page maps to.
- **frontend app design** [frontend-app.md](frontend-app.md): elaborates this page inventory into the AngularJS module, routing, and controller structure and the API calls each page makes.
- **prototype extraction** [prototype.md](prototype.md): the `jobsearch` prototype's observed run durations this UI's async-run handling accounts for.

## Information architecture

The nav is organized around **domain entities**, the things the user owns and comes back to check on, rather than around the workflow numbers used to spec them. A user thinks "let me check my leads" or "what did today's search turn up," rather than "let me go do workflow 5." Five of the six nav destinations are exactly the nouns in the glossary: **Tracks**, **Posts**, **Leads**, **Offers**, **Applications**. Match score, stage, and apply status, the mechanics workflows.md is precise about, show up as state *within* these entity views rather than as separate destinations.

The sixth destination, **Automation**, is deliberately not an entity the user curates. It's the operational machinery underneath the other four:

1. run history, which answers whether the last search or apply run actually worked.
2. MCF session status, which answers whether the credential the apply run depends on is still valid.

Neither is something the user "manages" day to day the way they manage a lead or a track. They're checked occasionally, usually when something looks wrong elsewhere. Bundling them into one admin-adjacent nav item keeps the primary nav to the five things the user actually works with, rather than diluting it with two ops or diagnostic screens that would otherwise sit as peers to "Leads."

This makes the page count line up with the nav count. Every nav destination is exactly one page. The contextual views, CVs, Search Profiles, Manual Post Entry, and Lead Detail, are reached *from* a page rather than sitting in the nav themselves.

## Navigation structure

A persistent left sidebar, or a top nav as an implementation detail, with six destinations, plus an always-visible session-status indicator and the signed-in user section. A signed-out visitor sees neither the destinations nor the user section, only the Sign in or Sign up page:

1. **Tracks**: Workflow 1
2. **Posts**: Workflows 2, 3, 4
3. **Leads**: Workflow 5
4. **Offers**: Workflow 5
5. **Applications**: Workflow 6
6. **Automation**: Workflows 8, 9

**User section**, top-right on every signed-in page, REQ-AUTH-08: a circle icon showing the user's photo, or their initials when no photo exists, that opens a small menu with the user's name and email, `Upload photo`, `Remove photo` when a photo exists, and `Log out`. Uploading opens the file picker for a JPEG, PNG, or WebP image and refuses a file over 2 MB before sending it. `Log out` returns the user to Sign in.

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
- A `401` from any call means the sign-in session has ended. The UI sends the user to Sign in and returns them to the page they were on afterward, and shows no error toast for it. A `429` from sign in shows the server's message.
- A missing or expired MCF session is treated as a blocking error on the Applications page specifically, where it prevents triggering a run, but only a passive badge state elsewhere.

### Confirmation modals

Reserved for actions that are destructive or hard to reverse: closing a lead, dropping leads in a batch, settling an offer, submitting an application batch, which mutates MCF-side application state per REQ-APPLY-03, and overwriting an existing valid session. Routine stage transitions, such as `TOAPPLY` → `APPLIED`, do not need a confirmation. They're reversible within the app.

### Empty / loading states

Every list-bearing page, meaning Posts, Leads, Offers, Applications, and Automation, defines an explicit empty state with a call to action rather than a bare empty table. For example, an empty Leads page shows "Run a search, or add a lead manually, to get started." Seed and demo data availability, per REQ-DEV-02, means these states will be seen often during development.

## Page inventory

| # | Page                                   | Nav destination | Primary requirement(s)               |
| - | -------------------------------------- | --------------- | ------------------------------------ |
| 1 | Tracks                                 | Tracks          | REQ-SRCH-01, REQ-APPLY-02, REQ-FE-01 |
| 2 | CVs (page, from Tracks)                | —               | REQ-APPLY-02                         |
| 3 | Posts                                  | Posts           | REQ-SRCH-02..09, REQ-FE-01           |
| 4 | Manual Post Entry (dialog, from Posts) | —               | REQ-SRCH-07                          |
| 5 | Leads                                  | Leads           | REQ-CRM-01..07, 09, 11, REQ-FE-01    |
| 6 | Lead Detail (panel, from Leads)        | —               | REQ-CRM-03, 04, 09, 10               |
| 7 | Applications                           | Applications    | REQ-APPLY-01..09, REQ-FE-01          |
| 8 | Automation (Runs)                      | Automation      | REQ-PLAT-03, REQ-FE-02               |
| 9 | Offers                                 | Offers          | REQ-CRM-10                           |
| 10 | Sign in                               | —               | REQ-AUTH-03..05                      |
| 11 | Sign up                               | —               | REQ-AUTH-01, 02                      |

### 1. Tracks

**Purpose:** configure the tracks a user is pursuing, Workflow 1, and their identity/lifecycle. This is the root config everything else hangs off — a lead cannot exist without a track (REQ-CRM-01).

- List of existing tracks, role plus seniority. Each row shows a read-only summary of its search profile — keywords, minimum salary, maximum age, minimum match score, and, if scheduled, when its next run fires — with a "Configure search" link to that track's Search Profiles page (1b). The search criteria are edited there, not on this page.
- Create or edit a track: role name and seniority fields only. A newly created track has no search profile until the user configures one on Search Profiles (1b); it simply cannot run a search yet.
- Default CV picker per track, sourced from the CV catalog, the data model's `cv` table. A "Manage CVs" link opens page 2 for adding or editing labels. If the catalog is empty, the picker itself surfaces that link inline rather than leaving the user stuck on an empty dropdown.
- Archive action per track, a soft delete per REQ-SRCH-10: archived tracks drop out of the active list and out of every track selector elsewhere in the app, including Posts, manual lead add, and apply default CV, by default, with a toggle on this page to show archived tracks and unarchive one. Historical posts, leads, and applications tied to an archived track remain intact and browsable.
- No on-demand search-trigger action lives here, and no search-profile editing either. Triggering a run on demand happens from Posts, scoped to a track selected there. This page is exclusively track identity and lifecycle.

### 1b. Search Profiles

**Purpose:** configure the search criteria for one track, REQ-SRCH-01. Reached from the "Configure search" row action on Tracks (page 1) rather than a standalone nav entry — the same reached-from-a-page pattern as CVs (page 2), since a search profile has no lifecycle independent of its owning track (Information architecture above).

- One form per track, 1:1 by `track_id`: keywords, minimum salary, maximum post age, minimum match score, and employment type, defaulting to Full Time.
- Schedule fields, REQ-SRCH-11: an on/off switch, an interval, and the next run time. Off by default for a new track. These are plain fields on this same form, not a separate dialog, since REQ-SRCH-11 keeps schedule configuration in the same place as the rest of the search criteria.
- No track-identity fields here. Role, seniority, default CV, and archive state stay on Tracks (page 1); this page cannot delete or archive the owning track.
- No on-demand search-trigger action here either, for the same reason it isn't on Tracks: triggering a run happens from Posts, scoped to a track selected there.

### 2. CVs

**Purpose:** maintain the CV/resume label catalog that Tracks draws from as a default and Applications draws from as a per-lead override, per REQ-APPLY-02.

- A simple list of `cv` rows, just a label each. Per the **data model**, the actual file lives on the user's MCF profile. This table only stores the substring the apply run matches against MCF's resume-selector options.
- Add, rename, or remove a CV label. Removing a label that's in use, as a track default, a lead override, or a past attempt's CV, is blocked with an inline explanation and a list of what references it, rather than silently orphaning those references.
- Reached from the "Manage CVs" link on Tracks, and from the CV override control on Applications. There is no standalone nav entry, since it's a small supporting catalog rather than an entity with its own workflow or lifecycle, per Information architecture above.
- No delete/archive ambiguity here the way there is for tracks: an unused CV label can simply be removed.

### 3. Posts

**Purpose:** the primary daily-use screen. Review postings for a track and act on them, Workflow 2 and 4.

- Track selector at the top. Postings are always viewed in the context of one track, since a post belongs to the one track that found it or that a manual entry named it to.
- "Run search" button → enters the async running state described above.
- Results table: title, company, salary, posted date, age, closing date if known, a `manual` tag for manual entries, and an `already a lead` indicator, true for every row since every result promotes on its own. Results are sorted by posted date descending by default.
- Filter: maximum age, adjustable per view. It limits only what this screen shows — every result is already a lead regardless of age, since promotion applies no filter of its own.
- Manual entries and scraped postings share this same list once persisted. Manual entries carry a small "manual" tag rather than living in a separate view, Workflow 3, since they fold into the same review flow per the requirements' framing.
- The system promotes every qualifying post to a lead when a search run ends, Workflow 4, so this page offers no promote action. Every row shows `already a lead`, and a post becomes at most one lead.
- "Add posting manually" button opens page 4 as a dialog.

### 4. Manual Post Entry (dialog)

**Purpose:** capture a posting MCF search didn't surface, Workflow 3 and REQ-SRCH-07.

- Form fields mirror `post`: position title, company, URL/reference, salary, and posted date, defaulting to today, plus a required track picker naming the one track the post belongs to.
- On save, the named track receives the posting's one `post_track` row, `search_match = false`, per the data model. There is no auto-assignment and no separate reassignment editor — the request names the track once.
- On save, returns the user to Posts with the new posting visible (tagged "manual"), promoted to a lead by the system on save (Workflow 4).

### 5. Leads

**Purpose:** the CRM view. Every open lead, organized by stage, the entry point to prune the apply queue, and the place to work a lead through to a close, Workflow 5.

The app opens on this page once the user is signed in: `/` and any unmatched path redirect to `/leads`, and a signed-out visitor is sent to Sign in first.

Sub-navigation: tabs across the top of the page: **TOAPPLY**, **Applied**, **Callbacks**, **Interviews**, **Offers**, **Closed**. All six are filtered views of the same `lead` list by stage rather than separate entities. A lead simply appears under whichever tab matches its current stage, moving itself when the stage changes, so there is no per-tab data to keep in sync.

An **Add lead** button above the tabs opens a form (track, title, company, post URL, salary, posted date) that creates the lead and a copy of its post at stage `APPLIED`, REQ-CRM-01.

The split follows how the two halves of a lead's life actually get used. `TOAPPLY` and `APPLIED` are high-volume and triage-y, involving scanning many leads at once, so each renders as compact table rows sized for 15 to 30 leads on one page. `CALLBACK` through `OFFER` are lower-volume and detail-y, involving one specific callback, one specific interview slot, or one specific offer to weigh, where a card that surfaces the latest note and last contact beats a generic row.

**TOAPPLY tab**: the apply queue, one column of compact rows:

- Columns: a checkbox, title (a link to the post), company, track, expected salary, deadline (highlighted if approaching or passed), and days left. Rows sort by days remaining, descending, so the freshest leads sit at the top and aged leads at the bottom.
- A row's days-left indicator shifts into a warning state as it approaches the deadline, REQ-CRM-05, so the user isn't surprised when a stale lead moves itself to Closed. This indicator applies across every tab on this page.
- Batch actions sit at the top of the column: `Apply (n)` moves the checked leads to `APPLIED`, which removes them from the apply queue, and `Drop (n)` closes them as `dropped` after one confirmation that names the number of leads. Each button sends one `POST /api/v1/lead/batch` that applies every checked lead or none, and a header checkbox selects or clears the column. The automated apply run, Workflow 6, works through the leads that remain.
- A row click opens Lead Detail, where a single lead moves to its next stage.

**Applied tab**: compact rows with the same columns as `TOAPPLY` without the checkbox, plus the applied date, sorted by days remaining, descending. The waiting-to-hear-back list.

**Callbacks / Interviews / Offers tabs**: cards, sorted by last contact date with the most recent first and leads with no contact last. Each card shows title, company, track, expected salary, days left, the latest note (first 120 characters), and `Last contact: <date>`:

- **Callbacks**: the user logs the callback, writing a `contact_logged` event and updating last-contact date and notes, and advances the lead to `INTERVIEW` from Lead Detail once one is scheduled.
- **Interviews**: there is no dedicated interview-date field. The interview's date and time is captured as free text in notes or the logged event's detail, and the lead's `deadline` field keeps its one consistent meaning rather than being repurposed per stage.
- **Offers**: each card shows the offer amount in place of the expected salary, the offer date and deadline, and the buttons `Accept`, `Reject`, and `Withdrawn`, each behind the confirmation modal. Each sets the offer's final status and closes the lead, REQ-CRM-10. The Offers page (page 9) lists the full history.
- A card click opens Lead Detail.

**Closed tab:**

- `CLOSED` leads as compact rows, listing `close_reason` and sorted by last update, most recent first, satisfying REQ-CRM-06's "removed from active pipeline view while history is preserved."
- A lead auto-closed as `expired` or `apply failed`, Workflow 5 and 7, appears here with that reason pre-filled and a subtle "auto-closed" marker distinguishing it from a manual close, so the user isn't confused about why it moved.

Clicking a card or row on any tab opens the Lead Detail panel.

### 6. Lead Detail (panel/dialog)

MCF posting links use the saved authenticated MCF session when it is valid, opening the exact target in a separate visible Chromium window. Without a valid saved session, the same link remains an ordinary unauthenticated new-tab URL. The Leads page title links use the same behavior.

**Purpose:** the day-to-day working surface for one lead. Everything REQ-CRM-03 lists that doesn't fit on a board card.

- Deadline, applied date, first-attempt date, last-contact date (editable date fields).
- Last-activity indicator, derived from the lead's activity log, REQ-CRM-08: days since the latest logged event and the resulting auto-expiry date, REQ-CRM-05, so the user can see at a glance whether a lead is at risk of expiring.
- Free-text notes. This is also where scheduled-interview and callback details, date/time, who, and what was discussed, live, since those aren't dedicated structured fields.
- Position title, company name, and post URL, editable text fields that open filled with the values copied from the post when the lead was created, per REQ-CRM-03 and REQ-CRM-04. Editing them changes the lead only, since a post is read-only to every user.
- Open post: a link to the lead's post URL in a new tab, shown when the URL is a valid `http` or `https` address and shown as unavailable otherwise. The post's own description stays read-only.
- Track, a drop-down of the active tracks (`role / seniority`) that re-assigns the lead, REQ-CRM-12. The change saves with the other fields, the lists show the lead under its new track, and the activity history logs the edit.
- Expected salary (SGD), editable at any stage and shown on the lead lists, REQ-CRM-09. A lead at `OFFER` shows its offer amount in the lists instead.
- Manual `CLOSED` action with a required reason picker, one of the following. This sits behind the confirmation-modal pattern above. A lead at `OFFER` has no close control, because its offer status closes it (see the offer block below).
  01. offer accepted
  02. rejected
  03. withdrawn
  04. expired
  05. cancelled
  06. duplicate
  07. apply failed
  08. dropped
- Offer block at `OFFER`, REQ-CRM-10: amount, offer date, and deadline, with `Accept`, `Reject`, and `Withdrawn` buttons, each behind the confirmation modal because each closes the lead. Moving an `INTERVIEW` lead to `OFFER` opens the offer dialog (see page 9). A `CLOSED` lead that closed from an offer shows `Re-open`, which returns it to `INTERVIEW`.
- Activity history for this lead, REQ-CRM-08: a reverse-chronological list of logged events, such as stage changes, contact logged, notes edited, and deadline changed, interleaved with any `application` attempts and their status and timestamp. A user investigating "why is this stuck at TOAPPLY" or "when did I last hear from them" doesn't have to leave the panel to check Automation. Each event shows its stage context from `stage_from` and `stage_to`: a stage change reads `TOAPPLY → APPLIED`, the promotion reads `new → TOAPPLY`, and a manual add reads `new → APPLIED`, and every other event reads `at <stage>`. Application attempts carry no stage context.
- Refresh after a save: every saved change (stage move, contact, fields, post URL, note) re-reads the lead, its notes, and its activity into the panel, and reloads the Leads page's list behind it. The lead appears under its new stage on the board, the panel header shows the new stage, and the stage button offers the following stage (`Move to CALLBACK` after a move to `APPLIED`).

### 7. Applications

**Purpose:** review and execute a batch apply run, Workflow 6.

- The apply queue, the open leads at `TOAPPLY`, each showing the lead's title, company, track, and its CV assignment, defaulting to the track's default CV per REQ-APPLY-02, with an inline override control drawing on the same CV catalog as page 2. A "manage CVs" link is available from the override control for adding a label on the fly.
- Leads with an unresolved problem from a prior attempt, for example `cv_not_found` needing a fixed CV per Workflow 7, are visually flagged and blocked from the next run until the CV override is set.
- Drop action per row, for a lead the user no longer wants to pursue before running, per REQ-APPLY-11: it closes the lead with reason `dropped` and sits behind the confirmation-modal pattern like any other lead close. A dropped lead is not available to re-queue later.
- Session status inline, mirroring the global badge. If invalid, the "Run" button is disabled with an explanation rather than allowing a doomed run to start, per REQ-APPLY-06.
- "Run apply batch" button, behind the confirmation modal since this mutates real MCF-side state, → async running state as described above, with per-application progress such as "3 of 8 processed."
- **Results view**, same page, post-run: each application's outcome, per REQ-APPLY-04's full vocabulary, with a per-outcome next action surfaced inline per Workflow 7's table. For example, a `cv_not_found` row gets a "fix CV and retry" action right there, a `post_closed` row shows "lead auto-closed" with a link to it, and an `applied` row shows "lead moved to Applied."

### MCF connection pop-up

**Purpose:** establish, inspect, open, or disconnect the MCF session from any guarded page, Workflow 8 and REQ-APPLY-06.

- The MCF nav icon carries a red, amber, or green status indicator and toggles one global pop-up. There is no separate MCF route or Automation Session tab.
- Missing or expired shows **Connect MCF**. Starting opens an isolated MCF/Singpass browser context and shows the current QR image and decoded Singpass app link. The user completes Singpass approval manually.
- A first authenticated account shows its email and requires confirmation. A previously confirmed matching account connects directly. A mismatch is blocked and explained.
- Connected shows the confirmed account, **Open**, and **Disconnect**. Open launches authenticated MCF home in a visible browser. Disconnect deletes the saved browser-state files and returns the session to missing.
- MCF posting links use the authenticated visible browser while valid. Otherwise they retain ordinary unauthenticated new-tab navigation.

### 8. Automation

**Purpose:** the operational and diagnostic hub for search and apply runs. It is where the user checks run outcomes and errors.

REQ-PLAT-03 and REQ-FE-02: diagnose a run without re-running it:

- Reverse-chronological list of `run_log` rows: type, search or apply, track if applicable, start and end time, status, and outcome counts.
- Expand a row for full error detail. For apply runs this also links to the resulting applications. For search runs it links back to Posts filtered to that run's discoveries.
- This is the page the "run in progress" nav badge indicator links to.

### 9. Offers

**Purpose:** the complete history of offers and the place to act on an open one, REQ-CRM-10, Workflow 5.

- Table of every offer, open and closed: lead title and company, offer date, deadline, amount in SGD, and status, sorted by offer date, most recent first, with a status filter.
- **New offer** opens the offer dialog: `Lead` (a drop-down of `INTERVIEW` leads with a search box), `Offer date` (a date picker, default today), `Amount (SGD)` (default the lead's expected salary), and `Deadline` (default the lead's deadline, editable). Saving attaches the offer and moves the lead to `OFFER`. The same dialog opens from Lead Detail when the user moves an `INTERVIEW` lead to `OFFER`, with that lead preselected.
- Open rows show `Accept`, `Reject`, and `Withdrawn`, each behind the confirmation modal because each closes the lead, and an open row's amount and deadline are editable. Rows with a final status are read-only. `expired` appears through auto-expiry only.

### 10. Sign in

**Purpose:** let a returning user reach their data, Workflow 10, REQ-AUTH-03 to REQ-AUTH-05. It has no nav destination, and every other page redirects here when nobody is signed in.

- Email and password fields with a `Sign in` button. A failure shows one message for a wrong password, an unknown email, and an account without a password. After repeated failures the page shows the server's wait message.
- A `Continue with Google` button, shown only when Google sign-in is configured. A cancelled consent, an invalid token, an unreachable provider, or an unverified Google email returns here with a specific message above the form.
- A `Create account` link to Sign up.
- After a successful sign in the user returns to the page they first asked for, or to Leads when they came here directly. A user who is already signed in and opens this page goes to Leads.

### 11. Sign up

**Purpose:** create an account, Workflow 10, REQ-AUTH-01 and REQ-AUTH-02. It has no nav destination.

- Name, email, and password fields with a `Create account` button, and a `Continue with Google` button that behaves as on Sign in.
- Beneath the password field, a checklist of the password rules that marks each rule met or unmet as the user types: at least 12 characters, a lowercase letter, an uppercase letter, a digit, a symbol, and no use of the email or name. The server checks the same rules and shows every unmet one if the form is submitted anyway.
- A duplicate email shows its message next to the email field.
- A `Sign in` link for existing users. A successful sign up signs the user in and returns them as Sign in does.
