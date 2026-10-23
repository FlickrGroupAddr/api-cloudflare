// Build process isolation ONLY. Not included in the Worker artifact.
const fs = require('node:fs'), path = require('node:path');
const net = require('node:net'), tls = require('node:tls'), dns = require('node:dns');
let blocked=0;
const refuse=()=>{blocked++;throw Error('pmb1_build_network_disabled');};
net.Socket.prototype.connect=refuse;net.connect=refuse;net.createConnection=refuse;tls.connect=refuse;
for(const name of ['lookup','resolve','resolve4','resolve6','resolveAny','reverse']){dns[name]=refuse;if(dns.promises)dns.promises[name]=refuse;}
globalThis.fetch=refuse;
require('node:dgram').Socket.prototype.send=refuse;
// Block cached credential files and dotenv reads outside the new build root.
const isolated=path.resolve(process.env.PMB1_ISOLATED_ROOT).toLowerCase();
const check=p=>{if(typeof p!=='string'&&!Buffer.isBuffer(p))return;const name=path.resolve(String(p)).toLowerCase();
  if((/[\\/](?:\.env(?:\..*)?|\.dev\.vars(?:\..*)?|config[\\/]default\.toml)$/.test(name)||/[\\/]\.wrangler[\\/]config[\\/]/.test(name))
    && !name.startsWith(isolated+path.sep))throw Error('pmb1_cached_auth_read_disabled');};
for(const name of ['readFileSync','readFile','openSync','open']){const original=fs[name];fs[name]=function(p,...args){check(p);return original.call(this,p,...args);};}
for(const name of ['readFile','open']){const original=fs.promises[name];fs.promises[name]=function(p,...args){check(p);return original.call(this,p,...args);};}
require('node:module').syncBuiltinESMExports();
process.on('exit',()=>fs.writeFileSync(process.env.PMB1_ISOLATION_RECEIPT.replace('.json','-'+process.pid+'.json'),JSON.stringify({networkAttempts:blocked,credentialCache:'relocated-and-guarded',pid:process.pid})));
