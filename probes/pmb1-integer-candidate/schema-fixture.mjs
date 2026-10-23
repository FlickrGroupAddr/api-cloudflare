// Synthetic local schema extraction; invokes the existing real source bootstrap.
// JavaScript is needed to import the TypeScript runtime under pinned Node.
import { bootstrapPartitionMaintenance } from '../../src/partition_maintenance.ts';
import { LocalStorage } from '../pmb1-native-alarm/local-storage.mjs';
const storage = new LocalStorage();
try {
  await bootstrapPartitionMaintenance(storage);
  const schema = storage.db.prepare('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name').all();
  process.stdout.write(JSON.stringify({ schema, kv: [...storage.kv].sort(), alarm: storage.alarm }));
} finally { storage.db.close(); }
