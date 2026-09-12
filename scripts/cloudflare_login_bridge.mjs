// Loopback-only handoff for the official Wrangler OAuth flow. Never exchanges tokens itself.
import http from "node:http";
import net from "node:net";
import {spawn} from "node:child_process";
import {randomBytes,timingSafeEqual} from "node:crypto";
import {fileURLToPath,pathToFileURL} from "node:url";
import {writeFile,mkdir} from "node:fs/promises";
import path from "node:path";
const ROOT=fileURLToPath(new URL("../",import.meta.url));
const UI_CHECK=process.argv.includes("--ui-check");
const PORT=UI_CHECK?18976:8976;
const ORIGIN=`http://localhost:${PORT}`;
const escape=value=>String(value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
export function findAuthorizationUrl(output){const marker="Visit this link to authenticate: ";const line=output.split("\n").find(value=>value.includes(marker));if(!line)return null;try{const url=new URL(line.slice(line.indexOf(marker)+marker.length).trim());return url.origin==="https://dash.cloudflare.com"&&url.pathname==="/oauth2/auth"&&url.searchParams.get("state")&&url.searchParams.get("redirect_uri")==="http://localhost:8976/oauth/callback"?url.href:null;}catch{return null;}}
export function acceptCallback(flow,url){
 if(!flow||!flow.url||flow.phase!=="waiting"||url.searchParams.getAll("state").length!==1)return false;
 const received=url.searchParams.get("state"),expected=new URL(flow.url).searchParams.get("state");
 return typeof received==="string"&&typeof expected==="string"&&Buffer.byteLength(received)===Buffer.byteLength(expected)&&timingSafeEqual(Buffer.from(received),Buffer.from(expected));
}
export function relayCallback(request,response,flow){
 const url=new URL(request.url,ORIGIN);
 if(!acceptCallback(flow,url)){response.writeHead(410,{"Content-Type":"text/html; charset=utf-8","Cache-Control":"no-store","Referrer-Policy":"no-referrer"});response.end('<h1>This login attempt has expired</h1><p>The current login has not been interrupted.</p><a href="/">Return to Cloudflare setup</a>');return;}
 if(flow.claimed){response.writeHead(303,{Location:"/result","Cache-Control":"no-store"});response.end();return;}
 flow.claimed=true;
 const upstream=http.request({host:"127.0.0.1",port:flow.port,path:request.url,method:"GET",headers:{Host:`localhost:${PORT}`}},reply=>{
  reply.resume();reply.on("end",()=>{response.writeHead(303,{Location:"/result","Cache-Control":"no-store","Referrer-Policy":"no-referrer"});response.end();});
 });
 upstream.on("error",()=>{flow.phase="failed";response.writeHead(503,{"Content-Type":"text/html; charset=utf-8","Cache-Control":"no-store"});response.end('<h1>Login could not finish</h1><p>The local Wrangler process ended. No callback code was reused.</p><a href="/">Return to setup</a>');});
 upstream.setTimeout(30000,()=>upstream.destroy());upstream.end();
}
async function freePort(){const server=net.createServer();await new Promise((resolve,reject)=>{server.once("error",reject);server.listen(0,"127.0.0.1",resolve);});const port=server.address().port;await new Promise(resolve=>server.close(resolve));return port;}
async function run(){
 const csrf=randomBytes(32).toString("base64url"),directory=path.join(ROOT,UI_CHECK?".coordination-runs/cloudflare-login/ui-test":".coordination-runs/cloudflare-login");await mkdir(directory,{recursive:true});let flow=null;const children=new Set();
 const writeStatus=()=>writeFile(path.join(directory,"status.json"),JSON.stringify({phase:flow?.phase??"idle",profile:"fga-sixbucks",url:ORIGIN,pid:process.pid}),"utf8");
 const start=async()=>{
  if(UI_CHECK)return "https://dash.cloudflare.com/oauth2/auth?state=browser-check&redirect_uri=http%3A%2F%2Flocalhost%3A8976%2Foauth%2Fcallback";
  if(flow?.phase==="waiting")return flow.url;
  const port=await freePort();flow={phase:"starting",port,url:null,claimed:false,success:false};const current=flow;await writeStatus();
  const child=spawn(process.execPath,[path.join(ROOT,"node_modules/wrangler/bin/wrangler.js"),"auth","create","fga-sixbucks","--browser","false","--callback-host","127.0.0.1","--callback-port",String(port),"--scopes","account:read","user:read","workers:write","workers_routes:write","workers_scripts:write","d1:write","zone:read","secrets_store:write"],{cwd:ROOT,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,WRANGLER_WRITE_LOGS:"false",WRANGLER_SEND_METRICS:"false"}});children.add(child);
  let output="";
  const ready=new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error("Wrangler did not start")),15000);
   child.stdout.on("data",bytes=>{output=(output+bytes.toString()).slice(-16000);if(output.includes("Successfully logged in"))current.success=true;const authorization=findAuthorizationUrl(output);if(authorization&&!current.url){current.url=authorization;current.phase="waiting";clearTimeout(timer);writeStatus().catch(()=>{});resolve(current.url);}});
   child.stderr.on("data",bytes=>{const text=bytes.toString();if(text.includes("Timed out waiting"))current.phase="expired";else if(text.includes("query string parameter"))current.phase="failed";});
   child.on("error",()=>{clearTimeout(timer);current.phase="failed";reject(Error("Wrangler failed to start"));});
   child.on("exit",code=>{children.delete(child);clearTimeout(timer);current.phase=code===0&&current.success?"succeeded":current.phase==="expired"?"expired":"failed";if(!current.url)reject(Error("Wrangler ended before login"));writeStatus().catch(()=>{});});
  });return ready;
 };
 const page=(title,body,script="")=>`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${escape(title)}</title><style nonce="${csrf}">body{font:17px system-ui;background:#f5f7fa;color:#20303f;max-width:680px;margin:60px auto;padding:24px}section{padding:32px;background:white;border-radius:16px}button,a{font:inherit}button{padding:14px 20px;background:#185c89;color:white;border:0;border-radius:8px}p{line-height:1.6}</style><section><h1>${escape(title)}</h1>${body}</section>${script?`<script nonce="${csrf}">${script}</script>`:""}</html>`;
 const handler=async(req,res)=>{
  const allowedAddress=["127.0.0.1","::1","::ffff:127.0.0.1"].includes(req.socket.remoteAddress);
  const allowedHost=[`localhost:${PORT}`,`127.0.0.1:${PORT}`,`[::1]:${PORT}`].includes(req.headers.host);
  const send=(status,body,type="text/html; charset=utf-8")=>{res.writeHead(status,{"Content-Type":type,"Cache-Control":"no-store","Referrer-Policy":"no-referrer","X-Content-Type-Options":"nosniff","Content-Security-Policy":`default-src 'none'; script-src 'nonce-${csrf}'; style-src 'nonce-${csrf}'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'`});res.end(body);};
  try{
   if(!allowedAddress||!allowedHost)return send(404,"Not found");
   const url=new URL(req.url,ORIGIN);
   if(req.method==="GET"&&url.pathname==="/health")return send(200,JSON.stringify({service:"fga-cloudflare-login-bridge",phase:flow?.phase??"idle"}),"application/json");
   if(req.method==="GET"&&url.pathname==="/oauth/callback")return relayCallback(req,res,flow);
   if(req.method==="GET"&&url.pathname==="/status")return send(200,JSON.stringify({phase:flow?.phase??"idle"}),"application/json");
   if(req.method==="GET"&&url.pathname==="/")return send(200,page("Connect FGA to Cloudflare",`<p>Use the browser profile already signed in to the <strong>sixbuckssolutions.com</strong> Cloudflare account.</p><p>The two-minute Wrangler login starts only when you press this button. Older callback tabs cannot interrupt it.</p><button id="start">Start Cloudflare login</button><p id="status" role="status"></p>`,`document.getElementById('start').onclick=async()=>{const button=document.getElementById('start'),status=document.getElementById('status');button.disabled=true;status.textContent='Starting the local login listener…';try{const response=await fetch('/start',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({csrf:'${csrf}'})});const value=await response.json();if(!response.ok)throw Error('Local login could not start.');const target=new URL(value.authorizationUrl);if(target.origin!=='https://dash.cloudflare.com'||target.pathname!=='/oauth2/auth')throw Error('Invalid authorization target.');if(value.uiCheck){status.textContent='Browser handoff check passed';button.disabled=false;return;}window.location.assign(target.href);}catch(error){status.textContent=error.message;button.disabled=false;}}`));
   if(req.method==="POST"&&url.pathname==="/start"){
    if(req.headers.origin!==ORIGIN)return send(403,"Invalid origin");let size=0,body="";for await(const chunk of req){size+=chunk.length;if(size>512)return send(413,"Request too large");body+=chunk.toString();}const value=new URLSearchParams(body).get("csrf");if(!value||Buffer.byteLength(value)!==Buffer.byteLength(csrf)||!timingSafeEqual(Buffer.from(value),Buffer.from(csrf)))return send(403,"Invalid request");
    const location=await start();return send(201,JSON.stringify({authorizationUrl:location,...(UI_CHECK?{uiCheck:true}:{})}),"application/json");
   }
   if(req.method==="GET"&&url.pathname==="/result")return send(200,page("Finishing Cloudflare login",'<p id="status">Checking the Wrangler result…</p><p><a href="/">Return to setup</a></p>',`let timer;async function check(){const response=await fetch('/status',{cache:'no-store'}),value=await response.json();document.getElementById('status').textContent=value.phase==='succeeded'?'Connected. The fga-sixbucks operator profile is ready. Return to Codex.':['failed','expired'].includes(value.phase)?'The login did not complete. Return to setup and start a new attempt.':'Waiting for Wrangler to finish…';if(!['succeeded','failed','expired'].includes(value.phase))timer=setTimeout(check,750);}check();`));
   return send(404,"Not found");
  }catch{return send(503,page("Login unavailable",'<p>The local login could not start. Return to Codex for the diagnostic result.</p>'));}
 };
 const servers=[];for(const host of ["127.0.0.1","::1"]){const server=http.createServer(handler);await new Promise((resolve,reject)=>{server.once("error",reject);server.listen(PORT,host,resolve);});servers.push(server);}await writeStatus();
 const close=()=>{for(const child of children)child.kill();for(const server of servers)server.close();};process.once("SIGTERM",close);process.once("SIGINT",close);setTimeout(close,3600000).unref();
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)run().catch(()=>{process.stderr.write("Cloudflare login bridge startup failed.\n");process.exitCode=1;});
