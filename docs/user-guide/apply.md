# Apply queue

## Contents

- [Before you start](#before-you-start)
- [Prepare the queue](#prepare-the-queue)
- [Connect your MCF session](#connect-your-mcf-session)
- [Run the batch](#run-the-batch)
- [Review the results](#review-the-results)
- [Troubleshoot a blocked or failed run](#troubleshoot-a-blocked-or-failed-run)

The Applications page applies to open leads in the `TOAPPLY` stage. Check every posting and its effective CV before starting a batch. In live use, confirming a batch submits real applications to MyCareersFuture.

## Before you start

1. Make sure the leads you intend to apply to are open and at `TOAPPLY`. The queue does not include closed leads or leads at other stages.
2. Check that each posting is still relevant and that its company, role, and track are correct.
3. Check the CV shown for each lead. The selected CV label must match a resume available in your MCF account.
4. Confirm that your MCF session is valid. If it is missing or expired, reconnect before running the batch.

## Prepare the queue

Each row shows the posting, track, effective CV, and last apply attempt. The effective CV is the lead's own CV override when set; otherwise it is the track's default CV.

To change a CV for one lead, select another CV in that row. The choice is saved to the lead and used on its next apply attempt. Choose the blank `Track default` option to remove the override and use the track's default again. Use **Manage CVs** to add or correct a CV label. The resume itself remains in your MCF account.

If a row says it is blocked because no MCF resume matched the CV, that lead will be skipped. Choose a CV whose label matches a resume available on MCF, or correct the CV label, then check that the blocked message clears. The apply button shows how many unblocked leads are runnable. If every queued lead is blocked, the button stays disabled.

Use **Drop** only when you no longer want to apply to a lead. Confirming the action closes the lead with the reason `dropped` and removes it from the apply queue.

## Connect your MCF session

The session status appears above the queue. If the page shows **Connect MCF**, select it and complete the connection and approval steps in [Connect MCF](mcf-connection.md). Return to the Applications page and make sure the session is valid before starting a batch. An apply run needs an already-authenticated session; Easy MCF does not sign in for you.

If the session expires during a run, the run-level error is shown with its details. Reconnect and review the queue and last-attempt values before starting another run.

## Run the batch

1. Review the runnable count on **Run apply batch**. It excludes blocked leads. If the count is unexpected, resolve the blocked rows or remove any leads you do not intend to apply to before continuing.
2. Select **Run apply batch**. Read the confirmation, which shows the number of postings and the session status. It warns that the action submits real applications.
3. Cancel if the count or session is unexpected. Confirm only when you are ready to submit applications to those postings.
4. Keep the page open while progress is shown. The page reports how many leads have been processed and summarizes outcomes as they arrive. Do not start another batch while a run is in progress.
5. When the run finishes, review every row in the results table. A failure for one lead does not stop the run from attempting the others.

If you navigate away or reload during a run, return to the Applications page. It checks for an active apply run and resumes showing its progress and results.

## Review the results

The results table lists each attempted posting, its outcome, any error detail, and a suggested next action. The last-attempt column in the queue also records the latest outcome for each lead.

01. **`applied`** The application was submitted. The lead moves to `APPLIED`; follow up from the Leads page.
02. **`questionnaire_required`** The application needs a multi-step questionnaire. Complete it manually on MCF, then mark the lead `APPLIED` from Lead Detail.
03. **`cv_not_found`** MCF did not show a resume matching the selected CV label. Choose a matching CV or correct the label, then retry.
04. **`cv_selector_error`** The resume picker could not be read. Try again later or apply directly on MCF. If it repeats, record the run number and error detail for support.
05. **`unable_to_apply`** The apply button did not become available. Check that the posting is still open, then retry later or apply directly on MCF.
06. **`post_unavailable`** The posting could not be loaded. The lead is closed as `apply_failed`; check the posting on MCF before deciding whether to reopen it.
07. **`post_closed`** MCF reported that the posting is closed. The lead is closed as `apply_failed`; do not retry unless the role is available again.
08. **`invalid_input`** A required lead field is missing. Correct the lead details and CV assignment, then run it again.

If MCF reports that you already applied, Easy MCF records that result as `applied` rather than as a separate failure.

## Troubleshoot a blocked or failed run

- **The run button is disabled because the session is missing.** Select **Connect MCF**, complete the approval flow, return to this page, and confirm the session is valid.
- **Every lead is blocked on a missing CV.** Correct the CV selection or label for each row. The batch can run once at least one queued lead has a matching CV.
- **The queue is empty.** Open the Leads page and move the intended open leads to `TOAPPLY`. Closed leads cannot be applied from this queue.
- **The page says a run is already in progress.** Wait for that run to finish. If you refreshed or navigated away, return to this page to resume its status instead of starting another batch.
- **The run ends with an error detail.** Note the run number and error text. Check the MCF connection, then review each lead's last attempt before retrying so you do not submit a duplicate application manually.
- **A single result failed.** Use that row's outcome and next action above. Other leads in the batch may still have completed successfully, so review all results before deciding what to retry.
