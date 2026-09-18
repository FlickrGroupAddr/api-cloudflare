// Node imports the executable TypeScript registry; Python owns artifact writing/checking.
import { ROUTES, GUARDS, ERROR_SCHEMA } from "../src/registry.ts";
import { GROUP_PENDING_SCHEMA } from "../src/group_registry.ts";
const paths={};
for(const route of ROUTES){
 const method=route.method.toLowerCase();if(paths[route.pathPattern]?.[method])throw new Error("Duplicate route");
 const noStore={description:"Always no-store",schema:{type:"string",const:"no-store"}};
 const responses={};
 for(const status of route.successStatuses)responses[status]={description:["admin","plugin_code","status_admin"].includes(route.handler)?"Administrative operation result":route.handler==="current"?"Current installation":route.handler==="binding"?"Fresh verified photo binding":"Complete ordered admission snapshot",headers:{"Cache-Control":noStore},...(status===204?{}:{content:{"application/json":{schema:route.response}}})};
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
}
console.log(JSON.stringify({inventory:{schemaVersion:1,scope:"installation-read-and-photo-admission",routes:ROUTES,guards:GUARDS,proofEndpointsExcluded:true},openapi:{openapi:"3.2.0",info:{title:"FGA API backend",version:"0.0.0"},paths,components:{securitySchemes:{installationBearer:{type:"http",scheme:"bearer"},browserSessionCookie:{type:"apiKey",in:"cookie",name:"__Host-fga_admin"}}}}}));
