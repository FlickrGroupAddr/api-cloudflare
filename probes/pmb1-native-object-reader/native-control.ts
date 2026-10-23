// MIT License; copyright 2026 Terry Ott.
// EXTERNAL operator state. Never deploy in any compared object's namespace.
import { DurableObject } from 'cloudflare:workers';
import { canonical, sha2_256 } from '../pmb1-no-real-object-reader/reader.ts';

export interface ControlReference { namespace: string; id: string; packetSha2_256: string }
export interface Reservation {
  controlSha2_256: string; namespace: string; id: string; packetSha2_256: string;
}
interface Plan extends ControlReference {
  schema: 'pmb1-external-native-capture-control-v1';
  startsAtMs: number; endsAtMs: number; maxCalls: number;
  objects: { namespace: string; id: string; packetSha2_256: string }[];
}
type Env = { PMB1_CAPTURE_CONTROL_PLAN: string };
const need = (ok: unknown): void => { if (!ok) throw new Error('native_capture_control_refused'); };

/** Only fixed reservation bookkeeping is writable. Source pins/configuration,
 * clock domain, binding ownership and durable commit semantics still require
 * actual qualification. No packet flag can establish them.
 */
export class NativeCaptureControl extends DurableObject<Env> {
  async #plan(expected?: string): Promise<{ plan: Plan; hash: string }> {
    const raw = this.env.PMB1_CAPTURE_CONTROL_PLAN;
    need(typeof raw === 'string' && raw.length <= 262144 && new TextEncoder().encode(raw).length <= 262144);
    let plan: Plan;
    try { plan = JSON.parse(raw); } catch { throw new Error('native_capture_control_refused'); }
    need(plan !== null && typeof plan === 'object'
      && canonical(Object.keys(plan).sort()) === canonical(['schema', 'namespace', 'id', 'packetSha2_256',
        'startsAtMs', 'endsAtMs', 'maxCalls', 'objects'].sort()));
    need(plan.schema === 'pmb1-external-native-capture-control-v1'
      && /^[a-f0-9]{32}$/.test(plan.namespace) && /^[a-f0-9]{64}$/.test(plan.id)
      && this.ctx.id.toString() === plan.id && Array.isArray(plan.objects)
      && plan.objects.length > 0 && plan.objects.length <= 128
      && Number.isSafeInteger(plan.maxCalls) && plan.maxCalls === plan.objects.length
      && Number.isSafeInteger(plan.startsAtMs) && Number.isSafeInteger(plan.endsAtMs)
      && plan.startsAtMs >= 0 && plan.endsAtMs > plan.startsAtMs
      && plan.endsAtMs - plan.startsAtMs <= 600000);
    const identities = new Set<string>();
    for (const object of plan.objects) {
      need(object !== null && typeof object === 'object'
        && canonical(Object.keys(object).sort()) === canonical(['namespace', 'id', 'packetSha2_256'].sort()));
      const identity = canonical([object.namespace, object.id]);
      need(/^[a-f0-9]{32}$/.test(object.namespace) && object.namespace !== plan.namespace
        && /^[a-f0-9]{64}$/.test(object.id) && /^[a-f0-9]{64}$/.test(object.packetSha2_256)
        && !identities.has(identity)); identities.add(identity);
    }
    const now = Date.now(); need(plan.startsAtMs <= now && now < plan.endsAtMs);
    // This config is source-pinned externally; its self-description is omitted
    // from the digest to avoid a self-referential hash.
    const { packetSha2_256: pin, ...body } = plan;
    const hash = await sha2_256(new TextEncoder().encode(canonical(body)));
    need(pin === hash && (expected === undefined || expected === hash));
    return { plan, hash };
  }
  #binding(hash: string) {
    const rows = this.ctx.storage.sql.exec('SELECT packet,calls FROM capture_control WHERE singleton=1').toArray();
    need(rows.length === 1 && rows[0].packet === hash); return rows[0];
  }
  async initialize(): Promise<void> {
    const { hash } = await this.#plan();
    this.ctx.storage.transactionSync(() => {
      need(this.ctx.storage.sql.exec("SELECT name FROM sqlite_schema WHERE type='table' AND name<>'__cf_kv'").toArray().length === 0);
      this.ctx.storage.sql.exec('CREATE TABLE capture_control(singleton INTEGER PRIMARY KEY CHECK(singleton=1),packet TEXT NOT NULL,calls INTEGER NOT NULL)');
      this.ctx.storage.sql.exec("CREATE TABLE captures(namespace TEXT NOT NULL,id TEXT NOT NULL,packet TEXT NOT NULL,phase TEXT NOT NULL CHECK(phase IN ('reserved','consumed','complete')),PRIMARY KEY(namespace,id)) WITHOUT ROWID");
      this.ctx.storage.sql.exec('INSERT INTO capture_control VALUES(1,?,0)', hash);
    });
  }
  async reserve(controlHash: string, namespace: string, id: string, packetHash: string): Promise<Reservation> {
    const { plan, hash } = await this.#plan(controlHash);
    need(plan.objects.some(o => o.namespace === namespace && o.id === id && o.packetSha2_256 === packetHash));
    this.ctx.storage.transactionSync(() => {
      const row = this.#binding(hash); need(typeof row.calls === 'number' && row.calls < plan.maxCalls);
      this.ctx.storage.sql.exec("INSERT INTO captures VALUES(?,?,?,'reserved')", namespace, id, packetHash);
      this.ctx.storage.sql.exec('UPDATE capture_control SET calls=calls+1 WHERE singleton=1');
    });
    return { controlSha2_256: hash, namespace, id, packetSha2_256: packetHash };
  }
  async #advance(receipt: Reservation, before: string, after: string): Promise<void> {
    need(receipt !== null && typeof receipt === 'object'
      && canonical(Object.keys(receipt).sort()) === canonical(['controlSha2_256', 'namespace', 'id', 'packetSha2_256'].sort()));
    const { hash } = await this.#plan(receipt.controlSha2_256);
    this.ctx.storage.transactionSync(() => {
      this.#binding(hash);
      const rows = this.ctx.storage.sql.exec('SELECT packet,phase FROM captures WHERE namespace=? AND id=?', receipt.namespace, receipt.id).toArray();
      need(rows.length === 1 && rows[0].packet === receipt.packetSha2_256 && rows[0].phase === before);
      this.ctx.storage.sql.exec('UPDATE captures SET phase=? WHERE namespace=? AND id=?', after, receipt.namespace, receipt.id);
    });
  }
  async consume(receipt: Reservation): Promise<void> { return this.#advance(receipt, 'reserved', 'consumed'); }
  async complete(receipt: Reservation): Promise<void> { return this.#advance(receipt, 'consumed', 'complete'); }
}
