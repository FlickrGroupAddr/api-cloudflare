import { MAX_GROUP_IDS } from "./admission.ts";
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
const ID_SCHEMA={type:"string",minLength:1,maxLength:128,pattern:"^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$"} as const;
const REV_SCHEMA={type:"integer",minimum:1,maximum:Number.MAX_SAFE_INTEGER} as const;
const TIMESTAMP_SCHEMA={type:"string",pattern:"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{6}Z$"} as const;
const INTENT_STATES=["queued","attempting","retrying","throttled","added","moderation_submitted","delivery_uncertain","needs_attention","cancelled"] as const;
export const BATCH_REQUEST_SCHEMA={type:"object",additionalProperties:false,required:["schemaVersion","photoBinding","flickrGroupIds"],properties:{schemaVersion:{const:2},photoBinding:{type:"object",additionalProperties:false,required:["fgaPhotoBindingId","expectedVerificationRevision"],properties:{fgaPhotoBindingId:ID_SCHEMA,expectedVerificationRevision:REV_SCHEMA}},flickrGroupIds:{type:"array",minItems:1,maxItems:MAX_GROUP_IDS,uniqueItems:true,items:ID_SCHEMA}}} as const;
export const BATCH_RESPONSE_SCHEMA={type:"object",additionalProperties:false,required:["schemaVersion","fgaPhotoBindingId","flickrPhotoId","submissions"],properties:{schemaVersion:{const:2},fgaPhotoBindingId:ID_SCHEMA,flickrPhotoId:ID_SCHEMA,submissions:{type:"array",minItems:1,maxItems:MAX_GROUP_IDS,items:{type:"object",additionalProperties:false,required:["fgaSubmissionIntentId","flickrGroupId","state","created","permanentSubmissionBlock"],properties:{fgaSubmissionIntentId:ID_SCHEMA,flickrGroupId:ID_SCHEMA,state:{enum:INTENT_STATES},created:{type:"boolean"},permanentSubmissionBlock:{oneOf:[{type:"null"},{type:"object",additionalProperties:false,required:["reasonCode","createdAt"],properties:{reasonCode:{type:"string",minLength:1},createdAt:TIMESTAMP_SCHEMA}}]}}}}}} as const;
export const BINDING_REQUEST_SCHEMA={type:"object",additionalProperties:false,required:["schemaVersion","flickrPhotoId","expectedLinkedFlickrRevision"],properties:{schemaVersion:{const:1},flickrPhotoId:ID_SCHEMA,expectedLinkedFlickrRevision:REV_SCHEMA}} as const;
export const BINDING_RESPONSE_SCHEMA={type:"object",additionalProperties:false,required:["schemaVersion","fgaPhotoBindingId","sourceKind","flickrPhotoId","linkedFlickrRevision","verificationRevision","verifiedAt"],properties:{schemaVersion:{const:1},fgaPhotoBindingId:ID_SCHEMA,sourceKind:{enum:["fga_direct_upload","existing_public_flickr_photo","photographer_reconciled_ambiguous_upload"]},flickrPhotoId:ID_SCHEMA,linkedFlickrRevision:REV_SCHEMA,verificationRevision:REV_SCHEMA,verifiedAt:TIMESTAMP_SCHEMA}} as const;
export const ROUTES = [
 {id:"installation_current",method:"GET",pathPattern:"/api/v001/installations/current",owner:"fga_api_backend",routingClass:"worker_first",probe:"missing_authentication",expectedStatus:401,expectedChallenge:'Bearer realm="fga-api"',handler:"current",auth:"installation_bearer",allowPending:true,response:CURRENT_SCHEMA,successStatuses:[200],request:null},
 {id:"existing_public_binding",method:"POST",pathPattern:"/api/v001/existing-public-photo-bindings",owner:"fga_api_backend",routingClass:"worker_first",probe:"missing_authentication",expectedStatus:401,expectedChallenge:'Bearer realm="fga-api"',handler:"binding",auth:"installation_bearer",allowPending:false,response:BINDING_RESPONSE_SCHEMA,successStatuses:[201,200],request:BINDING_REQUEST_SCHEMA},
 {id:"group_submission_batch",method:"POST",pathPattern:"/api/v001/group-submission-batches",owner:"fga_api_backend",routingClass:"worker_first",probe:"missing_authentication",expectedStatus:401,expectedChallenge:'Bearer realm="fga-api"',handler:"batch",auth:"installation_bearer",allowPending:false,response:BATCH_RESPONSE_SCHEMA,successStatuses:[202],request:BATCH_REQUEST_SCHEMA},
] as const;
export const GUARDS = ["/api", "/api/", "/healthz/"] as const;
