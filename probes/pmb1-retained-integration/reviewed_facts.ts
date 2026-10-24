// MIT License; copyright 2026 Terry Ott.
// No actual source/census/custody/retirement records have been supplied.
// A later private, independently authenticated source revision may construct the
// existing trusted inputs here. It is part of the exact retained build, never an
// environment/JSON/HTTP loader. This empty revision establishes no factual gate.
import type { AssembledTrustedInputs } from './trusted_inputs.ts';
import type { RetainedConfiguration } from './composition.ts';
export interface ReviewedFacts {
  configuration: RetainedConfiguration;
  trusted: AssembledTrustedInputs;
  partitionNamespace: string;
}
export async function reviewedFacts(): Promise<ReviewedFacts | undefined> { return undefined; }
