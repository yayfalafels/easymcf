# Tracks and search profiles

## Contents

- [Create or edit a track](#create-or-edit-a-track)
- [Configure the search profile](#configure-the-search-profile)
- [Schedule automatic searches](#schedule-automatic-searches)
- [Archive a track](#archive-a-track)
- [Fix a track setup problem](#fix-a-track-setup-problem)

Tracks group searches by role and seniority. Each track has one search profile, which controls the keywords and filters used for its search runs, plus an optional schedule and default CV.

## Create or edit a track

1. Open **Tracks**. In the form, choose a role and enter a seniority label such as `senior`.
2. Choose a **Default CV** if you want leads on this track to use a particular resume. You can leave it unset, but queued leads will need a CV assigned before apply automation can use them.
3. Select **Save**. The new track appears in the list with its search focus.
4. To change the role, seniority, or default CV later, select **Edit**, update the form, and save again.

If the form displays a field error, correct the value it names. If a track is missing from Posts or another selector, check that it has not been archived.

## Configure the search profile

Select **Configure search** beside the track. Set its keywords and employment type, then review the optional minimum salary and maximum posting age. Save the configuration before running a search.

The page also shows **Minimum match score**. This release currently records a fixed score of `1.0` for each posting/track pairing, so changing this value does not rank or filter the current search results.

## Schedule automatic searches

On the search configuration page, select **Enable schedule**, enter a repeat interval in hours, and save. Leave the schedule disabled if you only want to start searches manually from **Posts**. Scheduled runs apply only to active tracks with scheduling enabled; they run in the background and appear on **Automation**.

The interval must be at least one hour. If no scheduled run appears, verify the schedule is enabled, the track is active, and the interval was saved. Check the Automation page for a run record.

## Archive a track

Select **Archive** beside an active track to stop treating it as an active search track. To see archived tracks, select **Show archived**; select **Unarchive** to make a track active again. Archiving does not delete the track or its existing postings and leads.

## Fix a track setup problem

If a search cannot start, confirm that at least one active track exists and that its search profile has saved keywords and an employment type. If the track has no CV, assign a default before apply, or select a CV on each lead in the Applications queue. For a search failure after it starts, read the run details on [Automation](runs.md) and check the MCF connection on [Connect MCF](mcf-connection.md).
