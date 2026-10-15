import test from 'node:test';
import assert from 'node:assert/strict';
import {createWorker} from '../src/worker.ts';

test('photo read gate allows authentication independently of closed submission intake',async()=>{
  const worker=createWorker(()=>{throw Error('unexpected provider fetch');});
  const env={DB:{prepare(){throw Error('unexpected database access');}},FGA_READ_ENABLED:'1',
    FGA_EXISTING_PHOTOS_ENABLED:'0',FGA_INTAKE_ENABLED:'0',FGA_DISPATCH_ENABLED:'0'};
  for(const [path,method] of [
    ['/api/v001/existing-public-photos?page=1&page_size=100','GET'],
    ['/api/v001/photo-bindings/binding-1/group-memberships?page_size=100','GET'],
    ['/api/v001/existing-public-photo-bindings','POST'],
  ]){
    const make=()=>new Request('https://flickrgroupaddr.com'+path,{method});
    assert.equal((await worker.fetch(make(),env)).status,503);
    const enabled=await worker.fetch(make(),{...env,FGA_EXISTING_PHOTOS_ENABLED:'1'});
    assert.equal(enabled.status,401);assert.equal(enabled.headers.get('Cache-Control'),'no-store');
    assert.equal((await worker.fetch(make(),{...env,FGA_READ_ENABLED:'0',FGA_EXISTING_PHOTOS_ENABLED:'1'})).status,503);
  }
  const batch=await worker.fetch(new Request('https://flickrgroupaddr.com/api/v001/group-submission-batches',{method:'POST'}),
    {...env,FGA_EXISTING_PHOTOS_ENABLED:'1'});
  assert.equal(batch.status,503);
});
