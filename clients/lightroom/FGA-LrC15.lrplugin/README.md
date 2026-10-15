# FGA-LrC15 Lightroom plug-in 0.2.0, build 1

This `.lrplugin` directory is the production release bundle for Lightroom
Classic 15. It stores one installation
Plugin Code in Lightroom Classic's encrypted `LrPasswords` store and verifies
it through:

`GET https://flickrgroupaddr.com/api/v001/installations/current`

The group browser uses authenticated `GET /api/v001/groups` reads and shows only
complete snapshots, including explicit stale and unavailable states. Open it
through **Library > Plug-in Extras > FlickrGroupAddr: Browse writable groups...**.
Reload follows the server's freshness/admission policy; closing the dialog
cancels follow-up work. An in-flight native HTTP request may take up to its
30-second timeout to return, and its result is discarded after closure.

This candidate targets **Lightroom Classic 15.6**, Camera Raw 18.7, build
`202609251514-f839cde9`, using **Adobe SDK 15.3 (April 2026)**. Terry confirmed
both the installed host and newest available SDK on 2026-10-15. Fixture tests
and Adobe compilation pass; actual 15.6 host acceptance is pending. Prior
15.5.1 connection evidence remains historical.

Publishing, uploading, and group submissions remain unavailable. The
existing-public-photo modules are installed as disabled development work and
have no registered menu action pending provider/thumbnail qualification.
A later Lightroom major may
load it through backward compatibility, but that does not make the combination
supported; each Lightroom major requires its own qualified FGA client build.
That qualification includes a fresh SDK capability review so later facilities,
such as a documented cryptographic random-number generator, are evaluated
explicitly instead of being assumed present or absent.

## Install and connect

1. In Lightroom Classic, open **File > Plug-in Manager**.
2. Choose **Add**, select this `FGA-LrC15.lrplugin` directory, and confirm
   that Lightroom reports the plug-in as installed and running.
3. In the FGA-LrC15 section, use the displayed FGA URL in a private
   browser window and complete the on-screen transfer checklist.
4. Paste the one-time Plugin Code into Lightroom. Compare the complete
   clear-text value in both windows, then choose **Store and verify**.
5. After Lightroom shows **Connected**, erase the browser transfer view,
   overwrite the clipboard as instructed there, and close the private window.

If a transport or server failure interrupts the safe read, leave the code in
`LrPasswords` and use **Verify stored credential** later. If FGA rejects the
code as invalid, the plug-in clears its local current-code slot; revoke that
installation in the browser and create a new one.

The plug-in writes a bounded local diagnostic log through Lightroom's
`LrLogger` at `%LOCALAPPDATA%\Adobe\Lightroom\Logs\LrClassicLogs\FGA-LrC15.log`
on Windows. Entries contain only fixed connection-state names and allowlisted
SDK network error codes or numeric HTTP statuses, plus fixed discovery-state
codes. They never contain group names, a Plugin
Code, request/response body, header, installation ID, or account identity.

Rotation is intentionally fail-closed in this slice. A nonempty rotation
candidate blocks fallback to the prior current code and requires completion or
cancellation through the accepted browser workflow.
