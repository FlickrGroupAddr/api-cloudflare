import type { AdmissionAuth } from './admission.ts';
import type { FlickrFetch } from './flickr_reads.ts';
import { uploadBindingRequest, UPLOAD_PHOTO_BINDING_REQUEST_SCHEMA, UPLOAD_PHOTO_BINDING_RESPONSE_SCHEMA,
  type UploadPhotoBindingEnv } from './upload_photo_binding.ts';

export type UploadAmbiguityResolutionEnv = UploadPhotoBindingEnv;
export const UPLOAD_AMBIGUITY_RESOLUTION_REQUEST_SCHEMA = UPLOAD_PHOTO_BINDING_REQUEST_SCHEMA;
export const UPLOAD_AMBIGUITY_RESOLUTION_RESPONSE_SCHEMA = UPLOAD_PHOTO_BINDING_RESPONSE_SCHEMA;
export const UPLOAD_AMBIGUITY_RESOLUTION_ROUTES = [{ id: 'uploadAmbiguityResolution', method: 'PUT',
  pathPattern: '/api/v001/upload-authorizations/{uploadAuthorizationId}/ambiguity-resolution', owner: 'fga_api_backend',
  routingClass: 'worker_first', probe: 'missing_authentication', expectedStatus: 401,
  expectedChallenge: 'Bearer realm="fga-api"', handler: 'upload_ambiguity_resolution', auth: 'installation_bearer', allowPending: false,
  response: UPLOAD_AMBIGUITY_RESOLUTION_RESPONSE_SCHEMA, successStatuses: [200, 201], request: UPLOAD_AMBIGUITY_RESOLUTION_REQUEST_SCHEMA }] as const;
export const UPLOAD_AMBIGUITY_RESOLUTION_RELEASE_METADATA = {
  enabledFlag: 'FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED', defaultValue: '0', hostQualified: false } as const;

/** Photographer-selected correlation plus current ownership proof; never a claim about uploaded bytes. */
export async function uploadAmbiguityResolutionRequest(env: UploadAmbiguityResolutionEnv, auth: AdmissionAuth,
  authorizationId: string, value: unknown, fetcher: FlickrFetch): Promise<Response> {
  return uploadBindingRequest(env, auth, authorizationId, value, fetcher, true);
}
