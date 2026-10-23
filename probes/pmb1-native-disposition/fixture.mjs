// MIT License; copyright 2026 Terry Ott. Synthetic in-memory SQLite only.
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { ReviewedCoverage } from './coverage.ts';
import net from 'node:net';
import dns from 'node:dns';
let outbound=0;
const blocked=()=>{outbound++;throw Error('outbound_forbidden');};
globalThis.fetch=blocked;net.Socket.prototype.connect=blocked;dns.lookup=blocked;
export const assertNoOutbound=()=>{if(outbound!==0)throw Error('outbound_attempted');};
export const BINDING=Object.freeze({candidate:'a'.repeat(64),lifecycle:'synthetic',generation:'9007199254740993'});
export const JOURNAL='aaaaaaaa-0000-4000-8000-000000000000',DOMAIN='bbbbbbbb-0000-4000-8000-000000000000';
export const BOUNDS=Object.freeze({pages:256,rows:10000,bytes:4*1024*1024,milliseconds:10000});
export class LocalD1 {
  constructor(kind='domain') {
    this.db=new DatabaseSync(':memory:');this.calls=[];
    if(kind==='domain') {
      for(const path of ['d1-schema.sql','d1-guards.sql'])this.db.exec(readFileSync(new URL('../pmb1-integer-candidate/'+path,import.meta.url),'utf8'));
      this.db.exec('CREATE TABLE _cf_KV(key PRIMARY KEY,value) WITHOUT ROWID;');
    } else {
      this.db.exec(readFileSync(new URL('../pmb1-native-journal/schema.sql',import.meta.url),'utf8'));
      this.db.prepare(readFileSync(new URL('../pmb1-native-journal/provision.sql',import.meta.url),'utf8')).run(JOURNAL,BINDING.candidate,BINDING.lifecycle,BINDING.generation);
    }
  }
  prepare(sql){const self=this;return {sql,args:[],bind(...args){this.args=args;return this;},async all(){
    self.calls.push(sql);if(self.before)await self.before(sql);
    const rows=self.db.prepare(sql).all(...this.args);if(self.transform)return self.transform(sql,rows);
    return {success:true,results:rows};
  },async first(column){const r=(await this.all()).results[0];return r===undefined?null:column===undefined?r:r[column];},
  async run(){return this.all();}};}
  withSession(mode){if(mode!=='first-primary')throw Error('not_primary');return this;}
  async batch(statements){this.db.exec('BEGIN');try{const rows=[];for(const s of statements)rows.push(await s.all());this.db.exec('COMMIT');return rows;}catch(e){this.db.exec('ROLLBACK');throw e;}}
  close(){this.db.close();}
}
export function coverage(retiredExecutions=[],change=x=>x) {
  const writers=[{id:'main',version:'current-main',sourceSha2_256:'b'.repeat(64),authority:'main-journal-fenced'},
    {id:'partition',version:'current-partition',sourceSha2_256:'c'.repeat(64),authority:'partition-generation-fenced'},
    {id:'operator',version:'operator-source',sourceSha2_256:'d'.repeat(64),authority:'external-embargo'}];
  const resources=[{id:JOURNAL,kind:'external-journal'},{id:DOMAIN,kind:'d1'},{id:'b'.repeat(32)+'/'+'c'.repeat(64),kind:'object'},{id:'native-secret',kind:'native-secret'}];
  const expected={binding:BINDING,profile:'pmb1-private-application-no-real-v1',objectBoundary:'pmb1-private-object-kv-interface-v1',
    d1Operation:'fixed_update_with_exact_count_positional_v1',journalDatabaseId:JOURNAL,domainDatabaseId:DOMAIN,writers,resources};
  const now=Date.now();
  const actual={binding:BINDING,reviewer:'independent-reviewer',authenticationRecord:'synthetic/authenticated',censusRecord:'synthetic/census',
    writers:writers.map(w=>({...w,admissionRecord:'synthetic/admission/'+w.id,mutationFenceRecord:'synthetic/fence/'+w.id})),
    custody:resources.map(r=>({resource:r.id,holder:'independent-custodian',fromMs:now-1000,throughMs:now+300000,record:'synthetic/custody/'+r.id})),retiredExecutions};
  change({expected,actual});return new ReviewedCoverage(expected,actual);
}
