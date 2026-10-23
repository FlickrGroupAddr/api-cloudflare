// MIT License; copyright 2026 Terry Ott.
// Synthetic SQLite race only. Native threading is necessary to overlap two SQL
// connections; this test helper has no provider or application execution path.
import { parentPort, workerData } from 'node:worker_threads';
import { DatabaseSync } from 'node:sqlite';
const signal = new Int32Array(workerData.signal);
const db = new DatabaseSync(workerData.path);
db.exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000');
Atomics.add(signal,0,1);
Atomics.notify(signal,0);
Atomics.wait(signal,1,0,5000);
try { parentPort.postMessage({rows:db.prepare(workerData.sql).all(...workerData.args)}); }
catch(error) { parentPort.postMessage({error:error.message}); }
finally { db.close(); }
