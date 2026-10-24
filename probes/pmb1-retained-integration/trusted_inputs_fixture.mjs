// MIT License; copyright 2026 Terry Ott. Invented source/synthetic records only.
import { nativeFixture } from '../pmb1-native-disposition/native-fixture.mjs';
import { coverage, BINDING, BOUNDS, JOURNAL, DOMAIN } from '../pmb1-native-disposition/fixture.mjs';
import { assembleTrustedInputs } from './trusted_inputs.ts';

export function setupTrustedFixture(retiredExecutions = []) {
  const native = nativeFixture();
  const records = coverage(retiredExecutions).records();
  const expected = structuredClone(records.expected), authenticated = structuredClone(records.observed);
  const writer = { id: 'application', version: 'current-partition',
    sourceSha2_256: native.input.request.expectedSources['native-owner.ts'], authority: 'partition-generation-fenced' };
  expected.writers.push(writer);
  authenticated.writers.push({ ...writer, admissionRecord: 'synthetic/application-admission', mutationFenceRecord: 'synthetic/application-fence' });
  for (const custody of authenticated.custody) {
    custody.fromMs = Number(native.input.request.closure.start);
    custody.throughMs = Number(native.input.request.closure.end);
  }
  const config = { binding: { ...BINDING }, journalDatabaseId: JOURNAL, domainDatabaseId: DOMAIN, bounds: { ...BOUNDS } };
  return { native, expected, authenticated, config,
    assemble: () => assembleTrustedInputs(expected, authenticated, native.input), close: () => native.close() };
}
