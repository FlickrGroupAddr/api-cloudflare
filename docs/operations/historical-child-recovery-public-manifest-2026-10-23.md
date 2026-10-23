# Historical recovery: original public source manifest

Date: 2026-10-23

Implementation clarification under the unchanged
[accepted recovery contract](historical-child-recovery-contract-2026-10-23.md).
This note grants no inspection, credential access, recovery dispatch or POST run.

The historical `sourceManifest` role is the original public source descriptor
at the retained source root's literal
`probes/group-post-characterization/screenshot-successor-manifest.json` path.
The producer does not create a second private copy outside that root. The
controller admits only this exact path and pin; its inventory must report
`private=False`. The bounded stable source reader still checks regular-file,
single-link, reparse, identity, bytes, fixed schema and complete source map.
An optional source pin for this same file must have the same canonical path and
digest; this narrowly deduplicates its two evidence meanings, not general aliases.

Every actual private history/current/credential/journal/output role retains the
outside-source-root restriction and existing ACL, path, identity, link, sidecar
and isolation checks. Supporting original provenance also remains private and
separate. No private role may use the public descriptor exception.

The trusted operator caller must supply `ReviewedFacts.original_manifest` as an
explicit `OriginalManifestBinding`: original source root, commit, manifest
digest, full manifest map and separately retained provenance reference. The
caller authenticates that historical meaning; construction or matching hashes
alone do not. Missing/default `None` refuses before source loading. Original
commit/map evidence is distinct from current checkout source pins and does not
assert that the current checkout HEAD equals the original commit.

The original producer semantics, timestamps, issuer retirement latch, current
witness/judgment, finite recovery window and all action gates stay unchanged.
This compatibility correction revives no spent attempt and resolves no unknown
outcome. Synthetic tests establish source behavior only; current custody,
targets and any later exact action packet still need their own genuine evidence.
