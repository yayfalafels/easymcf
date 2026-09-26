<!--
boilerplate for one issue, matching this repo's actual conventions (see e.g.
docs/features/02-dev-env-setup-postgresql-db.md, issue 02.IS.01, for a real
worked example this was modeled on).

usage:
1. add one row to the tracker's issues table (## Validate -> **Issues**):
     | <F>.IS.<n> | <seq> | pending | <one-line issue summary> |
2. paste the section below right after that table, filling in <angle-bracket>
   placeholders as you go.
3. a first-out exception is NOT a diagnostic step - log it as data first, then
   add diagnostic steps as you actually take them (don't pre-write steps you
   haven't run yet).
4. keep the root cause framed as a **hypothesis** until a diagnostic step has
   confirmed it. flip status pending -> closed only once the fix is applied
   and re-validated.
-->
_<F>.IS.<n> (pending) <one-line issue summary>_

**problem description**

<what broke, observed vs expected, in enough detail that someone with no other context understands the symptom>

**exception**

```log
<the exact error/traceback text, or "<no error captured - describe what was observed instead>">
```

**triggering actions**

<the exact sequence of steps/commands that led to this - specific enough to reproduce>

**hypothesis**

- use hypothesis framing until a validated fix is applied

<leading theory of root cause, and any less-likely alternative theories still open>

**diagnostic steps**

- first out exception is NOT a diagnostic step
- diagnostic steps reveal information or apply a fix
- assume re-run and validation, these are not diagnostic steps
- keep the step description brief, use the diagnostic details section to elaborate actions and learnings for each step

| id             | seq | status  | step                     |
| -------------- | --- | ------- | -------------------------- |
| <F>.IS.<n>.01  | 01  | pending | \<diagnostic step 01\>     |

**diagnostic details**

01. (pending) <what was actually done for step 01, what it revealed, and how it narrows or confirms the hypothesis>
