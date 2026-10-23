// Local emulator host harness: loopback IPC only; never part of the Worker.
const fs=require('node:fs'),net=require('node:net'),dns=require('node:dns');let refused=0;
const connect=net.Socket.prototype.connect;
net.Socket.prototype.connect=function(...args){const v=args[0];
 const o=typeof v==='object'?v:{};const host=o.host??(typeof args[1]==='string'?args[1]:'localhost');
 // Node's internal normalized argument array carries the options at index zero.
 const actual=Array.isArray(v)?v[0]:o;const h=actual.host??host;
 const pipe=actual.path??(typeof v==='string'&&v.includes('pipe')?v:undefined);
 if(!pipe&&!['127.0.0.1','::1','localhost'].includes(h)){refused++;throw Error('host_nonloopback_disabled');}
 return connect.apply(this,args);};
const lookup=dns.lookup;dns.lookup=function(host,...args){if(!['localhost','127.0.0.1','::1'].includes(host)){refused++;throw Error('host_dns_disabled');}return lookup.call(this,host,...args);};
globalThis.fetch=()=>{refused++;throw Error('host_fetch_disabled');};
require('node:module').syncBuiltinESMExports();
process.on('exit',()=>fs.writeFileSync(process.env.PMB1_HOST_RECEIPT.replace('.json','-'+process.pid+'.json'),JSON.stringify({externalAttempts:refused,pid:process.pid})));
