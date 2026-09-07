// Isolated synthetic proof client. The hosted controller must supply a
// signed transport; there is deliberately no global fetch fallback.
export interface Scope {
  account: string;
  region: string;
  runId: string;
}

export interface Generation {
  name: string;
  version: string;
}

export interface Reference extends Generation {
  arn: string;
}

export type Transport = (request: Request) => Promise<Response>;
export type Failure = "invalid_input" | "transport" | "provider" | "protocol";

export class ProbeError extends Error {
  readonly category: Failure;
  constructor(category: Failure) {
    super(`secret_probe_${category}`);
    this.category = category;
  }
}

// Deliberately narrower than AWS's general input grammar. Only generated proof
// resources in the commercial partition are permitted, never production names.
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const NOT_FOUND = "ResourceNotFoundException";

function requireValue(condition: unknown, category: Failure = "invalid_input"): asserts condition {
  if (!condition) throw new ProbeError(category);
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export class SyntheticSecretsClient {
  readonly scope: Readonly<Scope>;
  readonly endpoint: string;
  readonly prefix: string;
  readonly #transport: Transport;

  constructor(scope: Scope, transport: Transport) {
    requireValue(/^\d{12}$/.test(scope.account));
    requireValue(/^(?:us|eu|ap|sa|ca|me|af|il|mx)-(?:[a-z]+)-\d$/.test(scope.region));
    requireValue(/^[0-9a-f]{24}$/.test(scope.runId));
    this.scope = Object.freeze({ ...scope });
    this.endpoint = `https://secretsmanager.${scope.region}.amazonaws.com/`;
    this.prefix = `fga-proof/${scope.runId}/`;
    this.#transport = transport;
  }

  generation(): Generation {
    const version = crypto.randomUUID();
    return { name: this.prefix + version, version };
  }

  #generation(value: Generation): void {
    requireValue(typeof value?.version === "string" && UUID.test(value.version));
    requireValue(value.name === this.prefix + value.version);
  }

  #reference(value: Reference): void {
    this.#generation(value);
    const base = `arn:aws:secretsmanager:${this.scope.region}:${this.scope.account}:secret:${value.name}-`;
    requireValue(typeof value.arn === "string" && value.arn.startsWith(base));
    requireValue(/^[a-zA-Z0-9]{6}$/.test(value.arn.slice(base.length)));
  }

  #payload(value: Generation): string {
    // The caller cannot provide real OAuth material to this proof client.
    return JSON.stringify({ fixture: "fga-synthetic-only", generation: value.version });
  }

  async #call(
    action: string, body: Record<string, unknown>, allowMissing = false,
  ): Promise<Record<string, unknown> | null> {
    const request = new Request(this.endpoint, {
      method: "POST",
      redirect: "manual",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": `secretsmanager.${action}`,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(10_000),
    });
    let response: Response;
    let parsed: unknown;
    try {
      response = await this.#transport(request);
      requireValue(!response.redirected, "protocol");
      // Secret payloads in this proof are tiny. Reject oversized or streaming
      // replies before retaining an unbounded provider error body.
      const reader = response.body?.getReader();
      requireValue(reader, "protocol");
      const parts: Uint8Array[] = [];
      let length = 0;
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        length += chunk.value.byteLength;
        if (length > 16_384) {
          await reader.cancel();
          throw new ProbeError("protocol");
        }
        parts.push(chunk.value);
      }
      const bytes = new Uint8Array(length);
      let offset = 0;
      for (const part of parts) {
        bytes.set(part, offset);
        offset += part.length;
      }
      parsed = JSON.parse(new TextDecoder("utf-8", { fatal: true, ignoreBOM: false }).decode(bytes));
    } catch (error) {
      // Do not propagate provider/transport exceptions, request headers, secret
      // payloads or causes into test evidence or future Worker responses.
      if (error instanceof ProbeError) throw error;
      throw new ProbeError("transport");
    }
    requireValue(record(parsed), "protocol");
    if (response.status !== 200) {
      if (allowMissing && response.status === 400 && parsed.__type === NOT_FOUND) return null;
      throw new ProbeError("provider");
    }
    return parsed;
  }

  async create(generation: Generation): Promise<Reference> {
    this.#generation(generation);
    const result = await this.#call("CreateSecret", {
      Name: generation.name,
      ClientRequestToken: generation.version,
      SecretString: this.#payload(generation),
    });
    requireValue(result && result.Name === generation.name && result.VersionId === generation.version,
      "protocol");
    const reference = { ...generation, arn: result.ARN as string };
    try { this.#reference(reference); } catch { throw new ProbeError("protocol"); }
    return reference;
  }

  async read(reference: Reference): Promise<void> {
    this.#reference(reference);
    const result = await this.#call("GetSecretValue", {
      SecretId: reference.arn, VersionId: reference.version,
    });
    requireValue(result && result.ARN === reference.arn && result.Name === reference.name &&
      result.VersionId === reference.version && result.SecretString === this.#payload(reference) &&
      result.SecretBinary === undefined, "protocol");
    // Assert the fixture in operation-local memory; return no payload to callers.
  }

  async recover(generation: Generation): Promise<Reference | null> {
    // A lost create response is uncertain. The controller must retain this
    // generation before create and retry bounded reconciliation, not assume that
    // one eventually-consistent not-found observation means nothing was created.
    this.#generation(generation);
    const result = await this.#call("DescribeSecret", { SecretId: generation.name }, true);
    if (result === null) return null;
    requireValue(result.Name === generation.name && record(result.VersionIdsToStages) &&
      Object.hasOwn(result.VersionIdsToStages, generation.version), "protocol");
    const reference = { ...generation, arn: result.ARN as string };
    try { this.#reference(reference); } catch { throw new ProbeError("protocol"); }
    await this.read(reference);
    return reference;
  }

  async requestDeletion(reference: Reference): Promise<void> {
    this.#reference(reference);
    // Low-level proof operation, not an authorization decision. A future
    // controller must confirm this generation is durably inactive first.
    const result = await this.#call("DeleteSecret", {
      SecretId: reference.arn, ForceDeleteWithoutRecovery: true,
    });
    requireValue(result && result.ARN === reference.arn && result.Name === reference.name,
      "protocol");
    // An acknowledgement never claims that asynchronous deletion has completed.
  }

  async observeAbsence(reference: Reference): Promise<boolean> {
    this.#reference(reference);
    const description = await this.#call("DescribeSecret", { SecretId: reference.arn }, true);
    if (description !== null) return false;
    const value = await this.#call("GetSecretValue", {
      SecretId: reference.arn, VersionId: reference.version,
    }, true);
    return value === null;
  }
}
