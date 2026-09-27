# Run history

## Contents

- [Open run history](#open-run-history)
- [Read a run](#read-a-run)
- [Handle a failed or incomplete run](#handle-a-failed-or-incomplete-run)

The **Automation** page contains the run history for searches and apply batches. It shows status and outcome counts so you can tell whether work completed, partially completed, or failed.

## Open run history

1. Select **Automation** in the navigation bar.
2. Wait for the run list to load. Runs are ordered with the newest first. If the list looks stale, select **Refresh**.
3. Select a run row to expand its details. The row includes the run number, type, track when applicable, start/end times, status, and outcome counts.

## Read a run

For a search run, check its status, track, counts, and error detail. For an apply run, expand the row and review each application outcome and its detail. Use the run number when discussing a problem with the person supporting your installation.

The navigation bar shows a run-in-progress marker while a search or apply run is active. A running row may not have an end time yet. Wait for it to finish, then refresh the history if the status has not updated.

## Handle a failed or incomplete run

1. Expand the failed or partial run and read its error detail before retrying.
2. For an apply run, check every application row. A run can complete some leads successfully even when another lead fails; use [Apply queue](apply.md) to interpret each outcome.
3. For a search run, check that the track is active, its search profile is saved, and its MCF connection is valid. Correct the issue before running again.
4. If the row remains `running`, select **Refresh** and give the active run time to finish. Do not trigger a duplicate run just because the end time is blank.
5. If the error persists, record the run number and displayed error detail for support.

An empty history means no search or apply run has been recorded for this account yet. It does not indicate that a run failed.
