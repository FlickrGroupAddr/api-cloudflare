/** Bounded provider-only JSON grammar. Admission requests retain their own parser. */
export function strictFlickrJson(raw: string, maxBytes = 262144): unknown {
  const invalid = (): never => { throw new Error('invalid_flickr_json'); };
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 1 || maxBytes > 1048576 || typeof raw !== 'string' || raw.length > maxBytes || new TextEncoder().encode(raw).length > maxBytes) return invalid();
  let offset = 0, nodes = 0;
  const space = () => { while (offset < raw.length && /[\x20\t\r\n]/.test(raw[offset]!)) offset++; };
  function string(): string {
    const start = offset++;
    while (offset < raw.length) {
      const c = raw[offset++];
      if (c === '"') {
        // JSON.parse owns escape/control-character grammar; the scan only finds
        // the token boundary, as in the existing strict Album request parser.
        const decoded: unknown = JSON.parse(raw.slice(start, offset));
        if (typeof decoded !== 'string' || /\p{Cs}/u.test(decoded)) return invalid();
        return decoded;
      }
      if (c === '\\') offset++;
    }
    return invalid();
  }
  function number(): number {
    const match = /^(-?)(0|[1-9][0-9]*)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?/.exec(raw.slice(offset));
    if (!match || match[0].length > 128) return invalid();
    offset += match[0].length;
    const value = Number(match[0]);
    if (!Number.isFinite(value)) return invalid();
    // A rounded decimal must never become a recognized integer status/code.
    // Normalize decimal digits without computing an attacker-sized power.
    if (Number.isInteger(value)) {
      if (!Number.isSafeInteger(value)) return invalid();
      let digits = (match[2]! + (match[3] ?? '')).replace(/^0+/, '');
      if (!digits) return value;
      let scale = Number(match[4] ?? 0) - (match[3]?.length ?? 0);
      if (!Number.isSafeInteger(scale)) return invalid();
      while (scale < 0 && digits.endsWith('0')) { digits = digits.slice(0, -1); scale++; }
      if (scale < 0 || digits.length + scale > 16) return invalid();
      const exact = `${match[1]}${digits}${'0'.repeat(scale)}`;
      if (exact !== String(value)) return invalid();
    }
    return value;
  }
  function value(depth: number): unknown {
    space();
    if (depth > 64 || ++nodes > 65536) return invalid();
    if (raw[offset] === '"') return string();
    if (raw[offset] === '{') {
      offset++; space();
      const result: Record<string, unknown> = Object.create(null);
      if (raw[offset] === '}') { offset++; return result; }
      for (;;) {
        space(); if (raw[offset] !== '"') return invalid();
        const name = string();
        if (Object.hasOwn(result, name)) return invalid();
        space(); if (raw[offset++] !== ':') return invalid();
        result[name] = value(depth + 1); space();
        const end = raw[offset++];
        if (end === '}') return result;
        if (end !== ',') return invalid();
      }
    }
    if (raw[offset] === '[') {
      offset++; space(); const result: unknown[] = [];
      if (raw[offset] === ']') { offset++; return result; }
      for (;;) {
        result.push(value(depth + 1)); space(); const end = raw[offset++];
        if (end === ']') return result;
        if (end !== ',') return invalid();
      }
    }
    for (const [token, literal] of [['true', true], ['false', false], ['null', null]] as const) {
      if (raw.startsWith(token, offset)) { offset += token.length; return literal; }
    }
    return number();
  }
  const parsed = value(0); space();
  if (offset !== raw.length) return invalid();
  return parsed;
}
