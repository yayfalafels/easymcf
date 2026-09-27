# Getting started

## Contents

- [Before you begin](#before-you-begin)
- [Main workflow](#main-workflow)
- [When something goes wrong](#when-something-goes-wrong)

Job seekers use live mode to read current MyCareersFuture postings and submit applications. Fixture mode is only for developers and validation. For a local installation, follow the developer guide to start the app, then use these steps to configure your account and MCF connection.

## Before you begin

1. Install and start Easy MCF as described in [Install](../developer-guide/index.md). Open the local app URL shown there.
2. Create an Easy MCF account or sign in with your existing email and password. Google sign-in is available when it has been configured for this instance.
3. Open **Tracks** and create a track for the roles you want to find. Set up its search profile and choose a default CV label.
4. Open **CVs** and make sure each label you plan to use matches a resume already stored in your MCF profile.
5. Select the MCF connection icon in the navigation bar, choose **Connect MCF**, scan the QR code with Singpass, and confirm the MCF account shown in Easy MCF.
6. Run a search from **Posts**, review the results, and track the created leads from **Leads**.
7. When you are ready to submit applications, review the queue and CVs on **Applications** before confirming a batch.

> WARNING:
> Live mode uses the real MyCareersFuture site. Confirming an apply batch can submit real applications. Review the posting count and MCF session before each live batch. Fixture mode is only for developers and validation.

## Main workflow

1. Configure a track and its search profile in [Tracks and search profiles](tracks.md).
2. Run searches and review discovered roles in [Run a search](search.md).
3. Search results are added to the open `TOAPPLY` stage automatically. Review them in the [Lead pipeline](leads.md); there is no separate promote action.
4. Track conversations, interviews, deadlines, and offers from lead details and the Offers page.
5. Submit applications from the [Apply queue](apply.md), then inspect outcomes in [Run history](runs.md).

## When something goes wrong

If sign-in fails, see [Sign in and your account](account.md). If the MCF connection is missing or expired, follow [Connect MCF](mcf-connection.md) before running a search or apply batch. For a failed or partial automation run, open **Automation**, expand the run, and read its error detail before trying again.
