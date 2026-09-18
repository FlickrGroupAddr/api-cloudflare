const ID = { type: 'string', minLength: 1, maxLength: 128, pattern: '^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$' } as const;
const properties = {
  schemaVersion: { const: 1 }, snapshotRevision: { type: 'integer', minimum: 1, maximum: Number.MAX_SAFE_INTEGER },
  refreshedAt: { type: 'string', format: 'date-time' },
  snapshotStatus: { enum: ['fresh','stale_refreshing','stale_refresh_failed'] },
  refreshFailedAt: { type: 'string', format: 'date-time' },
  groups: { type: 'array', maxItems: 100, items: { type: 'object', additionalProperties: false,
    required: ['flickrGroupId','displayName'], properties: { flickrGroupId: ID,
      displayName: { type: 'string', minLength: 1, maxLength: 1024 } } } },
  nextAfterGroupId: { oneOf: [ID, { type: 'null' }] },
} as const;
export const GROUP_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion','snapshotRevision','refreshedAt','snapshotStatus','groups','nextAfterGroupId'],
  properties, allOf: [{ if: { properties: { snapshotStatus: { const: 'stale_refresh_failed' } } },
    then: { required: ['refreshFailedAt'] }, else: { not: { required: ['refreshFailedAt'] } } }] } as const;
export const GROUP_PENDING_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion','status'], properties: { schemaVersion: { const: 1 }, status: { const: 'refreshing' } } } as const;
export const GROUP_ROUTES = [{ id: 'groups', method: 'GET', pathPattern: '/api/v001/groups',
  owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
  expectedChallenge: 'Bearer realm="fga-api"', handler: 'groups', auth: 'installation_bearer',
  allowPending: false, response: GROUP_SCHEMA, successStatuses: [200,202], request: null }] as const;
