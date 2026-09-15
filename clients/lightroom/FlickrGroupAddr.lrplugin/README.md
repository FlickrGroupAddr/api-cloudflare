# FlickrGroupAddr Lightroom plug-in 0.1.0

This `.lrplugin` directory is the production-named release bundle for FGA's
first read-only client slice. It stores one installation Plugin Code in
Lightroom Classic's encrypted `LrPasswords` store and verifies it through:

`GET https://flickrgroupaddr.com/api/v001/installations/current`

This release cannot publish, upload, submit a photo to a group, or call Flickr.

## Install and connect

1. In Lightroom Classic, open **File > Plug-in Manager**.
2. Choose **Add**, select this `FlickrGroupAddr.lrplugin` directory, and confirm
   that Lightroom reports the plug-in as installed and running.
3. In the FlickrGroupAddr section, use the displayed FGA URL in a private
   browser window and complete the on-screen transfer checklist.
4. Paste the one-time Plugin Code into Lightroom. Compare the complete
   clear-text value in both windows, then choose **Store and verify**.
5. After Lightroom shows **Connected**, erase the browser transfer view,
   overwrite the clipboard as instructed there, and close the private window.

If a transport or server failure interrupts the safe read, leave the code in
`LrPasswords` and use **Verify stored credential** later. If FGA rejects the
code as invalid, the plug-in clears its local current-code slot; revoke that
installation in the browser and create a new one.

Rotation is intentionally fail-closed in this slice. A nonempty rotation
candidate blocks fallback to the prior current code and requires completion or
cancellation through the accepted browser workflow.
