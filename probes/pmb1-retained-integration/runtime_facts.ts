// MIT License; copyright 2026 Terry Ott.
import { qualifiedRuntimeAuthority } from '../pmb1-fresh-native-capture/authority.ts';
import { validateRuntimePayload } from '../pmb1-fresh-native-capture/payload.ts';
import { AssembledFreshInputs } from '../pmb1-fresh-native-capture/trusted.ts';
import type { NativeAuthorityEnvironment } from '../pmb1-fresh-native-capture/authority.ts';
import type { QualifiedRuntimeAuthority } from '../pmb1-fresh-native-capture/authority.ts';

/** Protected publication supplies fresh finite facts to identical retained code.
 * Bootstrap provenance/executing identity must be independently qualified SOURCE;
 * the protected row cannot vouch for its own publisher, holders or execution.
 */
export async function consumeRuntimeFacts(authority: QualifiedRuntimeAuthority) {
  const envelope = await authority.ledger.reserveSelected(authority.operation);
  const payload = await validateRuntimePayload(envelope);
  const trusted = await AssembledFreshInputs.assemble(payload.coverage.expected,
    payload.coverage.authenticated, payload.native, envelope);
  return Object.freeze({ ...payload, trusted, ledger: authority.ledger, envelope });
}
export async function runtimeFacts(env: NativeAuthorityEnvironment) {
  const authority = qualifiedRuntimeAuthority(env);
  return authority ? consumeRuntimeFacts(authority) : undefined;
}
