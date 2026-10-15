const requiredMetadata = ['is_public', 'is_friend', 'is_family', 'safety_level', 'content_type', 'hidden'] as const;
const properties = {
  title: { type: 'string' }, description: { type: 'string' }, tags: { type: 'string' },
  is_public: { type: 'string', enum: ['0', '1'] }, is_friend: { type: 'string', enum: ['0', '1'] },
  is_family: { type: 'string', enum: ['0', '1'] }, safety_level: { type: 'string', enum: ['1', '2', '3'] },
  content_type: { type: 'string', enum: ['1', '2', '3'] }, hidden: { type: 'string', enum: ['1', '2'] },
} as const;
const metadataRequest = { type: 'object', additionalProperties: false, required: requiredMetadata, properties } as const;
export const UPLOAD_AUTHORIZATION_REQUEST_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'flickrMetadata'], properties: { schemaVersion: { const: 1 }, flickrMetadata: metadataRequest } } as const;
export const UPLOAD_AUTHORIZATION_RESPONSE_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'fgaUploadAuthorizationId', 'issuedAt', 'uploadUrl', 'authorizationHeader', 'flickrMetadata'],
  properties: { schemaVersion: { const: 1 }, fgaUploadAuthorizationId: { type: 'string', minLength: 1, maxLength: 128,
    pattern: '^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$' }, issuedAt: { type: 'string', format: 'date-time' },
    uploadUrl: { type: 'string', const: 'https://up.flickr.com/services/upload/' },
    authorizationHeader: { type: 'string', minLength: 1, 'x-fga-sensitive': true },
    flickrMetadata: { type: 'object', additionalProperties: false, required: ['api_key', ...requiredMetadata],
      properties: { api_key: { type: 'string', minLength: 1 }, ...properties } },
  } } as const;
export const UPLOAD_AUTHORIZATION_ROUTES = [{ id: 'createUploadAuthorization', method: 'POST',
  pathPattern: '/api/v001/upload-authorizations', owner: 'fga_api_backend', routingClass: 'worker_first',
  probe: 'missing_authentication', expectedStatus: 401, expectedChallenge: 'Bearer realm="fga-api"',
  handler: 'upload_authorization', auth: 'installation_bearer', allowPending: false,
  response: UPLOAD_AUTHORIZATION_RESPONSE_SCHEMA, successStatuses: [200], request: UPLOAD_AUTHORIZATION_REQUEST_SCHEMA }] as const;
export const UPLOAD_AUTHORIZATION_RELEASE_METADATA = { enabledFlag: 'FGA_UPLOAD_AUTHORIZATION_ENABLED',
  defaultValue: '0', hostQualified: false, bodyLimitBytes: 16_384 } as const;
