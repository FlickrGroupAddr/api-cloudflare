// Node's actual SQLite engine implements the D1 adapter for offline proof.
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';

export function createSyntheticStore(migrations, counters) {
  const raw = new DatabaseSync(':memory:');
  raw.exec('PRAGMA foreign_keys=ON');
  for (const file of readdirSync(migrations).filter(name => name.endsWith('.sql')).sort()) {
    raw.exec(readFileSync(join(migrations, file), 'utf8'));
  }
  const store = { raw, prepare(sql) {
    counters.syntheticSql++;
    return { sql, args: [], bind(...args) { this.args = args; return this; },
      async first() { return raw.prepare(sql).get(...this.args) ?? null; },
      async all() { return { results: raw.prepare(sql).all(...this.args) }; },
      async run() { const results = raw.prepare(sql).all(...this.args);
        return { results, meta: { changes: raw.prepare('SELECT changes() n').get().n } }; },
    };
  }, async batch(statements) {
    raw.exec('BEGIN');
    try { const results = []; for (const statement of statements) results.push(await statement.run());
      raw.exec('COMMIT'); return results;
    } catch (error) { raw.exec('ROLLBACK'); throw error; }
  } };
  const digest = createHash('sha256').update(Array(13).fill('0000').join('-')).digest('hex');
  raw.exec(`BEGIN; INSERT INTO fga_users VALUES('probe-user');
    INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id)
      VALUES('probe-install','probe-user','lrc_plugin','active',1,'probe-version');
    INSERT INTO flickr_links VALUES('probe-user','synthetic-owner',1,'linked');
    INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission)
      VALUES('probe-user','gen',1,'synthetic-owner','write');
    INSERT INTO flickr_connection_state(user_id,state,local_state) VALUES('probe-user','linked','available');`);
  raw.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal)
    VALUES('probe-version','probe-install',?,'current',1)`).run(digest);
  raw.exec('COMMIT');
  return store;
}
