# Lead pipeline

## Contents

- [Manage leads](#manage-leads)
- [Add a lead manually](#add-a-lead-manually)
- [Update a lead](#update-a-lead)
- [Move leads through the pipeline](#move-leads-through-the-pipeline)
- [Offers and expiry](#offers-and-expiry)
- [Find a missing lead](#find-a-missing-lead)

The Leads page tracks open opportunities from `TOAPPLY` through `OFFER`, plus closed leads. Search results are added to `TOAPPLY` automatically. Use the tabs to find a stage, and open a row to update its details, notes, and contact history.

## Manage leads

1. Open **Leads** and choose a stage tab: `TOAPPLY`, `Applied`, `Callbacks`, `Interviews`, `Offers`, or `Closed`.
2. Narrow the list with the track selector or the title/company search field.
3. Select a lead row to open its detail panel. Use the posting link when available to compare the record with the original listing.
4. Add a note for context or record a contact date with **Log contact**. Review the activity history to see stage changes, notes, and application attempts.

## Add a lead manually

Select **Add lead**, enter the role title, company, and track, then optionally add the posting URL, salary, and posted date. Select **Create lead**. A manually added lead starts at `APPLIED`, since the form is for tracking an application already made outside the search workflow.

If the form reports a missing or invalid field, correct it and submit again. If it reports a duplicate, find the existing lead with the track filter or title/company search instead of adding it again.

## Update a lead

In the detail panel, edit fields such as title, company, posting URL, deadline, expected salary, dates, or track, then choose **Save changes**. Use **Add note** to save context separately from structured fields. If the app shows a field error, correct the named value and save again.

Use the stage action to advance a lead through the pipeline. At `INTERVIEW`, advancing opens the offer form instead of moving the lead without offer details. A lead at `OFFER` is resolved through its offer status.

## Move leads through the pipeline

On the `TOAPPLY` tab, select one or more rows and choose **Apply** to move them to `APPLIED`, or **Drop** to close them with the reason `dropped`. The Leads page's **Apply** action only changes pipeline stage. It does not submit an application to MCF. Use the [Applications page](apply.md) to run browser-based apply automation.

From a lead's detail panel, choose **Close lead**, select the appropriate close reason, and confirm. Closed leads appear under the **Closed** tab. The standard close control is not shown for an `OFFER` lead; resolve its offer from the Offers page instead.

## Offers and expiry

When an interview produces an offer, advance the lead to open the offer form. Enter the offer date, amount, and deadline, then save. The lead moves to `OFFER`, and the offer appears on the Offers page. Update an open offer there, then choose **Accept**, **Reject**, or **Withdrawn** when it is resolved. Confirm the choice carefully: a final offer status closes the lead.

Open leads past their deadline are closed automatically as expired. Deadlines are maintained from posting dates and recent activity, and the offer deadline controls an open `OFFER` lead. Keep contact and interview activity current, and check the **Closed** tab if a lead disappears from the open stages. An offer deadline should be changed on the offer itself.

## Find a missing lead

Check the stage tabs, selected track filter, and search text first. A lead can leave its prior tab after a stage change, be closed after its deadline, or no longer match the active filters. Search results create leads automatically; manually changing a posting's `TOAPPLY` stage is not required.
