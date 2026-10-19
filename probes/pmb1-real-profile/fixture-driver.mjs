// Synthetic test driver: receives only bounded hex fixtures, never provider data.
import { readFileSync } from "node:fs";
import { encodeBindingRow } from "./binding_profile.ts";
if (process.versions.node !== "24.22.0") throw new Error("node_pin");
const input = readFileSync(0, { encoding: "utf8" });
if (input.length > 500_000) throw new Error("fixture_bound");
const fixtures = JSON.parse(input);
if (!Array.isArray(fixtures) || fixtures.length > 5000) throw new Error("fixture_shape");
const output = fixtures.map((fixture) => {
  if (fixture === null || typeof fixture !== "object" ||
      Object.keys(fixture).sort().join(",") !== "binary64,row_id") throw new Error("fixture_fields");
  const { binary64, row_id } = fixture;
  if (typeof binary64 !== "string" || !/^[0-9a-f]{16}(?![\s\S])/.test(binary64))
    throw new Error("fixture_bits");
  const view = new DataView(new ArrayBuffer(8));
  view.setBigUint64(0, BigInt(`0x${binary64}`), false);
  return encodeBindingRow([row_id, "real", view.getFloat64(0, false)]);
});
process.stdout.write(JSON.stringify(output));
