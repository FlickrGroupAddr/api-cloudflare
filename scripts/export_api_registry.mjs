import { ALBUM_CREATE_REPAIR_ERROR_SCHEMA } from "../src/album_create_repair.ts";
import { ALBUM_TITLE_ERROR_SCHEMA } from "../src/album_title.ts";
import { SERVICE_ID } from "../src/publish_services.ts";
// Node imports the executable TypeScript registry; Python owns artifact writing/checking.
import { ROUTES, GUARDS, ERROR_SCHEMA } from "../src/registry.ts";
import { GROUP_PENDING_SCHEMA } from "../src/group_registry.ts";
import { PHOTO_QUERY_PARAMETERS } from "../src/photo_registry.ts";
const paths={};
for(const route of ROUTES){
 const method=route.method.toLowerCase();if(paths[route.pathPattern]?.[method])throw new Error("Duplicate route");
 const noStore={description:"Always no-store",schema:{type:"string",const:"no-store"}};
 const responses={};
 for(const status of route.successStatuses)responses[status]={description:["admin","plugin_code","status_admin"].includes(route.handler)?"Administrative operation result":route.handler==="current"?"Current installation":["binding","upload_photo_binding","upload_ambiguity_resolution"].includes(route.handler)?"Fresh verified photo binding":"Complete ordered admission snapshot",headers:{"Cache-Control":noStore},...(status===204?{}:{content:{"application/json":{schema:route.response}}})};
 for(const status of route.handler==="current"?[400,401,405,503]:[400,401,403,404,405,409,412,413,415,422,428,429,500,503])responses[status]={description:status===401&&route.auth!=="browser_session"?"Missing authentication has an empty body and bare Bearer challenge; invalid credentials return the error representation.":"Request rejected",headers:{"Cache-Control":noStore,...(route.auth!=="browser_session"&&[400,401,403].includes(status)?{"WWW-Authenticate":{description:"Present for authentication-envelope and insufficient-scope errors; not for application validation errors.",schema:{type:"string"}}}:{}),...(status===405?{Allow:{schema:{type:"string",const:[...new Set(ROUTES.filter(r=>r.pathPattern===route.pathPattern).map(r=>r.method))].sort().join(", ")}}}:{})},content:{"application/json":{schema:ERROR_SCHEMA}}};
 responses[400].description="Application errors use JSON/no-store. ADR 0054 permits the bounded early provider duplicate-Authorization rejection to use non-JSON HTTP 400 without application headers; it cannot redirect, set session cookies, expose application data or serve the shell.";
 responses[400].content["text/html"]={schema:{type:"string"}};
 const description=["admin","plugin_code","status_admin"].includes(route.handler)?"Authenticated private browser session. Unsafe operations require exact Origin and session CSRF; sensitive operations require recent Google authentication.":route.handler==="current"?"No query parameters or request body. Pending credentials authorize only this safe read.":route.handler==="binding"?"Current plug-in credential only. Verifies exact owner/public photo using the current native grant; commits a stable binding only under unchanged authority.":"Current plug-in credential only. One complete selection, one D1 transaction and at most one post-commit wake. No Flickr call occurs in this request. Expired proof is acceptable only when every pair already exists.";
 const parameters=[...route.pathPattern.matchAll(/\{([^}]+)\}/g)].map(match=>({name:match[1],in:"path",required:true,schema:{type:"string",minLength:1,maxLength:128,pattern:"^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$"}}));
 if(["status","status_admin"].includes(route.handler)&&!route.pathPattern.includes("{")){
  for(const [name,schema] of Object.entries({view:{type:"string",enum:["active","attention","history"],default:"active"},page_size:{type:"integer",minimum:1,maximum:100,default:50},photo_binding_id:{type:"string",minLength:1,maxLength:128},before_created_at:{type:"string",pattern:"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{6}Z$"},before_intent_id:{type:"string",minLength:1,maxLength:128}}))parameters.push({name,in:"query",required:false,schema});
 }
 if(route.handler==="plugin_code"){
  if(method==="get"&&!route.pathPattern.includes("{"))parameters.push({name:"page_size",in:"query",required:false,schema:{type:"integer",minimum:1,maximum:100,default:50}},{name:"page_token",in:"query",required:false,schema:{type:"string",maxLength:2048}});
  if(method!=="get"&&route.pathPattern.includes("{"))parameters.push({name:"If-Match",in:"header",required:true,schema:{type:"string"},description:"One strong current parent validator; no wildcard or weak tag."});
  if(responses[200]&&route.pathPattern.includes("{"))responses[200].headers.ETag={description:"Strong current parent validator",schema:{type:"string"}};
 }
 if(route.handler in PHOTO_QUERY_PARAMETERS){
  parameters.push(...PHOTO_QUERY_PARAMETERS[route.handler]);
  responses[200].description=route.handler==="existing_photos"?"One completely validated page of current-owner public Flickr photos.":"One completely validated photo-membership observation keyset page.";
 }
 if(route.handler==="photo_thumbnail"){
  responses[200].description="One complete bounded JPEG or PNG thumbnail from a freshly validated owned public-photo page. Candidate; production disabled pending qualification.";
  responses[200].headers["Cache-Control"]={schema:{type:"string",const:"private, no-store"}};
  responses[200].content={"image/jpeg":{schema:route.response},"image/png":{schema:route.response}};
 }
 if(route.handler==="upload_candidates"){
  for(const response of Object.values(responses))response.headers["Cache-Control"]={schema:{type:"string",const:"private, no-store"}};
  parameters.push({name:"page",in:"query",required:true,schema:{type:"integer",minimum:1,maximum:1000}},
    {name:"page_size",in:"query",required:true,schema:{type:"integer",minimum:1,maximum:100}});
 }
 if(route.handler==="groups"){
  responses[200].description="One complete snapshot keyset page with explicit freshness state.";
  responses[202].description="First snapshot is refreshing; no group data is available yet.";
  responses[202].content["application/json"].schema=GROUP_PENDING_SCHEMA;
  responses[202].headers["Retry-After"]={schema:{type:"string",const:"60"}};
  parameters.push({name:"page_size",in:"query",required:true,schema:{type:"integer",minimum:1,maximum:100}},
   {name:"snapshot_revision",in:"query",required:false,schema:{type:"integer",minimum:1,maximum:Number.MAX_SAFE_INTEGER},description:"Required together with after_group_id on continuation."},
   {name:"after_group_id",in:"query",required:false,schema:{type:"string",minLength:1,maxLength:128},description:"Exact group ID boundary; required together with snapshot_revision."});
 }
 (paths[route.pathPattern]??={})[method]={operationId:route.id,description:["status","status_admin"].includes(route.handler)?"Read-only owner-scoped status snapshot. No Flickr or identity-provider request, worker wake, or domain mutation. Continuation fields are paired and bounded.":description,parameters,security:[route.auth==="browser_session"?{browserSessionCookie:[]}:{installationBearer:[]}],...(route.request?{requestBody:{required:true,content:{[route.requestMediaType??"application/json"]:{schema:route.request}}}}:{}),responses};
 if(route.handler==="groups")paths[route.pathPattern][method].description="Current installation credential only. Initial reads admit or join one bounded group refresh. Continuations require paired revision and exact keyset boundary; revision change returns 409 snapshot_changed. No request body. Flickr group additions remain disabled independently.";
 if(route.handler==="existing_photos")paths[route.pathPattern][method].description="Current installation credential and linked-owner authority only. Reads one bounded public-photo discovery page from Flickr. The feature is separately disabled pending qualification. No submission or upload occurs.";
 if(route.handler==="photo_thumbnail")paths[route.pathPattern][method].description="Proposed disabled candidate. Current installation and expected linked revision only. Re-reads and validates the complete referenced discovery page, selects the exact photo ID and fetches only its validated public static thumbnail. Refuses redirects; bounds the complete operation to 15 seconds and image to 256 KiB; fences current credentials and grant before private no-store publication. No arbitrary URL input or photo mutation.";
 if(route.handler==="photo_memberships")paths[route.pathPattern][method].description="Current installation credential and owned photo binding only. Each initial request reads a fresh complete Flickr membership observation. Continuations require paired revision and keyset boundary; a changed or invalidated observation returns 409 membership_observation_changed. No group addition occurs.";
 if(route.handler==="upload_photo_binding"){
  paths[route.pathPattern][method].description="Disabled upload-origin proof candidate. Current installation and exact upload authorization only. Fresh exact-photo/current-owner observation may verify a private upload. First commit is 201 with Location; identical committed tuple returns current common binding with 200 without another proof or revision inflation. A different photo conflicts. No image upload, album write or group admission occurs.";
  responses[201].headers.Location={description:"Relative URI of this authorization's photo-binding resource",schema:{type:"string"}};
  responses[503].description="Missing/failed or unavailable Flickr observations are retryable and include Retry-After. No binding/provenance is committed on failure.";
  responses[503].headers["Retry-After"]={schema:{type:"string",const:"5"}};
 }
 if(route.handler==="upload_ambiguity_resolution"){
  paths[route.pathPattern][method].description="Disabled explicit ambiguous-upload resolution. Photographer-selected exact photo under the current installation and upload authorization receives fresh current-owner proof; private photos are allowed. Immutable reconciliation provenance records the explicit choice without claiming byte identity. Same committed tuple returns 200 without another proof or event; a conflicting tuple is rejected. No image upload, album/group write or catalog mutation occurs.";
  responses[201].headers.Location={description:"Relative URI of this authorization's ambiguity-resolution resource",schema:{type:"string"}};
  responses[503].description="Missing or unavailable provider proof is retryable; no association or provenance is committed.";
  responses[503].headers["Retry-After"]={schema:{type:"string",const:"5"}};
 }
 if(route.handler==="upload_candidates"){
  paths[route.pathPattern][method].description="Disabled advisory candidate read. Current installation and original authorization link snapshot only. One complete bounded owner-photo page inside the retained authorization time window; rows do not establish upload success, byte identity or binding. No automatic selection, binding, upload, album or group mutation.";
 }
 if(route.handler==="publish_service_create"||route.handler==="publish_service_read"){
  const codes={400:["invalid_request",false],401:["invalid_token",false],403:["insufficient_scope",false],
    404:["publish_service_not_found",false],409:["flickr_link_unavailable",false],429:["rate_limited",true],503:["service_unavailable",true]};
  for(const status of Object.keys(responses))if(Number(status)>=400&&Number(status)!==405&&!(status in codes))delete responses[status];
  for(const [status,[code,retryable]] of Object.entries(codes)){
    const schema=structuredClone(ERROR_SCHEMA), properties=schema.properties.error.properties;
    properties.code={enum:[code]};properties.retryable={const:retryable};
    properties.message={type:"string",minLength:1,maxLength:256};
    properties.correlationId={type:"string",pattern:SERVICE_ID.source};
    responses[status].content["application/json"].schema=schema;
  }
  responses[503].headers["Retry-After"]={schema:{type:"string",const:"5"}};
  responses[429].headers["Retry-After"]={schema:{type:"string",pattern:"^[1-9][0-9]*$"}};
  for(const parameter of parameters)if(parameter.name==="fgaPublishServiceId")parameter.schema={type:"string",pattern:SERVICE_ID.source};

  paths[route.pathPattern][method].description="Disabled publish-service identity protocol. Current installation only. Create issues a fresh server UUID under current linked-owner authority; every create is distinct and lost responses may leave safe unused orphans. Read returns the owned identity and current link status. The client must durably save and freshly verify the exact identity before use. No Flickr request or Album provisioning.";
  if(route.handler==="publish_service_create")responses[201].headers.Location={description:"Relative URI of the issued publish-service resource",schema:{type:"string"}};
 }
 if(route.handler==="album_binding_ensure"||route.handler==="album_binding_read"||route.handler==="album_photo_association"){
  const codes={400:["invalid_request"],401:["invalid_token"],403:["insufficient_scope"],404:["resource_not_found"],
    409:["album_binding_exists","stale_binding_revision","stale_photo_revision","flickr_link_unavailable","album_closed","photo_not_ready"],
    429:["rate_limited"],503:["service_unavailable"]};
  for(const status of Object.keys(responses))if(Number(status)>=400&&Number(status)!==405&&!(status in codes))delete responses[status];
  for(const [status,values] of Object.entries(codes)){
    const schema=structuredClone(ERROR_SCHEMA),properties=schema.properties.error.properties;
    properties.code={enum:values};properties.retryable={const:["429","503"].includes(status)};
    properties.message={type:"string",minLength:1,maxLength:256};properties.correlationId={type:"string",pattern:SERVICE_ID.source};
    responses[status].content["application/json"].schema=schema;
  }
  responses[503].headers["Retry-After"]={schema:{type:"string",const:"5"}};
  responses[429].headers["Retry-After"]={schema:{type:"string",pattern:"^[1-9][0-9]*$"}};
  for(const parameter of parameters)if(parameter.name==="serviceId"||parameter.name==="bindingId")parameter.schema={type:"string",pattern:SERVICE_ID.source};
  if(route.handler==="album_binding_ensure")responses[201].headers.Location={description:"Relative URI of the service/local-collection binding",schema:{type:"string"}};
  if(route.handler==="album_photo_association"){
    responses[200].description="Current binding and retained natural-key obligation receipt; no revision change.";
    responses[201].description="Current binding and newly admitted natural-key obligation receipt.";
    paths[route.pathPattern][method].description="Disabled Album photo-association admission. Current non-pending installation, owning service/link and exact proved-photo authority only. New natural-key obligations require current binding/photo revisions and an active collection, increment the binding revision once and retain one immutable receipt. Exact replay rechecks current authority while ignoring stale expected revisions, allocates nothing and never resurrects archived relationships. No Flickr call, worker wake, image replay, materialization or membership claim.";
  } else paths[route.pathPattern][method].description="Disabled Album binding ensure/read protocol. Current owner, service/link and exact proved-photo authority only. First committed candidate creates one immutable natural-key binding and its initial obligation atomically; exact replay allocates nothing and ignores stale title/proof input while rechecking current authority. No Flickr create, membership write, general association delivery or production activation.";
 }

 if(["album_binding_status","album_photo_association_status","album_create_repair_candidates","album_create_repair_resolution","album_create_repair_admin","album_lifecycle_read","album_title_intent"].includes(route.handler)){
  const repair=!["album_lifecycle_read","album_title_intent"].includes(route.handler),admin=route.auth==="browser_session";
  const schema=repair?ALBUM_CREATE_REPAIR_ERROR_SCHEMA:ALBUM_TITLE_ERROR_SCHEMA;
  const codes={400:["invalid_request",...(repair?["page_out_of_range"]:[])],401:[admin?"unauthorized":"invalid_token"],
   403:[admin?"forbidden":"insufficient_scope"],404:["resource_not_found"],
   409:repair?["stale_binding_revision","flickr_link_unavailable","administrative_repair_required","create_repair_not_pending","resolution_conflict","selected_album_not_verified"]:["stale_binding_revision","stale_title_revision","title_intent_conflict","album_closed","flickr_link_unavailable","revision_exhausted"],
   429:["rate_limited"],503:repair?["candidate_evidence_unavailable","resolution_evidence_unavailable","service_unavailable"]:["service_unavailable"]};
  for(const status of Object.keys(responses))if(Number(status)>=400&&Number(status)!==405&&!(status in codes))delete responses[status];
  for(const [status,values] of Object.entries(codes)){
   const specific=structuredClone(schema),properties=specific.properties.error.properties;
   properties.code={enum:values};properties.retryable={const:["429","503"].includes(status)};
   responses[status].content={"application/json":{schema:specific}};
  }
  for(const response of Object.values(responses))response.headers["Cache-Control"]={schema:{type:"string",const:"private, no-store"}};
  responses[503].headers["Retry-After"]={schema:{type:"string",const:"5"}};
  responses[429].headers["Retry-After"]={schema:{type:"string",pattern:"^[1-9][0-9]*$"}};
  if(admin)responses[401].headers["Set-Cookie"]={description:"Only an exact-origin unauthorized request expires the host-only __Host-fga_admin cookie using Secure, HttpOnly, Path=/, SameSite=Strict and Max-Age=0. CSRF is browser memory only; no CSRF cookie is set.",schema:{type:"string"}};
  for(const parameter of parameters){
   if(parameter.name==="bindingId")parameter.schema={type:"string",pattern:SERVICE_ID.source};
   if(parameter.name==="titleRevision")parameter.schema={type:"integer",minimum:1,maximum:Number.MAX_SAFE_INTEGER};
  }
  const pageRoute=route.pathPattern.endsWith("/photo-association-status")||route.pathPattern.endsWith("/create-repair-candidates")||route.pathPattern.endsWith("/admin/album-create-repairs");
  if(pageRoute)parameters.push({name:"page",in:"query",required:true,schema:{type:"integer",minimum:1,maximum:1000},description:"Canonical positive decimal without leading zero or alternate encoding."},
   {name:"page_size",in:"query",required:true,schema:{type:"integer",minimum:1,maximum:route.pathPattern.endsWith("/create-repair-candidates")?20:100},description:"Canonical positive decimal; no other query fields are accepted."});
  paths[route.pathPattern][method].description=repair?
   "Default-off accepted album status/create-repair protocol. Current installation credential or the owning Google-admitted server session only; pending credentials cannot use this route. Administrative resolution requires exact Origin and synchronizer CSRF, with no additional recent-authentication ceremony. Status and obligation reads use stored facts only. Candidate discovery is advisory and selection requires fresh exact-owner and first-photo membership proof. Same-attempt/same-ID receipt replay performs no new proof or work. Immutable identity and archived admin-only repair are retained; no Flickr write or recreation occurs. Raw canonical paths, strict closed UTF-8 JSON and finite response/read budgets are enforced.":
   "Default-off accepted album lifecycle/title protocol. Current installation credential and owned binding only; pending credentials are refused. Lifecycle reads stored facts without Flickr calls. A title PUT addresses one explicit next revision, persists exact intent and returns an immutable receipt; exact replay returns the current lifecycle without another revision or work. This route performs no Flickr dispatch, local removal, deletion or recreation. Strict canonical paths and closed UTF-8 JSON are required.";
  if(route.request)paths[route.pathPattern][method].requestBody.description="UTF-8 application/json, at most 4096 bytes; duplicate, unknown and null members and alternate framing are rejected.";
  if(route.handler==="album_title_intent")responses[201].headers.Location={description:"Exact relative URI of the newly accepted title-revision resource",schema:{type:"string",pattern:"^/api/v001/album-bindings/[0-9a-f-]{36}/title-intents/[1-9][0-9]*$"}};
 }
 if(route.handler==="upload_authorization"){
  paths[route.pathPattern][method].description="Current installation credential only. Metadata-only direct-upload signing under current linked-account authority and both enabled Flickr write gates. The backend durably records the authorization association and sanitized audit before returning the exact signed metadata and fixed Flickr upload URL. The bearer envelope is kept in memory only, is not image-bound or guaranteed single-use, and has no backend-enforced Flickr expiry. No image or Flickr network request reaches this handler. Separately disabled pending hosted qualification.";
  responses[200].description="Durably recorded upload authorization with the exact signed metadata and fixed Flickr upload URL; sensitive bearer envelope must be used immediately and never persisted or logged.";
  responses[503].description="Paused Flickr write gates return flickr_writes_paused with retryable:false and no Retry-After; other unavailable dependencies fail closed without a signed envelope.";
 }
}
console.log(JSON.stringify({inventory:{schemaVersion:1,scope:"installation-read-and-photo-admission",routes:ROUTES,guards:GUARDS,proofEndpointsExcluded:true},openapi:{openapi:"3.2.0",info:{title:"FGA API backend",version:"0.0.0"},paths,components:{securitySchemes:{installationBearer:{type:"http",scheme:"bearer"},browserSessionCookie:{type:"apiKey",in:"cookie",name:"__Host-fga_admin"}}}}}));
