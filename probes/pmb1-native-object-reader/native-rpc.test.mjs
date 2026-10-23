// Local emulator API/type semantics only; never a managed qualification result.
import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { Miniflare } from 'miniflare';
import {createHash} from 'node:crypto';
import {canonical} from '../pmb1-no-real-object-reader/reader.ts';

test('real workerd typed RPC reaches the owning class; missing packet refuses once without initializing storage or outbound traffic', async () => {
  const bundled = await build({ stdin: { contents: `
    import {NativeCaptureOwner} from './probes/pmb1-native-object-reader/native-owner.ts';
    export class ExistingOwningClass extends NativeCaptureOwner {
      async inspect() { return this.ctx.storage.sql.exec("SELECT name FROM sqlite_schema ORDER BY name").toArray(); }
    }
    export default { async fetch(_request, env) {
      const stub = env.OWNING.getByName('synthetic-existing-owner');
      const before = await stub.inspect(), outcomes = [];
      for (let i = 0; i < 2; i++) {
        try { await stub.acquire('a'.repeat(64)); outcomes.push('unexpected'); }
        catch(error) { outcomes.push(error.message); }
      }
      const after = await stub.inspect();
      return Response.json({before, after, outcomes});
    }};`, resolveDir: process.cwd(), loader: 'ts' }, bundle: true, write: false,
    format: 'esm', platform: 'neutral', external: ['cloudflare:workers'] });
  let outbound = 0;
  const mf = new Miniflare({ modules: true, script: bundled.outputFiles[0].text,
    compatibilityDate: '2026-07-30', host: '127.0.0.1', port: 0, cf: false,
    logRequests: false, telemetry: { enabled: false },
    durableObjects: { OWNING: { className: 'ExistingOwningClass', useSQLite: true } },
    bindings: { PMB1_READ_NAMESPACE: 'b'.repeat(32), PMB1_READ_PACKETS: '[]' },
    outboundService() { outbound++; throw Error('External network disabled'); } });
  try {
    const result = await (await mf.dispatchFetch('http://synthetic.invalid/')).json();
    assert.deepEqual(result.before, result.after);
    assert.deepEqual(result.outcomes, ['native_owner_packet', 'native_owner_once_only']);
    assert.equal(outbound, 0);
  } finally { await mf.dispose(); }
});

test('real workerd external control persists finite reservations and consumed state across object abort/recreation', async () => {
  const bundled = await build({stdin:{contents:`
    import {NativeCaptureControl} from './probes/pmb1-native-object-reader/native-control.ts';
    export class Control extends NativeCaptureControl { async restart() { this.ctx.abort('synthetic restart'); } }
    export default {async fetch(request,env){
      const id=env.CONTROL.idFromName('external-control');
      if(new URL(request.url).pathname==='/identity')return Response.json({id:id.toString()});
      const stub=env.CONTROL.get(id), plan=JSON.parse(env.PMB1_CAPTURE_CONTROL_PLAN);
      const object=plan.objects[0], outcomes=[];
      await stub.initialize();
      const receipt=await stub.reserve(plan.packetSha2_256,object.namespace,object.id,object.packetSha2_256);
      await stub.consume(receipt);
      try{await stub.restart();}catch{}
      const fresh=env.CONTROL.get(id);
      try{await fresh.consume(receipt);outcomes.push('unexpected');}catch(error){outcomes.push(error.message);}
      try{await fresh.reserve(plan.packetSha2_256,object.namespace,object.id,object.packetSha2_256);outcomes.push('unexpected');}catch(error){outcomes.push(error.message);}
      await fresh.complete(receipt);
      try{await fresh.complete(receipt);outcomes.push('unexpected');}catch(error){outcomes.push(error.message);}
      return Response.json(outcomes);
    }};`,resolveDir:process.cwd(),loader:'ts'},bundle:true,write:false,format:'esm',platform:'neutral',external:['cloudflare:workers']});
  let outbound=0;
  const options={modules:true,script:bundled.outputFiles[0].text,compatibilityDate:'2026-07-30',
    host:'127.0.0.1',port:0,cf:false,logRequests:false,telemetry:{enabled:false},
    durableObjects:{CONTROL:{className:'Control',useSQLite:true}},bindings:{PMB1_CAPTURE_CONTROL_PLAN:''},
    outboundService(){outbound++;throw Error('External network disabled');}};
  const mf=new Miniflare(options);
  try{
    const {id}=await(await mf.dispatchFetch('http://synthetic.invalid/identity')).json();
    const now=Date.now(),body={schema:'pmb1-external-native-capture-control-v1',namespace:'e'.repeat(32),id,
      startsAtMs:now-1000,endsAtMs:now+30000,maxCalls:1,
      objects:[{namespace:'b'.repeat(32),id:'c'.repeat(64),packetSha2_256:'a'.repeat(64)}]};
    const packetSha2_256=createHash('sha256').update(canonical(body)).digest('hex');
    await mf.setOptions({...options,bindings:{PMB1_CAPTURE_CONTROL_PLAN:JSON.stringify({...body,packetSha2_256})}});
    const result=await(await mf.dispatchFetch('http://synthetic.invalid/run')).json();
    assert.deepEqual(result,['native_capture_control_refused','native_capture_control_refused','native_capture_control_refused']);
    assert.equal(outbound,0);
  }finally{await mf.dispose();}
});
