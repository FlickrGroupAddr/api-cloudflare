# Native Flickr connection review

Synthetic design preview for #0016 and proposed ADRs 0048/0057. Start from the repo root with `uv run --frozen python scripts/serve_native_preview.py`; read `.coordination-runs/native-ui-preview-status.json` for the loopback URL. The server makes no account changes. Buttons demonstrate wording only. The browser handoff experiment uses local synthetic responses and never navigates to Flickr.

This is not an authenticated production administration app. See `docs/research/2026-09-12-native-intake-integration.md` for implemented work, validation and remaining gates.
