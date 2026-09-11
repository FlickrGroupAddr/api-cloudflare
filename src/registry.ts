export const PRESENTED_STATES = ["current", "pending_rotation"] as const;
export interface CurrentInstallation {
  schemaVersion: 1; installationId: string; installationRevision: number;
  installationState: "active"; presentedCredentialState: typeof PRESENTED_STATES[number];
}
export const CURRENT_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["schemaVersion", "installationId", "installationRevision", "installationState", "presentedCredentialState"],
  properties: { schemaVersion: { const: 1 }, installationId: { type: "string", minLength: 1 },
    installationRevision: { type: "integer", minimum: 1, maximum: Number.MAX_SAFE_INTEGER },
    installationState: { const: "active" }, presentedCredentialState: { enum: PRESENTED_STATES } },
} as const;
export const ERROR_SCHEMA = { type: "object", additionalProperties: false,
  required: ["schemaVersion", "error"], properties: { schemaVersion: { const: 1 }, error: {
    type: "object", additionalProperties: false, required: ["code", "message", "retryable", "correlationId"],
    properties: { code: { type: "string" }, message: { type: "string" }, retryable: { type: "boolean" },
      correlationId: { type: "string", format: "uuid" } },
  } } } as const;
export const ROUTES = [{ id: "installation_current", method: "GET", pathPattern: "/api/v001/installations/current",
  owner: "fga_api_backend", routingClass: "worker_first", probe: "missing_authentication",
  expectedStatus: 401, expectedChallenge: 'Bearer realm="fga-api"',
  handler: "current", auth: "installation_bearer", allowPending: true, response: CURRENT_SCHEMA }] as const;
export const GUARDS = ["/api", "/api/", "/healthz/"] as const;
