// Operator-only loopback helper. Verifies identity; creates no FGA browser session.
import http from "node:http";
import {readFile,writeFile} from "node:fs/promises";
import {randomBytes,timingSafeEqual} from "node:crypto";
import {OAuth2Client} from "google-auth-library";
const configPath=new URL("../.coordination-runs/fga-google-config.json",import.meta.url);
const config=JSON.parse(await readFile(configPath,"utf8"));
if(!/^[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(config.GOOGLE_CLIENT_ID))throw new Error("Missing FGA client ID");
const csrf=randomBytes(32).toString("base64url"),nonce=randomBytes(32).toString("base64url");
let origin="",verified=null;
const client=new OAuth2Client(config.GOOGLE_CLIENT_ID);
const page=()=>`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>FGA owner setup</title><style nonce="${csrf}">body{font:17px system-ui;max-width:720px;margin:60px auto;padding:24px;color:#1c2733;background:#f6f7f9}section{background:white;padding:28px;border-radius:16px}button{padding:12px;font:inherit}pre{white-space:pre-wrap;overflow-wrap:anywhere}.note{color:#526170}</style><section><h1>Choose FGA's sole administrator</h1><p>This local helper verifies your Google identity and saves only your Google account ID (<code>sub</code>) in FGA's ignored local configuration. It creates no application session and makes no Flickr change.</p><p class="note">In the FGA Google OAuth client, temporarily add <strong>${origin}</strong> to Authorized JavaScript origins. The existing production redirect URI stays unchanged.</p><div id="google"></div><p id="status">Sign in with the Google account you want to administer FGA.</p><pre id="identity"></pre><button id="confirm" hidden>Use this Google account as FGA's sole administrator</button></section><script nonce="${csrf}">
const status=document.querySelector('#status'),identity=document.querySelector('#identity'),button=document.querySelector('#confirm');let subject='';
async function post(path,body){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Setup-CSRF':'${csrf}'},body:JSON.stringify(body)});const value=await response.json();if(!response.ok)throw Error(value.error);return value;}
window.initializeGoogle=()=>{google.accounts.id.initialize({client_id:${JSON.stringify(config.GOOGLE_CLIENT_ID)},nonce:'${nonce}',auto_select:false,callback:async result=>{try{const value=await post('/verify',{credential:result.credential});result.credential='';subject=value.sub;identity.textContent='Google account: '+value.email+'\\nAccount ID (sub): '+value.sub;button.hidden=false;status.textContent='Review the account, then confirm below.';}catch(error){status.textContent=error.message;button.hidden=true;}}});google.accounts.id.renderButton(document.querySelector('#google'),{type:'standard',theme:'outline',size:'large'});};
window.addEventListener("load",()=>window.initializeGoogle());
button.onclick=async()=>{button.disabled=true;try{await post('/confirm',{sub:subject});status.textContent='Confirmed. FGA local owner configuration is saved. You can close this page and remove the temporary localhost origin from Google.';button.hidden=true;}catch(error){status.textContent=error.message;button.disabled=false;}};
</script><script nonce="${csrf}" src="https://accounts.google.com/gsi/client" async defer></script></html>`;
const server=http.createServer(async(req,res)=>{
 const reply=(status,value,type="application/json")=>{res.writeHead(status,{"Content-Type":type,"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer","Content-Security-Policy":`default-src 'none'; script-src 'nonce-${csrf}' https://accounts.google.com/gsi/client; style-src 'nonce-${csrf}' https://accounts.google.com/gsi/style; frame-src https://accounts.google.com; connect-src 'self' https://accounts.google.com; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`});res.end(type==="application/json"?JSON.stringify(value):value);};
 try{
  if(req.headers.host!==new URL(origin).host)return reply(400,{error:"Invalid host"});
  if(req.method==="GET"&&req.url==="/")return reply(200,page(),"text/html; charset=utf-8");
  const header=req.headers["x-setup-csrf"];
  if(req.method!=="POST"||req.headers.origin!==origin||typeof header!=="string"||header.length!==csrf.length||!timingSafeEqual(Buffer.from(header),Buffer.from(csrf))||req.headers["content-type"]!=="application/json")return reply(403,{error:"Invalid local setup request"});
  let size=0;const chunks=[];for await(const chunk of req){size+=chunk.length;if(size>20000)return reply(413,{error:"Request too large"});chunks.push(chunk);}const body=JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if(req.url==="/verify"){
   if(typeof body.credential!=="string"||body.credential.length>16384)return reply(400,{error:"Invalid Google response"});
   const ticket=await client.verifyIdToken({idToken:body.credential,audience:config.GOOGLE_CLIENT_ID});body.credential="";const claims=ticket.getPayload();
   if(!claims||claims.nonce!==nonce||typeof claims.sub!=="string"||!claims.exp||claims.exp<=Date.now()/1000)return reply(401,{error:"Google identity verification failed"});
   verified={sub:claims.sub,expires:Math.min(claims.exp*1000,Date.now()+300000)};
   return reply(200,{sub:claims.sub,email:typeof claims.email==="string"?claims.email:"(email not supplied)"});
  }
  if(req.url==="/confirm"&&verified&&Date.now()<verified.expires&&body.sub===verified.sub){config.GOOGLE_OWNER_SUB=verified.sub;await writeFile(configPath,JSON.stringify(config),"utf8");await writeFile(new URL("../.coordination-runs/google-owner-confirmed.json",import.meta.url),JSON.stringify({confirmed:true,at:new Date().toISOString()}));verified=null;return reply(200,{confirmed:true});}
  return reply(400,{error:"Verify and confirm the intended Google account"});
 }catch{return reply(400,{error:"Google verification failed. Check the FGA client origin and try again."});}
});
server.listen(Number(process.argv[2]??0),"127.0.0.1",async()=>{origin="http://localhost:"+server.address().port;await writeFile(new URL("../.coordination-runs/google-owner-setup-status.json",import.meta.url),JSON.stringify({url:origin,pid:process.pid,expiresAt:new Date(Date.now()+1800000).toISOString()}));});
setTimeout(()=>server.close(),1800000).unref();
