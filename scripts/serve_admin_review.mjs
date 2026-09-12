// Local visual/interaction review of production assets using simulated API data only.
import http from "node:http";
import {readFile,writeFile} from "node:fs/promises";
const root=new URL("../assets/admin/",import.meta.url),now=new Date().toISOString().replace("Z","000Z");
let connection={schemaVersion:1,revision:7,state:"linked",flickrOwnerNsid:"123456789@N00",verifiedPermission:"write",verifiedAt:now,localCredentialState:"available",fgaOperationState:"read_only",flickrPermissionState:"not_requested",userWriteGate:{state:"paused",revision:2},deploymentWriteGate:{state:"paused",revision:3}};
const session={schemaVersion:1,sessionId:"example-session",revision:1,sessionSetRevision:1,createdAt:now,recentAuthenticationAt:now,lastActivityAt:now,expiresAt:now,csrfToken:"A".repeat(43)};
const server=http.createServer(async(req,res)=>{const url=new URL(req.url,"http://localhost"),reply=(status,value,type="application/json")=>{res.writeHead(status,{"Content-Type":type,"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer"});res.end(type==="application/json"?JSON.stringify(value):value);};try{
 if(req.method==="GET"&&url.pathname==="/admin/"){let html=await readFile(new URL("index.html",root),"utf8");html=html.replace('<div class="title">','<div class="preview"><strong>Local UI review · simulated data and actions. No account changes.</strong></div><div class="title">');return reply(200,html,"text/html; charset=utf-8");}
 const asset={"/admin/app.mjs":"app.mjs","/admin/model.mjs":"model.mjs","/admin/styles.css":"styles.css"}[url.pathname];if(req.method==="GET"&&asset)return reply(200,await readFile(new URL(asset,root),"utf8"),asset.endsWith(".css")?"text/css":"text/javascript");
 if(req.method==="GET"&&url.pathname==="/api/v001/admin/session")return reply(200,session);
 if(req.method==="GET"&&url.pathname==="/api/v001/admin/flickr-connection")return reply(200,connection);
 if(req.method==="GET"&&url.pathname==="/api/v001/admin/sessions")return reply(200,{schemaVersion:1,sessionSetRevision:1,sessions:[{...session,csrfToken:undefined,sessionSetRevision:undefined,isCurrent:true,state:"active",revokedAt:null}],nextPageToken:null});
 if(req.method==="POST"){let size=0,body="";for await(const chunk of req){size+=chunk.length;if(size>16384)return reply(413,{error:{message:"Preview request too large"}});body+=chunk;}const input=body?JSON.parse(body):{};
  if(url.pathname.endsWith("/authorization")||url.pathname.endsWith("/reauthentication"))return reply(503,{error:{code:"preview_only",message:"External sign-in is disabled in this synthetic UI review."}});
  if(url.pathname.endsWith("/disconnection")){if(input.expectedFlickrOwnerNsid!==connection.flickrOwnerNsid)return reply(400,{error:{message:"Owner confirmation mismatch"}});connection={...connection,revision:connection.revision+1,state:"disconnected",localCredentialState:"retired",fgaOperationState:"stopped",verifiedPermission:null,verifiedAt:null,flickrPermissionState:"owner_action_required",userWriteGate:{state:"paused",revision:3}};return reply(200,connection);}
  if(url.pathname.endsWith("/resume")){const key=url.pathname.includes("/deployment/")?"deploymentWriteGate":"userWriteGate";connection[key]={state:"enabled",revision:connection[key].revision+1};connection.fgaOperationState=connection.userWriteGate.state==="enabled"&&connection.deploymentWriteGate.state==="enabled"?"enabled":"read_only";return reply(200,connection);}
  if(url.pathname.endsWith("/logout")){res.writeHead(204,{"Cache-Control":"no-store"});return res.end();}
 }
 if(url.pathname==="/admin/signed-out")return reply(200,"<h1>Signed out of the simulated review session</h1>","text/html");
 return reply(404,{error:{message:"Preview route unavailable"}});
 }catch{return reply(500,{error:{message:"Preview unavailable"}});}});
server.listen(0,"127.0.0.1",async()=>{await writeFile(new URL("../.coordination-runs/admin-ui-review.json",import.meta.url),JSON.stringify({url:"http://127.0.0.1:"+server.address().port+"/admin/",pid:process.pid,synthetic:true}));});
