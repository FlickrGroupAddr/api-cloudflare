/** Unregistered synthetic cell prototype. No route, binding discovery or provider dispatch. */
export const CELL_SQL =
  "SELECT id, typeof(x), x FROM synthetic_values ORDER BY id";
export const PROFILE = "pmb1-real-binding-binary64-v1";
export const MAX_WIRE_BYTES = 256;

export class Refused extends Error {
  constructor(category: string) {
    super(category);
    this.name = "Refused";
  }
}

/** Encode the Number already delivered by a binding, before application JSON.
 * This proves nothing about earlier engine/adapter/provider conversion.
 * A caller must retain the source row's identity, actual typeof tag and value
 * from one evaluation of CELL_SQL. There is deliberately no D1 execution seam.
 */
export function encodeBindingRow(row: unknown): string {
  if (!Array.isArray(row) || row.length !== 3) throw new Refused("row_shape");
  const [id, tag, value] = row as unknown[];
  if (typeof id !== "string" || !/^synthetic-[a-z0-9-]{1,64}(?![\s\S])/.test(id))
    throw new Refused("row_identity");
  if (tag !== "real") throw new Refused("not_real");
  if (typeof value !== "number" || !Number.isFinite(value))
    throw new Refused("not_finite_number");
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, value, false);
  const binary64 = view.getBigUint64(0, false).toString(16).padStart(16, "0");
  const wire = JSON.stringify({ profile: PROFILE, row_id: id, type: tag, binary64 });
  if (new TextEncoder().encode(wire).byteLength > MAX_WIRE_BYTES)
    throw new Refused("wire_bound");
  return wire;
}
