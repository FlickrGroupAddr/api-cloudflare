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
