import test from "node:test";
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {runInNewContext} from "node:vm";
test("callback continuation uses only fixed local destinations and never reads cookies or callback URL",async()=>{
 const source=await readFile(new URL("../assets/admin/login-complete.mjs",import.meta.url),"utf8");
 for(const target of ["/admin/","/admin/?flickr=linked","/admin/?flickr=unconfirmed","https://evil.example/","//evil.example/",null]){
  let destination;
  const document={querySelector(selector){assert.equal(selector,"[data-auth-continue]");return target===null?null:{getAttribute(name){assert.equal(name,"href");return target;}}},get cookie(){throw Error("Cookie must stay HttpOnly");}};
  runInNewContext(source,{document,window:{location:{replace(value){destination=value;},get href(){throw Error("Never copy callback URL");}}}});
  assert.equal(destination,["/admin/","/admin/?flickr=linked","/admin/?flickr=unconfirmed"].includes(target)?target:"/admin/");
 }
});
