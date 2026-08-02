---
name: design-audit
description: Audits one release's design document set (requirements, workflows, data model, architecture, UI, test strategy, etc.) for internal consistency, current best-practice alignment, implementation risk, and correct requirements-to-design hierarchy. Use when asked to review, audit, critique, or sanity-check a release's design docs — not for reviewing implementation code (see /code-review for that).
---

# Design audit

Scope is always **one release**: everything under `docs/releases/<release>/*.md`, plus
[release-roadmap.md](../../../docs/releases/release-roadmap.md) and root `CLAUDE.md` for cross-release
context. This is a documentation/design audit, not a code review — for an early release the code may not
exist yet at all; the audit is about what the documents claim, and whether those claims hold together.

## Process

1. **Read every document in the set in full**, not excerpts — inconsistencies and dangling cross-references
   are the point, and both live in details a partial read misses. Note each document's declared decision-ID
   prefix (`REQ-*`, `ARCH-*`, `STRAT-*`, `TESTDATA-*`, etc.) and its stated place in the hierarchy (most of
   these docs say outright, in their own Purpose section, what they derive from and what derives from them —
   take that at face value and check it).
2. **Check the four questions below** against the full set, not document-by-document — most real findings are
   cross-document (a requirement's implied assumption contradicted three docs later, a decision made twice in
   incompatible ways).
3. **For best-practice claims, verify externally rather than opine** — use WebSearch for the specific
   technology/pattern actually named in the docs (a framework's current support status, a named architectural
   pattern's known failure modes, a security anti-pattern) and cite sources in the finding. Don't flag a
   generic "consider X" without evidence X is a live concern for what's actually written.
4. **Cross-check status/metadata against content**, not just prose against prose: a milestone tracker marking
   a document "pending" while that document is long, complete, and cited by three other docs as settled is
   itself a finding — the tracked status and the actual state of the repo have diverged.
5. Don't invent problems to fill a quota. A doc set with genuinely solid traceability should get a short
   report; padding it with nitpicks to look thorough is worse than a short accurate one.

## The four audit questions

1. **Internal consistency.** Do the documents' explicit statements and *implied* assumptions agree with each
   other? Look especially for: the same concept named or scoped differently in two docs, a decision stated as
   settled in one doc and left open or contradicted in another, and a requirement whose literal scope (e.g.
   "generic" or "all entities") silently collides with a more specific rule stated elsewhere for the same
   data.
2. **Design best practices.** For each domain the design set touches (data modeling, API design, frontend
   framework choice, concurrency/storage, security, browser automation, etc.), how does the design compare to
   current (not historical) best practice? This requires external research, not memory — search for the
   specific pattern or technology named in the docs. A deliberate, well-justified deviation (the docs here
   frequently argue for a "lowest-ceremony" choice on purpose) is not automatically a finding — only flag it
   where the trade-off is either unstated or where current evidence undercuts the stated rationale.
3. **Implementation risk.** What in the design, if built exactly as written, is likely to cause a concrete
   problem later — a race condition implied but not resolved, a performance budget stated elsewhere in the
   set that a different section's numbers don't fit inside, a closed enumeration with no seed/test coverage
   plan, a manual step with no fallback. Prefer risks you can point to a specific mechanism for, over vague
   "this might be hard."
4. **Hierarchy and traceability.** This project's convention is requirements → workflows/data-model →
   architecture/UI/test-strategy, each layer citing the requirement or upstream decision it operationalizes.
   Check both directions: does every requirement have downstream coverage (a requirement nobody's design
   references is unimplemented-by-omission), and does every downstream decision cite something upstream (a
   decision with no traceable justification is either an undocumented requirement or scope creep)? Also check
   that the *documented* sequencing (milestone/build order) matches the *actual* dependency order visible in
   the documents' own cross-references — these two drift apart easily and silently.

## Output

Write findings to `docs/releases/<release>/<release>-issues.md`:

- A summary table at the top: columns `ID | Severity | Category | Title | Docs`, one row per issue, most
  severe first. Keep it scannable — pad columns to a fixed width and keep every row under ~115 characters;
  this table is the thing a reader skims first, so it must not wrap or require horizontal scrolling in a
  plain markdown viewer.
- Severity: **Critical** (design is self-contradictory or unbuildable as written), **High** (a real defect a
  team would hit early and that's expensive to unwind later), **Medium** (a real defect, contained blast
  radius, or a best-practice gap with concrete evidence), **Low** (worth recording, not urgent).
- Category: one of `Internal Consistency`, `Design Best Practice`, `Implementation Risk`,
  `Hierarchy/Traceability`.
- Below the table, one subsection per issue (`### ISS-01 <title>`) with: what's wrong and where (cite
  specific files/sections/decision IDs, not just "the docs"), why it matters concretely, and a suggested
  resolution or question to raise with the owning role (product-manager for scope, architect for cross-domain
  design). Do not restate the summary table row — add the detail the table had no room for.
