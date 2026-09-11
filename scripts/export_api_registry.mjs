// Node imports the executable TypeScript registry; Python owns artifact writing/checking.
import { ROUTES, GUARDS, CURRENT_SCHEMA, ERROR_SCHEMA } from "../src/registry.ts";
const paths={};
for (const route of ROUTES) {
 if(paths[route.pathPattern]?.[route.method.toLowerCase()]) throw new Error("Duplicate route");
 const noStore={description:"Always no-store",schema:{type:"string",const:"no-store"}};
 const responses={200:{description:"Current installation for the presented current or pending credential",headers:{"Cache-Control":{...noStore}},content:{"application/json":{schema:CURRENT_SCHEMA}}}};
 for(const status of [400,401,405,503]) responses[status]={description:status===401?"Missing authentication has an empty body and a bare Bearer challenge; invalid credentials return the error representation.":"Request rejected",headers:{"Cache-Control":{...noStore},...([400,401].includes(status)?{"WWW-Authenticate":{schema:{type:"string"},description:"Bearer challenge with the same machine error code; absent error for missing authentication."}}:{}),...(status===405?{Allow:{schema:{type:"string",const:"GET"}}}:{})},content:{"application/json":{schema:ERROR_SCHEMA}}};
 responses[400].description="Application authentication-envelope errors use JSON/no-store and a matching Bearer challenge. ADR 0054 also permits an early provider HTTP 400 for duplicate Authorization fields before application execution to use the provider's non-JSON body without those headers; it cannot redirect, set an application/session cookie, serve the application shell or expose application/session data. The existing malformed-target exception remains.";
 responses[400].headers["Cache-Control"].description="Application-generated errors use no-store; the bounded early provider rejection may omit it.";
 responses[400].headers["WWW-Authenticate"].description="Application-generated Bearer errors carry the matching error code. The early provider parser rejection may omit this header.";
 responses[400].content["text/html"]={schema:{type:"string"}};
 (paths[route.pathPattern]??={})[route.method.toLowerCase()]={operationId:route.id,summary:"Read the current installation",description:"No query parameters or request body. Pending credentials authorize this safe read only. Credentials are canonical, opaque 64-character Crockford codes; their complete ASCII form is hashed for lookup. Missing authentication uses an empty 401 response.",security:[{installationBearer:[]}],responses};
}
console.log(JSON.stringify({inventory:{schemaVersion:1,scope:"current-installation-read",routes:ROUTES,guards:GUARDS,proofEndpointsExcluded:true},openapi:{openapi:"3.2.0",info:{title:"FGA API backend: installation read slice",version:"0.0.0"},paths,components:{securitySchemes:{installationBearer:{type:"http",scheme:"bearer"}}}}}));
