// Dedicated migration fixture: executes the production SQL through a small D1-shaped
// adapter, so #0020 rows can be admitted by the actual store before applying #0021.
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, readdirSync } from 'node:fs';
export function legacyAlbumStore() {
  const raw = new DatabaseSync(':memory:'); raw.exec('PRAGMA foreign_keys=ON');
  for (const name of readdirSync('migrations').filter(name => /^00(?:0[1-9]|1[0-9]|20)_.*\.sql$/.test(name)).sort()) raw.exec(readFileSync('migrations/' + name, 'utf8'));
  const db = { raw,
    prepare(sql) { return { args: [], bind(...args) { this.args = args; return this; },
      async first() { return raw.prepare(sql).get(...this.args) ?? null; },
      async run() { const results = raw.prepare(sql).all(...this.args); return { results, meta: { changes: raw.prepare('SELECT changes() n').get().n } }; },
    }; },
    async batch(statements) { raw.exec('BEGIN'); try { const results = []; for (const statement of statements) results.push(await statement.run()); raw.exec('COMMIT'); return results; } catch (error) { raw.exec('ROLLBACK'); throw error; } },
  };
  return db;
}
export function migrateAlbumObligations(db) {
  db.raw.exec('BEGIN');
  try { db.raw.exec(readFileSync('migrations/0021_album_obligations.sql', 'utf8')); db.raw.exec('COMMIT'); }
  catch (error) { db.raw.exec('ROLLBACK'); throw error; }
}
