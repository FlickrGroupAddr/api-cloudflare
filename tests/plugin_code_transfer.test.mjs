import test from "node:test";
import assert from "node:assert/strict";
import {transferView,CLEAN_CLIPBOARD_TEXT} from "../assets/admin/plugin-code-transfer.mjs";
const sample="0000-0000-0000-0000-0000-0000-0000-0000-0000-0000-0000-0000-0000";
test("transfer copies once, times out at five minutes, and explicit erasure overwrites without a read",async()=>{
 const rendered=[],writes=[];let expire;
 const view=transferView({render:(value,copy)=>rendered.push({value,copy}),writeClipboard:async value=>writes.push(value),schedule:(callback,delay)=>{assert.equal(delay,300000);expire=callback;return 1;},cancel:()=>{}});
 view.show(sample);assert(view.active);assert.equal(await view.copy(),true);assert.equal(await view.copy(),false);assert.equal(writes.length,1);
 expire();assert.equal(view.active,false);assert.equal(rendered.at(-1).value,"");assert.equal(await view.copy(),false);
 assert.equal(await view.finish(),true);assert.equal(writes.at(-1),CLEAN_CLIPBOARD_TEXT);
});
test("clipboard refusal still erases every UI reference and returns only a cleanup result",async()=>{
 let rendered;
 const view=transferView({render:value=>rendered=value,writeClipboard:async()=>{throw Error("denied");},schedule:()=>1,cancel:()=>{}});
 view.show(sample);assert.equal(await view.finish(),false);assert.equal(rendered,"");assert.equal(view.active,false);assert.equal(await view.copy(),false);
 assert.throws(()=>view.show("malformed"));assert.equal(view.active,false);
});
