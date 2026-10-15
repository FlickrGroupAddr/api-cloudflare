// Closed public projections of the accepted existing-photo and membership contracts.
const ID = { type: 'string', minLength: 1, maxLength: 128, pattern: '^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$' } as const;
const REVISION = { type: 'integer', minimum: 1, maximum: Number.MAX_SAFE_INTEGER } as const;
const COUNT = { type: 'integer', minimum: 0, maximum: Number.MAX_SAFE_INTEGER } as const;
const TITLE = { type: 'string', maxLength: 1024, pattern: '^[^\\u0000-\\u001f\\u007f]*$' } as const;
const TIME = { type: 'string', format: 'date-time' } as const;
const GROUP = { type: 'object', additionalProperties: false, required: ['flickrGroupId', 'displayName'],
  properties: { flickrGroupId: ID, displayName: TITLE } } as const;

export const EXISTING_PHOTOS_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'linkedFlickrRevision', 'observedAt', 'page', 'pageSize', 'pages', 'total', 'photos'],
  properties: {
    schemaVersion: { const: 1 }, linkedFlickrRevision: REVISION, observedAt: TIME,
    page: REVISION, pageSize: { type: 'integer', minimum: 1, maximum: 100 }, pages: COUNT, total: COUNT,
    photos: { type: 'array', maxItems: 100, items: { type: 'object', additionalProperties: false,
      required: ['flickrPhotoId', 'title', 'dateUploaded', 'dateTaken', 'thumbnail'], properties: {
        flickrPhotoId: ID, title: TITLE,
        dateUploaded: { type: 'string', minLength: 1, maxLength: 13, pattern: '^(0|[1-9][0-9]{0,12})$', description: 'Unix seconds; the complete upstream parser additionally requires a representable date.' },
        dateTaken: { type: 'string', pattern: '^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01]) ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$', description: 'Calendar-valid Flickr capture date; complete upstream parsing rejects impossible calendar dates.' },
        thumbnail: { type: 'object', additionalProperties: false, required: ['url', 'sizeClass'], properties: {
          url: { type: 'string', maxLength: 2048, format: 'uri', pattern: '^https://live\\.staticflickr\\.com/[0-9]+/[A-Za-z0-9_-]+_q\\.(jpg|jpeg|png)$' },
          sizeClass: { const: 'q' },
        } },
      } } },
  } } as const;

export const PHOTO_MEMBERSHIPS_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['schemaVersion', 'fgaPhotoBindingId', 'flickrPhotoId', 'observationRevision', 'observedAt', 'groups', 'nextAfterGroupId'],
  properties: { schemaVersion: { const: 1 }, fgaPhotoBindingId: ID, flickrPhotoId: ID,
    observationRevision: REVISION, observedAt: TIME, groups: { type: 'array', maxItems: 100, items: GROUP },
    nextAfterGroupId: { oneOf: [ID, { type: 'null' }] },
  } } as const;

export const PHOTO_ROUTES = [
  { id: 'existing_public_photos', method: 'GET', pathPattern: '/api/v001/existing-public-photos',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: 'Bearer realm="fga-api"', handler: 'existing_photos', auth: 'installation_bearer',
    allowPending: false, response: EXISTING_PHOTOS_SCHEMA, successStatuses: [200], request: null },
  { id: 'photo_binding_group_memberships', method: 'GET', pathPattern: '/api/v001/photo-bindings/{photoBindingId}/group-memberships',
    owner: 'fga_api_backend', routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
    expectedChallenge: 'Bearer realm="fga-api"', handler: 'photo_memberships', auth: 'installation_bearer',
    allowPending: false, response: PHOTO_MEMBERSHIPS_SCHEMA, successStatuses: [200], request: null },
] as const;

// The existing route registry has no query-parameter field. These are explicit projection
// inputs for the parent generator integration, not additional route-registry properties.
export const PHOTO_QUERY_PARAMETERS = {
  existing_photos: [
    { name: 'page', in: 'query', required: true, schema: REVISION },
    { name: 'page_size', in: 'query', required: true, schema: { type: 'integer', minimum: 1, maximum: 100 } },
  ],
  photo_memberships: [
    { name: 'page_size', in: 'query', required: true, schema: { type: 'integer', minimum: 1, maximum: 100 } },
    { name: 'observation_revision', in: 'query', required: false, schema: REVISION,
      description: 'Continuation only; required together with after_group_id.' },
    { name: 'after_group_id', in: 'query', required: false, schema: ID,
      description: 'Continuation only; required together with observation_revision.' },
  ],
} as const;

export const PHOTO_READ_RELEASE_METADATA = {
  enabledFlag: 'FGA_EXISTING_PHOTOS_ENABLED', defaultValue: '0', requiredReadFlag: 'FGA_READ_ENABLED',
  hostQualified: false,
} as const;
