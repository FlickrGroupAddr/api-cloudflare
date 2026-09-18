# Workers compatibility date: 2026-09-18

Status: qualified and active in production on 2026-09-18.

The repository uses `wrangler.example.jsonc`, not `wrangler.toml`, as its
deployment template. Private `wrangler.json` files under ignored coordination
directories are generated for production and tests. The current production
version uses 2026-09-18.

Cloudflare [recommends the current date](https://developers.cloudflare.com/workers/configuration/compatibility-dates/)
for new Workers and review on updates. The current date is 2026-09-18. The
[compatibility flag history](https://developers.cloudflare.com/workers/configuration/compatibility-flags/)
shows no new default flag between 2026-09-11 and 2026-09-18 for this TypeScript
Worker. Node compatibility became default on 2026-08-04, before both dates.
The existing `nodejs_compat` declaration stays for compatibility with the
project's current, already tested configuration; Cloudflare documents that it
is redundant and ignored at these dates.

Production template, full hosted matrix and its native Secrets Store bridge,
exact-module supplement, release receipt fields, and the isolated
group-discovery hosted proof now use 2026-09-18. Historical proof configurations,
local Miniflare fixtures, and
prior evidence retain their original dates. The pinned local workerd/Miniflare
generation supports only 2026-07-30; its checks remain local adapter evidence,
not proof of the later hosted runtime.

Wrangler 4.116.0 accepts a 2026-09-18 template in a dry run. Native TypeScript,
affected Python unit checks, Ruff, and Pyright passed. Isolated hosted group
discovery passed at 2026-09-18 with cleanup confirmed. The
[full exact-artifact qualification](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/35381025422)
passed 56 conformance cases and 28 mutations with cleanup confirmed. The
[production activation record](../evidence/group-discovery-production-2026-09-18.json)
ties that receipt to the active Worker version and successful real Flickr
read-only refresh. The previously passed run 35345742207 qualified the
2026-09-11 candidate and is retained only as historical evidence.
