// Fixed synthetic #0039 PNG bytes; Web APIs only, usable in a Worker.
export function png(size) {
  const base = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNoAAAAggCBd81ytgAAAABJRU5ErkJggg=='), c => c.charCodeAt(0));
  if (size === undefined) return base;
  if (!Number.isSafeInteger(size) || size < base.length + 12 || size > 262145) throw Error('invalid_png_size');
  const bytes = new Uint8Array(size), offset = base.length - 12;
  bytes.set(base.subarray(0, offset));
  const length = size - base.length - 12;
  new DataView(bytes.buffer).setUint32(offset, length);
  bytes.set([112, 97, 68, 100], offset + 4);
  let crc = 0xffffffff;
  for (const byte of bytes.subarray(offset + 4, offset + 8 + length)) {
    crc ^= byte;
    for (let n = 0; n < 8; n++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  new DataView(bytes.buffer).setUint32(offset + 8 + length, (crc ^ 0xffffffff) >>> 0);
  bytes.set(base.subarray(offset), size - 12);
  return bytes;
}
