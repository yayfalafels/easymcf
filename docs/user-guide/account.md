# Sign in and your account

## Contents

- [Sign in](#sign-in)
- [Account menu](#account-menu)

The app supports email/password sign-in and Google sign-in. After you sign in, the user menu shows the account details, profile photo, and sign-out action.

## Sign in

To create an account, open **Create account**, enter your name and email, and choose a password. The checklist updates as you type. The password must be at least 12 characters and include a lowercase letter, an uppercase letter, a digit, and a symbol. It must not contain your name or the part of your email before `@`. Submit after every rule is met.

If the email is already registered, return to **Sign in** and use that account. If the form shows a field error, correct the named field and submit again. The server applies the same password rules as the checklist, so its inline message is authoritative.

To sign in, enter the email and password for the account and select **Sign in**. If you opened a protected page first, successful sign-in returns you to that page. After repeated failed attempts, sign-in may be temporarily rate-limited. Wait before trying again and check that the email and password belong to the same account.

**Continue with Google** appears only when Google sign-in has been configured for this Easy MCF instance. Select it and complete Google's consent flow. If sign-in is cancelled, the Google account cannot be verified, or Google is temporarily unavailable, return to the sign-in page and retry later or use email and password. If the Google button is absent, use email and password or ask the person who configured this instance whether Google sign-in is enabled.

## Account menu

Select your avatar or initials to open the account menu. It shows the name and email associated with the signed-in account.

To add a profile photo, choose **Upload photo** and select a PNG, JPEG, or WebP image no larger than 2 MB. If the image is rejected, use one of those formats and reduce the file size. Choose **Remove photo** to return to your initials. The photo is stored with your account and remains available after you sign in again.

Choose **Log out** to end your Easy MCF session. If a protected page sends you back to sign in, sign in again; the app will return you to the page you originally requested.
