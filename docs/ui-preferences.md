# UI preferences

## Typography and stable initial rendering

Recorded: 2026-09-14, from Terry's explicit background guidance.

Prefer Inter and avoid the visible redraw or layout flicker caused by showing a
fallback typeface and then replacing it. Terry liked the result in the
[ItineraryWatch watches page](https://github.com/SixbucksSolutions/itinerarywatch-website-static/blob/main/src/watches/index.html),
but clarified that the method was another model's suggestion and is not a
required FGA implementation.

The referenced HTML was inspected through GitHub on 2026-09-14. It requests
Inter weights 400 and 700 from Google Fonts using `display=block`, with
preconnect hints for the Google font origins. These are separate mechanisms:
preconnect prepares an origin connection; font-display controls text rendering
while a font is unavailable. The font-display block interval is temporary, not
an explicit whole-page loading barrier or an indefinite promise against swaps.

For subsequent UI implementation, evaluate loading Inter from the application's
own assets and preloading the needed font resource. This is a candidate
implementation, not a completed change or a new owner mandate. Validate the
actual rendering experience on an uncached load and choose sensible behavior if
the font is slow or unavailable. Preserve the accepted CSP and credential-transfer
privacy requirements. No typography deployment was made while recording this note.

References: [preconnect](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel/preconnect)
and [font-display](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@font-face/font-display).

## Lightroom group-selection interaction

Terry approved the dual-list interaction on 2026-10-15 after using native
preview 0.0.1.5: available groups on the left, all selected additions on
the right, live filtering above the left list, and explicit Add/Remove
buttons between the lists. He found live filtering and the buttons
intuitive and responsive. Use equal-width buttons centered vertically
against the list boxes. Keep text useful to the photographer; unnecessary
technical scope/debug narration and empty state panels should not crowd
the selection controls. Preserve recognizable photo/Album context and
necessary membership/protection guidance. See the dual-list design and
actual-host evidence for acceptance scope and remaining checks.

## Empty selected list means no additions

Terry approved this refinement on 2026-10-15: remove the group-mode
radio buttons. The selected list alone owns choice. An empty list
is a valid unpublished Save, including clearing prior choices;
bound/existing-public Queue still requires 1-60 groups. Publishing
without groups must not require opening group selection. This
supersedes older radio-specific UI wording, not metadata, outbox,
proof, protection, idempotency or production activation requirements.

## Group-name visibility and dialog width

Terry directed on 2026-10-15 that group display names precede the Flickr
group NSID in list rows; the NSID goes at the end. Group names carry the
recognition value, while exact IDs continue to own internal identity.
Use the dialog's available horizontal space for the two lists: left
edge, available list, compact move-button column, selected list, right
edge, with normal native margins. Both lists should grow with the dialog
instead of retaining fixed widths and a large unused right margin.
Preserve readable full name/NSID details when a long row clips. A whole
list tooltip is not a documented per-row hover capability.

## Make active group filters conspicuous

On 2026-10-15, Terry reported the risk of looking for a known group while
an unrelated filter remained active. Any query characters, including
literal spaces, must produce an obvious persistent FILTERED cue near
the field. Show the current query, matching available count and eligible
total, and provide a nearby one-click Clear filter. The right selected
set remains unfiltered. Empty results must explain that the filter has
no matches rather than implying group membership or discovery is empty.

The chosen native treatment uses explicit bold text and clear recovery,
without relying on color or changing native list colors. This is a
design recommendation informed by [visibility of system status](https://www.nngroup.com/articles/visibility-system-status/) and the
[W3C explanation of conveying information beyond color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html), checked
2026-10-15. These principles inform this native design; no full
accessibility-conformance or screen-reader result is claimed.

## Align the lists and colocate their counts

Terry directed on 2026-10-15 that the match line use concise wording such
as FILTERED: 62 matches / 376 total when a filter is active, and
62 matches / 376 total without a filter. Keep the active-filter cue
separately visible in the search heading; the match numerator still means available matches
and total still means eligible choices including selected additions.
The match count stays above the left list. The selected/maximum count
belongs directly below the right list. Both native list tops and
bottoms must align; a simulated shared-height assertion is insufficient.
