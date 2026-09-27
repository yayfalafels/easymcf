# Run a search

## Contents

- [Run flow](#run-flow)
- [Read the results](#read-the-results)
- [Add a posting manually](#add-a-posting-manually)
- [Recover from a search problem](#recover-from-a-search-problem)

Searches use the saved search profile for one active track. The **Posts** page displays discovered postings and their age; search results are also added to the lead pipeline automatically.

## Run flow

1. Open **Posts** and choose the active track to search. The page selects the first active track when one is available.
2. Confirm the track's keywords and search settings on **Tracks** using **Configure search**. Save any changes before running.
3. Select **Run search**. Follow the progress indicators for searching pages and reading posting details. Keep the page open until the run finishes.
4. Review the results list. Open a posting link to check the source listing when one is available.

The **Maximum age (weeks)** field on Posts filters which saved results are displayed. It overrides the profile's age limit for this view; it does not delete older postings or change the collection process.

This release currently assigns a fixed match score to each posting/track pairing. The score is not a ranking signal for choosing which results to promote; matching keywords in the track profile determine what the search retrieves.

## Read the results

Results include the title, company, salary when available, posted date, age, and closing date. A **manual** tag identifies postings you entered yourself. An **already a lead** tag means the posting is already represented in your lead pipeline. Search-discovered postings are added to `TOAPPLY` automatically, so no separate promote action is needed.

If no results appear, check that the selected track is active and has saved keywords, then clear or widen the maximum-age filter. Confirm that the MCF connection is valid and check the run status on [Automation](runs.md). A failed search may still have saved postings that were found before the failure.

## Add a posting manually

Select **Add posting manually** and choose a track. Enter the title, company, and posted date; URL and salary are optional. Select **Save posting**. If the form reports a missing or invalid field, correct it and save again. If a duplicate is reported, review the existing result rather than entering the same posting again.

## Recover from a search problem

If the progress panel reports failure or partial completion, open [Automation](runs.md), expand the search run, and read its error detail. Check the MCF connection and track configuration before retrying. If a run failed after discovering some postings, check the results before starting another run because those saved postings remain available.
