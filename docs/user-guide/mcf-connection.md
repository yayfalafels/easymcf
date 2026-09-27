# Connect MCF

## Contents

- [Connect and approve](#connect-and-approve)
- [Reconnect after expiry](#reconnect-after-expiry)

Easy MCF creates an MCF browser session for your signed-in account. You approve the Singpass request on your own phone, and Easy MCF saves the resulting session locally for search and apply runs. The MCF icon in the navigation bar shows connection state: green means connected, amber means an attempt is active, and red means the session is missing or expired.

## Connect and approve

1. Sign in to Easy MCF and select the MCF icon in the navigation bar.
2. In the **MCF connection** pop-up, select **Connect MCF** and wait for the QR code to appear.
3. Scan the QR code with the Singpass app on your phone. If **Open Singpass** is offered and you are on a suitable device, you can use that link instead.
4. If the pop-up asks you to confirm an MCF account, check the displayed email carefully. Confirm only if it is the MCF account you intend to connect.
5. Wait for Easy MCF to show **Connected as** followed by the confirmed MCF email. The connection pop-up closes after a successful connection.

## Reconnect after expiry

If the icon is red or an apply run reports that the MCF session expired, open the icon and select **Connect MCF** to start a fresh approval. A QR code can expire before it is scanned; start a new attempt and scan the newly displayed code.

If Singpass authentication fails, choose **Retry** or cancel and start again. If the confirmed account is not the one you expected, reject the confirmation. If Easy MCF reports that this MCF account is already connected under a different Easy MCF account, dismiss the message and resolve which Easy MCF account owns the connection before trying again. Do not confirm an account you do not recognize.

When connected, the pop-up offers **Open** to open MCF and **Disconnect** to remove the saved Easy MCF session. Disconnect only when you intend to remove that connection; searches or apply runs that need MCF will require a new approval afterward.
