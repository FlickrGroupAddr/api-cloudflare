import assert from "node:assert/strict";
import test from "node:test";
import { CELL_SQL, encodeBindingRow, Refused } from "./binding_profile.ts";

assert.equal(process.versions.node, "24.22.0", "node_pin");

function numberOf(hex) {
  const view = new DataView(new ArrayBuffer(8));
  view.setBigUint64(0, BigInt(`0x${hex}`), false);
  return view.getFloat64(0, false);
}
function encoded(value) {
  return JSON.parse(encodeBindingRow(["synthetic-cell", "real", value])).binary64;
}

test("exact postbinding transport covers both signs of every finite exponent class", () => {
  for (let exponent = 0; exponent < 2047; exponent++) {
    for (const fraction of [0n, 1n, (1n << 52n) - 1n]) {
      for (const sign of [0n, 1n << 63n]) {
        const hex = (sign | (BigInt(exponent) << 52n) | fraction).toString(16).padStart(16, "0");
        assert.equal(encoded(numberOf(hex)), hex);
      }
    }
  }
});

test("signed zero survives explicit encoding, while earlier ordinary JSON loses it", () => {
  assert.equal(encoded(-0), "8000000000000000");
  assert.equal(encoded(+0), "0000000000000000");
  assert(Object.is(JSON.parse("-0"), -0)); // JSON grammar itself permits preservation.
  const damaged = JSON.parse(JSON.stringify(["synthetic-cell", "real", -0]));
  assert.equal(JSON.parse(encodeBindingRow(damaged)).binary64, "0000000000000000");
  assert.notEqual(JSON.parse(encodeBindingRow(damaged)).binary64, encoded(-0));
});

test("a finite neighbor substituted before encoding is indistinguishable without source oracle", () => {
  const actual = "3ff0000000000001";
  const damaged = encoded(numberOf("3ff0000000000000"));
  assert.notEqual(damaged, actual);
  assert.equal(damaged, encoded(1));
});

test("actual source type and finite Number are mandatory; no SQL guard or coercion", () => {
  for (const tag of ["integer", "text", "blob", "null", undefined])
    assert.throws(() => encodeBindingRow(["synthetic-cell", tag, 1]), Refused);
  for (const value of [NaN, Infinity, -Infinity, "1", 1n, null, false, {}, []])
    assert.throws(() => encodeBindingRow(["synthetic-cell", "real", value]), Refused);
  for (const row of [null, {}, [], ["synthetic-cell", "real"], ["synthetic-cell", "real", 1, 2]])
    assert.throws(() => encodeBindingRow(row), Refused);
  for (const id of ["", "private", "synthetic-", `synthetic-${"a".repeat(65)}`, "synthetic-a\n"])
    assert.throws(() => encodeBindingRow([id, "real", 1]), Refused);
  assert.equal(CELL_SQL, "SELECT id, typeof(x), x FROM synthetic_values ORDER BY id");
});
