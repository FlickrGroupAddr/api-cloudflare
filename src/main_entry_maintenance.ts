// MIT License; copyright 2026 Terry Ott.
// PMB-1 main-entry seam. No provider, control mutation, bootstrap or reopen API.
import type { AlbumCreateRepairDependencies } from './album_create_repair.ts';
import type { FlickrFetch } from './flickr_reads.ts';

export const MAIN_ENTRY_FAMILIES = Object.freeze([
  'installation-intake-publication-upload', 'album-routes-and-injected-repair-reader',
  'group-photo-thumbnail-and-rate', 'browser-google-oauth-session-plugin-code',
  'status-audit-error-recovery', 'native-credential-lifecycle-and-results',
  'scheduled-maintenance-refresh-and-wake',
] as const);
export interface MainEntryBinding { candidate: string; lifecycle: string; generation: string }
export interface MainEntryLease extends MainEntryBinding { invocation: string; entry: 'fetch' | 'scheduled' }
export type MainEffect = 'd1' | 'provider' | 'provider-body' | 'provider-cancel' | 'secret-read' | 'wake' | 'asset' | 'repair-reader';
export interface MainEntryStop extends MainEntryBinding { admission: 'stopped'; evidence: string }
export interface MainEntryDrainWindow { deadlineMs: number }
export interface MainEntryDisposition extends MainEntryBinding {
  status: 'complete-supported'; evidence: string;
  families: readonly string[];
  admittedHandlers: 'settled'; externalResults: 'settled'; requiredDomainResults: 'settled';
  oldCallbacks: 'fenced'; restartedInvocations: 'accounted';
}
/** Trusted ports, never request input. No default implementation or global provider-drain claim.
 * All journal operations are durable/atomic, bound to the exact candidate/lifecycle.
 * admit latches an invocation iff admission is open. effect latches one effect iff
 * that invocation still owns its original generation, even while admission drains.
 * stop irreversibly stops new handlers across ALL instances/versions/callers.
 * stopped admission never cancels a fixed domain result transaction. Restart,
 * timeout, response loss and a new bridge must not erase any retained obligation.
 * Cancellation disposes an ALREADY admitted transport. Its underlying synchronous
 * cancel is preserved before the secondary observation latch; an unreturned
 * invocation/body remains owned across any lost latch or restart. It never admits
 * another provider request. Methods have no internal replay and honor fixed bounds.
 */
export interface MainEntryJournal {
  admit(binding: MainEntryBinding, invocation: string, entry: MainEntryLease['entry']): Promise<MainEntryLease | null>;
  effect(lease: MainEntryLease, effect: string, kind: MainEffect): Promise<boolean>;
  settled(lease: MainEntryLease, effect: string, outcome: 'fulfilled' | 'rejected'): Promise<void>;
  returned(lease: MainEntryLease, outcome: 'fulfilled' | 'rejected'): Promise<void>;
  stop(binding: MainEntryBinding, window: MainEntryDrainWindow): Promise<MainEntryStop>;
}
/** Must independently establish complete actual invocation and pending-state coverage,
 * including native lifecycle/OAuth phases, failed/caught writes and old executions.
 * A journal acknowledgement, empty local Set, flags, counts or caller booleans do
 * not satisfy this interface. Actual supported adapter qualification is separate.
 */
export interface MainEntryObserver {
  assess(binding: MainEntryBinding, stop: MainEntryStop, families: readonly string[], window: MainEntryDrainWindow): Promise<MainEntryDisposition>;
}
export class MainEntryUnavailable extends Error { constructor() { super('main_entry_unavailable'); } }
const fail = (): never => { throw new MainEntryUnavailable(); };
const digest = (value: unknown) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
function validBinding(value: MainEntryBinding): boolean {
  return !!value && digest(value.candidate) && typeof value.lifecycle === 'string'
    && /^[A-Za-z0-9_-]{1,80}$/.test(value.lifecycle) && typeof value.generation === 'string'
    && /^[1-9][0-9]{0,18}$/.test(value.generation) && BigInt(value.generation) <= 9223372036854775807n;
}
function same(a: MainEntryBinding, b: MainEntryBinding): boolean {
  return validBinding(a) && a.candidate === b.candidate && a.lifecycle === b.lifecycle && a.generation === b.generation;
}
// Preserve native receiver branding; only callers below select fixed methods.
function call(target: object, key: PropertyKey, args: unknown[]): any {
  const method = Reflect.get(target, key, target);
  if (typeof method !== 'function') return fail();
  return Reflect.apply(method, target, args);
}

class InvocationScope {
  private accepting = true;
  private effects = new Set<Promise<unknown>>();
  private rawStatements = new WeakMap<object, object>();
  private lease: MainEntryLease;
  private journal: MainEntryJournal;
  private uncertain: () => void;
  constructor(lease: MainEntryLease, journal: MainEntryJournal, uncertain: () => void) {
    this.lease = lease; this.journal = journal; this.uncertain = uncertain;
  }

  private live() { if (!this.accepting) fail(); }
  private track<T>(run: () => Promise<T>): Promise<T> {
    this.live();
    // Register before the first await, including a pending permit or receipt.
    const promise = Promise.resolve().then(run);
    this.effects.add(promise);
    void promise.then(() => this.effects.delete(promise), () => this.effects.delete(promise));
    return promise;
  }
  effect<T>(kind: MainEffect, operation: () => Promise<T>): Promise<T> {
    return this.track(async () => {
      const id = crypto.randomUUID();
      let allowed: boolean;
      try { allowed = await this.journal.effect(this.lease, id, kind); }
      catch { this.uncertain(); return fail(); }
      this.live(); // A delayed permit cannot revive a returned/disposed invocation.
      if (allowed !== true) { this.uncertain(); return fail(); }
      let value: T;
      try { value = await operation(); }
      catch (error) {
        // Rejection can mean an unknown remote result. Preserve domain handling;
        // independent pending-state assessment must establish its disposition.
        try { await this.journal.settled(this.lease, id, 'rejected'); } catch { this.uncertain(); }
        throw error;
      }
      try { await this.journal.settled(this.lease, id, 'fulfilled'); } catch { this.uncertain(); }
      return value;
    });
  }
  /** Track consumption too: response headers are not a settled external result. */
  private response(response: Response): Response {
    if (!response.body) return response;
    let finished = false;
    let finish!: () => void;
    const bodyDone = new Promise<void>(resolve => { finish = resolve; });
    const held = this.effect('provider-body', () => bodyDone);
    // The body hold has no independent rejection consumer in an existing handler.
    void held.catch(() => this.uncertain());
    const done = () => { if (!finished) { finished = true; finish(); } };
    const scope = this;
    const cancellation = (target: object, args: unknown[]) => {
      scope.live();
      // Preserve immediate native cancellation (and its read-EOF ordering).
      // Deferring this call until a journal await would race releaseLock() in
      // the existing fire-and-forget cancellation helpers. This disposes the
      // existing admitted body; it dispatches no new provider operation.
      let pending: Promise<unknown>;
      try { pending = Promise.resolve(call(target, 'cancel', args)); }
      catch (error) { scope.uncertain(); done(); return Promise.reject(error); }
      // Observe rejection immediately even if the secondary journal latch hangs.
      void pending.catch(() => scope.uncertain());
      return scope.effect('provider-cancel', async () => {
        try { return await pending; } finally { done(); }
      });
    };
    const body = new Proxy(response.body, { get(target, key) {
      if (key === 'getReader') return (...args: unknown[]) => {
        const reader: ReadableStreamDefaultReader<Uint8Array> = call(target, 'getReader', args);
        return new Proxy(reader, { get(r, method) {
          if (method === 'read') return async (...values: unknown[]) => {
            try { const result = await call(r, 'read', values); if (result.done) done(); return result; }
            catch (error) { scope.uncertain(); done(); throw error; }
          };
          if (method === 'cancel') return async (...values: unknown[]) => {
            // cancel closes pending reads BEFORE its underlying cancellation
            // settles. EOF can release the body hold, never this distinct effect.
            return cancellation(r, values);
          };
          const value = Reflect.get(r, method, r); return typeof value === 'function' ? value.bind(r) : value;
        } });
      };
      if (key === 'cancel') return async (...args: unknown[]) => {
        return cancellation(target, args);
      };
      // None of the frozen main graph uses tee/pipeTo/async iteration. Refuse a
      // future unreviewed consumption surface rather than losing its body hold.
      const value = Reflect.get(target, key, target);
      if (typeof value === 'function') return () => { scope.uncertain(); return fail(); };
      return value;
    } });
    return new Proxy(response, { get(target, key) {
      if (key === 'body') return body;
      if (['text', 'json', 'arrayBuffer', 'blob', 'formData', 'bytes'].includes(String(key))) return async () => {
        try { return await call(target, key, []); }
        catch (error) { scope.uncertain(); throw error; } finally { done(); }
      };
      if (key === 'clone') return () => { scope.uncertain(); return fail(); };
      const value = Reflect.get(target, key, target); return typeof value === 'function' ? value.bind(target) : value;
    } });
  }
  fetcher(fetcher: FlickrFetch): FlickrFetch {
    return request => this.effect('provider', async () => this.response(await fetcher(request)));
  }
  database<T extends object>(db: T): T {
    const scope = this;
    const statement = (raw: object): object => {
      const wrapped = new Proxy(raw, { get(target, key) {
        if (key === 'bind') return (...args: unknown[]) => { scope.live(); return statement(call(target, key, args)); };
        if (['first', 'all', 'run', 'raw'].includes(String(key))) return (...args: unknown[]) =>
          scope.effect('d1', () => call(target, key, args));
        // Do not expose synthetic raw handles or new execution APIs.
        const value = Reflect.get(target, key, target);
        if (typeof value === 'function') return () => fail();
        return undefined;
      } });
      scope.rawStatements.set(wrapped, raw); return wrapped;
    };
    return new Proxy(db, { get(target, key) {
      if (key === 'prepare') return (sql: string) => { scope.live(); return statement(call(target, key, [sql])); };
      if (key === 'batch') return (statements: object[]) => {
        const raw = statements.map(s => scope.rawStatements.get(s) ?? fail());
        return scope.effect('d1', () => call(target, key, [raw]));
      };
      if (key === 'withSession') return (...args: unknown[]) => { scope.live(); return scope.database(call(target, key, args)); };
      // exec/dump and raw/session internals are absent from the frozen graph.
      return () => fail();
    } });
  }
  environment<T extends { DB: object }>(env: T): T {
    const scope = this, database = this.database(env.DB);
    const secrets = new Set(['FLICKR_GRANT', 'FLICKR_APPLICATION', 'AUTH_LIMITER_KEY', 'NATIVE_WRITER_TOKEN',
      'FLICKR_TEMP_0', 'FLICKR_TEMP_1', 'FLICKR_TEMP_2', 'FLICKR_TEMP_3', 'FLICKR_TEMP_4']);
    return new Proxy(env, { get(target, key) {
      if (key === 'DB') return database;
      const value = Reflect.get(target, key, target);
      if (!value) return value;
      if (secrets.has(String(key))) return { get: () => scope.effect('secret-read', () => call(value, 'get', [])) };
      if (key === 'ASSETS') return { fetch: (...args: unknown[]) => scope.effect('asset', () => call(value, 'fetch', args)) };
      if (key === 'COORD') return {
        idFromName: (name: string) => { scope.live(); return call(value, 'idFromName', [name]); },
        get: (id: unknown) => { scope.live(); const stub = call(value, 'get', [id]);
          return { fetch: (...args: unknown[]) => scope.effect('wake', () => call(stub, 'fetch', args)) }; },
      };
      return value;
    } });
  }
  repair(deps?: AlbumCreateRepairDependencies): AlbumCreateRepairDependencies | undefined {
    if (!deps) return undefined;
    return { reader: context => ({
      // Include the injected factory inside the admitted operation too.
      discover: (page, size) => this.effect('repair-reader', () => deps.reader(context).discover(page, size)),
      prove: id => this.effect('repair-reader', () => deps.reader(context).prove(id)),
    }) };
  }
  async returned(outcome: 'fulfilled' | 'rejected'): Promise<void> {
    // A handler that raced an effect has not disposed that effect. Keep its
    // original authority for mandatory safety callbacks; NEVER report drained.
    // No new handler is admitted and no storage close is authorized in this case.
    if (this.effects.size) { this.uncertain(); return; }
    this.accepting = false;
    try { await this.journal.returned(this.lease, outcome); } catch { this.uncertain(); }
  }
}

export class MainEntryMaintenance {
  private state: 'open' | 'draining' | 'stopped' | 'refused' = 'open';
  private uncertain = false;
  private active = new Set<Promise<unknown>>();
  readonly binding: Readonly<MainEntryBinding>;
  private journal: MainEntryJournal;
  private observer: MainEntryObserver;
  private now: () => number;
  constructor(binding: MainEntryBinding, journal: MainEntryJournal, observer: MainEntryObserver, now: () => number = () => performance.now()) {
    if (!validBinding(binding) || !journal || !observer ||
      !['admit', 'effect', 'settled', 'returned', 'stop'].every(k => typeof Reflect.get(journal, k) === 'function') ||
      typeof observer.assess !== 'function') fail();
    this.binding = Object.freeze({ ...binding }); this.journal = journal; this.observer = observer; this.now = now;
  }
  run<T>(entry: MainEntryLease['entry'], operation: (scope: InvocationScope) => Promise<T>): Promise<T> {
    if (this.state !== 'open' || this.active.size >= 256) return Promise.reject(new MainEntryUnavailable());
    const pending = this.invoke(entry, operation);
    this.active.add(pending);
    void pending.then(() => this.active.delete(pending), () => this.active.delete(pending));
    return pending;
  }
  private async invoke<T>(entry: MainEntryLease['entry'], operation: (scope: InvocationScope) => Promise<T>): Promise<T> {
    const invocation = crypto.randomUUID();
    let lease: MainEntryLease | null;
    try { lease = await this.journal.admit(this.binding, invocation, entry); }
    catch { this.uncertain = true; return fail(); }
    if (lease === null) return fail();
    if (!same(lease, this.binding) || lease.invocation !== invocation || lease.entry !== entry) { this.uncertain = true; return fail(); }
    // The atomic durable admission may have won the stop race. It remains part
    // of the drain, and fixed handlers/results must run before storage closes.
    const scope = new InvocationScope(Object.freeze({ ...lease }), this.journal, () => { this.uncertain = true; });
    let outcome: 'fulfilled' | 'rejected' = 'rejected';
    try { const result = await operation(scope); outcome = 'fulfilled'; return result; }
    finally { if (outcome === 'rejected') this.uncertain = true; await scope.returned(outcome); }
  }
  /** One irreversible bounded drain attempt; returns admission disposition only,
   * NEVER a D1/DO closure or reopen permission. Deadline does not abort handlers.
   */
  async stop(timeoutMs: number): Promise<MainEntryDisposition> {
    if (this.state !== 'open' || !Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 300_000) return fail();
    this.state = 'draining';
    let timer: ReturnType<typeof setTimeout> | undefined;
    let last = this.now();
    const window = Object.freeze({ deadlineMs: last + timeoutMs });
    const current = () => {
      const time = this.now();
      if (!Number.isFinite(time) || !Number.isFinite(last) || time < last || time >= window.deadlineMs || this.state !== 'draining') fail();
      last = time;
    };
    const operation = async () => {
      current();
      const stop = await this.journal.stop(this.binding, window);
      current();
      if (!same(stop, this.binding) || stop.admission !== 'stopped' || !digest(stop.evidence)) fail();
      await Promise.allSettled([...this.active]);
      current();
      if (this.uncertain) fail();
      const result = await this.observer.assess(this.binding, stop, MAIN_ENTRY_FAMILIES, window);
      current();
      if (!same(result, this.binding) || result.status !== 'complete-supported' || !digest(result.evidence)
        || result.admittedHandlers !== 'settled' || result.externalResults !== 'settled' || result.requiredDomainResults !== 'settled'
        || result.oldCallbacks !== 'fenced' || result.restartedInvocations !== 'accounted'
        || !Array.isArray(result.families) || result.families.length !== MAIN_ENTRY_FAMILIES.length
        || MAIN_ENTRY_FAMILIES.some(family => !result.families.includes(family))) fail();
      return result;
    };
    try {
      const result = await Promise.race([operation(), new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new MainEntryUnavailable()), timeoutMs);
      })]);
      current();
      if (this.state !== 'draining' || this.uncertain || this.active.size) return fail();
      this.state = 'stopped'; return Object.freeze({ ...result, families: Object.freeze([...result.families]) });
    } catch { this.state = 'refused'; return fail(); }
    finally { if (timer !== undefined) clearTimeout(timer); }
  }
}
